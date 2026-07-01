import os
import sys
import subprocess
import logging
from datetime import datetime
import openpyxl

ENV_PATH = r"c:\git\emailcampaigntracker\.env"

def load_env_at_startup(path):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                v = v.strip()
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                os.environ[k.strip()] = v

# Load environment before any other local imports execute
load_env_at_startup(ENV_PATH)

from app.services.sheet_sync_service import run_bidirectional_sync, EXCEL_PATH, load_env
from app.integrations.google_sheets import get_enhanced_profile_data, get_latest_post_for_profile

logger = logging.getLogger("qualify_scheduler")
def process_qualify_approvals():
    """Poll sheets for approved leads, queue their LinkedIn profiles, run scraper, and update Pipeline status."""
    from app.services.sheet_sync_service import get_google_client, load_env
    import gspread
    import subprocess
    
    print("--------------------------------------------------")
    print("[Scheduler] Running Qualify Approval Poller...")
    print("--------------------------------------------------")
    
    env = load_env(ENV_PATH)
    print("Connecting to Google Sheets...")
    gc = get_google_client(env)
    sheet_id = env.get("GOOGLE_SHEET_ID")
    gsheet = gc.open_by_key(sheet_id)
    g_ws = gsheet.worksheet("Pipeline")
    profiles_ws = gsheet.worksheet("Profiles")
    
    g_rows = g_ws.get_all_values()
    if not g_rows:
        return
        
    headers = [str(h).strip() for h in g_rows[0]]
    header_map = {h: idx for idx, h in enumerate(headers)}
    
    modified = False
    run_scraper_needed = False
    queued_profiles = []
    
    for r_idx, r in enumerate(g_rows[1:]):
        qualify_approval = str(r[header_map["Qualify Approval"]]).strip().lower()
        status = str(r[header_map["Automation Status"]]).strip()
        linkedin_url = r[header_map["(I) LinkedIn URL"]]
        email = r[header_map["Email"]]
        company_name = str(r[header_map["Company"]]).strip()

        # TEST MODE: only process the dummy Test Corp row
        test_mode = os.environ.get("TEST_MODE", "false").strip().lower() == "true"
        test_company = os.environ.get("TEST_COMPANY", "Test Corp").strip()
        if test_mode and company_name.lower() != test_company.lower():
            continue

        # Identify rows approved by human and pending LinkedIn scrape
        if qualify_approval == "approve" and status == "Pending Qualify Review":
            row_num = r_idx + 2
            g_updates = []
            
            if linkedin_url and "linkedin.com" in linkedin_url:
                # Add to Profiles sheet queue if not already there
                existing_profiles = [str(val).strip().lower() for val in profiles_ws.col_values(1) if val]
                if linkedin_url.strip().lower() not in existing_profiles:
                    profiles_ws.append_row([linkedin_url, email])
                    print(f"  [Queue] Queued LinkedIn Profile URL: {linkedin_url}")
                
                # Update status to LinkedIn Scrape Queued
                a1_status = gspread.utils.rowcol_to_a1(row_num, header_map["Automation Status"] + 1)
                a1_updated = gspread.utils.rowcol_to_a1(row_num, header_map["Last Updated"] + 1)
                g_ws.batch_update([
                    {"range": a1_status, "values": [["LinkedIn Scrape Queued"]]},
                    {"range": a1_updated, "values": [[datetime.now().strftime("%Y-%m-%dT%H:%M:%S")]]}
                ])
                modified = True
                run_scraper_needed = True
                queued_profiles.append((row_num, linkedin_url))
            else:
                # No LinkedIn URL found - skip to email phase directly
                print(f"  [Warning] Row {row_num}: No LinkedIn URL found for approved contact. Skipping to Email phase.")
                a1_status = gspread.utils.rowcol_to_a1(row_num, header_map["Automation Status"] + 1)
                a1_updated = gspread.utils.rowcol_to_a1(row_num, header_map["Last Updated"] + 1)
                g_ws.batch_update([
                    {"range": a1_status, "values": [["Pending Email Review"]]},
                    {"range": a1_updated, "values": [[datetime.now().strftime("%Y-%m-%dT%H:%M:%S")]]}
                ])
                modified = True

    if not modified:
        print("[Scheduler] No new approved rows found.")
        
    if run_scraper_needed:
        # Run Selenium Scraper
        print("\n[Scheduler] Launching Selenium LinkedIn Scraper...")
        p = subprocess.run(
            [sys.executable, "scraper/scrape_automation.py"],
            cwd=r"c:\git\emailcampaigntracker",
            env={**os.environ, **env}
        )
        print(f"[Scheduler] Scraper finished with code {p.returncode}.")
        
        # 3. Pull scraped results from LinkedIn_Enhanced_Data and update Pipeline sheet
        print("\n[Scheduler] Enriching Pipeline rows from scraped LinkedIn profiles...")
        modified_enrich = False
        
        for row_num, linkedin_url in queued_profiles:
            enhanced_data = get_enhanced_profile_data(linkedin_url)
            
            # Fallback to local Postgres database if sheet row is missing
            if not enhanced_data:
                try:
                    from database.db import SessionLocal
                    from database.models import Lead
                    from app.core.utils import normalize_linkedin_url
                    
                    norm_url = normalize_linkedin_url(linkedin_url)
                    db = SessionLocal()
                    lead_db = db.query(Lead).filter(Lead.linkedin_url == norm_url).first()
                    if lead_db:
                        enhanced_data = {
                            "role": lead_db.role or "",
                            "headline": lead_db.headline or "",
                            "about": lead_db.about or "",
                            "work_description": lead_db.work_description or ""
                        }
                        print(f"  [Database Fallback] Recovered profile data from local Postgres database.")
                    db.close()
                except Exception as dbe:
                    print(f"  Warning: Database lookup fallback failed ({dbe})")

            latest_post = get_latest_post_for_profile(linkedin_url)
            
            g_enrich_updates = []
            if enhanced_data:
                # Get City, Country, Notes
                role = enhanced_data.get("role", "")
                headline = enhanced_data.get("headline", "")
                about = enhanced_data.get("about", "")
                work_desc = enhanced_data.get("work_description", "")
                
                # Combine experience details as Notes
                scraped_notes = f"Role: {role}\nHeadline: {headline}\nAbout: {about}\nWork: {work_desc}"
                if latest_post:
                    scraped_notes += f"\n\nLatest LinkedIn Post: {latest_post.get('text', '')}"

                a1_notes = gspread.utils.rowcol_to_a1(row_num, header_map["(I) Notes"] + 1)
                g_enrich_updates.append({"range": a1_notes, "values": [[scraped_notes[:1000]]]})
                
                # Update status to Pending Email Review
                a1_status = gspread.utils.rowcol_to_a1(row_num, header_map["Automation Status"] + 1)
                a1_updated = gspread.utils.rowcol_to_a1(row_num, header_map["Last Updated"] + 1)
                g_enrich_updates.append({"range": a1_status, "values": [["Pending Email Review"]]})
                g_enrich_updates.append({"range": a1_updated, "values": [[datetime.now().strftime("%Y-%m-%dT%H:%M:%S")]]})
                print(f"  [Enriched] Row {row_num} successfully updated with LinkedIn profiles info.")
                modified_enrich = True
            else:
                # Scrape failed or no data - proceed to email phase anyway to not block the pipeline
                print(f"  [Warning] Row {row_num}: No enriched LinkedIn data found. Moving to Email phase.")
                a1_status = gspread.utils.rowcol_to_a1(row_num, header_map["Automation Status"] + 1)
                a1_updated = gspread.utils.rowcol_to_a1(row_num, header_map["Last Updated"] + 1)
                g_enrich_updates.append({"range": a1_status, "values": [["Pending Email Review"]]})
                g_enrich_updates.append({"range": a1_updated, "values": [[datetime.now().strftime("%Y-%m-%dT%H:%M:%S")]]})
                modified_enrich = True
                
            if g_enrich_updates:
                g_ws.batch_update(g_enrich_updates)

if __name__ == "__main__":
    process_qualify_approvals()


