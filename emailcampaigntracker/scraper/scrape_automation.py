import time
import os
import json
import pickle
import sys
import io
import re
from datetime import datetime
import requests
import logging


# FORCE UTF-8 FOR PRINTING
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("scraper.scrape_automation")

# Fix for module imports when running from subdirectories
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from deep_translator import GoogleTranslator

# Core Project Imports (Phase 3+)
from app.core.browser import create_driver, validate_session, check_browser_health, chrome_profile_lock
from app.core.settings import get_settings
from database.db import SessionLocal
from database.models import Event
from app.integrations.google_sheets import get_profile_urls

try:
    from database.save_data import save_lead, save_event, get_or_create_sequence
    from app.integrations.google_sheets import save_enhanced_data
except ImportError:
    def save_lead(**kwargs): return 1
    def save_event(**kwargs): pass
    def get_or_create_sequence(*args, **kwargs): pass
    def save_enhanced_data(**kwargs): pass

# Networking Configuration (Phase 0)
BACKEND_URL = os.getenv("BACKEND_INTERNAL_URL", "http://localhost:8001").rstrip("/")
API_URL = f"{BACKEND_URL}/api"

webhook_url = None

for arg in sys.argv:
    if "webhook_url=" in arg:
        webhook_url = arg.split("webhook_url=")[-1]

def update_backend_status(status, message=None, new_posts=None, error=None):
    """Sends status updates back to the FastAPI backend."""
    try:
        payload = {"status": status}
        if message: payload["message"] = message
        if new_posts is not None: payload["new_posts_found"] = new_posts
        if error: payload["error"] = str(error)
        
        api_key = os.getenv("SCRAPER_API_KEY") or os.getenv("API_KEY")
        headers = {"X-API-Key": api_key} if api_key else {}
        requests.post(f"{API_URL}/update-status", json=payload, headers=headers, timeout=5)
    except Exception as e:
        logger.warning("Backend status update failed: %s", e)

def translate_to_english(text):
    try:
        if not text or len(text.strip()) < 3:
            return text
        return GoogleTranslator(source='auto', target='en').translate(text)
    except:
        return text

def safe_translate(text):
    try:
        if not text or len(text.strip()) < 3:
            return text

        # 🔥 ALWAYS translate (no ASCII check)
        return GoogleTranslator(source='auto', target='en').translate(text)

    except Exception as e:
        logger.warning("Translation failed: %s", e)
        return text


def parse_linkedin_time(time_str):
    if not time_str: return 999
    ts = time_str.lower()
    if 'm' in ts and 'mo' not in ts: return int(ts.split('m')[0].strip())
    if 'h' in ts: return int(ts.split('h')[0].strip()) * 60
    if 'd' in ts: return int(ts.split('d')[0].strip()) * 1440
    if 'w' in ts: return int(ts.split('w')[0].strip()) * 10080
    if 'mo' in ts: return int(ts.split('mo')[0].strip()) * 43200
    if 'y' in ts: return int(ts.split('y')[0].strip()) * 525600
    return 999


def ensure_logged_in(driver):
    driver.get("https://www.linkedin.com/feed/")
    time.sleep(5)

    if "login" in driver.current_url or "checkpoint" in driver.current_url:
        logger.error("Session expired. Please login manually.")

        input("👉 Login fully, wait for feed, THEN press ENTER...")

        driver.get("https://www.linkedin.com/feed/")
        time.sleep(5)

    logger.info("Session active")


def is_valid_profile_page(driver):
    if "login" in driver.current_url:
        return False

    if "Join LinkedIn" in driver.page_source:
        return False

    return True


def safe_get(driver, url):
    driver.get(url)
    time.sleep(5)

    if "login" in driver.current_url:
        logger.warning("Session lost. Re-login required.")
        ensure_logged_in(driver)
        driver.get(url)
        time.sleep(5)

def get_post_data(element):
    try:
        text = element.text.strip()
        time_els = element.find_elements(By.CSS_SELECTOR, "span.update-components-text-view__badge-text, .update-components-actor__sub-description")
        post_time = time_els[0].text.split('•')[0].strip() if time_els else ""
        urn = element.get_attribute("data-urn") or str(hash(text))
        return {"text": text, "post_time": post_time, "urn": urn}
    except: return None

def clean_scraped_text(text):
    if not text:
        return ""

    bad_words = ["message", "connect", "follow", "more"]
    if any(b in text.lower() for b in bad_words):
        return ""

    return text.split('\n')[0].strip()
def safe_set(details, key, value):
    if not value:
        return

    value = value.strip()

    junk = [
    "", "N/A", "Sign Up", "0 Notifications",
    "LinkedIn", "Join LinkedIn"
]
    if value in junk:
        return

    if not details.get(key) or details[key] in junk:
        details[key] = value

from app.core.utils import normalize_linkedin_url as normalize_url

def extract_role_company_from_headline(headline):
    if not headline:
        return "", ""

    h = headline.strip()

    # Normalize
    h = h.replace("\n", " ").strip()

    # CASE 1: Role @ Company or Role & Company
    if "@" in h:
        parts = h.split("@")
        return parts[0].strip(), parts[1].split("|")[0].split(" at ")[0].strip()
    
    if " & " in h and " at " not in h.lower() and "@" not in h:
        parts = h.split(" & ")
        # Usually "Founder & CEO" or "Founder & Company"
        # We'll take the first part as role and everything after as company if it looks like one
        return parts[0].strip(), " ".join(parts[1:]).split("|")[0].strip()

    # CASE 2: Role at Company
    if " at " in h.lower():
        parts = h.lower().split(" at ")
        return parts[0].strip().title(), parts[1].split("|")[0].strip().title()

    # CASE 3: "Founder Company"
    words = h.split()
    if len(words) >= 2:
        role_keywords = ["founder", "ceo", "co-founder", "owner", "director"]

        if any(r in words[0].lower() for r in role_keywords):
            role = words[0]
            company = " ".join(words[1:]).split("|")[0]
            return role, company

    # CASE 4: "Founder X & Y"
    if "&" in h:
        parts = h.split("&")
        role = parts[0].split()[0]
        company = h.replace(role, "").strip()
        return role, company

    # CASE 5: looks like location → ignore
    if "," in h and len(h.split()) < 5:
        return "", ""

    return "", ""


def extract_from_experience(driver):
    try:
        main_text = driver.find_element(By.TAG_NAME, "main").text

        lines = [l.strip() for l in main_text.split("\n") if l.strip()]


        # Find first valid role line
        for i in range(len(lines)):
            if any(k in lines[i] for k in ["Founder", "CEO", "Manager", "Engineer", "Director"]):
                role = lines[i]

                if i + 1 < len(lines):
                    raw_company = lines[i + 1]

                    if "·" in raw_company:
                        company = raw_company.split("·")[0].strip()
                    elif "," in raw_company:
                        company = raw_company.split(",")[0].strip()
                    else:
                        company = raw_company.strip()

                break

        return role.strip(), company.strip()

    except Exception as e:
        logger.warning("Experience extraction failed: %s", e)
        return "", ""


def scrape_profile_details(driver, profile_url):
    logger.info("Scraping detailed info for: %s", profile_url)
    details = {
        "full_name": "", "headline": "", "role": "", "company": "",
        "about": "", "work_description": "", "email": ""
    }
    
    # 1. PASS 1: MAIN PROFILE PAGE (Identity & Headline)
    try:
        driver.get(profile_url)
        time.sleep(10)
        
        # Specific LinkedIn Name Selector
        name_selectors = [
            "h1.text-heading-xlarge",
            "//h1[contains(@class, 'text-heading-xlarge')]",
            "div.pv-text-details__left-panel h1"
        ]
        for sel in name_selectors:
            try:
                if sel.startswith("//"):
                    details["full_name"] = driver.find_element(By.XPATH, sel).text
                else:
                    details["full_name"] = driver.find_element(By.CSS_SELECTOR, sel).text
                if details["full_name"]: break
            except: pass
            
        if not details["full_name"]:
            details["full_name"] = driver.title.split("|")[0].strip()
            
        # PASS 0: LAZY-LOAD TRIGGER
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)

        # Bulletproof JavaScript Headline Extraction (3-Try Resilience)
        for attempt in range(3):
            details["headline"] = driver.execute_script(r"""
                function findHeadline() {
                    let docTitle = document.title.split('|')[0].split('-')[0].trim().toLowerCase();
                    let blacklist = ["contact info", "connections", "followers", "following"];
                    
                    function isJunk(txt) {
                        let t = txt.toLowerCase();
                        if (t.length < 10) return true;
                        if (blacklist.some(b => t.includes(b))) return true;
                        // Reject only if it's almost exactly the name
                        if (t === docTitle || (t.includes(docTitle) && t.length < docTitle.length + 5)) return true;
                        return false;
                    }

                    // Method 1: The Left Panel container (Primary)
                    let leftPanel = document.querySelector('.pv-text-details__left-panel');
                    if (leftPanel) {
                        let textEls = Array.from(leftPanel.querySelectorAll('div, span, p'));
                        let candidate = textEls.find(el => {
                            let txt = el.innerText.trim();
                            return !isJunk(txt) && !el.querySelector('h1');
                        });
                        if (candidate) return candidate.innerText.trim();
                    }
                    
                    // Method 2: Specific classes
                    let specific = document.querySelector('.text-body-medium.break-words');
                    if (specific && !isJunk(specific.innerText)) return specific.innerText.trim();
                    
                    // Method 3: Broad text search near the top
                    let topCard = document.querySelector('main');
                    if (topCard) {
                        let text = topCard.innerText.split('\n').filter(t => !isJunk(t) && t.length < 200)[0];
                        if (text) return text.trim();
                    }
                    return "";
                }
                return findHeadline();
            """)

            # FIX: take only first meaningful line
            if details["headline"]:
                details["headline"] = details["headline"].split("\n")[0].strip()
            
            if details["headline"] and len(details["headline"]) > 10 and "LinkedIn" not in details["headline"]:
                break
            logger.info("Headline missing/junk; scrolling to re-trigger (Attempt %s)...", attempt + 1)
            driver.execute_script(f"window.scrollTo(0, {200 * (attempt + 1)});")
            time.sleep(4)
                
        # HEADER CARD COMPANY (The "Right Side" button/logo)
        # This is often the most accurate source for the current company
        # --- LAYER 1: HEADER CARD DETECTION ---
        try:
            # The right panel often has two lines: [Company] and [Education]
            right_panel = driver.find_elements(By.CSS_SELECTOR, ".pv-text-details__right-panel li")
            for li in right_panel:
                txt = li.text.strip().split("\n")[0].strip().lower()

                ui_junk = [
                    "message", "connect", "follow", "more", "view profile", 
                    "visit my website", "pending", "remove", "ignore"
                ]

                if any(j == txt or j in txt for j in ui_junk):
                    continue

                if any(k in txt for k in ["university", "college", "school", "institute"]):
                    continue

                if "," in txt and len(txt.split()) < 5:
                    continue

                if len(txt) > 2:
                    details["company"] = txt.title()
                    logger.info("Fixed company: %s", details["company"])
                    break
        except: pass

        logger.info("Identity secured: %s", details["full_name"])
    except Exception as e: 
        logger.warning("Failed to secure Identity on Main Page: %s", e)

    # 2. PASS 2: EXPERIENCE SUB-PAGE
    try:
        logger.info("Navigating to dedicated Experience Page...")
        driver.get(profile_url.rstrip('/') + '/details/experience/')
        time.sleep(20)
    except: pass

    # 4. FINAL CLEANUP & FORMATTING
    details['company'] = clean_scraped_text(details['company'])
    if details.get('company') and details.get('full_name') and \
    details['company'].lower() == details['full_name'].lower():
        details['company'] = ""
        
    # Professional Capitalization for Role & Company
    if details['role'] and details['role'] == details['role'].lower():
        details['role'] = details['role'].title()
    if details['company'] and details['company'] == details['company'].lower():
        details['company'] = details['company'].title()

    if details["role"] and len(details["role"]) > 50:
        details["role"] = details["role"].split("|")[0].strip()

    # 🔥 FORCE ROLE + COMPANY FROM HEADLINE (FINAL FIX)
    h = details.get("headline", "")

    # 🔥 FINAL EXPERIENCE FALLBACK (STRONG FIX)
    if not details.get("role") or not details.get("company"):
        logger.info("Trying EXPERIENCE fallback...")

        role_exp, company_exp = extract_from_experience(driver)

        if role_exp and not details.get("role"):
            details["role"] = role_exp

        if company_exp and not details.get("company"):
            details["company"] = company_exp

    logger.info("Sync ready: %s at %s", details.get("role"), details.get("company"))

    # Cleanup
    details['full_name'] = details.get('full_name') or ""
    details['headline'] = details.get('headline') or ""

    # 2. ZONE B: EMAIL EXTRACTION (Bounty Hunter Dual Path)
    logger.info("Extracting Contact Info (Plus Premium Check)...")
    if not profile_url or "http" not in str(profile_url):
        logger.error("Invalid profile URL provided to scrape_profile_details: %s", profile_url)
        return details

    driver.get(profile_url.rstrip("/") + "/overlay/contact-info/")
    time.sleep(15)
    
    page_source = driver.page_source
    if "Try Premium" in page_source or "Premium for free" in page_source:
        logger.info("Email hidden behind a Premium wall.")
        details['email'] = "Premium Restricted"
    else:
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', page_source)
        if email_match:
            details['email'] = email_match.group(0)
            logger.info("Email secured (direct).")
        else:
            driver.get(profile_url)
            time.sleep(15)
            try:
                contact_btn = driver.find_element(By.PARTIAL_LINK_TEXT, "Contact info")
                driver.execute_script("arguments[0].click();", contact_btn)
                time.sleep(8)
                if "Try Premium" in driver.page_source:
                    details['email'] = "Premium Restricted"
                else:
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', driver.page_source)
                    details['email'] = email_match.group(0) if email_match else "Contact Restricted"
            except:
                details['email'] = "Contact Restricted"
            
    # Bounty Hunter Fallback
    if details['email'] in ["Contact Restricted", "Premium Restricted"]:
        combined_text = (details['about'] or "") + " " + (details['headline'] or "")
        bounty_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', combined_text)
        if bounty_match:
            details['email'] = bounty_match.group(0)

    # 3. ZONE C: IDENTITY & SYNTHESIS
    logger.info("Capturing Final Identity sections...")
    if not ("linkedin.com/in/" in driver.current_url and "/overlay/" not in driver.current_url):
        driver.get(profile_url)
        time.sleep(12)

    # About (Scroll-and-Capture v14)
    try:
        driver.execute_script("window.scrollTo(0, 1000);")
        time.sleep(3)
        
        # Click "see more" if it exists
        try:
            see_more = driver.find_element(By.XPATH, "//button[contains(@aria-label, 'see more') or contains(., 'see more')]")
            driver.execute_script("arguments[0].click();", see_more)
            time.sleep(2)
        except: pass

        details['about'] = driver.execute_script(r"""
            let sections = Array.from(document.querySelectorAll('section'));
            let aboutSection = sections.find(s => {
                let header = s.querySelector('h2');
                return header && header.innerText.includes('About');
            });
            if (aboutSection) {
                let text = aboutSection.innerText.split('\\n').slice(1).join(' ').replace('…see more', '').replace('… more', '').trim();
                return text;
            }
            return "";
        """)
    except: pass

    # --- PROFESSIONAL SYNTHESIS ---
    if not details['headline'] and details['role']:
        details['headline'] = f"Professional {details['role']} at {details['company']}"
    
    if not details['about'] and details['role']:
        details['about'] = f"Dedicated professional serving as {details['role']} at {details['company']}. Committed to excellence."

    if not details['work_description'] and details['role']:
        details['work_description'] = f"As the {details['role']} at {details['company']}, {details['full_name']} is responsible for driving organizational growth and high-impact solutions."
        logger.info("Synthesis: generated job description.")
    
    if details['headline']:
        logger.info("Headline secured.")
    if details['about']:
        logger.info("About secured.")

    logger.info("Final details prepared.")

    # 🔥 FORCE SAFE VALUES
    if not details.get("full_name"):
        details["full_name"] = "Unknown"

    if not details.get("headline"):
        details["headline"] = ""

    if not details.get("role"):
        details["role"] = ""

    if not details.get("company"):
        details["company"] = ""

    return details

def scrape_activity_from_tab(driver, url, interaction_type):
    logger.info("Checking %s tab...", interaction_type)
    results = []
    try:
        driver.get(url)
        time.sleep(8)
        elements = driver.find_elements(By.CSS_SELECTOR, ".feed-shared-update-v2, [data-urn]")
        for el in elements[:2]:
            data = get_post_data(el)
            if data:
                data["interaction_type"] = interaction_type
                data["sort_score"] = parse_linkedin_time(data["post_time"])
                results.append(data)
    except: pass
    return results

import hashlib

def get_content_hash(text):
    if not text: return ""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def scrape_profile(driver, profile_url):
    db = SessionLocal()
    from database.models import Lead
    
    # Normalize URL ONLY for consistent database matching
    target_url = normalize_url(profile_url)
    existing_lead = db.query(Lead).filter(Lead.linkedin_url == target_url).first()
    
    is_new_lead = False
    if not existing_lead:
        is_new_lead = True
        logger.info("New lead detected: %s", profile_url)
        # ✅ USE ORIGINAL URL (profile_url) FOR SELENIUM
        details = scrape_profile_details(driver, profile_url)
    else:
        logger.info("Existing lead detected, skipping full details scrape: %s", target_url)
        details = {
            "full_name": existing_lead.name,
            "headline": existing_lead.headline,
            "role": existing_lead.role,
            "company": existing_lead.company,
            "about": existing_lead.about,
            "work_description": existing_lead.work_description,
            "email": existing_lead.email
        }
    
    db.close()

    if not details or not details.get("full_name") or "LinkedIn" in details.get("full_name", ""):
        return None

    # Only translate if it's a new lead (existing leads already have translated data in DB)
    if is_new_lead:
        details["headline"] = safe_translate(details.get("headline"))
        details["about"] = safe_translate(details.get("about"))
        details["work_description"] = safe_translate(details.get("work_description"))
        details["company"] = safe_translate(details.get("company"))
        details["role"] = safe_translate(details.get("role"))

    # ✅ Save/Update lead (with Safety Net)
    try:
        lead_id = save_lead(
            linkedin_url=target_url,
            name=details.get("full_name"),
            email=details.get("email", ""),
            company=details.get("company", ""),
            role=details.get("role") or details.get("headline", ""),
            headline=details.get("headline", ""),
            about=details.get("about", ""),
            work_description=details.get("work_description", "")
        )
        if not lead_id:
            logger.error("Failed to get a valid lead_id for %s. Skipping events.", target_url)
            return None
    except Exception as e:
        logger.error("Database error while saving lead %s: %s", target_url, e)
        return None

    base_url = profile_url.rstrip("/")
    all_activities = []

    all_activities.extend(scrape_activity_from_tab(driver, f"{base_url}/recent-activity/shares/", "Post"))
    all_activities.extend(scrape_activity_from_tab(driver, f"{base_url}/recent-activity/comments/", "Comment"))
    all_activities.extend(scrape_activity_from_tab(driver, f"{base_url}/recent-activity/reactions/", "Like"))

    # ✅ Sort activities
    all_activities.sort(key=lambda x: x.get("sort_score", 999999))

    activity_list = []
    latest_item = all_activities[0] if all_activities else None
    if latest_item:
        latest_item["text"] = safe_translate(latest_item.get("text", ""))

    for act in all_activities:
        pref = (
            "Posted" if act["interaction_type"] == "Post"
            else "Commented" if act["interaction_type"] == "Comment"
            else "Liked"
        )

        # 🔥 TRANSLATE ACTIVITY TEXT
        translated_text = safe_translate(act.get("text", ""))

        activity_list.append(f"{pref}: {translated_text[:50]} ({act.get('post_time','')})")
    
    # 🔁 DEDUPLICATION LOGIC
    if latest_item:
        current_content = latest_item.get("text", "")
        current_hash = get_content_hash(current_content)

        db = SessionLocal()
        try:
            last_event = db.query(Event).filter(
                Event.lead_id == lead_id,
                Event.event_type == "interaction_summary"
            ).order_by(Event.timestamp.desc()).first()

            last_hash = ""
            if last_event and last_event.additional_data and "content_hash" in last_event.additional_data:
                last_hash = last_event.additional_data["content_hash"]

            if current_hash != last_hash:
                logger.info("New activity detected for %s", details.get("full_name"))

                try:
                    save_event(lead_id, "interaction_summary", {
                        "content_hash": current_hash,
                        "recent_activity": activity_list,
                        "latest_text": current_content[:200],
                        "has_new_activity": True
                    })
                except Exception as e:
                    logger.warning("Could not save interaction_summary event: %s", e)

                # ✅ Save to Google Sheets
                save_enhanced_data(
                    full_name=details.get("full_name"),
                    profile_url=target_url,
                    headline=details.get("headline"),
                    company=details.get("company"),
                    about=details.get("about"),
                    email=details.get("email"),
                    interaction_type=latest_item.get("interaction_type"),
                    content=latest_item.get("text"),
                    interaction_date=time.strftime("%Y-%m-%d"),
                    role=details.get("role", ""),
                    work_description=details.get("work_description", ""),
                    recent_activity="\n".join(activity_list)
                )

                return {
                    "name": details.get("full_name"),
                    "headline": details.get("headline"),
                    "company": details.get("company"),
                    "role": details.get("role"),
                    "about": details.get("about"),
                    "work_description": details.get("work_description"),
                    "email": details.get("email"),
                    "url": profile_url,
                    "is_new_lead": is_new_lead,
                    "interaction_type": latest_item.get("interaction_type"),
                    "latest_content": current_content
                }

            else:
                logger.info("Duplicate: no new activity for %s", details.get("full_name"))
                try:
                    save_event(lead_id, "profile_scraped", {"status": "no_new_activity"})
                except Exception as e:
                    logger.warning("Could not save profile_scraped event: %s", e)
                return None
        finally:
            db.close()

    else:
        try:
            save_event(lead_id, "profile_scraped", {"status": "no_activity_found"})
        except Exception as e:
            logger.warning("Could not save profile_scraped event: %s", e)
        return None


def save_cookies(driver):
    """Saves the current session cookies to a file."""
    try:
        pickle.dump(driver.get_cookies(), open("scraper/cookies.pkl", "wb"))
        logger.info("Fresh cookies saved for future sessions.")
    except Exception as e:
        logger.warning("Failed to save cookies: %s", e)


# Networking Configuration (Phase 0)
BACKEND_URL = os.getenv("BACKEND_INTERNAL_URL", "http://localhost:8000").rstrip("/")
API_URL = f"{BACKEND_URL}/api"

# ✅ Webhook Fallback (Phase 4): Use Env if not passed via CLI
webhook_url = os.getenv("N8N_WEBHOOK_URL")

for arg in sys.argv:
    if "webhook_url=" in arg:
        webhook_url = arg.split("webhook_url=")[-1]

# 🐳 SMART REDIRECTION: If in Docker and using localhost, switch to host.docker.internal
if os.path.exists("/.dockerenv") and webhook_url and "localhost" in webhook_url:
    logger.info("Docker environment detected: Redirecting localhost webhook to host.docker.internal")
    webhook_url = webhook_url.replace("localhost", "host.docker.internal")

def run_scraper():
    health = check_browser_health()
    logger.info("--- SCRAPER STARTUP DIAGNOSTICS ---")
    logger.info("OS: %s", health['os'])
    logger.info("Headless: %s", health['headless'])
    logger.info("Profile Path: %s", health['profile_path'])
    logger.info("Binary: %s", health['binary'])
    logger.info("-----------------------------------")

    urls = get_profile_urls()
    all_results = []
    
    settings = get_settings()

    # 1. PROFILE LOCKING (Phase 3)
    with chrome_profile_lock(settings.linkedin_profile_name) as acquired:
        if not acquired:
            logger.error("Job aborted: Chrome profile %s is currently locked by another worker", settings.linkedin_profile_name)
            update_backend_status("error", f"Concurrency Lock: Profile {settings.linkedin_profile_name} in use")
            raise RuntimeError(f"Lock active for {settings.linkedin_profile_name}")

        driver = create_driver()
        try:
            # --- JSON COOKIE BRIDGE ---
            cookie_path = os.path.join(os.getcwd(), "cookies.json")
            if os.path.exists(cookie_path):
                logger.info("Found cookies.json - Injecting session...")
                try:
                    driver.get("https://www.linkedin.com")
                    with open(cookie_path, 'r') as f:
                        cookies = json.load(f)
                    for cookie in cookies:
                        if 'expiry' in cookie:
                            cookie['expiry'] = int(cookie['expiry'])
                        driver.add_cookie(cookie)
                    driver.refresh()
                    logger.info("JSON cookies injected successfully!")
                except Exception as e:
                    logger.error("Failed to inject JSON cookies: %s", e)
            # --------------------------

            update_backend_status("running", "Validating LinkedIn session...")
            
            if not validate_session(driver):
                if not settings.headless:
                    logger.error("AUTHENTICATION REQUIRED. The session has expired or been challenged.")
                    update_backend_status("running", "Waiting for manual login in browser...")
                    print("\n" + "!"*60)
                    print("⚠️  LINKEDIN LOGIN REQUIRED!")
                    print("👉 Please log in manually in the Chrome window that just opened.")
                    print("👉 Once you see your LinkedIn Feed, come back here and press ENTER.")
                    print("!"*60 + "\n")
                    input("Press ENTER after you have logged in...")
                    
                    # Retry validation after manual login
                    if not validate_session(driver):
                        logger.error("Session still invalid after manual attempt. Aborting.")
                        update_backend_status("error", "LinkedIn session expired. Manual login failed.")
                        return
                else:
                    logger.error("AUTHENTICATION REQUIRED. The session has expired or been challenged.")
                    update_backend_status("error", "LinkedIn session expired. Login required.")
                    return

            for i, url in enumerate(urls):
                if not url or not str(url).strip() or "linkedin.com" not in str(url):
                    logger.warning("Skipping invalid URL at row %s: %s", i+1, url)
                    continue

                print(f"\n🚀 [SCRAPER] Processing Profile {i+1}/{len(urls)}: {url}")
                logger.info("Starting scrape for: %s", url)
                
                update_backend_status("running", f"Scraping profile {i+1}/{len(urls)}: {url}")
                result = scrape_profile(driver, url)
                
                if result:
                    print(f"✅ [SCRAPER] Successfully scraped: {url}")
                    # Send to n8n if there is ANY new result (new lead OR new activity)
                    all_results.append(result)
                    
                    if result.get("is_new_lead"):
                        logger.info("New lead queued for webhook: %s", url)
                    else:
                        logger.info("New activity for existing lead queued for webhook: %s", url)
                    
                    update_backend_status("running", f"Synced {i+1} profiles...", new_posts=len(all_results))
                else:
                    print(f"❌ [SCRAPER] Failed to scrape: {url}")
                
                print(f"⏱️ [SCRAPER] Sleeping for 10s to stay under the radar...")
                time.sleep(10)

            update_backend_status("completed", f"Finished! Found {len(all_results)} profiles.", new_posts=len(all_results))

            # ✅ FINAL WEBHOOK TRIGGER (Phase 4)
            if webhook_url and all_results:
                logger.info("Triggering final n8n webhook with %d results...", len(all_results))
                try:
                    # n8n often expects a list of items or a JSON object
                    response = requests.post(webhook_url, json={"data": all_results}, timeout=30)
                    logger.info("Webhook triggered! n8n responded: %s", response.status_code)
                except Exception as e:
                    logger.warning("Failed to trigger n8n webhook: %s", e)

        except Exception as e:
            logger.exception("CRITICAL ERROR: %s", e)
            update_backend_status("error", error=str(e))
            raise
        finally:
            logger.info("Closing browser.")
            try:
                driver.quit()
            except: pass

if __name__ == "__main__":
    run_scraper()
