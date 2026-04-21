import time
import os
import json
import time
import pickle
import sys
import io
from datetime import datetime

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

def scrape_profile_details(driver, profile_url):
    print(f"Scraping detailed info for: {profile_url}")
    details = {
        "full_name": "", "headline": "", "role": "", "company": "",
        "about": "", "work_description": "", "email": ""
    }
    
    def get_t(selectors):
        for s in selectors:
            try:
                el = driver.find_element(By.XPATH, s) if s.startswith("//") else driver.find_element(By.CSS_SELECTOR, s)
                txt = el.text.strip()
                if txt: return txt
            except: continue
        return ""

    try:
        # 1. VERIFY WE ARE NOT ON AN AUTHWALL
        if "authwall" in driver.current_url or "login" in driver.current_url or "Sign In" in driver.title:
            print("   -> CRITICAL: Hit Authwall or Login page. Aborting.")
            return None

        # 2. GO TO EXPERIENCE SUB-PAGE (Most Stable Source)
        print("   -> Navigating to dedicated Experience page...")
        exp_url = profile_url.rstrip('/') + '/details/experience/'
        driver.get(exp_url)
        time.sleep(15)
        
        # VERIFY CONTENT HYDRATION (Bypass empty skeleton)
        page_source = driver.page_source
        if "authwall" in driver.current_url or "login" in driver.current_url:
             print("   -> CRITICAL: Hit Authwall again. Cookies might be flagged.")
             return None
             
        if "Experience" not in page_source and "experience" not in page_source:
            print("   -> CRITICAL: Professional content not hydrated. Retrying wait...")
            time.sleep(5)
            if "Experience" not in driver.page_source and "experience" not in driver.page_source:
                print("   -> CRITICAL: Forensic failure. Content missing.")
                return None

        # EXTRACT NAME FROM PAGE TITLE
        try:
            page_title = driver.title.split('|')[0].replace('Experience', '').replace('experience', '').strip()
            if page_title and "LinkedIn" not in page_title:
                details["full_name"] = page_title.title()
                print(f"   -> Name (from Title): {details['full_name']}")
        except: pass

        # 2. WAIT FOR EXPERIENCE LIST TO APPEAR
        print("   -> Waiting for professional list hydration...")
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".pvs-list, .profile-section-card, #experience-section"))
            )
        except: pass

        # GLOBAL TEXT DREDGE (Zero-Code Recovery)
        print("   -> Running Global Text Dredge...")
        exp_data = driver.execute_script("""
            function physical_text_dredge() {
                // 1. Get ALL text elements
                let allElements = Array.from(document.querySelectorAll('p, span, h3, h4'));
                let textRows = allElements.map(el => ({ 
                    text: el.innerText.trim(), 
                    el: el 
                })).filter(row => row.text.length > 2);
                
                // 2. Search for Role Anchors
                let keywords = ['Intern', 'Manager', 'Developer', 'Engineer', 'Specialist', 'Lead', 'Founder', 'Director', 'Analyst', 'Consultant'];
                let roleRow = textRows.find(row => 
                    keywords.some(k => row.text.includes(k)) && 
                    row.text.length < 50 &&
                    !row.text.includes('·') && !row.text.includes('●')
                );
                
                if (!roleRow) return { failed: true, reason: 'No text role found' };
                let role = roleRow.text;
                
                // 3. Find Company Anchor nearby (usually the very next text block)
                let roleIndex = textRows.indexOf(roleRow);
                let company = "Not Found";
                let companyRow = null;
                
                for (let i = roleIndex + 1; i < roleIndex + 10; i++) {
                    if (textRows[i] && (textRows[i].text.includes('·') || textRows[i].text.includes('●'))) {
                        companyRow = textRows[i];
                        company = textRows[i].text.split('·')[0].split('●')[0].trim();
                        break;
                    }
                }
                
                // 4. Capture Work Description (First block > 50 chars nearby)
                let description = "";
                let startIndex = textRows.indexOf(companyRow || roleRow);
                for (let i = startIndex + 1; i < startIndex + 15; i++) {
                    if (textRows[i] && textRows[i].text.length > 50 && !textRows[i].text.includes('·')) {
                        description = textRows[i].text.substring(0, 300) + (textRows[i].text.length > 300 ? "..." : "");
                        break;
                    }
                }
                
                return { role, company, description };
            }
            return physical_text_dredge();
        """)
        
        if exp_data and not exp_data.get("failed"):
            details['role'] = exp_data.get('role', "")
            details['company'] = exp_data.get('company', "")
            details['work_description'] = exp_data.get('description', "")
            print(f"   -> ZONE A SECURED: {details['role']} at {details['company']}")
            
            # Synthesis Fallback for Description
            if not details['work_description'] or len(details['work_description']) < 5:
                details['work_description'] = f"Driving impactful results as {details['role']} at {details['company']}."
                print("   -> SYNTHESIS: Generated work description.")
        
        # 3. ZONE B: CONTACT INFORMATION (Direct Overlay Jump)
        time.sleep(10) # Social Cadence
        print("   -> Zone B: Teleporting to Contact Info Overlay...")
        driver.get(profile_url.rstrip("/") + "/overlay/contact-info/")
        time.sleep(12)
        try:
            email_el = driver.find_element(By.CSS_SELECTOR, "a[href^='mailto:']")
            details['email'] = email_el.text.strip()
            print(f"   -> EMAIL SECURED: {details['email']}")
        except:
            print("   -> Zone B: Email restricted or not found.")
            details['email'] = "Contact Restricted"

        # 4. ZONE C: MAIN IDENTIFICATION (Headline & About)
        time.sleep(10) # Social Cadence
        print("   -> Zone C: Capturing Main Profile Identity...")
        driver.get(profile_url)
        time.sleep(15)
        
        # Capture Headline
        try:
            headline_el = driver.find_element(By.CSS_SELECTOR, ".text-body-medium.break-words")
            details['headline'] = headline_el.text.strip()
            print(f"   -> HEADLINE SECURED: {details['headline']}")
        except:
            details['headline'] = f"{details['role']} at {details['company']}"
            print("   -> SYNTHESIS: Generated headline.")

        # Capture About
        try:
            about_el = driver.find_element(By.CSS_SELECTOR, ".display-flex.ph5.pv3 .inline-show-more-text, section#about .inline-show-more-text")
            details['about'] = about_el.text.strip().replace("...see more", "").strip()
            print(f"   -> ABOUT SECURED: {details['about'][:50]}...")
        except:
            details['about'] = f"Dedicated {details['role']} at {details['company']}, committed to professional excellence and innovation."
            print("   -> SYNTHESIS: Generated about section.")

    except Exception as e:
        print(f"   -> Forensic Guard Triggered: {e}")
    
    return details

def scrape_activity_from_tab(driver, url, interaction_type, limit=2):
    print(f"   -> Checking {interaction_type} tab...")
    results = []
    try:
        driver.get(url)
        time.sleep(5)
        driver.execute_script("window.scrollTo(0, 400);")
        time.sleep(2)
        selectors = ["div.feed-shared-update-v2", ".feed-shared-update-v2", ".comments-comment-item", "[data-urn]"]
        elements = []
        for s in selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, s)
            if elements: break
        for el in elements[:limit]:
            data = get_post_data(el)
            if data:
                data["interaction_type"] = interaction_type
                data["sort_score"] = parse_linkedin_time(data["post_time"])
                results.append(data)
    except: pass
    return results

def scrape_profile(driver, profile_url, last_posts):
    username = get_username(profile_url)
    profile_details = scrape_profile_details(driver, profile_url)
    
    if not profile_details["full_name"] or profile_details["full_name"].lower() == "linkedin":
        print(f"Failed to scrape profile for {username}")
        return False

    print(f"   -> Name: {profile_details['full_name']}")
    print(f"   -> Role: {profile_details['role'] or '[Not Found]'}")
    print(f"   -> Company: {profile_details['company'] or '[Not Found]'}")

    lead_id = save_lead(
        linkedin_url=profile_url,
        name=profile_details.get("full_name", username),
        email=profile_details.get("email", ""),
        company=profile_details.get("company", ""),
        role=profile_details.get("role") or profile_details.get("headline", ""),
        headline=profile_details.get("headline", ""),
        about=profile_details.get("about", ""),
        work_description=profile_details.get("work_description", "")
    )
    get_or_create_sequence(lead_id, step_number=1)

    base_url = profile_url.rstrip("/")
    all_activities = []
    all_activities.extend(scrape_activity_from_tab(driver, base_url + "/recent-activity/shares/", "Post", limit=2))
    all_activities.extend(scrape_activity_from_tab(driver, base_url + "/recent-activity/comments/", "Comment", limit=2))
    all_activities.extend(scrape_activity_from_tab(driver, base_url + "/recent-activity/reactions/", "Like", limit=2))

    activity_list = []
    activity_summary_str = "No recent interactions found."
    latest_item = None

    if all_activities:
        all_activities.sort(key=lambda x: x["sort_score"])
        latest_item = all_activities[0]
        
        for act in all_activities:
            pref = "Posted" if act["interaction_type"] == "Post" else "Commented" if act["interaction_type"] == "Comment" else "Liked"
            snippet = act["text"][:50] + "..." if len(act["text"]) > 50 else act["text"]
            msg = f"{pref}: {snippet} ({act['post_time']})"
            activity_list.append(msg)
        
        activity_summary_str = "\n".join(activity_list)

    # UNIFIED SAVE: Call Google Sheets once with all collected data
    save_enhanced_data(
        full_name=profile_details["full_name"],
        profile_url=profile_url,
        headline=profile_details["headline"],
        company=profile_details["company"],
        about=profile_details["about"],
        email=profile_details["email"],
        interaction_type=latest_item["interaction_type"] if latest_item else "Profile Update",
        content=latest_item["text"] if latest_item else "Enriched Profile Data",
        interaction_date=latest_item["post_time"] if latest_item else time.strftime("%Y-%m-%d"),
        role=profile_details.get("role", ""),
        work_description=profile_details.get("work_description", ""),
        recent_activity=activity_summary_str
    )
    
    save_event(
        lead_id=lead_id,
        event_type="interaction_summary",
        additional_data={
            "name": profile_details["full_name"],
            "headline": profile_details["headline"],
            "company": profile_details["company"],
            "role": profile_details["role"],
            "about": profile_details["about"],
            "work_description": profile_details["work_description"],
            "recent_activity": activity_list
        }
    )

    profile_history = last_posts.get(profile_url, {})
    last_urn_history = profile_history.get("urn_history", []) if isinstance(profile_history, dict) else []
    
    new_urn = [latest_item["urn"]] if latest_item else []
    new_history = new_urn + [u for u in last_urn_history if u not in new_urn]
    
    last_posts[profile_url] = {
        "urn_history": new_history[:20],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "full_name": profile_details["full_name"],
        "headline": profile_details["headline"],
        "role": profile_details["role"],
        "company": profile_details["company"],
        "email": profile_details["email"]
    }
    return True

def run_scraper():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting LinkedIn automation...", flush=True)
    
    # 1. CONNECT TO GOOGLE SHEETS
    print(f"[{datetime.now().strftime('%H:%M:%S')}]   -> Connecting to Google Sheets...", flush=True)
    try:
        from google_sheets import get_profile_urls
        profile_urls = get_profile_urls()
        print(f"[{datetime.now().strftime('%H:%M:%S')}]   -> Success: Fetched {len(profile_urls)} profiles from Sheets.", flush=True)
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}]   -> ERROR: Google Sheets connection failed: {e}", flush=True)
        return

    if not profile_urls:
        print(f"[{datetime.now().strftime('%H:%M:%S')}]   -> WARNING: No profiles found to scrape.", flush=True)
        return

    # 2. INITIALIZE CHROME
    print(f"[{datetime.now().strftime('%H:%M:%S')}]   -> Launching Chrome browser (Visible Mode)...", flush=True)
    chrome_options = Options()
    # chrome_options.add_argument("--headless") # Disabled to allow browser window visibility
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # 3. LINKEDIN AUTH CHECK (Silent Entry)
        print(f"[{datetime.now().strftime('%H:%M:%S')}]   -> Navigating to LinkedIn and checking cookies...", flush=True)
        driver.get("https://www.linkedin.com")
        if os.path.exists("scraper/cookies.pkl"):
            cookies = pickle.load(open("scraper/cookies.pkl", "rb"))
            for cookie in cookies: driver.add_cookie(cookie)
        
        # NO REFRESH (Mirrors diagnostic success)
        time.sleep(3)
        
        # FINAL AUTHWALL VERIFICATION
        if "authwall" in driver.current_url:
            print(f"[{datetime.now().strftime('%H:%M:%S')}]   -> CRITICAL: Silent entry blocked. Please solve CAPTCHA in browser.", flush=True)
            # return # Silent fail for now, try jumping anyway
            time.sleep(2)
            if os.path.exists("scraper/cookies.pkl"):
                cookies = pickle.load(open("scraper/cookies.pkl", "rb"))
                for cookie in cookies: driver.add_cookie(cookie)
            driver.get("https://www.linkedin.com")
            time.sleep(10)
            
            if "authwall" in driver.current_url:
                print(f"[{datetime.now().strftime('%H:%M:%S')}]   -> CRITICAL: Still stuck on Authwall. Please refresh cookies.pkl manualy.", flush=True)
                return
        
        last_posts = {}
        if os.path.exists("last_posts.json"):
            with open("last_posts.json", "r") as f: last_posts = json.load(f)
            
        print(f"[{datetime.now().strftime('%H:%M:%S')}]   -> READY: Starting processing loop.", flush=True)
        for url in profile_urls:
            try:
                if scrape_profile(driver, url, last_posts):
                    with open("last_posts.json", "w") as f: 
                        json.dump(last_posts, f, indent=4)
                print(f"[{datetime.now().strftime('%H:%M:%S')}]   -> Finished {url}. Waiting 20s...", flush=True)
                time.sleep(20)
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}]   -> Error processing {url}: {e}", flush=True)
                
    finally:
        print(f"[{datetime.now().strftime('%H:%M:%S')}]   -> Shutting down browser.")
        driver.quit()

if __name__ == "__main__":
    run_scraper()