import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os
import threading
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Define the scope
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Map environment variables to the format expected by Google Auth
info = {
    "type": os.getenv("GOOGLE_TYPE"),
    "project_id": os.getenv("GOOGLE_PROJECT_ID"),
    "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n"),
    "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
    "auth_uri": os.getenv("GOOGLE_AUTH_URI"),
    "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("GOOGLE_AUTH_PROVIDER_CERT_URL"),
    "client_x509_cert_url": os.getenv("GOOGLE_CLIENT_CERT_URL"),
    "universe_domain": os.getenv("GOOGLE_UNIVERSE_DOMAIN")
}

# Check if essential credentials are present
if not info["private_key"] or not info["client_email"]:
    print("WARNING: Google Sheets credentials not found. Falling back to credentials.json.")
    creds_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
    if os.path.exists(creds_path):
        creds = Credentials.from_service_account_file(creds_path, scopes=scope)
    else:
        creds = None
else:
    creds = Credentials.from_service_account_info(info, scopes=scope)

if creds:
    client = gspread.authorize(creds)
else:
    client = None

# Initialize sheet variables
sheet = None
enhanced_sheet = None

if client:
    try:
        sheet = client.open("LinkedIn_Profile_DataScraper").sheet1
    except: pass
    try:
        enhanced_sheet = client.open("LinkedIn_Enhanced_Data").sheet1
    except: pass

def normalize_url(url):
    if not url: return ""
    url = url.strip().lower()
    return url.replace("https://nl.linkedin.com", "https://www.linkedin.com").replace("https://www.linkedin.com", "https://www.linkedin.com").rstrip("/")

def save_to_sheet(user, profile, post_type, text, likes, comments, reposts, photo_url="", post_time="", is_repost=False, reposter_name="", reposter_photo="", original_author_name=""):
    if not sheet: return
    def clean_num(val):
        if not val: return 0
        digits = "".join(filter(str.isdigit, str(val).replace(',', '')))
        return int(digits) if digits else 0

    row = [str(user), str(profile), str(post_type), str(text), clean_num(likes), clean_num(comments), clean_num(reposts), str(post_time), str(photo_url), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "TRUE" if is_repost else "FALSE", str(reposter_name), str(reposter_photo), str(original_author_name)]
    try:
        sheet.append_row(row)
    except Exception as e: print(f"Error: {e}")

def save_enhanced_data(full_name, profile_url, headline, company, about, email, interaction_type, content, interaction_date, role="", work_description="", recent_activity=""):
    if not enhanced_sheet: return
    row = [str(full_name), str(profile_url), str(role), str(headline), str(company), str(about), str(work_description), str(email), str(interaction_type), str(content), str(interaction_date), str(recent_activity), datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    try:
        enhanced_sheet.append_row(row)
    except Exception as e: print(f"Error: {e}")

def get_profile_urls(sheet_name="Profiles"):
    try:
        spreadsheet = client.open("LinkedIn_Profile_DataScraper")
        profile_sheet = spreadsheet.worksheet(sheet_name)
        all_urls = profile_sheet.col_values(1)
        return [url.strip() for url in all_urls if "linkedin.com/in/" in url.lower()]
    except: return []

def sync_leads_status(leads_data):
    """Updates the status column in the Google Sheet for all listed leads."""
    try:
        spreadsheet = client.open("LinkedIn_Profile_DataScraper")
        try:
            profile_sheet = spreadsheet.worksheet("Profiles")
        except:
            profile_sheet = spreadsheet.sheet1
            
        all_rows = profile_sheet.get_all_values()
        if not all_rows: return False
        
        headers = [h.strip().lower() for h in all_rows[0]]
        status_col = -1
        url_col = -1
        open_col = -1
        
        for i, h in enumerate(headers):
            if "status" in h: status_col = i + 1
            if "profile url" in h or "linkedin" in h: url_col = i + 1
            if "open count" in h: open_col = i + 1
        
        if open_col == -1:
            open_col = len(headers) + 1
            profile_sheet.update_cell(1, open_col, "Open Count")

        status_map = {normalize_url(l['linkedin_url']): l for l in leads_data}
        urls = profile_sheet.col_values(url_col or 1)
        
        updates = []
        for i, url in enumerate(urls):
            if i == 0: continue
            clean_url = normalize_url(url)
            if clean_url in status_map:
                lead = status_map[clean_url]
                updates.append({'range': gspread.utils.rowcol_to_a1(i+1, status_col), 'values': [[lead['status'].upper()]]})
                if open_col != -1 and 'open_count' in lead:
                    updates.append({'range': gspread.utils.rowcol_to_a1(i+1, open_col), 'values': [[lead['open_count']]]})
        
        if updates: profile_sheet.batch_update(updates)
        return True
    except Exception as e:
        print(f"Sync error: {e}")
        return False

def sync_sheet_status_async(linkedin_url, status, open_count=0):
    """Async wrapper to update a single lead's status in the sheet."""
    lead_data = {
        "linkedin_url": linkedin_url,
        "status": status,
        "open_count": open_count
    }
    sync_leads_status([lead_data])
