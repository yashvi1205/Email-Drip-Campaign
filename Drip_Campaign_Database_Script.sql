BEGIN;

-- =====================================================
-- LEADS TABLE
-- =====================================================

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
);

-- Unique constraint
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'unique_linkedin_url'
    ) THEN
        ALTER TABLE leads ADD CONSTRAINT unique_linkedin_url UNIQUE (linkedin_url);
    END IF;
END $$;

-- Phase 3 Performance Indexes
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_linkedin_url ON leads(linkedin_url);
CREATE INDEX IF NOT EXISTS idx_leads_headline ON leads(headline);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at);

-- =====================================================
-- EMAIL SEQUENCES TABLE
-- =====================================================

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
);

-- Constraints & Foreign Keys
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_email_sequences_lead'
    ) THEN
        ALTER TABLE email_sequences
        ADD CONSTRAINT fk_email_sequences_lead
        FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'unique_tracking_id'
    ) THEN
        ALTER TABLE email_sequences ADD CONSTRAINT unique_tracking_id UNIQUE (tracking_id);
    END IF;
END $$;

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_es_lead_id ON email_sequences(lead_id);
CREATE INDEX IF NOT EXISTS idx_es_tracking_id ON email_sequences(tracking_id);
CREATE INDEX IF NOT EXISTS idx_es_status ON email_sequences(status);
CREATE INDEX IF NOT EXISTS idx_es_opened ON email_sequences(last_opened);
CREATE INDEX IF NOT EXISTS idx_es_clicked ON email_sequences(last_clicked);
CREATE INDEX IF NOT EXISTS idx_es_replied ON email_sequences(replied);

-- =====================================================
-- EVENTS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER,
    event_type VARCHAR,
    timestamp TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

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

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_events_lead_id ON events(lead_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);

-- =====================================================
-- SCRAPER JOBS TABLE (New for Phase 2 & 3)
-- =====================================================

CREATE TABLE IF NOT EXISTS scraper_jobs (
    id SERIAL PRIMARY KEY,
    status VARCHAR DEFAULT 'queued',
    source VARCHAR DEFAULT 'unknown',
    webhook_url TEXT,
    payload JSONB,
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    cancelled BOOLEAN DEFAULT FALSE,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    last_heartbeat TIMESTAMP,
    finished_at TIMESTAMP,
    last_error TEXT,
    log_excerpt TEXT,
    rq_job_id VARCHAR
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_scraper_status ON scraper_jobs(status);
CREATE INDEX IF NOT EXISTS idx_scraper_created_at ON scraper_jobs(created_at);

COMMIT;

-- Maintenance Queries (Optional)
-- TRUNCATE TABLE leads RESTART IDENTITY CASCADE;
-- TRUNCATE TABLE events RESTART IDENTITY;
-- TRUNCATE TABLE email_sequences RESTART IDENTITY;
-- TRUNCATE TABLE scraper_jobs RESTART IDENTITY;
