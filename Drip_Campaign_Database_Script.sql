BEGIN;

-- =====================================================
-- LEADS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS leads (
    id SERIAL PRIMARY KEY
);

-- Add missing columns
ALTER TABLE leads ADD COLUMN IF NOT EXISTS name VARCHAR;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS email VARCHAR;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS linkedin_url VARCHAR;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS company VARCHAR;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS role VARCHAR;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS headline VARCHAR;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS about TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS work_description TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'active';
ALTER TABLE leads ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();

-- Unique constraint
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'unique_linkedin_url'
    ) THEN
        ALTER TABLE leads ADD CONSTRAINT unique_linkedin_url UNIQUE (linkedin_url);
    END IF;
END $$;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);

-- =====================================================
-- EMAIL SEQUENCES TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS email_sequences (
    id SERIAL PRIMARY KEY
);

ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS lead_id INTEGER;
ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS step_number INTEGER;
ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS subject VARCHAR;
ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS body TEXT;
ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS status VARCHAR;
ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS tracking_id VARCHAR;
ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS message_id VARCHAR;
ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMP;
ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS sent_at TIMESTAMP;
ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS opened_at TIMESTAMP;
ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS replied BOOLEAN DEFAULT FALSE;
ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS lead_name VARCHAR;

-- Foreign key constraint
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

-- Indexes
CREATE INDEX IF NOT EXISTS idx_email_sequences_lead_id ON email_sequences(lead_id);
CREATE INDEX IF NOT EXISTS idx_email_sequences_tracking_id ON email_sequences(tracking_id);
CREATE INDEX IF NOT EXISTS idx_email_sequences_status ON email_sequences(status);

-- =====================================================
-- EVENTS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY
);

ALTER TABLE events ADD COLUMN IF NOT EXISTS lead_id INTEGER;
ALTER TABLE events ADD COLUMN IF NOT EXISTS event_type VARCHAR;
ALTER TABLE events ADD COLUMN IF NOT EXISTS timestamp TIMESTAMP DEFAULT NOW();
ALTER TABLE events ADD COLUMN IF NOT EXISTS metadata JSONB;

-- Foreign key constraint
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_events_lead'
    ) THEN
        ALTER TABLE events
        ADD CONSTRAINT fk_events_lead
        FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_events_lead_id ON events(lead_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);

COMMIT;

SELECT * FROM LEADS
SELECT * FROM EVENTS

SELECT * FROM EMAIL_SEQUENCES



TRUNCATE TABLE LEADS RESTART IDENTITY CASCADE

TRUNCATE TABLE EVENTS RESTART IDENTITY
TRUNCATE TABLE EMAIL_SEQUENCES RESTART IDENTITY

ALTER TABLE email_sequences 
ADD COLUMN IF NOT EXISTS open_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS click_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS replied BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS last_opened TIMESTAMP,
ADD COLUMN IF NOT EXISTS last_clicked TIMESTAMP,
ADD COLUMN IF NOT EXISTS last_replied TIMESTAMP;


ALTER TABLE email_sequences
ADD CONSTRAINT unique_tracking_id UNIQUE (tracking_id);


CREATE INDEX IF NOT EXISTS idx_es_tracking_id ON email_sequences(tracking_id);
CREATE INDEX IF NOT EXISTS idx_es_opened ON email_sequences(last_opened);
CREATE INDEX IF NOT EXISTS idx_es_clicked ON email_sequences(last_clicked);
CREATE INDEX IF NOT EXISTS idx_es_replied ON email_sequences(replied);

UPDATE email_sequences
SET open_count = COALESCE(open_count, 0),
    click_count = COALESCE(click_count, 0),
    replied = COALESCE(replied, FALSE);

ALTER TABLE email_sequences
ALTER COLUMN open_count SET DEFAULT 0,
ALTER COLUMN click_count SET DEFAULT 0,
ALTER COLUMN replied SET DEFAULT FALSE;
