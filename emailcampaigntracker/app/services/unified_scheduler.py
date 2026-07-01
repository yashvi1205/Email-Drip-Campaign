import os
import sys
import time
import logging
from datetime import datetime

# Load environment variables before any other imports
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

load_env_at_startup(ENV_PATH)

from app.services.scrape_orchestrator import process_pending_qualifications
from app.services.qualify_scheduler import process_qualify_approvals
from app.services.email_draft_service import process_pending_email_drafts
from app.services.email_send_service import process_email_approvals_and_sends

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("unified_scheduler")

def main():
    print("==================================================")
    print("Unified Sales Automation Pipeline Daemon Started")
    print("==================================================")
    print("This background service automatically polls and processes:")
    print("  1. Scraper & Qualifications (Include in Qualify Batch = Yes)")
    print("  2. approved LinkedIn Profiles Queue & Selenium Scraper")
    print("  3. Gemini 5-Email sequence drafts & revisions")
    print("  4. Gmail Send Deliveries & Follow-ups")
    print("Press Ctrl+C to terminate the daemon.")
    print("==================================================")
    
    interval_seconds = 60 # Check every 60 seconds
    print("Daemon polling loop is currently COMMENTED OUT (using n8n workflows instead).")
    
    # while True:
    #     try:
    #         now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #         print(f"\n--- [Cycle Start] {now_str} ---")
    #         
    #         # Step 1: Scrape & Qualify new target websites
    #         try:
    #             process_pending_qualifications()
    #         except Exception as e:
    #             logger.error(f"Error in process_pending_qualifications: {e}")
    #             
    #         # Step 2: process human approved qualify rows (trigger LinkedIn Scraper)
    #         try:
    #             process_qualify_approvals()
    #         except Exception as e:
    #             logger.error(f"Error in process_qualify_approvals: {e}")
    #             
    #         # Step 3: Generate 5-email sequence drafts or revisions
    #         try:
    #             process_pending_email_drafts()
    #         except Exception as e:
    #             logger.error(f"Error in process_pending_email_drafts: {e}")
    #             
    #         # Step 4: Deliver approved initial emails & follow-ups
    #         try:
    #             process_email_approvals_and_sends()
    #         except Exception as e:
    #             logger.error(f"Error in process_email_approvals_and_sends: {e}")
    #             
    #         print(f"--- [Cycle End] Sleeping for {interval_seconds}s ---")
    #         time.sleep(interval_seconds)
    #         
    #     except KeyboardInterrupt:
    #         print("\nShutting down Unified Sales Automation Pipeline Daemon.")
    #         break
    #     except Exception as e:
    #         logger.error(f"Unexpected error in daemon main loop: {e}")
    #         time.sleep(10)

if __name__ == "__main__":
    main()
