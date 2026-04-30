<<<<<<< HEAD
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os


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
    print("WARNING: Google Sheets credentials not found in environment variables. Falling back to credentials.json if available.")
    creds_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
    if os.path.exists(creds_path):
        creds = Credentials.from_service_account_file(creds_path, scopes=scope)
    else:
        print("ERROR: No Google Sheets credentials found. Functionality will be limited.")
        creds = None
else:
    # Modern authentication using service account info from environment variables
    creds = Credentials.from_service_account_info(info, scopes=scope)

if creds:
    client = gspread.authorize(creds)
else:
    client = None

# Standard sheet for existing functionality
sheet = client.open("LinkedIn_Profile_DataScraper").sheet1

# Enhanced sheet for profile details and interactions
try:
    enhanced_sheet = client.open("LinkedIn_Enhanced_Data").sheet1
except Exception as e:
    print(f"WARNING: Could not open 'LinkedIn_Enhanced_Data'. Make sure it exists and is shared. Error: {e}")
    enhanced_sheet = None


def save_to_sheet(user, profile, post_type, text, likes, comments, reposts, photo_url="", post_time="", is_repost=False, reposter_name="", reposter_photo="", original_author_name=""):
    """Saves a new entry with standardized column order including repost details."""
    def clean_num(val):
        if not val: return 0
        val_str = str(val).replace(',', '').strip()
        digits = "".join(filter(str.isdigit, val_str))
        return int(digits) if digits else 0

    row = [
        str(user).strip(),
        str(profile).strip(),
        str(post_type).strip(),
        str(text),
        clean_num(likes),
        clean_num(comments),
        clean_num(reposts),
        str(post_time).strip(),
        str(photo_url),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "TRUE" if is_repost else "FALSE",
        str(reposter_name),
        str(reposter_photo),
        str(original_author_name)
    ]

    try:
        # Check for sheet headers
        first_row = sheet.row_values(1)
        if not first_row:
            headers = [
                "User Name", "Profile (URL)", "Posts", "Text", "Likes", "Comments", "Reposts", 
                "Post Timeline", "Profile Photo", "Scraped Time", 
                "Is Repost", "Reposter Name", "Reposter Photo", "Original Author"
            ]
            sheet.insert_row(headers, 1)
        
        sheet.append_row(row)
        print("Saved to Google Sheets")
    except Exception as e:
        print(f"Error saving to Google Sheets: {e}")

def save_enhanced_data(full_name, profile_url, headline, company, about, email, interaction_type, content, interaction_date, role="", work_description="", recent_activity=""):
    """Saves enriched profile data and interactions to the new Google Sheet."""
    if not enhanced_sheet:
        print("ERROR: Enhanced sheet not initialized. Cannot save data.")
        return

    row = [
        str(full_name).strip(),
        str(profile_url).strip(),
        str(role).strip(), # New field
        str(headline).strip(),
        str(company).strip(),
        str(about).replace('\n', ' ').strip(),
        str(work_description).replace('\n', ' ').strip(), # New field
        str(email).strip(),
        str(interaction_type).strip(),
        str(content).strip(),
        str(interaction_date).strip(),
        str(recent_activity).strip(), # New field
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ]

    try:
        # Check for sheet headers and update if old version detected
        first_row = enhanced_sheet.row_values(1)
        headers = [
            "Full Name", "Profile URL", "Role", "Headline", "Company", "About", "Work Description", "Email", 
            "Interaction Type", "Content", "Interaction Date", "Recent Activity List", "Scraped Date"
        ]
        if not first_row or len(first_row) < 13:
            # Overwrite header row to ensure correct order
            enhanced_sheet.update('A1', [headers])
            print("Updated Google Sheet headers to modern layout.")
        
        enhanced_sheet.append_row(row)
        print(f"Saved enhanced data for {full_name} to Google Sheets")
    except Exception as e:
        print(f"Error saving enhanced data to Google Sheets: {e}")


def get_enhanced_profile_data(profile_url):
    """Retrieve full enriched details from the 'LinkedIn_Enhanced_Data' sheet."""
    if not enhanced_sheet: return None
    try:
        all_records = enhanced_sheet.get_all_records()
        if not all_records: return None
        
        # Search from most recent (bottom of sheet) up
        for record in reversed(all_records):
            # Normalizing keys (lowercase and stripped)
            norm = {str(k).lower().strip().replace(' ', ''): v for k, v in record.items()}
            
            url_in_sheet = norm.get("profileurl") or norm.get("url")
            if url_in_sheet == profile_url:
                return {
                    "role": norm.get("role") or "",
                    "headline": norm.get("headline") or "",
                    "company": norm.get("company") or "",
                    "about": norm.get("about") or "",
                    "work_description": norm.get("workdescription") or "",
                    "email": norm.get("email") or ""
                }
        return None
    except Exception as e:
        print(f"Error fetching enhanced data from sheet: {e}")
        return None

def get_latest_post_for_profile(profile_url):
    """Search Google Sheets for the most recent entry for a specific profile URL."""
    try:
        all_records = sheet.get_all_records()
        if not all_records:
            return None
        
        # Reverse to find the most recent one
        for record in reversed(all_records):
            # Normalizing keys (lowercase and stripped)
            norm = {str(k).lower().strip(): v for k, v in record.items()}
            
            url_in_sheet = norm.get("profile (url)") or norm.get("profile url") or norm.get("profile")
            if url_in_sheet == profile_url:
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
    except Exception as e:
        print(f"Error searching sheet: {e}")
        return None


def get_last_entries(count=5):
    """Retrieve the last N entries from the sheet and normalize them for the API."""
    try:
        # Use get_all_values to avoid "duplicate header" errors from empty cells in row 1
        all_rows = sheet.get_all_values()
        if not all_rows or len(all_rows) < 2:
            return []
        
        headers = [str(h).lower().strip().replace(' ', '') for h in all_rows[0]]
        all_data = all_rows[1:] # Skip header row
        
        # Take the last N rows
        raw_rows = all_data[-count:]
        normalized_entries = []
        
        from datetime import datetime, timedelta
        
        def parse_relative_time(rt):
            if not rt or not isinstance(rt, str): return 9999999
            rt = rt.lower().split('•')[0].strip()
            if any(x in rt for x in ['now', 'moment', 'just']): return 0
            num_str = "".join(filter(str.isdigit, rt))
            if not num_str: return 9999998
            num = int(num_str)
            if 's' in rt: return num
            if 'm' in rt: return num * 60
            if 'h' in rt: return num * 3600
            if 'd' in rt: return num * 86400
            if 'w' in rt: return num * 604800
            if 'mo' in rt: return num * 2592000
            if 'yr' in rt: return num * 31536000
            return 9999997

        def get_estimated_post_date(entry):
            ts_str = entry.get("timestamp", "")
            rt = entry.get("post_time", "")
            try:
                base_time = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                rel_sec = parse_relative_time(rt)
                return base_time - timedelta(seconds=rel_sec)
            except:
                return datetime(1970, 1, 1)

        # Mapping of simplified header names to their column index
        col_map = {h: i for i, h in enumerate(headers)}
        
        for row in raw_rows:
            def get_val(key_list):
                for k in key_list:
                    if k in col_map and col_map[k] < len(row):
                        return row[col_map[k]]
                return ""

            p_url = str(get_val(["profilephoto", "photourl", "profile(photo)"]))
            p_time = str(get_val(["posttimeline", "posttime"]))
            
            # Simple heuristic to fix potential swaps in older data
            if p_time.startswith("http") and not p_url.startswith("http"):
                p_url, p_time = p_time, p_url
            
            normalized_entries.append({
                "url": get_val(["profile(url)", "profileurl", "profile"]),
                "username": get_val(["username", "username", "user"]),
                "text": get_val(["text", "activity"]),
                "likes": get_val(["likes"]) or 0,
                "comments": get_val(["comments"]) or 0,
                "reposts": get_val(["reposts"]) or 0,
                "post_time": p_time or "Unknown",
                "photo_url": p_url or "",
                "timestamp": get_val(["scrapedtime", "timestamp"]) or "Recently",
                "is_repost": str(get_val(["isrepost"])).upper() == "TRUE",
                "reposter_name": get_val(["repostername"]) or "",
                "reposter_photo": get_val(["reposterphoto"]) or "",
                "original_author_name": get_val(["originalauthor"]) or ""
            })
            
        # Reverse the list to get most recently appended entries first
        normalized_entries.reverse()
        return normalized_entries
    except Exception as e:
        print(f"Error fetching from Google Sheets: {e}")
        return []


def get_profile_urls(sheet_name="Profiles"):
    """Fetch LinkedIn profile URLs from the 'Profiles' worksheet."""
    try:
        # Open the spreadsheet and the specific worksheet
        spreadsheet = client.open("LinkedIn_Profile_DataScraper")
        profile_sheet = spreadsheet.worksheet(sheet_name)
        
        # Get all values from the first column (col 1)
        # Using col_values is efficient for getting a single column
        all_urls = profile_sheet.col_values(1)
        
        # Filter out header (if any) and empty values
        # We assume the first row might be 'Profile URL' or similar if it's the only value
        # but the user said "just we need to fetch the profile links now from google sheets"
        # I'll keep everything that looks like a LinkedIn URL
        clean_urls = []
        for url in all_urls:
            url = url.strip()
            if not url:
                continue
            if "linkedin.com/in/" in url.lower():
                clean_urls.append(url)
                
        return clean_urls
    except Exception as e:
        print(f"Error fetching profile URLs from Google Sheet '{sheet_name}': {e}")
        return []
=======
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os


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
    print("WARNING: Google Sheets credentials not found in environment variables. Falling back to credentials.json if available.")
    creds_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
    if os.path.exists(creds_path):
        creds = Credentials.from_service_account_file(creds_path, scopes=scope)
    else:
        print("ERROR: No Google Sheets credentials found. Functionality will be limited.")
        creds = None
else:
    # Modern authentication using service account info from environment variables
    creds = Credentials.from_service_account_info(info, scopes=scope)

if creds:
    client = gspread.authorize(creds)
else:
    client = None

# Initialize sheet variables as None
sheet = None
enhanced_sheet = None

if client:
    # Standard sheet for existing functionality
    try:
        sheet = client.open("LinkedIn_Profile_DataScraper").sheet1
    except Exception as e:
        print(f"WARNING: Could not open 'LinkedIn_Profile_DataScraper'. Error: {e}")
        sheet = None

    # Enhanced sheet for profile details and interactions
    try:
        enhanced_sheet = client.open("LinkedIn_Enhanced_Data").sheet1
    except Exception as e:
        print(f"WARNING: Could not open 'LinkedIn_Enhanced_Data'. Error: {e}")
        enhanced_sheet = None
else:
    print("ERROR: Google Sheets client not initialized.")


def save_to_sheet(user, profile, post_type, text, likes, comments, reposts, photo_url="", post_time="", is_repost=False, reposter_name="", reposter_photo="", original_author_name=""):
    """Saves a new entry with standardized column order including repost details."""
    def clean_num(val):
        if not val: return 0
        val_str = str(val).replace(',', '').strip()
        digits = "".join(filter(str.isdigit, val_str))
        return int(digits) if digits else 0

    row = [
        str(user).strip(),
        str(profile).strip(),
        str(post_type).strip(),
        str(text),
        clean_num(likes),
        clean_num(comments),
        clean_num(reposts),
        str(post_time).strip(),
        str(photo_url),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "TRUE" if is_repost else "FALSE",
        str(reposter_name),
        str(reposter_photo),
        str(original_author_name)
    ]

    try:
        # Check for sheet headers
        first_row = sheet.row_values(1)
        if not first_row:
            headers = [
                "User Name", "Profile (URL)", "Posts", "Text", "Likes", "Comments", "Reposts", 
                "Post Timeline", "Profile Photo", "Scraped Time", 
                "Is Repost", "Reposter Name", "Reposter Photo", "Original Author"
            ]
            sheet.insert_row(headers, 1)
        
        sheet.append_row(row)
        print("Saved to Google Sheets")
    except Exception as e:
        print(f"Error saving to Google Sheets: {e}")

def save_enhanced_data(full_name, profile_url, headline, company, about, email, interaction_type, content, interaction_date, role="", work_description="", recent_activity=""):
    """Saves enriched profile data and interactions to the new Google Sheet."""
    if not enhanced_sheet:
        print("ERROR: Enhanced sheet not initialized. Cannot save data.")
        return

    row = [
        str(full_name).strip(),
        str(profile_url).strip(),
        str(role).strip(), # New field
        str(headline).strip(),
        str(company).strip(),
        str(about).replace('\n', ' ').strip(),
        str(work_description).replace('\n', ' ').strip(), # New field
        str(email).strip(),
        str(interaction_type).strip(),
        str(content).strip(),
        str(interaction_date).strip(),
        str(recent_activity).strip(), # New field
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ]

    try:
        # Check for sheet headers and update if old version detected
        first_row = enhanced_sheet.row_values(1)
        headers = [
            "Full Name", "Profile URL", "Role", "Headline", "Company", "About", "Work Description", "Email", 
            "Interaction Type", "Content", "Interaction Date", "Recent Activity List", "Scraped Date", "Status"
        ]
        if not first_row or len(first_row) < 14:
            # Overwrite header row to ensure correct order
            enhanced_sheet.update('A1', [headers])
            print("Updated Google Sheet headers to modern layout.")
        
        # v16.0: DE-DUPLICATION LOGIC
        # Find if this profile already exists in the sheet
        all_urls = enhanced_sheet.col_values(2) # Column B is Profile URL
        existing_row_idx = -1
        
        # Normalize the incoming URL for matching
        clean_url = normalize_url(profile_url)
        
        for i, url in enumerate(all_urls):
            if i == 0: continue # Skip header
            if normalize_url(url) == clean_url:
                existing_row_idx = i + 1
                break
        
        if existing_row_idx != -1:
            # UPDATE EXISTING ROW
            print(f"   -> Updating existing entry for {full_name} at row {existing_row_idx}")
            
            # Update columns 9 through 13 (Interaction info and Scraped Date)
            # We also update headline, company, role etc in case they changed
            updates = [
                {'range': f'A{existing_row_idx}', 'values': [[str(full_name).strip()]]},
                {'range': f'C{existing_row_idx}', 'values': [[str(role).strip()]]},
                {'range': f'D{existing_row_idx}', 'values': [[str(headline).strip()]]},
                {'range': f'E{existing_row_idx}', 'values': [[str(company).strip()]]},
                {'range': f'F{existing_row_idx}', 'values': [[str(about).replace("\n", " ").strip()]]},
                {'range': f'G{existing_row_idx}', 'values': [[str(work_description).replace("\n", " ").strip()]]},
                {'range': f'H{existing_row_idx}', 'values': [[str(email).strip()]]},
                {'range': f'I{existing_row_idx}', 'values': [[str(interaction_type).strip()]]},
                {'range': f'J{existing_row_idx}', 'values': [[str(content).strip()]]},
                {'range': f'K{existing_row_idx}', 'values': [[str(interaction_date).strip()]]},
                {'range': f'L{existing_row_idx}', 'values': [[str(recent_activity).strip()]]},
                {'range': f'M{existing_row_idx}', 'values': [[datetime.now().strftime("%Y-%m-%d %H:%M:%S")]]}
            ]
            enhanced_sheet.batch_update(updates)
            print(f"   -> [UPDATE COMPLETE] for {full_name}")
        else:
            # APPEND NEW ROW
            enhanced_sheet.append_row(row + ["active"])
            print(f"Saved new enhanced data for {full_name} to Google Sheets")
    except Exception as e:
        print(f"Error saving/updating enhanced data to Google Sheets: {e}")

def normalize_url(url):
    if not url:
        return ""
    url = url.strip().lower()
    return (
        url.replace("https://nl.linkedin.com", "https://www.linkedin.com")
           .replace("https://www.linkedin.com", "https://www.linkedin.com")
           .rstrip("/")
    )


def sync_leads_status(leads_data):
    """Updates the status column in the Google Sheet for all listed leads."""
    try:
        # User specified: "the sheet is same from where it is fetching the data"
        spreadsheet = client.open("LinkedIn_Profile_DataScraper")
        try:
            profile_sheet = spreadsheet.worksheet("Profiles")
        except:
            # Fallback to the very first sheet if "Profiles" doesn't exist
            profile_sheet = spreadsheet.sheet1
            
        all_rows = profile_sheet.get_all_values()
        if not all_rows: return False
        
        headers = [h.strip().lower() for h in all_rows[0]]
        status_col_idx = -1
        url_col_idx = -1
        open_count_col_idx = -1
        
        for i, h in enumerate(headers):
            if "email status" in h: status_col_idx = i + 1
            if "url" in h: url_col_idx = i + 1
            if "open" in h and "count" in h: open_count_col_idx = i + 1
        
        # If Open Count column doesn't exist, create it at the end
        if open_count_col_idx == -1:
            open_count_col_idx = len(headers) + 1
            profile_sheet.update_cell(1, open_count_col_idx, "Open Count")
            print(f"   -> Added 'Open Count' column to Profiles sheet at column {open_count_col_idx}")

        if status_col_idx == -1:
            print("ERROR: Could not find a column containing 'status' in headers.")
            return False
            
        if url_col_idx == -1: 
            url_col_idx = 1 # Default to column A if URL not found
            
        # Map with NORMALIZED URLs
        status_map = {normalize_url(l['linkedin_url']): l for l in leads_data}
        urls = profile_sheet.col_values(url_col_idx)
        
        updates = []
        for i, url in enumerate(urls):
            if i == 0: continue # Skip header
            clean_url = normalize_url(url)
            if clean_url in status_map:
                print("Matching:", clean_url)
                row_num = i + 1
                lead_data = status_map[clean_url]
                
                # Update Status
                updates.append({
                    'range': f'{gspread.utils.rowcol_to_a1(row_num, status_col_idx)}',
                    'values': [[lead_data['status']]]
                })
                
                # Update Open Count
                if 'open_count' in lead_data:
                    updates.append({
                        'range': f'{gspread.utils.rowcol_to_a1(row_num, open_count_col_idx)}',
                        'values': [[lead_data['open_count']]]
                    })
        
        if updates:
            profile_sheet.batch_update(updates)
            print(f"Synced {len(updates)} statuses to Profiles sheet.")
            
        # Also try syncing to Enhanced sheet if it exists
        if enhanced_sheet:
            try:
                enhanced_headers = enhanced_sheet.row_values(1)
                e_headers_low = [h.lower() for h in enhanced_headers]
                if "status" in e_headers_low:
                    e_status_idx = e_headers_low.index("status") + 1
                    e_url_idx = e_headers_low.index("profile url") + 1
                    e_urls = enhanced_sheet.col_values(e_url_idx)
                    e_updates = []
                    for i, url in enumerate(e_urls):
                        if i == 0: continue
                        clean_url = normalize_url(url)
                        if clean_url in status_map:
                            e_updates.append({
                                'range': f'{gspread.utils.rowcol_to_a1(i+1, e_status_idx)}',
                                'values': [[status_map[clean_url]['status']]]
                            })
                    if e_updates:
                        enhanced_sheet.batch_update(e_updates)
            except: pass
            
        return True
    except Exception as e:
        print(f"Error syncing lead statuses: {e}")
        return False


def get_enhanced_profile_data(profile_url):
    """Retrieve full enriched details from the 'LinkedIn_Enhanced_Data' sheet."""
    if not enhanced_sheet: return None
    try:
        all_records = enhanced_sheet.get_all_records()
        if not all_records: return None
        
        # Search from most recent (bottom of sheet) up
        for record in reversed(all_records):
            # Normalizing keys (lowercase and stripped)
            norm = {str(k).lower().strip().replace(' ', ''): v for k, v in record.items()}
            
            url_in_sheet = norm.get("profileurl") or norm.get("url")
            if url_in_sheet == profile_url:
                return {
                    "role": norm.get("role") or "",
                    "headline": norm.get("headline") or "",
                    "company": norm.get("company") or "",
                    "about": norm.get("about") or "",
                    "work_description": norm.get("workdescription") or "",
                    "email": norm.get("email") or ""
                }
        return None
    except Exception as e:
        print(f"Error fetching enhanced data from sheet: {e}")
        return None

def get_latest_post_for_profile(profile_url):
    """Search Google Sheets for the most recent entry for a specific profile URL."""
    try:
        all_records = sheet.get_all_records()
        if not all_records:
            return None
        
        # Reverse to find the most recent one
        for record in reversed(all_records):
            # Normalizing keys (lowercase and stripped)
            norm = {str(k).lower().strip(): v for k, v in record.items()}
            
            url_in_sheet = norm.get("profile (url)") or norm.get("profile url") or norm.get("profile")
            if url_in_sheet == profile_url:
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
    except Exception as e:
        print(f"Error searching sheet: {e}")
        return None


def get_last_entries(count=5):
    """Retrieve the last N entries from the sheet and normalize them for the API."""
    try:
        # Use get_all_values to avoid "duplicate header" errors from empty cells in row 1
        all_rows = sheet.get_all_values()
        if not all_rows or len(all_rows) < 2:
            return []
        
        headers = [str(h).lower().strip().replace(' ', '') for h in all_rows[0]]
        all_data = all_rows[1:] # Skip header row
        
        # Take the last N rows
        raw_rows = all_data[-count:]
        normalized_entries = []
        
        from datetime import datetime, timedelta
        
        def parse_relative_time(rt):
            if not rt or not isinstance(rt, str): return 9999999
            rt = rt.lower().split('•')[0].strip()
            if any(x in rt for x in ['now', 'moment', 'just']): return 0
            num_str = "".join(filter(str.isdigit, rt))
            if not num_str: return 9999998
            num = int(num_str)
            if 's' in rt: return num
            if 'm' in rt: return num * 60
            if 'h' in rt: return num * 3600
            if 'd' in rt: return num * 86400
            if 'w' in rt: return num * 604800
            if 'mo' in rt: return num * 2592000
            if 'yr' in rt: return num * 31536000
            return 9999997

        def get_estimated_post_date(entry):
            ts_str = entry.get("timestamp", "")
            rt = entry.get("post_time", "")
            try:
                base_time = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                rel_sec = parse_relative_time(rt)
                return base_time - timedelta(seconds=rel_sec)
            except:
                return datetime(1970, 1, 1)

        # Mapping of simplified header names to their column index
        col_map = {h: i for i, h in enumerate(headers)}
        
        for row in raw_rows:
            def get_val(key_list):
                for k in key_list:
                    if k in col_map and col_map[k] < len(row):
                        return row[col_map[k]]
                return ""

            p_url = str(get_val(["profilephoto", "photourl", "profile(photo)"]))
            p_time = str(get_val(["posttimeline", "posttime"]))
            
            # Simple heuristic to fix potential swaps in older data
            if p_time.startswith("http") and not p_url.startswith("http"):
                p_url, p_time = p_time, p_url
            
            normalized_entries.append({
                "url": get_val(["profile(url)", "profileurl", "profile"]),
                "username": get_val(["username", "username", "user"]),
                "text": get_val(["text", "activity"]),
                "likes": get_val(["likes"]) or 0,
                "comments": get_val(["comments"]) or 0,
                "reposts": get_val(["reposts"]) or 0,
                "post_time": p_time or "Unknown",
                "photo_url": p_url or "",
                "timestamp": get_val(["scrapedtime", "timestamp"]) or "Recently",
                "is_repost": str(get_val(["isrepost"])).upper() == "TRUE",
                "reposter_name": get_val(["repostername"]) or "",
                "reposter_photo": get_val(["reposterphoto"]) or "",
                "original_author_name": get_val(["originalauthor"]) or ""
            })
            
        # Reverse the list to get most recently appended entries first
        normalized_entries.reverse()
        return normalized_entries
    except Exception as e:
        print(f"Error fetching from Google Sheets: {e}")
        return []


def get_profile_urls(sheet_name="Profiles"):
    """Fetch LinkedIn profile URLs from the 'Profiles' worksheet."""
    try:
        # Open the spreadsheet and the specific worksheet
        spreadsheet = client.open("LinkedIn_Profile_DataScraper")
        profile_sheet = spreadsheet.worksheet(sheet_name)
        
        # Get all values from the first column (col 1)
        # Using col_values is efficient for getting a single column
        all_urls = profile_sheet.col_values(1)
        
        # Filter out header (if any) and empty values
        # We assume the first row might be 'Profile URL' or similar if it's the only value
        # but the user said "just we need to fetch the profile links now from google sheets"
        # I'll keep everything that looks like a LinkedIn URL
        clean_urls = []
        for url in all_urls:
            url = url.strip()
            if not url:
                continue
            if "linkedin.com/in/" in url.lower():
                clean_urls.append(url)
                
        return clean_urls
    except Exception as e:
        print(f"Error fetching profile URLs from Google Sheet '{sheet_name}': {e}")
        return []

def get_profile_email_map(sheet_name="Profiles"):
    """Fetch mapping of LinkedIn URLs to Email IDs from the Google Sheet."""
    try:
        spreadsheet = client.open("LinkedIn_Profile_DataScraper")
        try:
            profile_sheet = spreadsheet.worksheet(sheet_name)
        except:
            profile_sheet = spreadsheet.sheet1
            
        all_rows = profile_sheet.get_all_values()
        if not all_rows: return {}
        
        headers = [h.strip().lower() for h in all_rows[0]]
        url_idx = -1
        email_idx = -1
        
        for i, h in enumerate(headers):
            if "url" in h: url_idx = i
            if "email" in h: email_idx = i
            
        if url_idx == -1: return {}
        
        email_map = {}
        for row in all_rows[1:]: # Skip header
            if len(row) > url_idx:
                url = row[url_idx].strip()
                if not url: continue
                
                # Normalize the URL for matching
                clean_url = normalize_url(url)
                
                email = ""
                if email_idx != -1 and len(row) > email_idx:
                    email = row[email_idx].strip()
                
                email_map[clean_url] = email
        return email_map
    except Exception as e:
        print(f"Error fetching email map from sheet: {e}")
        return {}
>>>>>>> b9e809e (Fixed Tracker)
