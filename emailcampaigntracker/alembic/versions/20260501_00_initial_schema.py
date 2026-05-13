"""Initial schema creation - Phase 0.

Revision ID: 20260501_00
Revises: 
Create Date: 2026-05-01
"""

from alembic import op
import sqlalchemy as sa


revision = "20260501_00"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create leads table
    op.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id SERIAL PRIMARY KEY,
            name VARCHAR,
            email VARCHAR,
            linkedin_url VARCHAR,
            company VARCHAR,
            role VARCHAR,
            headline VARCHAR,
            about TEXT,
            work_description TEXT,
            status VARCHAR DEFAULT 'active',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Add unique constraint to leads
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'unique_linkedin_url'
            ) THEN
                ALTER TABLE leads ADD CONSTRAINT unique_linkedin_url UNIQUE (linkedin_url);
            END IF;
        END $$;
    """)

    # Create indexes for leads
    op.execute("CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_leads_linkedin_url ON leads(linkedin_url)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_leads_headline ON leads(headline)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at)")

    # Create email_sequences table
    op.execute("""
        CREATE TABLE IF NOT EXISTS email_sequences (
            id SERIAL PRIMARY KEY,
            lead_id INTEGER,
            step_number INTEGER,
            subject VARCHAR,
            body TEXT,
            status VARCHAR,
            tracking_id VARCHAR,
            message_id VARCHAR,
            scheduled_at TIMESTAMP,
            sent_at TIMESTAMP,
            opened_at TIMESTAMP,
            last_opened TIMESTAMP,
            last_clicked TIMESTAMP,
            last_replied TIMESTAMP,
            open_count INTEGER DEFAULT 0,
            click_count INTEGER DEFAULT 0,
            replied BOOLEAN DEFAULT FALSE,
            lead_name VARCHAR
        )
    """)

    # Add foreign key constraint
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_email_sequences_lead'
            ) THEN
                ALTER TABLE email_sequences
                ADD CONSTRAINT fk_email_sequences_lead
                FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE;
            END IF;
        END $$;
    """)

    # Create indexes for email_sequences
    op.execute("CREATE INDEX IF NOT EXISTS idx_es_lead_id ON email_sequences(lead_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_es_tracking_id ON email_sequences(tracking_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_es_status ON email_sequences(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_es_opened ON email_sequences(last_opened)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_es_clicked ON email_sequences(last_clicked)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_es_replied ON email_sequences(replied)")

    # Create events table
    op.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id SERIAL PRIMARY KEY,
            lead_id INTEGER,
            event_type VARCHAR,
            timestamp TIMESTAMP DEFAULT NOW(),
            metadata JSONB
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS events")
    op.execute("DROP TABLE IF EXISTS email_sequences")
    op.execute("DROP TABLE IF EXISTS leads")
