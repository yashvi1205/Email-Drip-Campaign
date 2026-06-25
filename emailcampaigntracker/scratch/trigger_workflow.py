import os
import sys
from dotenv import load_dotenv

# Add parent directory to path so we can import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()

import requests
from database.db import SessionLocal
from database.models import Lead, Event

def main():
    db = SessionLocal()
    try:
        leads = db.query(Lead).all()
        if not leads:
            print("No leads found in the database. Please run the scraper first.")
            return

        payload_data = []
        for lead in leads:
            # Try to get the latest interaction_summary event to fetch interaction_type and content
            latest_event = (
                db.query(Event)
                .filter(Event.lead_id == lead.id, Event.event_type == "interaction_summary")
                .order_by(Event.timestamp.desc())
                .first()
            )
            
            latest_content = ""
            interaction_type = "Like"
            if latest_event and latest_event.additional_data:
                latest_content = latest_event.additional_data.get("latest_text", "")
                # Reconstruct interaction_type from first word of recent_activity if present
                recent = latest_event.additional_data.get("recent_activity", [])
                if recent:
                    first_act = recent[0]
                    if first_act.startswith("Posted:"):
                        interaction_type = "Post"
                    elif first_act.startswith("Commented:"):
                        interaction_type = "Comment"
                    else:
                        interaction_type = "Like"

            profile_data = {
                "name": lead.name,
                "headline": lead.headline,
                "company": lead.company,
                "role": lead.role,
                "about": lead.about,
                "work_description": lead.work_description,
                "email": lead.email, # This might be 'Premium Restricted', the workflow will look it up in the Google Sheet
                "url": lead.linkedin_url,
                "is_new_lead": True,
                "interaction_type": interaction_type,
                "latest_content": latest_content
            }
            payload_data.append(profile_data)
            print(f"Adding lead: {lead.name} ({lead.linkedin_url})")

        webhook_url = "http://localhost:8000/webhook/scraper-callback"
        print(f"\nTriggering webhook at {webhook_url} with {len(payload_data)} profiles...")
        response = requests.post(webhook_url, json={"data": payload_data}, timeout=30)
        
        if response.status_code == 200:
            print("Webhook triggered successfully! Workflow 1+2 is now running in the background.")
            print("Response:", response.json())
        else:
            print(f"Failed to trigger webhook. Status code: {response.status_code}")
            print("Response:", response.text)

    finally:
        db.close()

if __name__ == "__main__":
    main()
