import os
from dotenv import load_dotenv
import psycopg2
import logging
from api.settings import get_settings

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("migrate_db")

DATABASE_URL = get_settings().database_url

def migrate():
    logger.info("Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    try:
        logger.info("Adding columns to email_sequences...")
        cur.execute("""
            ALTER TABLE email_sequences
            ADD COLUMN IF NOT EXISTS open_count INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS click_count INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS replied BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS last_opened TIMESTAMP,
            ADD COLUMN IF NOT EXISTS last_clicked TIMESTAMP,
            ADD COLUMN IF NOT EXISTS last_replied TIMESTAMP;
        """)
        
        logger.info("Ensuring unique tracking_id...")
        cur.execute("""
            ALTER TABLE email_sequences
            ADD CONSTRAINT unique_tracking_id UNIQUE (tracking_id);
        """)
    except Exception as e:
        logger.exception("Migration warning/error: %s", e)
        conn.rollback()
    else:
        conn.commit()
        logger.info("Migration completed successfully.")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
