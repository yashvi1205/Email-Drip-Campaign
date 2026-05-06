import os
import psycopg2
from dotenv import load_dotenv
import logging
from api.settings import get_settings

# Load .env
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("test_db")

DB_URL = get_settings().database_url

logger.info("DB URL loaded from environment.")

try:
    logger.info("Connecting to DB...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    cur.execute("SELECT 1;")
    logger.info("DB Connected: %s", cur.fetchone())

    # Check tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public';
    """)

    tables = cur.fetchall()
    logger.info("Tables: %s", [t[0] for t in tables])

    cur.close()
    conn.close()

except Exception as e:
    logger.exception("DB Error: %s", str(e))