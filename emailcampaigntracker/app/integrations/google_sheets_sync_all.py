import logging
from database.db import SessionLocal
from database.models import Lead, EmailSequence
from app.integrations.google_sheets import sync_leads_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("force_sync")

def force_sync():
    logger.info("Starting Force Sync from DB to Google Sheets...")
    db = SessionLocal()
    try:
        leads = db.query(Lead).all()
        sync_data_list = []
        
        for lead in leads:
            # Get latest sequence for this lead to get open counts, etc.
            seq = db.query(EmailSequence).filter(EmailSequence.lead_id == lead.id).order_by(EmailSequence.id.desc()).first()
            
            data = {
                "linkedin_url": lead.linkedin_url,
                "email": lead.email,
                "status": lead.status,
                "open_count": seq.open_count if seq else 0,
                "last_opened": seq.last_opened if seq else None,
                "click_count": seq.click_count if seq else 0,
                "last_clicked": seq.last_clicked if seq else None,
                "replied": seq.replied if seq else False,
                "last_replied": seq.last_replied if seq else None,
            }
            sync_data_list.append(data)
            
        if sync_data_list:
            logger.info(f"Syncing {len(sync_data_list)} leads to Sheet...")
            success = sync_leads_status(sync_data_list)
            if success:
                logger.info("[SUCCESS] Sheet is now fully synced with DB!")
            else:
                logger.error("[ERROR] Sheet sync failed. Check your Google credentials.")
        else:
            logger.info("No leads found in DB to sync.")
            
    finally:
        db.close()

if __name__ == "__main__":
    force_sync()
