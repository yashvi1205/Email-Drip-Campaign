from .db import SessionLocal
from .models import Lead, Event, EmailSequence
from datetime import datetime
import json

def save_lead(linkedin_url, name=None, email=None, company=None, role=None, headline=None, about=None, work_description=None, status="active"):
    db = SessionLocal()
    lead = db.query(Lead).filter(Lead.linkedin_url == linkedin_url).first()
    if not lead:
        lead = Lead(
            linkedin_url=linkedin_url,
            name=name,
            email=email,
            company=company,
            role=role,
            headline=headline,
            about=about,
            work_description=work_description,
            status=status,
            created_at=datetime.utcnow()
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
    else:
        # Update existing lead info if provided
        if name: lead.name = name
        if email: lead.email = email
        if company: lead.company = company
        if role: lead.role = role
        if headline: lead.headline = headline
        if about: lead.about = about
        if work_description: lead.work_description = work_description
        db.commit()
    
    lead_id = lead.id
    db.close()
    return lead_id

def save_event(lead_id, event_type, additional_data=None):
    db = SessionLocal()
    event = Event(
        lead_id=lead_id,
        event_type=event_type,
        timestamp=datetime.utcnow(),
        additional_data=additional_data or {}
    )
    db.add(event)
    db.commit()
    db.close()

def get_or_create_sequence(lead_id, step_number=1):
    db = SessionLocal()
    seq = db.query(EmailSequence).filter(
        EmailSequence.lead_id == lead_id, 
        EmailSequence.step_number == step_number
    ).first()
    
    if not seq:
        seq = EmailSequence(
            lead_id=lead_id,
            step_number=step_number,
            status="pending"
        )
        db.add(seq)
        db.commit()
        db.refresh(seq)
    
    seq_id = seq.id
    db.close()
    return seq_id