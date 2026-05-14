import os
import json
import time
from scraper.scrape_automation import create_driver

def export():
    print("\n--- COOKIE EXPORTER ---")
    print("This will capture your LinkedIn session and save it for Docker.")
    
    driver = create_driver()
    try:
        driver.get("https://www.linkedin.com/login")
        print("\n👉 Please log in to LinkedIn in the browser window.")
        print("👉 Once you see your FEED, come back here and press ENTER.")
        input("\nPress ENTER when you are logged in and seeing your feed...")
        
        cookies = driver.get_cookies()
        with open("cookies.json", "w") as f:
            json.dump(cookies, f)
            
        print("\n✅ SUCCESS! 'cookies.json' has been created.")
        print("Now, Docker will use this file to log in automatically.")
    finally:
        driver.quit()

if __name__ == "__main__":
    export()
