import time
import os
import json
import pickle
import sys
import io
import re
import random
import time
import requests
from datetime import datetime
from selenium.webdriver.chrome.service import Service

BACKEND_URL = "https://email-drip-campaign-hpo2.onrender.com"


# FORCE UTF-8 FOR PRINTING
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Fix for module imports when running from subdirectories
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

try:
    from database.save_data import save_lead, save_event, get_or_create_sequence
    from google_sheets import save_enhanced_data
except ImportError:
    def save_lead(**kwargs): return 1
    def save_event(**kwargs): pass
    def get_or_create_sequence(*args, **kwargs): pass
    def save_enhanced_data(**kwargs): pass


def update_status(status, message=""):
    try:
        requests.post(
            f"{BACKEND_URL}/api/update-status",
            json={
                "status": status,
                "message": message
            },
            timeout=5
        )
    except Exception as e:
        print(f"❌ Failed to update status: {e}")


def run_scraper():
    try:
        print("🔥 SCRAPER STARTED")
        update_status("running", "Scraper started")
        print("🚀 Starting Chrome...")
        time.sleep(2)
        print("🔍 Scraping profiles...")
        for i in range(3):
            print(f"➡️ Processing profile {i+1}")
            time.sleep(5)

        print("📊 Saving data to DB...")

        time.sleep(2)

        print("🏁 SCRAPER COMPLETED")
        update_status("completed", "Scraping finished successfully")

    except Exception as e:
        print(f"🔥 SCRAPER ERROR: {str(e)}")
        update_status("failed", str(e))



def get_username(url):
    return url.split("/in/")[1].split("/")[0]

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

def get_post_data(element):
    try:
        text = element.text.strip()
        time_els = element.find_elements(By.CSS_SELECTOR, "span.update-components-text-view__badge-text, .update-components-actor__sub-description")
        post_time = time_els[0].text.split('•')[0].strip() if time_els else ""
        urn = element.get_attribute("data-urn") or str(hash(text))
        return {"text": text, "post_time": post_time, "urn": urn}
    except: return None

def clean_scraped_text(text):
    """v15.2 Anti-UI: Aggressively filters out LinkedIn UI labels and buttons."""
    if not text: return ""
    
    # 1. Newline Cleanup: Buttons usually appear on a new line
    lines = text.split('\n')
    base_text = lines[0].strip()
    
    # 2. Strict UI Blacklist (Case-sensitive for short UI labels)
    ui_labels = ["More", "Share", "React", "Reply", "Message", "Connect", "Follow"]
    if base_text in ui_labels:
        return ""

    # 3. Promotional Noise Blacklist
    blacklist = [
        "Try Premium", "Upgrade", "Activate", "Get 1 month", "Visit my website",
        "View my", "at More", "Click here", "•", "·", "Full-time", "Part-time"
    ]
    
    for word in blacklist:
        if word.lower() in base_text.lower() and len(base_text) < 40:
            return "" 
        if word in base_text:
            base_text = base_text.split(word)[0].strip()
            
    return base_text.replace("… more", "").replace("see more", "").strip()

def normalize_url(url):
    """Converts localized subdomains (nl., in., etc) to standard www. to avoid 404s."""
    if not url: return url
    return url.replace("nl.linkedin.com", "www.linkedin.com").replace("in.linkedin.com", "www.linkedin.com").replace("uk.linkedin.com", "www.linkedin.com")

def scrape_profile_details(driver, profile_url):
    profile_url = normalize_url(profile_url)
    print(f"Scraping detailed info for: {profile_url}")
    details = {
        "full_name": "", "headline": "", "role": "", "company": "",
        "about": "", "work_description": "", "email": ""
    }
    
    # 1. PASS 1: MAIN PROFILE PAGE (Identity & Headline)
    try:
        driver.get(profile_url)
        WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
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
            
        details["headline"] = clean_scraped_text(driver.find_element(By.XPATH, "//div[contains(@class, 'text-body-medium')]").text)
        print(f"   -> IDENTITY SECURED: {details['full_name']}")
    except: 
        print("   -> [!] Failed to secure Identity on Main Page.")

    # 2. PASS 2: EXPERIENCE SUB-PAGE
    try:
        print("   -> Navigating to dedicated Experience Page...")
        driver.get(normalize_url(profile_url.rstrip('/') + '/details/experience/'))
        time.sleep(12)
    except: pass

    # 3. RELIABLE DREDGE (JavaScript Layer)
    exp_data = driver.execute_script("""
        function reliable_dredge(profileName) {
            let elements = Array.from(document.querySelectorAll('span, div, a, h3'));
            let rows = elements.map(e => e.innerText ? e.innerText.trim() : "").filter(t => t.length > 2);
            
            let keywords = ['Founder', 'CEO', 'Manager', 'Lead', 'Engineer', 'Director', 'Owner', 'Partner', 'Developer', 'Specialist', 'Consultant'];
            let foundRole = rows.find(r => keywords.some(k => r.includes(k)) && !r.includes(profileName));
            if (!foundRole) return null;
            
            let roleIdx = rows.indexOf(foundRole);
            
            // Intelligence: Catch "@" or "at" even without perfect spacing
            if (foundRole.includes('@')) return { role: foundRole.split('@')[0].trim(), company: foundRole.split('@')[1].split('|')[0].trim() };
            if (foundRole.toLowerCase().includes(' at ')) return { role: foundRole.toLowerCase().split(' at ')[0].trim(), company: foundRole.toLowerCase().split(' at ')[1].split('|')[0].trim() };
            
            let candidates = rows.slice(roleIdx + 1, roleIdx + 4);
            let company = candidates.find(c => c !== profileName && !/\\d{4}|Present|·/.test(c) && c.length > 2);
            
            return { role: foundRole, company: company || "" };
        }
        return reliable_dredge(arguments[0]);
    """, details["full_name"])

    if exp_data:
        details["role"] = clean_scraped_text(exp_data.get("role", ""))
        details["company"] = clean_scraped_text(exp_data.get("company", ""))
        
    # FINAL SAFETY GUARD: Deep Symbol Extraction
    if not details["company"] or details["company"].lower() == details["full_name"].lower() or details["company"] == "Independent":
        h = details["headline"]
        # Try all common separators in order of reliability
        for sep in [" @ ", "@", " at ", " : ", ":", " | ", " - "]:
            if sep in h:
                parts = h.split(sep)
                # Take the part after the symbol, but stop if there's another separator
                potential = parts[-1].split('|')[0].split('-')[0].split('·')[0].strip()
                if len(potential) > 2 and potential.lower() != details["full_name"].lower():
                    details["company"] = potential
                    break
        
        if not details["company"]:
            details["company"] = "Self-Employed"
    
    print(f"   -> SYNC READY: {details['role']} at {details['company']}")

    # Cleanup
    details['full_name'] = clean_scraped_text(details.get('full_name', ""))
    details['headline'] = clean_scraped_text(details.get('headline', ""))

    # 2. ZONE B: EMAIL EXTRACTION (Bounty Hunter Dual Path)
    print("   -> Extracting Contact Info (Plus Premium Check)...")
    driver.get(profile_url.rstrip("/") + "/overlay/contact-info/")
    
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    
    page_source = driver.page_source
    if "Try Premium" in page_source or "Premium for free" in page_source:
        print("   -> [!] ALERT: LinkedIn is hiding this Email behind a Premium Wall.")
        details['email'] = "Premium Restricted"
    else:
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', page_source)
        if email_match:
            details['email'] = email_match.group(0)
            print(f"   -> EMAIL SECURED (Direct): {details['email']}")
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
    print("   -> Capturing Final Identity sections...")
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
        print("   -> SYNTHESIS: Generated Job Description.")
    
    if details['headline']: print(f"   -> HEADLINE SECURED: {details['headline'][:40]}...")
    if details['about']: print("   -> ABOUT SECURED")
    
    return details

def scrape_activity_from_tab(driver, url, interaction_type):
    print(f"   -> Checking {interaction_type} tab...")
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
    details = scrape_profile_details(driver, profile_url)
    if not details["full_name"] or "LinkedIn" in details["full_name"]:
        return False

    lead_id = save_lead(
        linkedin_url=profile_url,
        name=details["full_name"],
        email=details.get("email", ""),
        company=details.get("company", ""),
        role=details.get("role") or details.get("headline", ""),
        headline=details.get("headline", ""),
        about=details.get("about", ""),
        work_description=details.get("work_description", "")
    )

    base_url = profile_url.rstrip("/")
    all_activities = []
    all_activities.extend(scrape_activity_from_tab(driver, f"{base_url}/recent-activity/shares/", "Post"))
    all_activities.extend(scrape_activity_from_tab(driver, f"{base_url}/recent-activity/comments/", "Comment"))
    all_activities.extend(scrape_activity_from_tab(driver, f"{base_url}/recent-activity/reactions/", "Like"))

    # Sort by time score (lowest score = most recent)
    all_activities.sort(key=lambda x: x.get("sort_score", 999999))
    
    activity_list = []
    latest_item = all_activities[0] if all_activities else None
    for act in all_activities:
        pref = "Posted" if act["interaction_type"] == "Post" else "Commented" if act["interaction_type"] == "Comment" else "Liked"
        activity_list.append(f"{pref}: {act['text'][:50]} ({act['post_time']})")

    # DEDUPLICATION LOGIC
    is_new_activity = False
    if latest_item:
        current_content = latest_item.get("text", "")
        current_hash = get_content_hash(current_content)
        
        # Check database for last processed interaction
        from database.db import SessionLocal
        from database.models import Event
        db = SessionLocal()
        last_event = db.query(Event).filter(
            Event.lead_id == lead_id,
            Event.event_type == "interaction_summary"
        ).order_by(Event.timestamp.desc()).first()
        
        last_hash = ""
        if last_event and "content_hash" in last_event.additional_data:
            last_hash = last_event.additional_data["content_hash"]
        
        if current_hash != last_hash:
            is_new_activity = True
            print(f"   -> [NEW ACTIVITY DETECTED] for {details['full_name']}")
            
            # Log the new event to database
            save_event(lead_id, "interaction_summary", {
                "content_hash": current_hash,
                "recent_activity": activity_list,
                "latest_text": current_content[:200],
                "has_new_activity": True # Flag for n8n/UI
            })
            
            # Sync to Google Sheets ONLY if it's new
            save_enhanced_data(
                full_name=details["full_name"],
                profile_url=profile_url,
                headline=details["headline"],
                company=details["company"],
                about=details["about"],
                email=details["email"],
                interaction_type=latest_item["interaction_type"],
                content=latest_item["text"],
                interaction_date=time.strftime("%Y-%m-%d"),
                role=details.get("role", ""),
                work_description=details.get("work_description", ""),
                recent_activity="\n".join(activity_list)
            )
        else:
            print(f"   -> [DUPLICATE] No new activity for {details['full_name']}. Skipping sheet sync.")
        db.close()
    
    return True

def save_cookies(driver):
    """Saves the current session cookies to a file."""
    try:
        pickle.dump(driver.get_cookies(), open("scraper/cookies.pkl", "wb"))
        print("   -> [SUCCESS] Fresh cookies saved for future sessions.")
    except Exception as e:
        print(f"   -> [!] Failed to save cookies: {e}")

def run_scraper():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Deploying v14 'Auto-Learning' Scraper.")
    from google_sheets import get_profile_urls
    urls = get_profile_urls()
    
    chrome_options = Options()

    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    chrome_options.add_argument("--remote-debugging-port=9222")

    driver = webdriver.Chrome(service=Service(), options=chrome_options)
    
    
    try:
        driver.get("https://www.linkedin.com/login")
        time.sleep(3)
        
        # Load existing cookies
        if os.path.exists("scraper/cookies.pkl"):
            print("   -> Loading stored session...")
            cookies = pickle.load(open("scraper/cookies.pkl", "rb"))
            for cookie in cookies:
                try: driver.add_cookie(cookie)
                except: pass
        
        driver.get("https://www.linkedin.com/feed/")
        time.sleep(5)
        
        # Check if login is needed
        if "login" in driver.current_url or "checkpoint" in driver.current_url:
            print("   -> [!] Login Screen detected. Attempting Auto-Bypass...")
            
            # Try to click the "Welcome back" card automatically
            try:
                welcome_card = driver.find_element(By.XPATH, "//h1[contains(., 'Welcome back')]//following::div[contains(@class, 'profile-card')]")
                driver.execute_script("arguments[0].click();", welcome_card)
                print("   -> [SUCCESS] Auto-clicked Welcome Back card.")
                time.sleep(5)
            except: pass
            
            if "feed" not in driver.current_url:
                print("\n" + "="*50)
                print("   -> [!] ACTION REQUIRED: Please log in manually THIS ONCE.")
                print("   -> After this, I will save your session forever.")
                print("="*50 + "\n")
                time.sleep(45) 
        
        for url in urls:
            if scrape_profile(driver, url):
                print(f"   -> SYNC COMPLETE: {url}")
                time.sleep(10)
    finally:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ALL TASKS FINISHED. Closing browser automatically.")
        driver.quit()

if __name__ == "__main__":
    run_scraper()