import sys
import os
# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
from google_sheets import sync_leads_status
import logging
from app.core.settings import get_settings

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("force_sync_to_sheet")

DATABASE_URL = get_settings().database_url

def force_sync():
    logger.info("Starting Force Sync from Database to Google Sheets...")
    
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        cur = conn.cursor()
        
        # 1. Fetch all sequence data and lead URLs
        logger.info("Fetching data from database...")
        cur.execute("""
            SELECT 
                l.linkedin_url, 
                l.email,
                s.status as current_db_status,
                s.open_count, 
                s.last_opened, 
                s.click_count, 
                s.last_clicked, 
                s.replied, 
                s.last_replied,
                s.sent_at
            FROM email_sequences s
            JOIN leads l ON s.lead_id = l.id
        """)
        records = cur.fetchall()
        
        if not records:
            logger.info("No tracking data found in database.")
            return

        sync_payload = []
        for r in records:
            # Derive status (Latest Action Logic)
            events = [
                (r['sent_at'] or datetime.datetime.min, "SENT"),
                (r['last_opened'] or datetime.datetime.min, "OPENED"),
                (r['last_clicked'] or datetime.datetime.min, "CLICKED"),
                (r['last_replied'] or datetime.datetime.min, "REPLIED")
            ]
            events.sort(key=lambda x: x[0], reverse=True)
            derived_status = events[0][1]

            sync_payload.append({
                "linkedin_url": r['linkedin_url'],
                "email": r['email'],
                "status": derived_status,
                "open_count": r['open_count'],
                "last_opened": r['last_opened'],
                "click_count": r['click_count'],
                "last_clicked": r['last_clicked'],
                "replied": r['replied'],
                "last_replied": r['last_replied']
            })

        logger.info("Prepared %s leads for sync.", len(sync_payload))
        
        # 2. Push to Google Sheets
        if sync_leads_status(sync_payload):
            logger.info("Successfully synced all database records to Google Sheets!")
        else:
            logger.warning("Sheet sync failed. Check your Google Sheets credentials/connection.")
            
    except Exception as e:
        logger.exception("Error during sync: %s", e)
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    force_sync()
