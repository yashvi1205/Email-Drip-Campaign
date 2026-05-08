import os
import json
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load .env file at the earliest possible moment
load_dotenv()


def _require_env(name: str) -> str:
    val = os.getenv(name)
    if val is None or not str(val).strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return str(val).strip()


def _get_env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as e:
        raise RuntimeError(f"Invalid integer for {name}: {raw!r}") from e


def _parse_origins(raw: str) -> List[str]:
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if not origins:
        raise RuntimeError("CORS_ALLOW_ORIGINS must contain at least one origin")
    if any(o == "*" for o in origins):
        raise RuntimeError("CORS_ALLOW_ORIGINS must not contain '*' in production")
    return origins


@dataclass(frozen=True)
class Settings:
    database_url: str
    cors_allow_origins: List[str]

    # Networking
    backend_internal_url: str
    n8n_webhook_url: Optional[str]

    # Browser & Scraper Configuration (Phase 1)
    chrome_binary_path: Optional[str]
    chrome_profile_base_path: str
    linkedin_profile_name: str
    headless: bool
    browser_window_size: str

    # Temporary API keys (Phase 0)
    api_key: str
    dashboard_api_key: str
    scraper_api_key: str

    # Rate limiting (Phase 0)
    tracking_rate_limit_per_minute: int
    scraper_rate_limit_per_minute: int

    # Optional forwarding config used by tracking endpoints
    local_backend_url: Optional[str]
    render: bool
    jwt_secret_key: str
    jwt_refresh_secret_key: str
    jwt_algorithm: str
    jwt_access_token_exp_minutes: int
    jwt_refresh_token_exp_minutes: int
    auth_users_json: str
    require_signed_tracking: bool
    tracking_signing_secret: str

    # Scraper background jobs (Phase 3)
    redis_url: str
    scraper_queue_name: str
    scraper_job_timeout_seconds: int
    scraper_job_max_attempts: int
    scraper_job_retry_interval_seconds: int
    scraper_cancel_poll_seconds: int
    scraper_run_lock_ttl_seconds: int
    scraper_max_running_age_seconds: int
    app_env: str
    log_json: bool
    otel_enabled: bool
    otel_service_name: str
    otel_exporter_otlp_endpoint: Optional[str]


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def _validate_database_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise RuntimeError("DATABASE_URL must be a PostgreSQL URL (postgresql://...)")
    if not parsed.hostname:
        raise RuntimeError("DATABASE_URL must include a hostname")
    return _normalize_database_url(url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    database_url = _validate_database_url(_require_env("DATABASE_URL"))
    cors_allow_origins = _parse_origins(_require_env("CORS_ALLOW_ORIGINS"))

    # Default to localhost for dev, but require env for production/docker
    backend_internal_url = os.getenv("BACKEND_INTERNAL_URL", "http://localhost:8001").strip()
    n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL", "").strip() or None

    api_key = _require_env("API_KEY")
    dashboard_api_key = os.getenv("DASHBOARD_API_KEY", api_key).strip()
    scraper_api_key = os.getenv("SCRAPER_API_KEY", api_key).strip()
    if not dashboard_api_key:
        raise RuntimeError("DASHBOARD_API_KEY is empty (or API_KEY is empty)")
    if not scraper_api_key:
        raise RuntimeError("SCRAPER_API_KEY is empty (or API_KEY is empty)")

    tracking_rate = _get_env_int("TRACKING_RATE_LIMIT_PER_MINUTE", 120)
    scraper_rate = _get_env_int("SCRAPER_RATE_LIMIT_PER_MINUTE", 30)
    if tracking_rate <= 0:
        raise RuntimeError("TRACKING_RATE_LIMIT_PER_MINUTE must be > 0")
    if scraper_rate <= 0:
        raise RuntimeError("SCRAPER_RATE_LIMIT_PER_MINUTE must be > 0")

    local_backend_url = os.getenv("LOCAL_BACKEND_URL")
    render = bool(os.getenv("RENDER"))
    jwt_secret_key = _require_env("JWT_SECRET_KEY")
    jwt_refresh_secret_key = _require_env("JWT_REFRESH_SECRET_KEY")
    jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256").strip() or "HS256"
    access_exp = _get_env_int("JWT_ACCESS_TOKEN_EXP_MINUTES", 30)
    refresh_exp = _get_env_int("JWT_REFRESH_TOKEN_EXP_MINUTES", 60 * 24 * 7)
    if access_exp <= 0 or refresh_exp <= 0:
        raise RuntimeError("JWT token expiry values must be > 0")

    auth_users_json = _require_env("AUTH_USERS_JSON")
    try:
        parsed_users = json.loads(auth_users_json)
        if not isinstance(parsed_users, list) or not parsed_users:
            raise RuntimeError("AUTH_USERS_JSON must be a non-empty JSON array")
    except json.JSONDecodeError as e:
        raise RuntimeError("AUTH_USERS_JSON must be valid JSON") from e

    require_signed_tracking = os.getenv("REQUIRE_SIGNED_TRACKING", "false").lower() == "true"
    tracking_signing_secret = _require_env("TRACKING_SIGNING_SECRET")

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0").strip()
    scraper_queue_name = os.getenv("SCRAPER_QUEUE_NAME", "scraper").strip() or "scraper"
    scraper_job_timeout_seconds = _get_env_int("SCRAPER_JOB_TIMEOUT_SECONDS", 60 * 30)
    scraper_job_max_attempts = _get_env_int("SCRAPER_JOB_MAX_ATTEMPTS", 3)
    scraper_job_retry_interval_seconds = _get_env_int("SCRAPER_JOB_RETRY_INTERVAL_SECONDS", 30)
    scraper_cancel_poll_seconds = _get_env_int("SCRAPER_CANCEL_POLL_SECONDS", 2)
    scraper_run_lock_ttl_seconds = _get_env_int("SCRAPER_RUN_LOCK_TTL_SECONDS", 60 * 60)
    scraper_max_running_age_seconds = _get_env_int("SCRAPER_MAX_RUNNING_AGE_SECONDS", 45 * 60)

    if scraper_job_timeout_seconds <= 0:
        raise RuntimeError("SCRAPER_JOB_TIMEOUT_SECONDS must be > 0")
    if scraper_job_max_attempts <= 0:
        raise RuntimeError("SCRAPER_JOB_MAX_ATTEMPTS must be > 0")
    if scraper_job_retry_interval_seconds < 0:
        raise RuntimeError("SCRAPER_JOB_RETRY_INTERVAL_SECONDS must be >= 0")

    app_env = os.getenv("APP_ENV", "development").strip().lower()
    if app_env not in {"development", "staging", "production", "test"}:
        raise RuntimeError("APP_ENV must be one of development|staging|production|test")

    # Browser & Scraper Settings (Phase 1)
    chrome_binary_path = os.getenv("CHROME_BINARY_PATH", "").strip() or None
    
    # Default profile path varies by OS to keep things tidy
    import platform
    default_profile_base = "/app/data/browser" if platform.system() == "Linux" else r"C:\selenium-profile"
    chrome_profile_base_path = os.getenv("CHROME_PROFILE_BASE_PATH", default_profile_base).strip()
    
    linkedin_profile_name = os.getenv("LINKEDIN_PROFILE_NAME", "Default").strip()
    headless = os.getenv("HEADLESS", "true").lower() == "true"
    browser_window_size = os.getenv("BROWSER_WINDOW_SIZE", "1920,1080").strip()

    log_json = os.getenv("LOG_JSON", "false").lower() == "true"
    otel_enabled = os.getenv("OTEL_ENABLED", "false").lower() == "true"
    otel_service_name = os.getenv("OTEL_SERVICE_NAME", "emailcampaigntracker").strip()
    otel_exporter_otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip() or None

    return Settings(
        database_url=database_url,
        cors_allow_origins=cors_allow_origins,
        backend_internal_url=backend_internal_url,
        n8n_webhook_url=n8n_webhook_url,
        chrome_binary_path=chrome_binary_path,
        chrome_profile_base_path=chrome_profile_base_path,
        linkedin_profile_name=linkedin_profile_name,
        headless=headless,
        browser_window_size=browser_window_size,
        api_key=api_key,
        dashboard_api_key=dashboard_api_key,
        scraper_api_key=scraper_api_key,
        tracking_rate_limit_per_minute=tracking_rate,
        scraper_rate_limit_per_minute=scraper_rate,
        local_backend_url=local_backend_url.strip() if local_backend_url else None,
        render=render,
        jwt_secret_key=jwt_secret_key,
        jwt_refresh_secret_key=jwt_refresh_secret_key,
        jwt_algorithm=jwt_algorithm,
        jwt_access_token_exp_minutes=access_exp,
        jwt_refresh_token_exp_minutes=refresh_exp,
        auth_users_json=auth_users_json,
        require_signed_tracking=require_signed_tracking,
        tracking_signing_secret=tracking_signing_secret,
        redis_url=redis_url,
        scraper_queue_name=scraper_queue_name,
        scraper_job_timeout_seconds=scraper_job_timeout_seconds,
        scraper_job_max_attempts=scraper_job_max_attempts,
        scraper_job_retry_interval_seconds=scraper_job_retry_interval_seconds,
        scraper_cancel_poll_seconds=scraper_cancel_poll_seconds,
        scraper_run_lock_ttl_seconds=scraper_run_lock_ttl_seconds,
        scraper_max_running_age_seconds=scraper_max_running_age_seconds,
        app_env=app_env,
        log_json=log_json,
        otel_enabled=otel_enabled,
        otel_service_name=otel_service_name,
        otel_exporter_otlp_endpoint=otel_exporter_otlp_endpoint,
    )

