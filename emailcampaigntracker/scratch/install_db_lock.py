import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from database.db import SessionLocal
from sqlalchemy import text

def install_super_lock():
    db = SessionLocal()
    try:
        print("Installing the 'URL Normalization Trigger' (The Super Lock)...")
        
        # 1. Create the cleaning function in Postgres
        # This function mimics our Python normalization logic exactly
        sql_function = """
        CREATE OR REPLACE FUNCTION normalize_linkedin_url_trigger()
        RETURNS TRIGGER AS $$
        BEGIN
            -- 1. Lowercase and trim
            NEW.linkedin_url := TRIM(LOWER(NEW.linkedin_url));
            
            -- 2. Remove protocol
            NEW.linkedin_url := REGEXP_REPLACE(NEW.linkedin_url, '^https?://', '');
            
            -- 3. Remove www. and localized subdomains (nl., in., etc.)
            NEW.linkedin_url := REGEXP_REPLACE(NEW.linkedin_url, '^([a-z]{2}\.)?www\.', '');
            NEW.linkedin_url := REGEXP_REPLACE(NEW.linkedin_url, '^[a-z]{2}\.', '');
            NEW.linkedin_url := REGEXP_REPLACE(NEW.linkedin_url, '^www\.', '');
            
            -- 4. Remove trailing slash and parameters
            NEW.linkedin_url := SPLIT_PART(NEW.linkedin_url, '?', 1);
            NEW.linkedin_url := RTRIM(NEW.linkedin_url, '/');
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
        
        # 2. Create the trigger
        sql_trigger = """
        DROP TRIGGER IF EXISTS trg_normalize_linkedin_url ON leads;
        CREATE TRIGGER trg_normalize_linkedin_url
        BEFORE INSERT OR UPDATE OF linkedin_url ON leads
        FOR EACH ROW
        EXECUTE FUNCTION normalize_linkedin_url_trigger();
        """
        
        db.execute(text(sql_function))
        db.execute(text(sql_trigger))
        db.commit()
        
        print("Super Lock Installed! Your database will now auto-clean every URL it receives.")
    except Exception as e:
        print(f"Error installing Super Lock: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    install_super_lock()
