import pickle
import os
import random
import time
from selenium import webdriver


def human_delay(min_time=2, max_time=5):
    time.sleep(random.uniform(min_time, max_time))


def get_driver():

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")

    driver = webdriver.Chrome(options=options)

    driver.get("https://www.linkedin.com")

    cookie_path = os.path.join(os.path.dirname(__file__), "cookies.pkl")

    cookies = pickle.load(open(cookie_path, "rb"))

    for cookie in cookies:
        driver.add_cookie(cookie)

    driver.refresh()

    human_delay(4, 7)

    return driver