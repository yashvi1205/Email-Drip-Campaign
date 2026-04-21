from selenium import webdriver
import pickle

driver = webdriver.Chrome()

driver.get("https://www.linkedin.com/login")

print("Login manually in the browser...")

input("Press ENTER after logging in...")

cookies = driver.get_cookies()

pickle.dump(cookies, open("cookies.pkl", "wb"))

print("Cookies saved successfully")

driver.quit()