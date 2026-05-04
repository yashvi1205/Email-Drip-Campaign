import time
import os
import pickle
import sys
import io
import re
import random
import json
from datetime import datetime
import requests


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
from deep_translator import GoogleTranslator

try:
    from database.save_data import save_lead, save_event, get_or_create_sequence
    from google_sheets import save_enhanced_data
except ImportError:
    def save_lead(**kwargs): return 1
    def save_event(**kwargs): pass
    def get_or_create_sequence(*args, **kwargs): pass
    def save_enhanced_data(**kwargs): pass

webhook_url = None

for arg in sys.argv:
    if "webhook_url=" in arg:
        webhook_url = arg.split("webhook_url=")[-1]

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
        print(f"Translation failed: {e}")
        return text


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


def ensure_logged_in(driver):
    driver.get("https://www.linkedin.com/feed/")
    time.sleep(5)

    if "login" in driver.current_url or "checkpoint" in driver.current_url:
        print("❌ Session expired. Please login manually.")

        input("👉 Login fully, wait for feed, THEN press ENTER...")

        driver.get("https://www.linkedin.com/feed/")
        time.sleep(5)

    print("✅ Session active")


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
        print("⚠️ Session lost. Re-login required.")
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

def safe_set(details, key, value):
    if not value:
        return

    value = value.strip()

    junk = [
        "", "N/A", "Sign Up", "0 Notifications",
        "LinkedIn", "Join LinkedIn",
        "Self-Employed", "Independent", "Freelance",
        "& CEO", "CEO", "Founder"
    ]

    if value in junk:
        return

    if not details.get(key) or details[key] in junk:
        details[key] = value

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
                    // Method 1: The Left Panel container
                    let leftPanel = document.querySelector('.pv-text-details__left-panel');
                    if (leftPanel) {
                        let textEls = Array.from(leftPanel.querySelectorAll('div, span, p'));
                        let candidate = textEls.find(el => el.innerText.length > 10 && !el.querySelector('h1') && !el.innerText.includes(document.title.split('|')[0].trim()));
                        if (candidate) return candidate.innerText.trim();
                    }
                    
                    // Method 2: Specific classes
                    let specific = document.querySelector('.text-body-medium.break-words');
                    if (specific) return specific.innerText.trim();
                    
                    // Method 3: Broad text search near the top
                    let topCard = document.querySelector('main');
                    if (topCard) {
                        let text = topCard.innerText.split('\n').filter(t => t.length > 20 && t.length < 200)[0];
                        if (text) return text.trim();
                    }
                    return "";
                }
                return findHeadline();
            """)
            
            if details["headline"] and len(details["headline"]) > 10 and "LinkedIn" not in details["headline"]:
                break
            print(f"   -> [!] Headline missing or junk, scrolling to re-trigger (Attempt {attempt+1})...")
            driver.execute_script(f"window.scrollTo(0, {200 * (attempt + 1)});")
            time.sleep(4)
        
        if not details["headline"] or len(details["headline"]) < 5:
            details["headline"] = "Professional at LinkedIn"
        
        # HEADER CARD COMPANY (The "Right Side" button/logo)
        # This is often the most accurate source for the current company
        # --- LAYER 1: HEADER CARD DETECTION ---
        try:
            # The right panel often has two lines: [Company] and [Education]
            right_panel = driver.find_elements(By.CSS_SELECTOR, ".pv-text-details__right-panel li")
            for li in right_panel:
                txt = li.text.strip().split("\n")[0].strip()
                # If it's education, skip it
                if any(k in txt.lower() for k in ["university", "college", "school", "institute", "darshan"]):
                    continue
                # If it matches the name or role, skip it
                if txt.lower() == details["full_name"].lower() or (details["role"] and txt.lower() == details["role"].lower()):
                    continue
                if txt and len(txt) > 2 and txt.lower() not in ["experience", "self-employed"]:
                    details["company"] = clean_scraped_text(txt)
                    print(f"   -> LAYER 1 (Right Panel) Company: {details['company']}")
                    break
        except: pass

        print(f"   -> IDENTITY SECURED: {details['full_name']}")

        # --- LAYER 2: HEADLINE INTELLIGENCE (Force-Check) ---
        h = details["headline"]
        if h and len(h) > 5:
            # Pattern: "Role at Company"
            for sep in [" at ", " @ ", "@"]:
                if sep in h.lower():
                    # Find the last occurrence of the separator to be safe
                    idx = h.lower().rfind(sep)
                    h_role = h[:idx].strip().split("|")[-1].split("-")[-1].strip()
                    h_company = h[idx+len(sep):].split("|")[0].split("-")[0].split("·")[0].strip()
                    
                    if not details["role"] or details["role"].lower() == "experience":
                        details["role"] = h_role
                    # Force update if company is missing, junk, or matches role
                    invalid_values = ["self-employed", "independent", "freelance", "experience"]
                    if not details["company"] or details["company"].lower() in invalid_values:

                            h = details["headline"]

                            # Handle "Founder X & Y at Self-Employed"
                            if " at " in h.lower():
                                parts = h.split(" at ")
                                left = parts[0]

                                # STEP 1: Remove role keywords
                                cleaned = re.sub(r"\b(Founder|CEO|Co-Founder|Owner|Director|Lead)\b", "", left, flags=re.IGNORECASE)
                                cleaned = cleaned.strip(" -|")
                                
                                # STEP 2: Remove extra symbols/spaces
                                cleaned = cleaned.strip()

                                # STEP 3: Extract multiple companies cleanly
                                companies = re.split(r"&|,| and ", cleaned)
                                companies = [c.strip() for c in companies if len(c.strip()) > 2]

                                # STEP 4: Assign final company
                                if companies and (
                                    not details["company"] or details["company"].lower() in invalid_values
                                ):
                                    safe_set(details, "company", h_company)
                                    safe_set(details, "role", h_role)
                    break
    except Exception as e: 
        print(f"   -> [!] Failed to secure Identity on Main Page: {e}")

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
            
            let keywords = ['Founder', 'CEO', 'Manager', 'Lead', 'Engineer', 'Director', 'Owner', 'Partner', 'Developer', 'Specialist', 'Consultant', 'Tester', 'Analyst'];
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
        extracted_role = clean_scraped_text(exp_data.get("role", ""))
        extracted_company = clean_scraped_text(exp_data.get("company", ""))
            
        # FIX: Handle "Founder & CEO @ Company"
        if extracted_role:
            if "@" in extracted_role:
                parts = extracted_role.split("@")
                safe_set(details, "role", parts[0].strip())
                safe_set(details, "company", parts[1].split("|")[0].strip())

            elif " at " in extracted_role.lower():
                parts = extracted_role.split(" at ")
                safe_set(details, "role", parts[0].strip())
                safe_set(details, "company", parts[1].strip())

        else:
            # Only set role if clean
            safe_set(details, "role", extracted_role)

    # ONLY set company if it's NOT junk
        if extracted_company and extracted_company.lower() not in ["self-employed", "independent"]:
            (details, "company", extracted_company)   


    # 4. FINAL CLEANUP & FORMATTING
    details['company'] = clean_scraped_text(details['company'])
    if details['company'].lower() == details['full_name'].lower():
        details['company'] = ""
        
    # Professional Capitalization for Role & Company
    if details['role'] and details['role'] == details['role'].lower():
        details['role'] = details['role'].title()
    if details['company'] and details['company'] == details['company'].lower():
        details['company'] = details['company'].title()

    if details["role"] and not details["company"]:
        role_text = details["role"]

        if "@" in role_text:
            parts = role_text.split("@")
            details["role"] = parts[0].strip()
            details["company"] = parts[1].strip()

        elif " at " in role_text.lower():
            parts = role_text.split(" at ")
            details["role"] = parts[0].strip()
            details["company"] = parts[1].strip()

    bad_values = ["self-employed", "independent", "freelance", "& ceo", "ceo"]

    if details["company"] and details["company"].lower() in bad_values:
        print("   -> FIX: Removing bad company value")
        details["company"] = ""

    if details["role"] and len(details["role"]) > 50:
        details["role"] = details["role"].split("|")[0].strip()

    print(f"   -> SYNC READY: {details['role']} at {details['company']}")

    # Cleanup
    details['full_name'] = clean_scraped_text(details.get('full_name', ""))
    details['headline'] = clean_scraped_text(details.get('headline', ""))

    # 2. ZONE B: EMAIL EXTRACTION (Bounty Hunter Dual Path)
    print("   -> Extracting Contact Info (Plus Premium Check)...")
    driver.get(profile_url.rstrip("/") + "/overlay/contact-info/")
    time.sleep(15)
    
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

    if not details or not details.get("full_name") or "LinkedIn" in details.get("full_name", ""):
        return False

    details["headline"] = safe_translate(details.get("headline"))
    details["about"] = safe_translate(details.get("about"))
    details["work_description"] = safe_translate(details.get("work_description"))
    details["company"] = safe_translate(details.get("company"))
    details["role"] = safe_translate(details.get("role"))

    # ✅ Save lead AFTER cleaning/translation
    lead_id = save_lead(
        linkedin_url=profile_url,
        name=details.get("full_name"),
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

        from database.db import SessionLocal
        from database.models import Event

        db = SessionLocal()

        last_event = db.query(Event).filter(
            Event.lead_id == lead_id,
            Event.event_type == "interaction_summary"
        ).order_by(Event.timestamp.desc()).first()

        last_hash = ""
        if last_event and last_event.additional_data and "content_hash" in last_event.additional_data:
            last_hash = last_event.additional_data["content_hash"]

        if current_hash != last_hash:
            print(f"   -> [NEW ACTIVITY DETECTED] for {details['full_name']}")

            save_event(lead_id, "interaction_summary", {
                "content_hash": current_hash,
                "recent_activity": activity_list,
                "latest_text": current_content[:200],
                "has_new_activity": True
            })

            # ✅ Save to Google Sheets
            save_enhanced_data(
                full_name=details.get("full_name"),
                profile_url=profile_url,
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

        else:
            print(f"   -> [DUPLICATE] No new activity for {details['full_name']}")
            save_event(lead_id, "profile_scraped", {"status": "no_new_activity"})

        db.close()

    else:
        save_event(lead_id, "profile_scraped", {"status": "no_activity_found"})

    # ✅ FINAL RETURN (FIXED SYNTAX)
    return {
        "name": details.get("full_name"),
        "headline": details.get("headline"),
        "company": details.get("company"),
        "role": details.get("role"),
        "about": details.get("about"),
        "work_description": details.get("work_description"),
        "email": details.get("email"),
        "url": profile_url
    }


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
    all_results = []
    
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    chrome_options.add_argument(r"--user-data-dir=C:\selenium-profile")
    chrome_options.add_argument("--profile-directory=Default")
    chrome_options.add_argument("--lang=en-US")

    
    driver = webdriver.Chrome(options=chrome_options)
    try:
        driver.get("https://www.linkedin.com/feed/")
        time.sleep(5)

        ensure_logged_in(driver)

        save_cookies(driver)

        for url in urls:
            result = scrape_profile(driver, url)
            if result:
                all_results.append(result)
                print(f"   -> SYNC COMPLETE: {url}")
            time.sleep(10)

    finally:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ALL TASKS FINISHED. Closing browser automatically.")

        if webhook_url and all_results:
            try:
                print(f"🚀 Sending {len(all_results)} profiles to webhook...")
                response = requests.post(webhook_url, json={"data": all_results})
                print(f"✅ Webhook response: {response.status_code}")
            except Exception as e:
                print(f"❌ Webhook failed: {e}")
        else:
            print("⚠️ No webhook URL or no data to send")
        
        driver.quit()

if __name__ == "__main__":
    run_scraper()
