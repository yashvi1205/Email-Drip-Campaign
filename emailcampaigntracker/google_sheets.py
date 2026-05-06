import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os
import threading
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger("google_sheets")

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

# Check if essential credentials are present (Phase 0: env-only secrets; no file fallbacks)
if not info["private_key"] or not info["client_email"]:
    logger.warning("Google Sheets credentials not found in environment; Sheets features disabled.")
    creds = None
else:
    try:
        creds = Credentials.from_service_account_info(info, scopes=scope)
    except Exception:
        logger.exception("Failed to initialize Google credentials from environment; Sheets features disabled.")
        creds = None

if creds:
    try:
        client = gspread.authorize(creds)
    except Exception:
        logger.exception("Failed to authorize gspread client; Sheets features disabled.")
        client = None
else:
    client = None

# Initialize sheet variables
sheet = None
enhanced_sheet = None

if client:
    try:
        sheet = client.open("LinkedIn_Profile_DataScraper").sheet1
    except Exception:
        logger.exception("Failed to open LinkedIn_Profile_DataScraper sheet.")
    try:
        enhanced_sheet = client.open("LinkedIn_Enhanced_Data").sheet1
    except Exception:
        logger.exception("Failed to open LinkedIn_Enhanced_Data sheet.")

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
    except Exception:
        logger.exception("Failed to append row to sheet.")

def save_enhanced_data(full_name, profile_url, headline, company, about, email, interaction_type, content, interaction_date, role="", work_description="", recent_activity=""):
    if not enhanced_sheet: return
    row = [str(full_name), str(profile_url), str(role), str(headline), str(company), str(about), str(work_description), str(email), str(interaction_type), str(content), str(interaction_date), str(recent_activity), datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    try:
        enhanced_sheet.append_row(row)
    except Exception:
        logger.exception("Failed to append row to enhanced sheet.")

def get_profile_urls(sheet_name="Profiles"):
    try:
        spreadsheet = client.open("LinkedIn_Profile_DataScraper")
        profile_sheet = spreadsheet.worksheet(sheet_name)
        all_urls = profile_sheet.col_values(1)
        return [url.strip() for url in all_urls if "linkedin.com/in/" in url.lower()]
    except Exception:
        logger.exception("Failed to get profile URLs from sheet.")
        return []

def sync_leads_status(leads_data):
    """Updates the status and tracking columns in the Google Sheet for all listed leads."""
    try:
        spreadsheet = client.open("LinkedIn_Profile_DataScraper")
        try:
            profile_sheet = spreadsheet.worksheet("Profiles")
        except:
            profile_sheet = spreadsheet.sheet1
            
        all_rows = profile_sheet.get_all_values()
        if not all_rows: return False
        
        headers = [h.strip().lower() for h in all_rows[0]]
        
        # Define columns we want to track
        tracking_fields = {
            "profile url": "linkedin_url",
            "email": "email",
            "status": "status",
            "open count": "open_count",
            "last opened": "last_opened",
            "click count": "click_count",
            "last clicked": "last_clicked",
            "replied": "replied",
            "last replied": "last_replied"
        }
        
        col_indices = {}
        for h_text, field_key in tracking_fields.items():
            found = False
            for i, h in enumerate(headers):
                if h_text in h:
                    col_indices[field_key] = i + 1
                    found = True
                    break
            
            # If column not found, create it
            if not found:
                new_col = len(headers) + 1
                profile_sheet.update_cell(1, new_col, h_text.title())
                headers.append(h_text)
                col_indices[field_key] = new_col

        url_col = col_indices.get("linkedin_url", 1)
        status_map = {normalize_url(l.get('linkedin_url', '')): l for l in leads_data}
        urls = profile_sheet.col_values(url_col)
        
        updates = []
        for i, url in enumerate(urls):
            if i == 0: continue # Skip header
            clean_url = normalize_url(url)
            if clean_url in status_map:
                lead = status_map[clean_url]
                
                # Update each tracked field if present in lead data
                for field_key, col_idx in col_indices.items():
                    if field_key == "linkedin_url": continue # Don't update the URL itself
                    
                    val = lead.get(field_key)
                    if val is not None:
                        # Format timestamps
                        if "last" in field_key and hasattr(val, "strftime"):
                            val = val.strftime("%Y-%m-%d %H:%M:%S")
                        
                        updates.append({
                            'range': gspread.utils.rowcol_to_a1(i+1, col_idx), 
                            'values': [[str(val).upper() if field_key == "status" else str(val)]]
                        })
        
        if updates: 
            profile_sheet.batch_update(updates)
        return True
    except Exception as e:
        logger.exception("Sync error.")
        return False

def get_enhanced_profile_data(profile_url):
    """Retrieve full enriched details from the 'LinkedIn_Enhanced_Data' sheet."""
    if not enhanced_sheet: return None
    try:
        all_records = enhanced_sheet.get_all_records()
        if not all_records: return None
        for record in reversed(all_records):
            norm = {str(k).lower().strip().replace(' ', ''): v for k, v in record.items()}
            url_in_sheet = norm.get("profileurl") or norm.get("url")
            if normalize_url(url_in_sheet) == normalize_url(profile_url):
                return {
                    "role": norm.get("role") or "",
                    "headline": norm.get("headline") or "",
                    "company": norm.get("company") or "",
                    "about": norm.get("about") or "",
                    "work_description": norm.get("workdescription") or "",
                    "email": norm.get("email") or ""
                }
        return None
    except Exception:
        logger.exception("Failed to read enhanced profile data.")
        return None

def get_latest_post_for_profile(profile_url):
    if not sheet: return None
    try:
        all_records = sheet.get_all_records()
        for record in reversed(all_records):
            norm = {str(k).lower().strip(): v for k, v in record.items()}
            url_in_sheet = norm.get("profile (url)") or norm.get("profile url") or norm.get("profile")
            if normalize_url(url_in_sheet) == normalize_url(profile_url):
                return {
                    "text": norm.get("text") or "No text",
                    "likes": norm.get("likes") or "0",
                    "comments": norm.get("comments") or "0",
                    "reposts": norm.get("reposts") or "0",
                    "photo_url": norm.get("profile photo") or norm.get("photo url") or "",
                    "post_time": norm.get("post timeline") or "Recently",
                    "timestamp": norm.get("scraped time") or norm.get("timestamp") or "Recently"
                }
        return None
    except Exception:
        logger.exception("Failed to read latest post for profile.")
        return None

def get_last_entries(count=5):
    if not sheet: return []
    try:
        all_rows = sheet.get_all_values()
        if not all_rows or len(all_rows) < 2: return []
        headers = [str(h).lower().strip().replace(' ', '') for h in all_rows[0]]
        col_map = {h: i for i, h in enumerate(headers)}
        raw_rows = all_rows[1:][-count:]
        
        results = []
        for row in reversed(raw_rows):
            def get_val(key_list):
                for k in key_list:
                    if k in col_map and col_map[k] < len(row): return row[col_map[k]]
                return ""
            results.append({
                "url": get_val(["profile(url)", "profileurl", "profile"]),
                "username": get_val(["username", "user"]),
                "text": get_val(["text", "activity"]),
                "likes": get_val(["likes"]) or 0,
                "comments": get_val(["comments"]) or 0,
                "reposts": get_val(["reposts"]) or 0,
                "post_time": get_val(["posttimeline", "posttime"]),
                "photo_url": get_val(["profilephoto", "photourl"]),
                "timestamp": get_val(["scrapedtime", "timestamp"]) or "Recently",
                "is_repost": str(get_val(["isrepost"])).upper() == "TRUE"
            })
        return results
    except Exception:
        logger.exception("Failed to read last entries.")
        return []

def sync_sheet_status_async(linkedin_url, status, open_count=0):
    """Async wrapper to update a single lead's status in the sheet."""
    lead_data = {
        "linkedin_url": linkedin_url,
        "status": status,
        "open_count": open_count
    }
    sync_leads_status([lead_data])
