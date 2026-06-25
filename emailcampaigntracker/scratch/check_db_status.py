import dotenv
dotenv.load_dotenv()
from database.db import SessionLocal
from database.models import Lead, EmailSequence, Event

db = SessionLocal()
print("=== LEADS ===")
for l in db.query(Lead).all():
    print(f"ID: {l.id}, Name: {l.name}, Status: {l.status}, Email: {l.email}")

print("\n=== SEQUENCES ===")
for seq in db.query(EmailSequence).all():
    print(f"ID: {seq.id}, Lead ID: {seq.lead_id}, Tracking ID: {seq.tracking_id}, Status: {seq.status}, Sent At: {seq.sent_at}, Open Count: {seq.open_count}, Click Count: {seq.click_count}")

print("\n=== EVENTS ===")
from database.models import Event
for ev in db.query(Event).order_by(Event.timestamp.desc()).limit(15):
    print(f"Time: {ev.timestamp}, Lead ID: {ev.lead_id}, Event: {ev.event_type}, Data: {ev.additional_data}")

print("\n=== SCRAPER JOBS ===")
from database.models import ScraperJob
for job in db.query(ScraperJob).order_by(ScraperJob.created_at.desc()).limit(10):
    print(f"ID: {job.id}, Status: {job.status}, Created At: {job.created_at}, Started At: {job.started_at}, Finished At: {job.finished_at}, Error: {job.last_error}")
