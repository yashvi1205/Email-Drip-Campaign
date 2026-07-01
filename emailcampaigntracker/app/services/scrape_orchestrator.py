import os
import sys
import json
import subprocess
import logging
from datetime import datetime
import openpyxl
import requests

from app.integrations.gdocs_uploader import upload_to_gdocs, load_env
from app.services.sheet_sync_service import run_bidirectional_sync

logger = logging.getLogger("scrape_orchestrator")

EXCEL_PATH = r"c:\git\Sales_Automation_Pipeline.xlsx"
ENV_PATH = r"c:\git\emailcampaigntracker\.env"
ANALYZE_PROSPECT_SCRIPT = r"c:\git\codex-fastapi\skills-repo\ai-sales-team-claude\scripts\analyze_prospect.py"
CONTACT_FINDER_SCRIPT = r"c:\git\codex-fastapi\skills-repo\ai-sales-team-claude\scripts\contact_finder.py"

def _call_gemini(prompt: str, api_key: str, model: str) -> str:
    if not model.startswith("models/"):
        model = f"models/{model}"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    resp = requests.post(url, json=payload, timeout=90)
    resp.raise_for_status()
    data = resp.json()
    candidates = data.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        if parts:
            return parts[0].get("text", "")
    return ""

def run_scrapers(url: str):
    """Run analyze_prospect.py and contact_finder.py as subprocesses."""
    print(f"  [Scraper] Analyzing prospect website: {url}...")
    try:
        # Run analyze_prospect.py
        p1 = subprocess.run(
            [sys.executable, ANALYZE_PROSPECT_SCRIPT, "--url", url, "--output", "json"],
            capture_output=True, timeout=120
        )
        stdout_str = p1.stdout.decode("utf-8", errors="replace")
        stderr_str = p1.stderr.decode("utf-8", errors="replace")
        if p1.returncode != 0:
            print(f"    Error running analyze_prospect.py: {stderr_str}")
            company_data = {}
        else:
            company_data = json.loads(stdout_str)
    except Exception as e:
        print(f"    Exception running analyze_prospect.py: {e}")
        company_data = {}

    print(f"  [Scraper] Finding contact information: {url}...")
    try:
        # Run contact_finder.py
        p2 = subprocess.run(
            [sys.executable, CONTACT_FINDER_SCRIPT, "--url", url, "--output", "json"],
            capture_output=True, timeout=120
        )
        stdout_str = p2.stdout.decode("utf-8", errors="replace")
        stderr_str = p2.stderr.decode("utf-8", errors="replace")
        if p2.returncode != 0:
            print(f"    Error running contact_finder.py: {stderr_str}")
            contact_data = {}
        else:
            contact_data = json.loads(stdout_str)
    except Exception as e:
        print(f"    Exception running contact_finder.py: {e}")
        contact_data = {}

    return company_data, contact_data

def convert_md_to_html(md_text: str) -> str:
    """Basic helper to wrap Markdown text into clean HTML tags for Google Docs upload."""
    lines = md_text.splitlines()
    html_lines = []
    in_table = False
    table_headers = []
    
    html_lines.append("<html><body style='font-family: Arial, sans-serif; line-height: 1.5;'>")
    
    for line in lines:
        line_strip = line.strip()
        
        # Table detection
        if line_strip.startswith("|") and line_strip.endswith("|"):
            if "---" in line_strip:
                continue # Skip divider row
            parts = [p.strip() for p in line_strip.split("|")[1:-1]]
            if not in_table:
                in_table = True
                html_lines.append("<table border='1' cellpadding='5' style='border-collapse: collapse; margin: 10px 0;'>")
                html_lines.append("<tr>" + "".join(f"<th>{p}</th>" for p in parts) + "</tr>")
            else:
                html_lines.append("<tr>" + "".join(f"<td>{p}</td>" for p in parts) + "</tr>")
            continue
        elif in_table:
            html_lines.append("</table>")
            in_table = False

        if line_strip.startswith("###"):
            html_lines.append(f"<h3 style='color: #1B2A4A; margin-top: 15px;'>{line_strip[3:].strip()}</h3>")
        elif line_strip.startswith("##"):
            html_lines.append(f"<h2 style='color: #1B2A4A; border-bottom: 1px solid #CBD5E1; padding-bottom: 5px; margin-top: 20px;'>{line_strip[2:].strip()}</h2>")
        elif line_strip.startswith("#"):
            html_lines.append(f"<h1 style='color: #1B2A4A; border-bottom: 2px solid #1B2A4A; padding-bottom: 10px;'>{line_strip[1:].strip()}</h1>")
        elif line_strip.startswith("*") or line_strip.startswith("-"):
            html_lines.append(f"<li>{line_strip[1:].strip()}</li>")
        elif line_strip:
            # Bold formatting inside paragraph
            line_html = line_strip
            bold_matches = re.findall(r"\*\*(.*?)\*\*", line_html)
            for bm in bold_matches:
                line_html = line_html.replace(f"**{bm}**", f"<b>{bm}</b>")
            html_lines.append(f"<p>{line_html}</p>")
        else:
            html_lines.append("<br/>")
            
    if in_table:
        html_lines.append("</table>")
        
    html_lines.append("</body></html>")
    return "\n".join(html_lines)

import re

def process_pending_qualifications():
    """Reads Pipeline sheet, scrapes pending websites, generates Google Doc research, and syncs sheets."""
    from app.services.sheet_sync_service import get_google_client, load_env
    import gspread
    
    env = load_env(ENV_PATH)
    gemini_key = env.get("GEMINI_API_KEY")
    gemini_model = env.get("GEMINI_MODEL", "gemini-flash-lite-latest")
    
    if not gemini_key:
        print("Error: GEMINI_API_KEY not configured in .env file.")
        return

    print("Connecting to Google Sheets...")
    gc = get_google_client(env)
    sheet_id = env.get("GOOGLE_SHEET_ID")
    gsheet = gc.open_by_key(sheet_id)
    g_ws = gsheet.worksheet("Pipeline")
    
    g_rows = g_ws.get_all_values()
    if not g_rows:
        return
    headers = [str(h).strip() for h in g_rows[0]]
    header_map = {h: idx for idx, h in enumerate(headers)}

    modified = False

    for r_idx, r in enumerate(g_rows[1:]):
        include_val = str(r[header_map["Include in Qualify Batch"]]).strip().lower()
        doc_link_val = r[header_map["Qualify Doc Link"]]
        website_val = str(r[header_map["Website"]]).strip()
        company_name = str(r[header_map["Company"]]).strip()

        # TEST MODE: only process the dummy Test Corp row
        test_mode = env.get("TEST_MODE", "false").strip().lower() == "true"
        test_company = env.get("TEST_COMPANY", "Test Corp").strip()
        if test_mode and company_name.lower() != test_company.lower():
            continue

        # Run if user selected Include in Qualify Batch = Yes AND Qualify Doc Link is empty
        if include_val == "yes" and not doc_link_val and website_val and website_val.lower() != "none":
            row_num = r_idx + 2
            print(f"\n==================================================")
            print(f"--> Processing Row {row_num}: {company_name} ({website_val})")
            print(f"==================================================")

            # 1. Run CLI Scrapers
            company_data, contact_data = run_scrapers(website_val)

            # Extract basic details from scraper to auto-populate columns
            social_links = company_data.get("social_links", {})
            company_linkedin = ""
            if "linkedin" in social_links:
                company_linkedin = social_links["linkedin"][0] if isinstance(social_links["linkedin"], list) else social_links["linkedin"]
            
            # Find primary contact (CEO / Founder / CTO)
            contacts = contact_data.get("contacts", [])
            primary_contact = {}
            for c in contacts:
                role_lower = c.get("role", "").lower()
                if "ceo" in role_lower or "founder" in role_lower or "president" in role_lower:
                    primary_contact = c
                    break
            if not primary_contact and contacts:
                primary_contact = contacts[0]

            contact_name = primary_contact.get("name", "")
            first_name = contact_name.split()[0] if contact_name else ""
            last_name = " ".join(contact_name.split()[1:]) if contact_name and len(contact_name.split()) > 1 else ""
            contact_title = primary_contact.get("role", "")
            contact_linkedin = primary_contact.get("linkedin_url", "")
            
            # Found emails / phones
            found_emails = company_data.get("contact_info", {}).get("emails", [])
            found_phones = company_data.get("contact_info", {}).get("phones", [])
            email_val = found_emails[0] if found_emails else ""
            phone_val = found_phones[0] if found_phones else ""

            # Populate scraped columns if empty
            g_updates = []
            def set_cell_if_empty(header_name, val):
                col_idx = header_map[header_name] + 1
                current_val = str(r[header_map[header_name]]).strip()
                if not current_val and val:
                    a1 = gspread.utils.rowcol_to_a1(row_num, col_idx)
                    g_updates.append({"range": a1, "values": [[val]]})
                    print(f"  Populated empty '{header_name}' -> '{val}'")

            set_cell_if_empty("(I) LinkedIn URL", contact_linkedin)
            set_cell_if_empty("(C) LinkedIn", company_linkedin)
            set_cell_if_empty("(C) Phone", phone_val)
            set_cell_if_empty("(C) Email", email_val)
            set_cell_if_empty("First Name", first_name)
            set_cell_if_empty("Last Name", last_name)
            set_cell_if_empty("Title", contact_title)
            
            # Store all POC names in Point of Contacts (AA)
            all_pocs = "; ".join([f"{c.get('name', '')} ({c.get('role', '')})" for c in contacts])
            set_cell_if_empty("Point of Contacts", all_pocs)

            # 2. Build BANT / MEDDIC Qualification Report using Gemini
            print("  [Orchestrator] Scoring and qualifying lead using Gemini...")
            prompt = f"""
You are a senior sales qualification assistant. Given the company details and leadership team found during web crawling, perform a full BANT and MEDDIC qualification.

= Company Data =
{json.dumps(company_data, indent=2, ensure_ascii=False)}

= Leadership & Contact Data =
{json.dumps(contact_data, indent=2, ensure_ascii=False)}

Analyze this prospect and generate 4 specific markdown sections in your output in this exact sequence:

# Section 1: Company Research
Identify company overview, business model, size, latest news, and tech stack details.

# Section 2: Decision Makers
List named contacts, titles, seniority, department, and social URLs.

# Section 3: Lead Qualification & Score
Calculate BANT scoring:
- Budget: 0 to 25 points
- Authority: 0 to 25 points
- Need: 0 to 25 points
- Timeline: 0 to 25 points
Total score: Sum of above (0 to 100).
Define a letter grade (A >= 75, B >= 60, C >= 40, D < 40).
Assess MEDDIC fit.

# Section 4: Competitive Intelligence
Identify key competitors and positioning angles.

At the very end of your response, output a raw JSON block containing ONLY the score and grade:
```json
{{
  "score": <score>,
  "grade": "<grade>"
}}
```
"""
            try:
                raw_analysis = _call_gemini(prompt, gemini_key, gemini_model)
                
                # Parse JSON block from response
                score_match = re.search(r"```json\s*(\{.*?\})\s*```", raw_analysis, re.DOTALL)
                if score_match:
                    score_info = json.loads(score_match.group(1))
                    bant_score = int(score_info.get("score", 0))
                    lead_grade = score_info.get("grade", "D")
                else:
                    bant_score = 40
                    lead_grade = "C"
                
                # Remove the JSON code block from the markdown output
                report_md = re.sub(r"```json\s*\{.*?\}\s*```", "", raw_analysis, flags=re.DOTALL).strip()
            except Exception as e:
                print(f"    Gemini scoring failed: {e}")
                bant_score = 40
                lead_grade = "C"
                report_md = f"# Research Report: {company_name}\nFailed to generate qualification details due to Gemini API timeout."

            # 3. Upload Merged Report to Google Docs
            report_html = convert_md_to_html(report_md)
            doc_title = f"Qualify Report: {company_name}"
            doc_url = upload_to_gdocs(doc_title, report_html)

            # 4. Prepare batch updates for Google Sheet
            def add_update(header_name, val):
                col_idx = header_map[header_name] + 1
                a1 = gspread.utils.rowcol_to_a1(row_num, col_idx)
                g_updates.append({"range": a1, "values": [[val]]})

            status_val = "Pending Qualify Review" if bant_score >= 40 else "Skipped - Low Score"
            add_update("Qualify Score (0-100)", bant_score)
            add_update("Qualify Doc Link", doc_url)
            add_update("Automation Status", status_val)
            add_update("Qualify Batch ID", "QB_" + datetime.now().strftime("%Y%m%d"))
            add_update("Last Updated", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))

            if g_updates:
                print(f"  Sending qualification updates to Google Sheet row {row_num}...")
                g_ws.batch_update(g_updates)
            
            print(f"[SUCCESS] Row {row_num} qualified. Score: {bant_score}, Grade: {lead_grade}, Doc Link: {doc_url}, Status: {status_val}")
            modified = True

    if not modified:
        print("No pending qualification rows found.")


if __name__ == "__main__":
    process_pending_qualifications()
