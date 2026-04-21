from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import subprocess
import sys

# Add project root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from google_sheets import get_last_entries, get_latest_post_for_profile, get_profile_urls, get_enhanced_profile_data
from database.db import SessionLocal
from database.models import Lead, Event, EmailSequence


from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="LinkedIn Scraper API")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROFILES_FILE = os.path.join(os.path.dirname(__file__), "..", "profiles.txt")
LAST_POSTS_FILE = os.path.join(os.path.dirname(__file__), "..", "last_posts.json")
SCRAPER_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scraper", "scrape_automation.py")
SCRAPER_STATUS_FILE = os.path.join(os.path.dirname(__file__), "..", "scraper_status.json")

def read_profiles():
    # Try fetching from Google Sheets first
    try:
        profiles = get_profile_urls("Profiles")
        if profiles:
            return profiles
    except Exception as e:
        print(f"Error fetching profiles from Google Sheets in API: {e}")

    # Fallback to local profiles.txt
    if not os.path.exists(PROFILES_FILE):
        return []
    with open(PROFILES_FILE, "r") as f:
        return [line.strip() for line in f.readlines() if line.strip()]


def load_last_posts():
    if not os.path.exists(LAST_POSTS_FILE):
        return {}
    with open(LAST_POSTS_FILE, "r") as f:
        return json.load(f)

def save_last_posts(data):
    with open(LAST_POSTS_FILE, "w") as f:
        json.dump(data, f, indent=4)

@app.get("/api/profiles")
def get_profiles():
    profiles = read_profiles()
    last_posts = load_last_posts()
    updated = False
    
    result = []
    for url in profiles:
        username = url.split("/in/")[1].split("/")[0].replace("-", " ").title() if "/in/" in url else url
        entry = last_posts.get(url)
        
        # Fallback to Google Sheets if local data is missing or incomplete
        if not entry or (isinstance(entry, str) and entry == "No activity tracked yet"):
            sheet_entry = get_latest_post_for_profile(url)
            if sheet_entry:
                entry = sheet_entry
                last_posts[url] = entry
                updated = True
            else:
                entry = "No activity tracked yet"

        if isinstance(entry, dict):
            post_text = entry.get("text", "No text found")
            photo_url = entry.get("photo_url", "")
            post_time = entry.get("post_time", "")
            is_repost = entry.get("is_repost", False)
            reposter_name = entry.get("reposter_name", "")
            reposter_photo = entry.get("reposter_photo", "")
            original_author_name = entry.get("original_author_name", "")
            recent_posts = entry.get("recent_posts", [])
            stats = {
                "likes": entry.get("likes", 0),
                "comments": entry.get("comments", 0),
                "reposts": entry.get("reposts", 0)
            }
        else:
            post_text = entry
            photo_url = ""
            post_time = ""
            is_repost = False
            reposter_name = ""
            reposter_photo = ""
            original_author_name = ""
            recent_posts = []
            stats = {"likes": 0, "comments": 0, "reposts": 0}

        # FINAL DATA DREDGE (Bridge to Enriched Data)
        headline = entry.get("headline", "") if isinstance(entry, dict) else ""
        about = entry.get("about", "") if isinstance(entry, dict) else ""
        work_description = entry.get("work_description", "") if isinstance(entry, dict) else ""
        company = entry.get("company", "") if isinstance(entry, dict) else ""
        role = entry.get("role", "") if isinstance(entry, dict) else ""
        email = entry.get("email", "") if isinstance(entry, dict) else ""

        # SHEET FALLBACK: If core fields are missing, dredge from Enhanced Sheet
        if not about or not role:
            enhanced = get_enhanced_profile_data(url)
            if enhanced:
                role = role or enhanced.get("role")
                company = company or enhanced.get("company")
                headline = headline or enhanced.get("headline")
                about = about or enhanced.get("about")
                work_description = work_description or enhanced.get("work_description")
                email = email or enhanced.get("email")

        # Check database for lead info first
        db = SessionLocal()
        lead = db.query(Lead).filter(Lead.linkedin_url == url).first()
        db.close()

        # Internal fields for UI matching
        p_data = {
            "url": url,
            "name": lead.name if lead else username,
            "headline": headline,
            "company": company,
            "role": role,
            "about": about,
            "work_description": work_description,
            "recent_activity": [],
            "is_repost": is_repost,
            "reposter_name": reposter_name,
            "reposter_photo": reposter_photo,
            "original_author_name": original_author_name,
            "photo_url": photo_url,
            "post_time": post_time,
            "stats": stats
        }

        # Fetch latest interaction summary for recent_activity
        db = SessionLocal()
        latest_event = db.query(Event).filter(
            Event.lead_id == (lead.id if lead else None),
            Event.event_type == "interaction_summary"
        ).order_by(Event.timestamp.desc()).first()
        
        if latest_event and "recent_activity" in latest_event.additional_data:
            p_data["recent_activity"] = latest_event.additional_data["recent_activity"]
        elif post_text and post_text != "No activity tracked yet":
            p_data["recent_activity"] = [post_text]
        
        result.append(p_data)
        db.close()
    
    from datetime import datetime, timedelta
    
    def parse_relative_time(rt):
        if not rt or not isinstance(rt, str): return 9999999
        rt = rt.lower().split('•')[0].strip()
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

    def get_estimated_post_date(p):
        ts_str = p.get("timestamp", "")
        rt = p.get("post_time", "")
        if not ts_str: return datetime(1970, 1, 1)
        try:
            base_time = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            rel_sec = parse_relative_time(rt)
            return base_time - timedelta(seconds=rel_sec)
        except:
            return datetime(1970, 1, 1)

    # Sorting logic: move profiles with the latest posts to the top
    for p in result:
        url = p["url"]
        entry = last_posts.get(url)
        if isinstance(entry, dict):
            p["timestamp"] = entry.get("timestamp", "")
        else:
            p["timestamp"] = ""
            
        p["full_name"] = p["name"]
        db = SessionLocal()
        lead = db.query(Lead).filter(Lead.linkedin_url == p["url"]).first()
        if lead:
            p["name"] = lead.name or p["name"]
            p["email"] = lead.email or p.get("email")
            p["company"] = lead.company or p.get("company")
            p["role"] = lead.role or p.get("role")
            p["headline"] = lead.headline or p.get("headline")
            p["about"] = lead.about or p.get("about")
            p["work_description"] = lead.work_description or p.get("work_description")
            p["status"] = lead.status
        db.close()

    result.sort(key=get_estimated_post_date, reverse=True)

    if updated:
        save_last_posts(last_posts)
        
    # User-requested "Clean" Format
    clean_result = []
    for p in result:
        clean_result.append({
            "name": p.get("name"),
            "headline": p.get("headline"),
            "company": p.get("company"),
            "role": p.get("role"),
            "about": p.get("about"),
            "work_description": p.get("work_description"),
            "recent_activity": p.get("recent_activity")
        })
    return clean_result

@app.get("/api/profiles/raw")
def get_profiles_raw():
    # This endpoint provides the full data needed for the premium UI
    profiles = read_profiles()
    last_posts = load_last_posts()
    updated = False
    
    result = []
    for url in profiles:
        username = url.split("/in/")[1].split("/")[0].replace("-", " ").title() if "/in/" in url else url
        entry = last_posts.get(url)
        
        if isinstance(entry, dict):
            post_text = entry.get("text", "No text found")
            photo_url = entry.get("photo_url", "")
            post_time = entry.get("post_time", "")
            is_repost = entry.get("is_repost", False)
            reposter_name = entry.get("reposter_name", "")
            reposter_photo = entry.get("reposter_photo", "")
            original_author_name = entry.get("original_author_name", "")
            recent_posts = entry.get("recent_posts", [])
            stats = {
                "likes": entry.get("likes", 0),
                "comments": entry.get("comments", 0),
                "reposts": entry.get("reposts", 0)
            }
        else:
            post_text = entry
            photo_url = ""
            post_time = ""
            is_repost = False
            reposter_name = ""
            reposter_photo = ""
            original_author_name = ""
            recent_posts = []
            stats = {"likes": 0, "comments": 0, "reposts": 0}

        headline = entry.get("headline", "") if isinstance(entry, dict) else ""
        about = entry.get("about", "") if isinstance(entry, dict) else ""
        work_description = entry.get("work_description", "") if isinstance(entry, dict) else ""
        company = entry.get("company", "") if isinstance(entry, dict) else ""
        role = entry.get("role", "") if isinstance(entry, dict) else ""
        email = entry.get("email", "") if isinstance(entry, dict) else ""

        db = SessionLocal()
        lead = db.query(Lead).filter(Lead.linkedin_url == url).first()
        db.close()

        p_data = {
            "url": url,
            "name": lead.name if lead else username,
            "headline": headline or (lead.headline if lead else ""),
            "company": company or (lead.company if lead else ""),
            "role": role or (lead.role if lead else ""),
            "about": about or (lead.about if lead else ""),
            "work_description": work_description or (lead.work_description if lead else ""),
            "recent_activity": [],
            "is_repost": is_repost,
            "reposter_name": reposter_name,
            "reposter_photo": reposter_photo,
            "original_author_name": original_author_name,
            "photo_url": photo_url,
            "post_time": post_time,
            "stats": stats,
            "email": email or (lead.email if lead else ""),
            "status": lead.status if lead else "active"
        }

        db = SessionLocal()
        latest_event = db.query(Event).filter(
            Event.lead_id == (lead.id if lead else None),
            Event.event_type == "interaction_summary"
        ).order_by(Event.timestamp.desc()).first()
        
        if latest_event and "recent_activity" in latest_event.additional_data:
            p_data["recent_activity"] = latest_event.additional_data["recent_activity"]
        elif post_text and post_text != "No activity tracked yet":
            p_data["recent_activity"] = [post_text]
        
        result.append(p_data)
        db.close()
    
    return result

@app.get("/api/leads")
def get_leads():
    db = SessionLocal()
    leads = db.query(Lead).all()
    result = []
    for lead in leads:
        result.append({
            "id": lead.id,
            "name": lead.name,
            "email": lead.email,
            "linkedin_url": lead.linkedin_url,
            "company": lead.company,
            "role": lead.role,
            "headline": lead.headline,
            "about": lead.about,
            "work_description": lead.work_description,
            "status": lead.status,
            "created_at": lead.created_at
        })
    db.close()
    return result

@app.get("/api/leads/{lead_id}/events")
def get_lead_events(lead_id: int):
    db = SessionLocal()
    events = db.query(Event).filter(Event.lead_id == lead_id).order_by(Event.timestamp.desc()).all()
    result = []
    for event in events:
        result.append({
            "id": event.id,
            "type": event.event_type,
            "timestamp": event.timestamp,
            "metadata": event.additional_data
        })
    db.close()
    return result

@app.get("/api/activity")
def get_activity():
    return load_last_posts()

@app.get("/api/feed")
def get_feed():
    # Fetch last 50 entries from Google Sheets to build a comprehensive feed
    entries = get_last_entries(50)
    return {"entries": entries}

@app.get("/api/sheets-status")
def get_sheets_status():
    entries = get_last_entries(10)
    print(f"DEBUG: Fetched {len(entries)} entries from Sheet.")
    return {"entries": entries, "count": len(entries)}

@app.get("/api/scraper-status")
def get_scraper_status():
    if not os.path.exists(SCRAPER_STATUS_FILE):
        return {"status": "idle", "new_posts_found": 0}
    try:
        with open(SCRAPER_STATUS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/scrape")
def trigger_scrape():
    try:
        # Run scraper in the background
        subprocess.Popen([sys.executable, SCRAPER_SCRIPT])
        return {"status": "Scraper started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
