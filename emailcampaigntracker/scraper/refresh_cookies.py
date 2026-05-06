import pickle
import os
import time
from selenium import webdriver
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("scraper.refresh_cookies")

def refresh_cookies():
    cookie_path = os.path.join(os.path.dirname(__file__), "cookies.pkl")
    
    # Initialize driver
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)
    
    logger.info("--- LinkedIn Cookie Refresher ---")
    logger.info("1. Please log in manually in the browser that just opened.")
    logger.info("2. Once you are logged in and see your LinkedIn home feed, come back here.")
    logger.info("3. Press Enter to save your new session cookies.")
    
    driver.get("https://www.linkedin.com/login")
    
    input("\nPress Enter after you have logged in and are on the Home Feed...")
    
    # Save cookies
    cookies = driver.get_cookies()
    with open(cookie_path, "wb") as f:
        pickle.dump(cookies, f)
    
    logger.info("SUCCESS: Cookies saved to %s", cookie_path)
    logger.info("You can now close the browser and run the scraper again.")
    
    driver.quit()

if __name__ == "__main__":
    refresh_cookies()
