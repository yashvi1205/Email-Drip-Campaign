from database.db import SessionLocal
from database.models import Lead

db = SessionLocal()
ted_leads = db.query(Lead).filter(Lead.name.ilike('%ted%')).all()

print(f"Found {len(ted_leads)} leads for Ted:")
for lead in ted_leads:
    print(f"ID: {lead.id} | Name: {lead.name} | URL: {lead.linkedin_url} | Email: {lead.email}")

db.close()
