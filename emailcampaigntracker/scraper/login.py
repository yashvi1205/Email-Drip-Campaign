from selenium import webdriver
import pickle
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("scraper.login")

driver = webdriver.Chrome()

driver.get("https://www.linkedin.com/login")

logger.info("Login manually in the browser...")

input("Press ENTER after logging in...")

cookies = driver.get_cookies()

pickle.dump(cookies, open("cookies.pkl", "wb"))

logger.info("Cookies saved successfully")

driver.quit()

