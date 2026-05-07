import os
import json
import redis
from database.db import SessionLocal
from database.models import ScraperJob
from app.core.settings import get_settings

def reset():
    print("Starting Total Scraper Reset...")
    settings = get_settings()

    # 1. Clear Redis Lock
    try:
        r = redis.from_url(settings.redis_url)
        r.delete("scraper:run_lock")
        print("✅ Redis lock cleared.")
    except Exception as e:
        print(f"❌ Redis clear failed: {e}")

    # 2. Reset Status File
    try:
        path = "scraper_status.json"
        with open(path, "w") as f:
            json.dump({"status": "idle", "message": "Manual reset performed", "new_posts_found": 0}, f)
        print("✅ scraper_status.json reset to idle.")
    except Exception as e:
        print(f"❌ File reset failed: {e}")

    # 3. Clean up Database
    try:
        session = SessionLocal()
        stuck_jobs = session.query(ScraperJob).filter(ScraperJob.status.in_(["queued", "running", "retrying"])).all()
        for job in stuck_jobs:
            job.status = "failed"
            job.last_error = "Cleaned up by manual reset script"
        session.commit()
        session.close()
        print(f"✅ Database cleaned: {len(stuck_jobs)} stuck jobs marked as failed.")
    except Exception as e:
        print(f"❌ Database reset failed: {e}")

    print("\n🚀 System is now IDLE. You can run n8n now!")

if __name__ == "__main__":
    reset()
