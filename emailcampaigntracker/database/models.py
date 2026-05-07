from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, JSON
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)
    linkedin_url = Column(String, unique=True)
    company = Column(String)
    role = Column(String)
    headline = Column(String)
    about = Column(Text)
    work_description = Column(Text)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    sequences = relationship("EmailSequence", back_populates="lead")
    events = relationship("Event", back_populates="lead")

class EmailSequence(Base):
    __tablename__ = "email_sequences"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id"))
    step_number = Column(Integer)
    subject = Column(String)
    body = Column(Text)
    status = Column(String)
    tracking_id = Column(String)
    message_id = Column(String)
    scheduled_at = Column(DateTime)
    sent_at = Column(DateTime)
    opened_at = Column(DateTime)
    replied = Column(Boolean, default=False)
    open_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    last_opened = Column(DateTime)
    last_clicked = Column(DateTime)
    last_replied = Column(DateTime)
    lead_name = Column(String)  # Denormalized for easier dashboard viewing

    lead = relationship("Lead", back_populates="sequences")

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id"))
    event_type = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    additional_data = Column("metadata", JSON) # Use Column name to avoid reserved keyword conflict

    lead = relationship("Lead", back_populates="events")


class ScraperJob(Base):
    __tablename__ = "scraper_jobs"

    id = Column(Integer, primary_key=True)
    status = Column(String, default="queued")  # queued|running|succeeded|failed|cancelled
    source = Column(String, default="unknown")
    webhook_url = Column(Text, nullable=True)

    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)

    cancelled = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    last_error = Column(Text, nullable=True)
    log_excerpt = Column(Text, nullable=True)

    rq_job_id = Column(String, nullable=True)  # RQ job id (string)
