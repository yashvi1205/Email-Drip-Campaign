import os


def pytest_configure():
    # Phase 0 requires these env vars at import time.
    # Tests provide safe defaults; DB connectivity is validated only when DB endpoints are exercised.
    os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/drip_campaign")
    os.environ.setdefault("CORS_ALLOW_ORIGINS", "http://localhost:3000")
    os.environ.setdefault("API_KEY", "test-api-key")

