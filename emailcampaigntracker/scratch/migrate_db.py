import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "postgresql://postgres:121205@localhost:5432/drip_campaign"

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def migrate():
    print(f"Connecting to {DATABASE_URL}...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    try:
        print("Adding columns to email_sequences...")
        cur.execute("""
            ALTER TABLE email_sequences
            ADD COLUMN IF NOT EXISTS open_count INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS click_count INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS replied BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS last_opened TIMESTAMP,
            ADD COLUMN IF NOT EXISTS last_clicked TIMESTAMP,
            ADD COLUMN IF NOT EXISTS last_replied TIMESTAMP;
        """)
        
        print("Ensuring unique tracking_id...")
        cur.execute("""
            ALTER TABLE email_sequences
            ADD CONSTRAINT unique_tracking_id UNIQUE (tracking_id);
        """)
    except Exception as e:
        print(f"Migration warning/error: {e}")
        conn.rollback()
    else:
        conn.commit()
        print("Migration completed successfully.")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
