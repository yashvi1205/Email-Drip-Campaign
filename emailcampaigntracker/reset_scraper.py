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
        print("[SUCCESS] Redis lock cleared.")
    except Exception as e:
        print(f"[ERROR] Redis clear failed: {e}")

    # 2. Reset Status File
    try:
        path = "scraper_status.json"
        with open(path, "w") as f:
            json.dump({"status": "idle", "message": "Manual reset performed", "new_posts_found": 0}, f)
        print("[SUCCESS] scraper_status.json reset to idle.")
    except Exception as e:
        print(f"[ERROR] File reset failed: {e}")

    # 3. Clean up Database
    try:
        session = SessionLocal()
        stuck_jobs = session.query(ScraperJob).filter(ScraperJob.status.in_(["queued", "running", "retrying"])).all()
        for job in stuck_jobs:
            job.status = "failed"
            job.last_error = "Cleaned up by manual reset script"
        session.commit()
        session.close()
        print(f"[SUCCESS] Database cleaned: {len(stuck_jobs)} stuck jobs marked as failed.")
    except Exception as e:
        print(f"[ERROR] Database reset failed: {e}")

    # 4. Optional: Clear Chrome Profile (Phase 3)
    if os.getenv("CLEAN_PROFILE", "false").lower() == "true":
        import shutil
        from pathlib import Path
        try:
            profile_path = Path(settings.chrome_profile_base_path) / settings.linkedin_profile_name
            if profile_path.exists():
                shutil.rmtree(profile_path)
                print(f"[SUCCESS] Chrome profile cleared: {profile_path}")
            else:
                print(f"[SKIP] Profile path does not exist: {profile_path}")
        except Exception as e:
            print(f"[ERROR] Profile clear failed: {e}")

    print("\n[READY] System is now IDLE. You can run n8n now!")

if __name__ == "__main__":
    reset()
