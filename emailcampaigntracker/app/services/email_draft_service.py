import os
import sys
import json
import logging
from datetime import datetime
import openpyxl
import requests

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

# Load environment before any other local imports execute
load_env_at_startup(ENV_PATH)

from app.integrations.gdocs_uploader import upload_to_gdocs, load_env
from app.services.sheet_sync_service import run_bidirectional_sync, EXCEL_PATH

logger = logging.getLogger("email_draft_service")

def _call_gemini(prompt: str, api_key: str, model: str) -> str:
    if not model.startswith("models/"):
        model = f"models/{model}"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    resp = requests.post(url, json=payload, timeout=90)
    resp.raise_for_status()
    data = resp.json()
    candidates = data.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        if parts:
            return parts[0].get("text", "")
    return ""

def convert_md_to_html(md_text: str, from_email: str = "", to_email: str = "") -> str:
    """Basic helper to wrap Markdown text into clean HTML tags for Google Docs upload."""
    lines = md_text.splitlines()
    html_lines = []
    
    html_lines.append("<html><body style='font-family: Arial, sans-serif; line-height: 1.5;'>")
    
    if from_email or to_email:
        html_lines.append("<div style='border: 1px solid #CBD5E1; background-color: #F8FAFC; padding: 12px; margin-bottom: 20px; border-radius: 4px;'>")
        if from_email:
            html_lines.append(f"<p style='margin: 0 0 6px 0; font-size: 11pt; color: #334155;'><strong>From:</strong> {from_email}</p>")
        if to_email:
            html_lines.append(f"<p style='margin: 0; font-size: 11pt; color: #334155;'><strong>To:</strong> {to_email}</p>")
        html_lines.append("</div>")
    
    for line in lines:
        line_strip = line.strip()
        
        if line_strip.startswith("###"):
            html_lines.append(f"<h3 style='color: #1B2A4A; margin-top: 15px;'>{line_strip[3:].strip()}</h3>")
        elif line_strip.startswith("##"):
            html_lines.append(f"<h2 style='color: #1B2A4A; border-bottom: 1px solid #CBD5E1; padding-bottom: 5px; margin-top: 20px;'>{line_strip[2:].strip()}</h2>")
        elif line_strip.startswith("#"):
            html_lines.append(f"<h1 style='color: #1B2A4A; border-bottom: 2px solid #1B2A4A; padding-bottom: 10px;'>{line_strip[1:].strip()}</h1>")
        elif line_strip.startswith("*") or line_strip.startswith("-"):
            html_lines.append(f"<li>{line_strip[1:].strip()}</li>")
        elif line_strip:
            line_html = line_strip
            import re
            bold_matches = re.findall(r"\*\*(.*?)\*\*", line_html)
            for bm in bold_matches:
                line_html = line_html.replace(f"**{bm}**", f"<b>{bm}</b>")
            html_lines.append(f"<p>{line_html}</p>")
        else:
            html_lines.append("<br/>")
            
    html_lines.append("</body></html>")
    return "\n".join(html_lines)

def get_sender_email(creds_path):
    """Query Gmail API using authorized user credentials to find the sender email address."""
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials as UserCredentials
        if os.path.exists(creds_path):
            creds = UserCredentials.from_authorized_user_file(creds_path)
            gmail_service = build('gmail', 'v1', credentials=creds)
            profile = gmail_service.users().getProfile(userId='me').execute()
            return profile.get('emailAddress', 'Sender Email (me)')
    except Exception as e:
        print(f"    Warning: Could not get sender email address ({e})")
    return "Sender Email (me)"

def process_pending_email_drafts():
    """Poll sheets for pending drafts, generate 5-email drip sequence using Gemini, upload to GDocs, and sync to DB."""
    from app.services.sheet_sync_service import get_google_client, load_env
    import gspread
    
    print("--------------------------------------------------")
    print("[Email Draft Service] Running Draft Generator...")
    print("--------------------------------------------------")
    
    env = load_env(ENV_PATH)
    gemini_key = env.get("GEMINI_API_KEY")
    gemini_model = env.get("GEMINI_MODEL", "gemini-flash-lite-latest")
    
    if not gemini_key:
        print("Error: GEMINI_API_KEY not configured in .env file.")
        return

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

    for r_idx, r in enumerate(g_rows[1:]):
        status = str(r[header_map["Automation Status"]]).strip()
        email_approval = str(r[header_map["Email Approval"]]).strip().lower()
        doc_link = r[header_map["Email Draft Doc Link"]]
        row_num = r_idx + 2
        company = str(r[header_map["Company"]]).strip()

        # TEST MODE: only process the dummy Test Corp row
        test_mode = env.get("TEST_MODE", "false").strip().lower() == "true"
        test_company = env.get("TEST_COMPANY", "Test Corp").strip()
        if test_mode and company.lower() != test_company.lower():
            continue

        # Trigger condition: Status = Pending Email Review AND (No doc link OR Email Approval = Revise)
        if status == "Pending Email Review" and (not doc_link or email_approval == "revise"):
            contact_name = f"{r[header_map['First Name']]} {r[header_map['Last Name']]}".strip()
            role = str(r[header_map["Title"]]).strip()
            scraped_notes = str(r[header_map["(I) Notes"]]).strip()
            website = str(r[header_map["Website"]]).strip()
            
            print(f"\n==================================================")
            print(f"--> Generating 5-Email Sequence for Row {row_num}: {contact_name} ({company})")
            print(f"==================================================")

            # Build Gemini Email Drafting Prompt using customizations & rules from sales-outreach/SKILL.md
            prompt = f"""
You are a senior cold outreach copywriter. Create a highly personalized 5-email drip sequence targeting the following contact:

Company: {company} (Website: {website})
Contact Name: {contact_name}
Title/Role: {role}

= Contact Background & Scraped LinkedIn Notes =
{scraped_notes}

Follow these strict rules to draft the outreach sequence:
1. **Never use generic templates**. Use a specific reference to their LinkedIn background, headline, or latest posts to hook their attention.
2. Structure the 5-email drip sequence in the exact sequence:
   * **Email 1: The Initial Hook & Value Prop**. Start with a warm trigger/reference, specify the core value proposition, and close with a soft CTA.
   * **Email 2: Soft Follow-up**. Mention Email 1, add a quick tip or observation related to their company.
   * **Email 3: Case Study / Social Proof**. Share a metric-driven customer success story.
   * **Email 4: Objection Handler**. Address a common roadblock (e.g. "don't have budget", "too busy") and provide a counterpoint.
   * **Email 5: Break-up**. A polite, professional final touchpoint to close the thread if no response.
3. Every email must include a **Subject Line** and **Email Body**.
4. Use a natural, warm, professional, human-like voice. Keep the email lengths under 150 words per email.
5. Incorporate formatting like bold text and lists where helpful.

Format the output clearly as a single markdown document with headings for each email (e.g. "## Email 1: Initial Touch", "## Email 2: Follow-up"). Do not include any JSON blocks in the output.
"""
            try:
                sequence_md = _call_gemini(prompt, gemini_key, gemini_model)
            except Exception as e:
                print(f"    Gemini draft generation failed: {e}")
                sequence_md = f"# Outreach Sequence: {company}\nFailed to draft sequence due to Gemini API error: {e}"

            # Fetch sender email address dynamically
            token_path = env.get("GMAIL_OAUTH_CREDENTIALS_PATH", r"C:\git\emailcampaigntracker\gmail_token.json")
            sender_email = get_sender_email(token_path)
            
            # Upload the drafted sequence to Google Docs
            sequence_html = convert_md_to_html(sequence_md, from_email=sender_email, to_email=email_val)
            doc_title = f"Outreach Sequence: {contact_name} ({company})"
            
            try:
                new_doc_url = upload_to_gdocs(doc_title, sequence_html)
            except Exception as ue:
                print(f"    Failed to upload draft to Google Docs: {ue}")
                new_doc_url = doc_link # keep old link on failure

            # --- Parse and Sync to Postgres Database ---
            try:
                from database.db import SessionLocal
                from database.models import Lead, EmailSequence
                from app.core.utils import normalize_linkedin_url
                import uuid
                import re

                # Parse the 5-email sequence from markdown
                emails = []
                # Match "## Email 1: ...", "### Email 2: ...", etc.
                sections = re.split(r"##+\s*Email\s*(\d+)", sequence_md, flags=re.IGNORECASE)
                
                if len(sections) > 1:
                    for idx in range(1, len(sections), 2):
                        step_num = int(sections[idx])
                        content = sections[idx+1]
                        
                        subject = f"Outreach from {company}"
                        subj_match = re.search(r"Subject:\s*(.*)", content, re.IGNORECASE)
                        if subj_match:
                            subject = subj_match.group(1).strip()
                            body = re.sub(r"Subject:\s*.*", "", content, flags=re.IGNORECASE).strip()
                        else:
                            body = content.strip()
                            
                        # Clean up formatting markers like triple backticks if any
                        body = re.sub(r"```.*?```", "", body, flags=re.DOTALL).strip()
                        
                        emails.append({
                            "step_number": step_num,
                            "subject": subject,
                            "body": body
                        })
                
                if not emails:
                    print("  Warning: No individual emails parsed from markdown response. Generating fallback steps...")
                    emails = [{
                        "step_number": 1,
                        "subject": f"Quick question regarding {company}",
                        "body": sequence_md
                    }]

                # Upsert Lead in Postgres DB
                linkedin_url = r[header_map["(I) LinkedIn URL"]]
                email_val = r[header_map["Email"]]
                
                db = SessionLocal()
                
                # Try finding lead by LinkedIn URL or Email
                lead_db = None
                if linkedin_url:
                    norm_li = normalize_linkedin_url(linkedin_url)
                    lead_db = db.query(Lead).filter(Lead.linkedin_url == norm_li).first()
                if not lead_db and email_val:
                    lead_db = db.query(Lead).filter(Lead.email == email_val).first()
                    
                if not lead_db:
                    lead_db = Lead(
                        name=contact_name,
                        email=email_val,
                        linkedin_url=normalize_linkedin_url(linkedin_url) if linkedin_url else None,
                        company=company,
                        role=role,
                        about=scraped_notes[:1000] if scraped_notes else None
                    )
                    db.add(lead_db)
                    db.commit()
                    db.refresh(lead_db)
                    print(f"  Created new Lead in Postgres: {contact_name}")
                else:
                    # Update details
                    lead_db.name = contact_name
                    lead_db.email = email_val
                    lead_db.company = company
                    lead_db.role = role
                    if scraped_notes:
                        lead_db.about = scraped_notes[:1000]
                    db.commit()
                    print(f"  Found and updated existing Lead in Postgres: {contact_name}")

                # Delete any old sequence steps to handle revisions
                db.query(EmailSequence).filter(EmailSequence.lead_id == lead_db.id).delete()
                db.commit()

                # Add new sequence steps as drafts
                for mail in emails:
                    seq_row = EmailSequence(
                        lead_id=lead_db.id,
                        step_number=mail["step_number"],
                        subject=mail["subject"],
                        body=mail["body"],
                        status="draft",
                        tracking_id=f"trk_{uuid.uuid4().hex[:12]}",
                        lead_name=contact_name
                    )
                    db.add(seq_row)
                db.commit()
                print(f"  Saved {len(emails)} email sequence drafts to database.")
                db.close()
            except Exception as dbe:
                print(f"  Warning: Failed to sync email drafts to Postgres database ({dbe})")

            # Update Google Sheet cells directly
            g_draft_updates = []
            a1_doc = gspread.utils.rowcol_to_a1(row_num, header_map["Email Draft Doc Link"] + 1)
            a1_appr = gspread.utils.rowcol_to_a1(row_num, header_map["Email Approval"] + 1)
            a1_status = gspread.utils.rowcol_to_a1(row_num, header_map["Automation Status"] + 1)
            a1_updated = gspread.utils.rowcol_to_a1(row_num, header_map["Last Updated"] + 1)
            
            g_draft_updates.append({"range": a1_doc, "values": [[new_doc_url]]})
            g_draft_updates.append({"range": a1_appr, "values": [[""]]})
            g_draft_updates.append({"range": a1_status, "values": [["Pending Email Review"]]})
            g_draft_updates.append({"range": a1_updated, "values": [[datetime.now().strftime("%Y-%m-%dT%H:%M:%S")]]})
            
            g_ws.batch_update(g_draft_updates)
            
            print(f"[SUCCESS] Row {row_num}: 5-email sequence drafted and uploaded. Link: {new_doc_url}")
            modified = True

    if not modified:
        print("[Email Draft Service] No pending draft rows found.")

if __name__ == "__main__":
    process_pending_email_drafts()
