import os
import sys
import logging
import re
from datetime import datetime, timedelta
import openpyxl
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials as UserCredentials

# Manually load environment before any local imports
ENV_PATH = r"c:\git\emailcampaigntracker\.env"
def load_env_at_startup(path):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                v = v.strip()
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                os.environ[k.strip()] = v

load_env_at_startup(ENV_PATH)

from app.services.sheet_sync_service import run_bidirectional_sync, EXCEL_PATH, load_env
from database.db import SessionLocal
from database.models import Lead, EmailSequence
from app.core.utils import normalize_linkedin_url
from app.workflows.workflow2_new_lead_email import _build_email_html, node_send_email_via_gmail

logger = logging.getLogger("email_send_service")

# Default follow-up delays in days
SEQUENCE_DELAYS = {
    2: 3, # Send Email 2 after 3 days
    3: 7, # Send Email 3 after 7 days (4 days after Email 2)
    4: 11, # Send Email 4 after 11 days (4 days after Email 3)
    5: 15, # Send Email 5 after 15 days (4 days after Email 4)
}

def _build_gmail_service():
    env = load_env(ENV_PATH)
    creds_path = env.get("GMAIL_OAUTH_CREDENTIALS_PATH", r"C:\git\emailcampaigntracker\gmail_token.json")
    if not os.path.exists(creds_path):
        raise FileNotFoundError(f"Gmail OAuth token not found at {creds_path}")
    creds = UserCredentials.from_authorized_user_file(creds_path)
    return build("gmail", "v1", credentials=creds)

def process_email_approvals_and_sends():
    """Checks Pipeline approvals, sends Email 1, and processes pending scheduled follow-ups (Email 2-5)."""
    from app.services.sheet_sync_service import get_google_client, load_env
    import gspread
    
    print("--------------------------------------------------")
    print("[Email Send Service] Running Approval & Send Scheduler...")
    print("--------------------------------------------------")

    # Build Gmail service client
    try:
        gmail_service = _build_gmail_service()
    except Exception as ge:
        print(f"Error: Failed to initialize Gmail API service ({ge}). Send aborted.")
        return

    env = load_env(ENV_PATH)
    print("Connecting to Google Sheets...")
    gc = get_google_client(env)
    sheet_id = env.get("GOOGLE_SHEET_ID")
    gsheet = gc.open_by_key(sheet_id)
    g_ws = gsheet.worksheet("Pipeline")
    
    g_rows = g_ws.get_all_values()
    if not g_rows:
        return
    headers = [str(h).strip() for h in g_rows[0]]
    header_map = {h: idx for idx, h in enumerate(headers)}

    modified = False
    db = SessionLocal()

    # Get settings or default tracking backend URL
    backend_url = env.get("LOCAL_BACKEND_URL", "http://localhost:8000")

    # --- Part A: Handle Human Approvals (Send Email 1) ---
    test_mode = os.environ.get("TEST_MODE", "false").strip().lower() == "true"
    test_company = os.environ.get("TEST_COMPANY", "Test Corp").strip()
    if test_mode:
        print(f"  [TEST MODE] Only processing rows for company: '{test_company}'")

    for r_idx, r in enumerate(g_rows[1:]):
        email_approval = str(r[header_map["Email Approval"]]).strip().lower()
        status = str(r[header_map["Automation Status"]]).strip()
        row_num = r_idx + 2
        company = str(r[header_map["Company"]]).strip()

        # TEST MODE: only process the dummy Test Corp row
        if test_mode and company.lower() != test_company.lower():
            continue

        if email_approval == "approve" and status == "Pending Email Review":
            contact_name = f"{r[header_map['First Name']]} {r[header_map['Last Name']]}".strip()
            email_val = r[header_map["Email"]]
            linkedin_url = r[header_map["(I) LinkedIn URL"]]

            print(f"\n[Send] Processing approved Row {row_num}: {contact_name} ({company})")

            
            # Find lead in DB
            lead_db = None
            if linkedin_url:
                norm_li = normalize_linkedin_url(linkedin_url)
                lead_db = db.query(Lead).filter(Lead.linkedin_url == norm_li).first()
            if not lead_db and email_val:
                lead_db = db.query(Lead).filter(Lead.email == email_val).first()

            if not lead_db:
                print(f"  Warning: Lead record not found in database. Skipping send for {contact_name}.")
                continue

            # Fetch Email 1 (Initial Hook)
            email_seq = db.query(EmailSequence).filter(
                EmailSequence.lead_id == lead_db.id,
                EmailSequence.step_number == 1,
                EmailSequence.status == "draft"
            ).first()

            if not email_seq:
                print(f"  Warning: Email 1 draft not found in database for {contact_name}. Skipping send.")
                continue

            # Prepare tracked HTML body
            html_body = _build_email_html(
                body=email_seq.body,
                tracking_id=email_seq.tracking_id,
                backend_url=backend_url
            )

            # Send Email 1 via Gmail
            send_data = {
                "email": email_val,
                "email_subject": email_seq.subject,
                "email_body_html": html_body,
                "tracking_id": email_seq.tracking_id
            }

            try:
                print(f"  Sending Email 1 to {email_val}...")
                node_send_email_via_gmail(send_data, gmail_service)
                
                # Update Email 1 step status in DB
                email_seq.status = "sent"
                email_seq.sent_at = datetime.utcnow()
                
                # Schedule remaining sequence follow-ups
                for step in range(2, 6):
                    other_seq = db.query(EmailSequence).filter(
                        EmailSequence.lead_id == lead_db.id,
                        EmailSequence.step_number == step
                    ).first()
                    if other_seq:
                        other_seq.status = "scheduled"
                        other_seq.scheduled_at = datetime.utcnow() + timedelta(days=SEQUENCE_DELAYS[step])

                db.commit()

                # Update Google Sheet Pipeline columns directly
                g_send_updates = []
                a1_status = gspread.utils.rowcol_to_a1(row_num, header_map["Automation Status"] + 1)
                a1_appr = gspread.utils.rowcol_to_a1(row_num, header_map["Email Approval"] + 1)
                a1_sent = gspread.utils.rowcol_to_a1(row_num, header_map["Sent Date"] + 1)
                a1_email1 = gspread.utils.rowcol_to_a1(row_num, header_map["Email 1 Sent Date"] + 1)
                a1_updated = gspread.utils.rowcol_to_a1(row_num, header_map["Last Updated"] + 1)
                
                now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                g_send_updates.append({"range": a1_status, "values": [["Sent"]]})
                g_send_updates.append({"range": a1_appr, "values": [[""]]})
                g_send_updates.append({"range": a1_sent, "values": [[now_str]]})
                g_send_updates.append({"range": a1_email1, "values": [[now_str]]})
                g_send_updates.append({"range": a1_updated, "values": [[now_str]]})
                
                g_ws.batch_update(g_send_updates)
                
                print(f"  [SUCCESS] Email 1 sent successfully to {contact_name}.")
                modified = True

            except Exception as se:
                print(f"  Error: Failed to send email via Gmail API: {se}")
                a1_skip = gspread.utils.rowcol_to_a1(row_num, header_map["Skip / Reject Reason"] + 1)
                a1_updated = gspread.utils.rowcol_to_a1(row_num, header_map["Last Updated"] + 1)
                g_ws.batch_update([
                    {"range": a1_skip, "values": [[f"Gmail API send failed: {se}"]]},
                    {"range": a1_updated, "values": [[datetime.now().strftime("%Y-%m-%dT%H:%M:%S")]]}
                ])
                modified = True

    # --- Part B: Process Scheduled Follow-up Emails (Email 2–5) ---
    print("\n[Send] Checking for scheduled follow-ups ready to deliver...")
    now = datetime.utcnow()
    scheduled_steps = db.query(EmailSequence).filter(
        EmailSequence.status == "scheduled",
        EmailSequence.scheduled_at <= now
    ).all()

    for seq in scheduled_steps:
        lead = db.query(Lead).filter(Lead.id == seq.lead_id).first()
        if not lead:
            continue

        # Stop sequence if lead has replied
        if lead.status == "replied" or lead.email == "opt_out":
            print(f"  Sequence cancelled for {lead.name}: Lead has replied or opted out.")
            seq.status = "cancelled"
            db.commit()
            continue

        # Find corresponding row in Google Sheets
        matching_row = None
        for r_idx, r in enumerate(g_rows[1:]):
            email_val = r[header_map["Email"]]
            if email_val == lead.email:
                matching_row = r_idx + 2
                break

        if not matching_row:
            continue

        # Prepare follow-up tracked HTML
        html_body = _build_email_html(
            body=seq.body,
            tracking_id=seq.tracking_id,
            backend_url=backend_url
        )

        send_data = {
            "email": lead.email,
            "email_subject": seq.subject,
            "email_body_html": html_body,
            "tracking_id": seq.tracking_id
        }

        try:
            print(f"  Sending Follow-up Email {seq.step_number} to {lead.email}...")
            node_send_email_via_gmail(send_data, gmail_service)
            
            # Update status in DB
            seq.status = "sent"
            seq.sent_at = datetime.utcnow()
            db.commit()

            # Update Google Sheet Pipeline columns
            g_follow_updates = []
            a1_email_sent = gspread.utils.rowcol_to_a1(matching_row, header_map[f"Email {seq.step_number} Sent Date"] + 1)
            a1_activity = gspread.utils.rowcol_to_a1(matching_row, header_map["Last Activity"] + 1)
            a1_updated = gspread.utils.rowcol_to_a1(matching_row, header_map["Last Updated"] + 1)
            
            now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            g_follow_updates.append({"range": a1_email_sent, "values": [[now_str]]})
            g_follow_updates.append({"range": a1_activity, "values": [[now_str]]})
            g_follow_updates.append({"range": a1_updated, "values": [[now_str]]})
            
            g_ws.batch_update(g_follow_updates)
            
            modified = True
            print(f"  [SUCCESS] Follow-up step {seq.step_number} sent successfully.")

        except Exception as se:
            print(f"  Error: Failed to deliver follow-up email {seq.step_number}: {se}")

    # --- Part C: Check for Inactive Sequences (5 sent and 30 days of inactivity) ---
    print("\n[Send] Checking for sequences with 30-day inactivity post-Email 5...")
    all_leads = db.query(Lead).filter(Lead.status != "Rejected at Email by Client", Lead.status != "REPLIED").all()
    for lead in all_leads:
        # Check if Email 5 is sent
        seq5 = db.query(EmailSequence).filter(
            EmailSequence.lead_id == lead.id,
            EmailSequence.step_number == 5,
            EmailSequence.status == "sent"
        ).first()
        
        if seq5 and seq5.sent_at:
            if datetime.utcnow() - seq5.sent_at > timedelta(days=30):
                print(f"  Lead {lead.name} reached 30 days since Email 5 without reply. Marking as Rejected.")
                lead.status = "Rejected at Email by Client"
                db.commit()
                
                # Update Google Sheet row status
                for r_idx, r in enumerate(g_rows[1:]):
                    email_val = r[header_map["Email"]]
                    if email_val == lead.email:
                        a1_status = gspread.utils.rowcol_to_a1(r_idx + 2, header_map["Automation Status"] + 1)
                        a1_updated = gspread.utils.rowcol_to_a1(r_idx + 2, header_map["Last Updated"] + 1)
                        g_ws.batch_update([
                            {"range": a1_status, "values": [["Rejected at Email by Client"]]},
                            {"range": a1_updated, "values": [[datetime.now().strftime("%Y-%m-%dT%H:%M:%S")]]}
                        ])
                        modified = True
                        break

    db.close()

    if not modified:
        print("[Email Send Service] No approved or scheduled sends ready.")

if __name__ == "__main__":
    process_email_approvals_and_sends()
