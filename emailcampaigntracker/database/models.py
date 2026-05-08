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
    linkedin_url = Column(String, unique=True, index=True)
    company = Column(String)
    role = Column(String)
    headline = Column(String, index=True)
    about = Column(Text)
    work_description = Column(Text)
    status = Column(String, default="active", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
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
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True)
    event_type = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    additional_data = Column("metadata", JSON) # Use Column name to avoid reserved keyword conflict

    lead = relationship("Lead", back_populates="events")


class ScraperJob(Base):
    __tablename__ = "scraper_jobs"

    id = Column(Integer, primary_key=True)
    status = Column(String, default="queued", index=True)  # queued|running|succeeded|failed|cancelled|retrying
    source = Column(String, default="unknown")
    webhook_url = Column(Text, nullable=True)
    payload = Column(JSON, nullable=True)  # Store specific job parameters

    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)

    cancelled = Column(Boolean, default=False)
    version = Column(Integer, default=1, nullable=False)  # For optimistic locking

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    last_heartbeat = Column(DateTime, nullable=True)  # For zombie job detection
    finished_at = Column(DateTime, nullable=True)

    last_error = Column(Text, nullable=True)
    log_excerpt = Column(Text, nullable=True)

    rq_job_id = Column(String, nullable=True)
