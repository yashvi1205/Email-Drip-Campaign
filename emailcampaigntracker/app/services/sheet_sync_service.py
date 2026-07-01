import os
import gspread
import logging
from datetime import datetime

ENV_PATH = r"c:\git\emailcampaigntracker\.env"
EXCEL_PATH = r"c:\git\Sales_Automation_Pipeline.xlsx"

def load_env(env_path):
    env = {}
    if not os.path.exists(env_path):
        return env
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                v = v.strip()
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                env[k.strip()] = v
    return env

# Pre-load environment into os.environ for database imports
_startup_env = load_env(ENV_PATH)
for _k, _v in _startup_env.items():
    os.environ[_k] = _v

logger = logging.getLogger("sheet_sync")

def get_google_client(env):
    from google.oauth2.service_account import Credentials
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    info = {
        "type": env.get("GOOGLE_TYPE"),
        "project_id": env.get("GOOGLE_PROJECT_ID"),
        "private_key_id": env.get("GOOGLE_PRIVATE_KEY_ID"),
        "private_key": env.get("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n"),
        "client_email": env.get("GOOGLE_CLIENT_EMAIL"),
        "client_id": env.get("GOOGLE_CLIENT_ID"),
        "auth_uri": env.get("GOOGLE_AUTH_URI"),
        "token_uri": env.get("GOOGLE_TOKEN_URI"),
        "auth_provider_x509_cert_url": env.get("GOOGLE_AUTH_PROVIDER_CERT_URL"),
        "client_x509_cert_url": env.get("GOOGLE_CLIENT_CERT_URL"),
        "universe_domain": env.get("GOOGLE_UNIVERSE_DOMAIN"),
    }
    creds = Credentials.from_service_account_info(info, scopes=scope)
    return gspread.authorize(creds)

def run_bidirectional_sync():
    """Load config and synchronize local Postgres stats directly to the online Google Sheets Profiles worksheet."""
    print("--------------------------------------------------")
    print("[Sheet Sync Service] Running direct database stats-to-Sheets sync...")
    print("--------------------------------------------------")
    env = load_env(ENV_PATH)
    sheet_id = env.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        print("Error: GOOGLE_SHEET_ID not set in .env")
        return
        
    try:
        from database.db import SessionLocal
        from database.models import Lead, EmailSequence
        from app.core.utils import normalize_linkedin_url

        db = SessionLocal()
        leads_db = db.query(Lead).all()
        
        print(f"Loading remote Google Sheet ID: {sheet_id}")
        g_client = get_google_client(env)
        gsheet = g_client.open_by_key(sheet_id)
        g_ws = gsheet.worksheet("Profiles")
        
        g_rows = g_ws.get_all_values()
        headers = ["Profile URL", "Email", "Status", "Open Count", "Last Opened", "Click Count", "Last Clicked", "Replied", "Last Replied"]
        if g_rows:
            headers = [str(h).strip() for h in g_rows[0]]
        g_header_map = {h: idx for idx, h in enumerate(headers)}
        
        # Map remote profiles
        g_by_profile = {}
        if g_rows:
            for r_idx, r in enumerate(g_rows[1:]):
                profile_val = r[g_header_map["Profile URL"]].strip().lower()
                if profile_val:
                    g_by_profile[profile_val] = (r_idx + 2, r)

        g_updates = []
        
        for lead in leads_db:
            if not lead.linkedin_url:
                continue
                
            norm_li = lead.linkedin_url.strip().lower()
            
            # Aggregate stats from EmailSequence
            seqs = db.query(EmailSequence).filter(EmailSequence.lead_id == lead.id).all()
            
            open_count = sum(s.open_count or 0 for s in seqs)
            click_count = sum(s.click_count or 0 for s in seqs)
            replied = "True" if any(s.replied for s in seqs) or lead.status == "replied" else "False"
            
            last_opened = ""
            last_clicked = ""
            last_replied = ""
            
            dates_open = [s.last_opened for s in seqs if s.last_opened]
            if dates_open:
                last_opened = max(dates_open).strftime("%Y-%m-%dT%H:%M:%S")
            
            dates_click = [s.last_clicked for s in seqs if s.last_clicked]
            if dates_click:
                last_clicked = max(dates_click).strftime("%Y-%m-%dT%H:%M:%S")
                
            dates_reply = [s.last_replied for s in seqs if s.last_replied]
            if dates_reply:
                last_replied = max(dates_reply).strftime("%Y-%m-%dT%H:%M:%S")
            
            lead_status = lead.status or "active"
            
            # Write directly to Google Sheets
            if norm_li in g_by_profile:
                row_num, g_row_data = g_by_profile[norm_li]
                
                # Check for changes and queue updates
                updates_map = {
                    "Status": lead_status.upper(),
                    "Open Count": str(open_count),
                    "Last Opened": last_opened,
                    "Click Count": str(click_count),
                    "Last Clicked": last_clicked,
                    "Replied": replied,
                    "Last Replied": last_replied
                }
                
                for col_name, new_val in updates_map.items():
                    if col_name in g_header_map:
                        col_idx = g_header_map[col_name]
                        old_val = str(g_row_data[col_idx]).strip()
                        if old_val != new_val:
                            a1 = gspread.utils.rowcol_to_a1(row_num, col_idx + 1)
                            g_updates.append({"range": a1, "values": [[new_val]]})
            else:
                # Add new row directly to remote
                new_row = [""] * len(headers)
                new_row[g_header_map["Profile URL"]] = lead.linkedin_url
                new_row[g_header_map["Email"]] = lead.email or ""
                new_row[g_header_map["Status"]] = lead_status.upper()
                new_row[g_header_map["Open Count"]] = str(open_count)
                new_row[g_header_map["Last Opened"]] = last_opened
                new_row[g_header_map["Click Count"]] = str(click_count)
                new_row[g_header_map["Last Clicked"]] = last_clicked
                new_row[g_header_map["Replied"]] = replied
                new_row[g_header_map["Last Replied"]] = last_replied
                g_ws.append_row(new_row)
                print(f"  Added new profile to Google Sheet Profiles: {lead.linkedin_url}")

        if g_updates:
            print(f"  Updating {len(g_updates)} cells in Google Sheet Profiles...")
            g_ws.batch_update(g_updates)
            
        db.close()
        print("Database stats-to-Sheets sync completed successfully!")
    except Exception as dbe:
        print(f"  Warning: Failed to sync database tracking stats to Google Sheet Profiles ({dbe})")

if __name__ == "__main__":
    run_bidirectional_sync()
