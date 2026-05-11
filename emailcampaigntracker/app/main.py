import logging
from urllib.parse import urlparse

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes.auth import router as auth_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.diagnostics import router as diagnostics_router
from app.api.routes.health import router as health_router
from app.api.routes.leads import router as leads_router
from app.api.routes.profiles import router as profiles_router
from app.api.routes.scraper import router as scraper_router
from app.api.routes.tracking import router as tracking_router
from app.core.logging import setup_logging, get_logger
from app.core.auth import require_roles
from app.core.rate_limit import rate_limit
from app.core.errors import (
    http_exception_handler,
    starlette_http_exception_handler,
    unhandled_exception_handler,
)
from app.core.observability import setup_opentelemetry, setup_prometheus
from app.core.settings import get_settings
from app.middleware.request_context import (
    RequestIdMiddleware,
    RequestLoggingMiddleware,
)
from fastapi import HTTPException

# Load environment variables (local/dev convenience). Secrets still come from environment variables.
load_dotenv()

# 1. Initialize Standardized Logging (Phase 4)
setup_logging()
logger = get_logger("api")

settings = get_settings()  # fail-fast on invalid configuration

app = FastAPI(title="LinkedIn Scraper API")
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(RequestLoggingMiddleware, logger=logger)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting LinkedIn Scraper API...")
    logger.info("Environment: %s", settings.app_env)
    logger.info("Database Host: %s", urlparse(settings.database_url).hostname)
    logger.info("Redis Status: %s", "Enabled" if settings.redis_url else "Disabled")
    logger.info("CORS Origins: %s", ", ".join(settings.cors_allow_origins))
    
    # Internal callback validation
    logger.info("Internal Backend URL: %s", settings.backend_internal_url)
    if settings.n8n_webhook_url:
        logger.info("n8n Webhook Target: %s", settings.n8n_webhook_url)

setup_prometheus(app)
if settings.otel_enabled and settings.otel_exporter_otlp_endpoint:
    setup_opentelemetry(
        app,
        service_name=settings.otel_service_name,
        otlp_endpoint=settings.otel_exporter_otlp_endpoint,
    )

# Tracking endpoints: rate limiting (Phase 0)
tracking_rate_limit = rate_limit("tracking", settings.tracking_rate_limit_per_minute)
app.include_router(
    tracking_router,
    prefix="/api/tracking",
    dependencies=[Depends(tracking_rate_limit)],
)

# Scraper endpoints: rate limiting + API key protection (Phase 0)
scraper_rate_limit = rate_limit("scraper", settings.scraper_rate_limit_per_minute)
scraper_auth = require_roles("scraper", "admin")

# Dashboard endpoints: API key protection (Phase 0)
dashboard_auth = require_roles("dashboard", "admin")

# Feature routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(diagnostics_router)
app.include_router(profiles_router)
app.include_router(leads_router)
app.include_router(
    dashboard_router,
    dependencies=[Depends(dashboard_auth)]
)
app.include_router(
    scraper_router,
    dependencies=[Depends(scraper_rate_limit), Depends(scraper_auth)]
)







