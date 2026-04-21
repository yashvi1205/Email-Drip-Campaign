from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = "postgresql://postgres:121205@localhost:5432/drip_campaign"

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)