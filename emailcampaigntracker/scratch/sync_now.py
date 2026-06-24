import dotenv, os
dotenv.load_dotenv(override=True)
from database.db import SessionLocal
from database.models import Lead
from app.integrations.google_sheets import sync_leads_status

db = SessionLocal()
leads = db.query(Lead).all()

leads_data = []
for lead in leads:
    seqs = sorted([s for s in lead.sequences], key=lambda s: s.id)
    latest_seq = seqs[-1] if seqs else None
    data = {
        'linkedin_url': lead.linkedin_url,
        'email': lead.email,
        'status': lead.status,
        'open_count': latest_seq.open_count if latest_seq else 0,
        'last_opened': latest_seq.last_opened if latest_seq else None,
        'click_count': latest_seq.click_count if latest_seq else 0,
        'last_clicked': latest_seq.last_clicked if latest_seq else None,
        'replied': latest_seq.replied if latest_seq else False,
        'last_replied': latest_seq.last_replied if latest_seq else None,
    }
    leads_data.append(data)
    print(f"Syncing to new sheet: {lead.name} ({lead.linkedin_url}) Status={lead.status}")

result = sync_leads_status(leads_data)
print(f"Sync result: {result}")
db.close()
