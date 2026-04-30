import os
import psycopg2
from dotenv import load_dotenv

# Load .env
load_dotenv()

DB_URL = os.getenv("DATABASE_URL")

print("📌 DB URL:", DB_URL)

try:
    print("🔌 Connecting to DB...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    cur.execute("SELECT 1;")
    print("✅ DB Connected:", cur.fetchone())

    # Check tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public';
    """)

    tables = cur.fetchall()
    print("📊 Tables:", [t[0] for t in tables])

    cur.close()
    conn.close()

except Exception as e:
    print("❌ DB Error:", str(e))