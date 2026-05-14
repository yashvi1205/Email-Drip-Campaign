import os
import sys
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from database.db import SessionLocal
from database.models import Lead, Event, EmailSequence
from app.core.utils import normalize_linkedin_url

def cleanup_duplicates():
    db = SessionLocal()
    try:
        all_leads = db.query(Lead).all()
        print(f"Total leads in database: {len(all_leads)}")

        url_map = {} # clean_url -> list of lead objects

        for lead in all_leads:
            clean_url = normalize_linkedin_url(lead.linkedin_url)
            if clean_url not in url_map:
                url_map[clean_url] = []
            url_map[clean_url].append(lead)

        for clean_url, leads in url_map.items():
            if len(leads) > 1:
                print(f"\nMerging duplicates for: {clean_url}")
                
                # Sort by email quality (real email first) and then by ID
                def lead_priority(l):
                    if l.email and "@" in l.email: return 0
                    if l.email and "Restricted" in l.email: return 1
                    return 2
                
                leads.sort(key=lead_priority)
                
                master = leads[0]
                to_delete = leads[1:]

                print(f"Keeping Master Lead ID: {master.id} (Email: {master.email})")

                for dup in to_delete:
                    print(f"Deleting Duplicate ID: {dup.id} (Email: {dup.email})")
                    
                    # 1. Update any events to point to the master
                    db.query(Event).filter(Event.lead_id == dup.id).update({"lead_id": master.id})
                    
                    # 2. Update any sequences to point to the master
                    # (Careful: if both have sequences, we might get unique constraint errors, 
                    # but here we just merge)
                    db.query(EmailSequence).filter(EmailSequence.lead_id == dup.id).update({"lead_id": master.id})
                    
                    # 3. Delete the duplicate lead
                    db.delete(dup)

        db.commit()
        print("\nCleanup complete! Your database is now clean.")
    except Exception as e:
        print(f"Error during cleanup: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_duplicates()
