import logging

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
from app.core.logging import configure_logging
from app.core.rate_limit import rate_limit
from app.core.errors import (
    http_exception_handler,
    starlette_http_exception_handler,
    unhandled_exception_handler,
)
from app.core.settings import get_settings
from app.middleware.request_context import (
    RequestIdMiddleware,
    RequestLoggingMiddleware,
    get_request_id,
)
from fastapi import HTTPException

# Load environment variables (local/dev convenience). Secrets still come from environment variables.
load_dotenv()

configure_logging(get_request_id)
logger = logging.getLogger("api")

settings = get_settings()  # fail-fast on invalid configuration

app = FastAPI(title="LinkedIn Scraper API")
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(RequestLoggingMiddleware, logger=logger)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tracking endpoints: rate limiting (Phase 0)
tracking_rate_limit = rate_limit("tracking", settings.tracking_rate_limit_per_minute)
app.include_router(
    tracking_router,
    prefix="/api/tracking",
    dependencies=[Depends(tracking_rate_limit)],
)

# Feature routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(diagnostics_router)
app.include_router(profiles_router)
app.include_router(leads_router)
app.include_router(dashboard_router)
app.include_router(scraper_router)

