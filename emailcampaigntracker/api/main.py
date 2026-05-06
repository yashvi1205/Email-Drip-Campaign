from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import subprocess
import sys
from datetime import datetime, timedelta




# Add project root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from google_sheets import (
    get_last_entries,
    get_latest_post_for_profile,
    get_profile_urls,
    get_enhanced_profile_data,
    sync_leads_status 
)
from database.db import SessionLocal
from database.models import Lead, Event, EmailSequence
from api.tracking import router as tracking_router
from database.db import get_db_conn



from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="LinkedIn Scraper API")
app.include_router(tracking_router, prefix="/api/tracking")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/test-db")
def test_db():
    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM leads;")
    count = cur.fetchone()["count"]

    cur.close()
    conn.close()

    return {"leads_count": count}
@app.get("/api/health")
def health_check():
    return {"status": "healthy", "version": "1.1.0", "endpoints": ["/api/dashboard/drip", "/api/profiles/raw"]}

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
            p["company"] = (
                p.get("company") if p.get("company") and p.get("company").lower() not in ["self-employed", ""] 
                else lead.company
            )
            p["role"] = (
                p.get("role") if p.get("role") and p.get("role").lower() not in ["experience", ""] 
                else lead.role
            )
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

def fetch_profiles_raw_data():
    """Helper to gather full profile data from all sources."""
    profiles = read_profiles()
    last_posts = load_last_posts()
    result = []
    
    for url in profiles:
        username = url.split("/in/")[1].split("/")[0].replace("-", " ").title() if "/in/" in url else url
        entry = last_posts.get(url)
        
        # Extract basic info from last_posts cache if it's a dict
        if isinstance(entry, dict):
            post_text = entry.get("text", "No text found")
            headline = entry.get("headline", "")
            about = entry.get("about", "")
            work_description = entry.get("work_description", "")
            company = entry.get("company", "")
            role = entry.get("role", "")
            email = entry.get("email", "")
        else:
            post_text = entry
            headline = about = work_description = company = role = email = ""

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
            "email": email or (lead.email if lead else ""),
            "status": lead.status if lead else "active",
            "recent_activity": [],
            "has_new_activity": False
        }

        db = SessionLocal()
        latest_event = db.query(Event).filter(
            Event.lead_id == (lead.id if lead else None),
            Event.event_type == "interaction_summary"
        ).order_by(Event.timestamp.desc()).first()
        
        if latest_event:
            if "recent_activity" in latest_event.additional_data:
                p_data["recent_activity"] = latest_event.additional_data["recent_activity"]
            p_data["has_new_activity"] = latest_event.additional_data.get("has_new_activity", False)
        elif post_text and post_text != "No activity tracked yet":
            p_data["recent_activity"] = [post_text]
        
        result.append(p_data)
        db.close()
    return result

@app.get("/api/profiles/raw")
def get_profiles_raw():
    return fetch_profiles_raw_data()

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

@app.get("/api/dashboard/drip")
def get_drip_dashboard():
    db = SessionLocal()
    try:
        leads = db.query(Lead).all()
        result = []
        
        for lead in leads:
            # Get latest sequence for this lead
            latest_seq = db.query(EmailSequence).filter(
                EmailSequence.lead_id == lead.id
            ).order_by(EmailSequence.id.desc()).first()
            
            # Count events
            sent_count = db.query(Event).filter(
                Event.lead_id == lead.id,
                Event.event_type == "sent"
            ).count()
            
            click_count = db.query(Event).filter(
                Event.lead_id == lead.id,
                Event.event_type == "click"
            ).count()
            
            open_count = db.query(Event).filter(
                Event.lead_id == lead.id,
                Event.event_type == "open"
            ).count()
            
            # Check for delete event
            deleted = db.query(Event).filter(
                Event.lead_id == lead.id,
                Event.event_type == "delete"
            ).first() is not None
            
            result.append({
                "lead_id": lead.id,
                "name": lead.name,
                "email": lead.email,
                "company": lead.company,
                "role": lead.role,
                "status": lead.status,
                "sequence": {
                    "step": latest_seq.step_number if latest_seq else None,
                    "status": latest_seq.status if latest_seq else "not_started",
                    "sent_at": latest_seq.sent_at if latest_seq else None,
                    "opened_at": latest_seq.last_opened if latest_seq else None,
                    "replied": latest_seq.replied if latest_seq else False,
                    "tracking_id": latest_seq.tracking_id if latest_seq else None,
                    "clicked": (latest_seq.click_count or 0) > 0 if latest_seq else False,
                    "click_count": latest_seq.click_count if latest_seq else 0,
                    "open_count": latest_seq.open_count if latest_seq else 0,
                    "sent_count": sent_count,
                    "last_replied": latest_seq.last_replied if latest_seq else None
                } if latest_seq else None
            })
        return result
    except Exception as e:
        print(f"Error in drip dashboard: {e}")
        return []
    finally:
        db.close()

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
def trigger_scrape(webhook_url: str = None, source: str = "unknown"):
    import subprocess, sys
    global SCRAPER_STATUS

    # Check if scraper is already running
    if SCRAPER_STATUS.get("status") == "running":
        now = datetime.utcnow().timestamp()
        last_update = SCRAPER_STATUS.get("timestamp", 0)
        
        # 5 min safety lock, but also ignore if triggered within last 60s
        if now - last_update < 300:
            print(f"⚠️ REJECTED: Scraper already running (Source: {source})")
            return {"status": "already running", "source": source}

    print(f"\n🚀 SCRAPER TRIGGERED BY: {source}")
    if webhook_url:
        print(f"   -> WEBHOOK TARGET: {webhook_url}")

    SCRAPER_STATUS["status"] = "running"
    SCRAPER_STATUS["message"] = f"Scraper started by {source}"
    SCRAPER_STATUS["timestamp"] = datetime.utcnow().timestamp()
    SCRAPER_STATUS["new_posts_found"] = 0

    try:
        args = [sys.executable, SCRAPER_SCRIPT]
        if webhook_url:
            args.append(f"webhook_url={webhook_url}")
        
        subprocess.Popen(args)

        # Save initial status to file
        with open(SCRAPER_STATUS_FILE, "w") as f:
            json.dump(SCRAPER_STATUS, f)

        return {
            "status": "started",
            "source": source,
            "webhook_url": webhook_url
        }

    except Exception as e:
        SCRAPER_STATUS["status"] = "error"
        SCRAPER_STATUS["error"] = str(e)
        raise HTTPException(status_code=500, detail=str(e))

SCRAPER_STATUS = {
    "status": "idle",
    "message": ""
}

@app.post("/api/update-status")
def update_status(data: dict):
    global SCRAPER_STATUS
    SCRAPER_STATUS.update(data)
    SCRAPER_STATUS["timestamp"] = datetime.utcnow().timestamp()
    
    # Persist to file
    try:
        with open(SCRAPER_STATUS_FILE, "w") as f:
            json.dump(SCRAPER_STATUS, f)
    except: pass
    
    return {"ok": True}

@app.get("/api/scrape/status")
def get_status():
    return SCRAPER_STATUS

@app.post("/api/sync-status")
def sync_status():
    db = SessionLocal()

    try:
        leads = db.query(Lead).all()

        leads_data = []

        for lead in leads:
            open_count = db.query(Event).filter(
                Event.lead_id == lead.id,
                Event.event_type == "open"
            ).count()

            leads_data.append({
                "linkedin_url": lead.linkedin_url,
                "status": lead.status,
                "open_count": open_count
            })

        print(f"🔄 Syncing {len(leads_data)} leads to Google Sheet...")

        success = sync_leads_status(leads_data)

        return {
            "success": success,
            "total_synced": len(leads_data)
        }

    except Exception as e:
        print("❌ Sync failed:", e)
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        db.close()

        
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
