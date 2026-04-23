from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

# Get database URL from environment or fallback to local
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    DATABASE_URL = "postgresql://postgres:121205@localhost:5432/drip_campaign"
else:
    # Render sometimes provides "postgres://", which SQLAlchemy 1.4+ requires "postgresql://"
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)

@contextmanager
def get_db_conn():
    """Reusable database connection helper using psycopg2."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()