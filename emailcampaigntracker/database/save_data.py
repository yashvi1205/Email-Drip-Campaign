from .db import SessionLocal
from .models import Lead, Event, EmailSequence
from datetime import datetime
import json
from app.core.utils import normalize_linkedin_url

def save_lead(linkedin_url, name=None, email=None, company=None, role=None, headline=None, about=None, work_description=None, status="active"):
    db = SessionLocal()
    
    # 🛡️ MANDATORY NORMALIZATION (The Duplicate Killer)
    clean_url = normalize_linkedin_url(linkedin_url)
    
    lead = db.query(Lead).filter(Lead.linkedin_url == clean_url).first()
    if not lead:
        lead = Lead(
            linkedin_url=clean_url,
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
        # Only update email if it's a real email and not 'Contact Restricted'
        if email and email.lower() != "contact restricted" and "@" in email:
            lead.email = email
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
        # Fetch lead name for denormalization
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        lead_name = lead.name if lead else None
        
        seq = EmailSequence(
            lead_id=lead_id,
            lead_name=lead_name,
            step_number=step_number,
            status="pending"
        )
        db.add(seq)
        db.commit()
        db.refresh(seq)
    
    seq_id = seq.id
    db.close()
    return seq_id