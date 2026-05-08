import os
import platform
import logging
import time
import uuid
from pathlib import Path
from typing import Optional, Generator
from contextlib import contextmanager

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app.core.settings import get_settings
from app.queue.redis_queue import get_redis_connection

logger = logging.getLogger("app.browser")

@contextmanager
def chrome_profile_lock(profile_name: str) -> Generator[bool, None, None]:
    """
    Distributed lock to prevent multiple workers from using the same Chrome profile.
    """
    settings = get_settings()
    redis = get_redis_connection()
    lock_key = f"lock:profile:{profile_name}"
    lock_value = str(uuid.uuid4())
    
    # TTL should be slightly longer than max job timeout
    ttl = settings.scraper_job_timeout_seconds + 300
    
    logger.info("Attempting to acquire lock for profile: %s", profile_name)
    acquired = redis.set(lock_key, lock_value, nx=True, ex=ttl)
    
    if not acquired:
        logger.error("Failed to acquire lock: Profile %s is already in use by another worker", profile_name)
        yield False
        return

    try:
        yield True
    finally:
        # Only delete if we still own the lock (compare value)
        current_val = redis.get(lock_key)
        if current_val and current_val.decode() == lock_value:
            redis.delete(lock_key)
            logger.info("Released lock for profile: %s", profile_name)

def get_browser_options() -> Options:
    settings = get_settings()
    options = Options()
    
    # 1. Binary Path (Docker/Custom support)
    if settings.chrome_binary_path:
        options.binary_location = settings.chrome_binary_path
        logger.info("Using custom Chrome binary: %s", settings.chrome_binary_path)

    # 2. Profile Management
    profile_dir = Path(settings.chrome_profile_base_path) / settings.linkedin_profile_name
    # Ensure directory exists (parent)
    profile_dir.parent.mkdir(parents=True, exist_ok=True)
    
    options.add_argument(f"--user-data-dir={profile_dir}")
    logger.info("Using Chrome profile: %s", profile_dir)

    # 3. Production Hardening Flags
    if settings.headless:
        options.add_argument("--headless=new")
        logger.info("Running in HEADLESS mode")

    options.add_argument(f"--window-size={settings.browser_window_size}")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Anti-detection: Real user agent (optional but safer)
    options.add_argument("--lang=en-US")
    
    return options

def create_driver() -> webdriver.Chrome:
    """Initializes and returns a production-ready ChromeDriver."""
    logger.info("Initializing Selenium Runtime (OS: %s)", platform.system())
    options = get_browser_options()
    
    try:
        # On Linux/Docker, we expect chromedriver in /usr/bin/chromedriver or managed by PATH
        driver = webdriver.Chrome(options=options)
        
        # Anti-detection: Patch navigator.webdriver
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        
        return driver
    except Exception as e:
        logger.error("Failed to start browser: %s", e)
        raise RuntimeError(f"Selenium Startup Failed: {e}")

def validate_session(driver: webdriver.Chrome) -> bool:
    """
    Checks if the current session is valid and logged into LinkedIn.
    Returns True if logged in, False if at login screen or challenged.
    """
    try:
        driver.get("https://www.linkedin.com/feed/")
        time.sleep(3) # Wait for redirects
        
        current_url = driver.current_url
        if "login" in current_url or "checkpoint" in current_url:
            logger.warning("Session invalid: Redirected to %s", current_url)
            return False
            
        # Look for common feed element
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "global-nav"))
        )
        logger.info("Session validated: Successfully authenticated.")
        return True
    except Exception as e:
        logger.warning("Session validation check failed: %s", e)
        return False

def check_browser_health() -> dict:
    """System health check for browser readiness."""
    settings = get_settings()
    return {
        "os": platform.system(),
        "profile_path": settings.chrome_profile_base_path,
        "headless": settings.headless,
        "binary": settings.chrome_binary_path or "system-default"
    }
