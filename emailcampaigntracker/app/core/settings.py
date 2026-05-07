import os
import json
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional
from urllib.parse import urlparse


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

    return Settings(
        database_url=database_url,
        cors_allow_origins=cors_allow_origins,
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
    )

