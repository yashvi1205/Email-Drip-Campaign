import os


def pytest_configure():
    # Phase 0 requires these env vars at import time.
    # We prefer .env values if they exist, so we only set defaults for non-sensitive keys.
    os.environ.setdefault("CORS_ALLOW_ORIGINS", "http://localhost:3000")
    os.environ.setdefault("API_KEY", "test-api-key")
    os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
    os.environ.setdefault("JWT_REFRESH_SECRET_KEY", "test-jwt-refresh-secret")
    os.environ.setdefault(
        "AUTH_USERS_JSON",
        '[{"username":"admin","password":"admin123","role":"admin"},{"username":"scraper","password":"scraper123","role":"scraper"},{"username":"dashboard","password":"dashboard123","role":"dashboard"}]',
    )
    os.environ.setdefault("TRACKING_SIGNING_SECRET", "test-tracking-signing-secret")

