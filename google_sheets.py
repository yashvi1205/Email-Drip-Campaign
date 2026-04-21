import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os


# Define the scope
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Use absolute path for credentials
base_path = os.path.dirname(os.path.abspath(__file__))
creds_path = os.path.join(base_path, "credentials.json")

# Modern authentication using google-auth
creds = Credentials.from_service_account_file(creds_path, scopes=scope)
client = gspread.authorize(creds)

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