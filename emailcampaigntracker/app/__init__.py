"""LinkedIn Scraper API - Backend Application

Clean Architecture Structure (Phase 1+):

app/
├── main.py                      # FastAPI application entry point
├── config/                      # Configuration management
│   └── settings.py (from core/)  # Environment-based configuration
├── api/                         # API layer (request/response handling)
│   ├── routes/                  # Route definitions by feature
│   │   ├── auth.py
│   │   ├── leads.py
│   │   ├── dashboard.py
│   │   ├── tracking.py
│   │   └── scraper.py
│   ├── dependencies.py          # FastAPI dependency injection
│   └── models.py (Pydantic)     # Request/response schemas
├── domain/                      # Business logic layer (independent of frameworks)
│   ├── entities.py             # Core domain objects (Lead, EmailSequence, etc.)
│   ├── value_objects.py        # Immutable value types
│   ├── exceptions.py           # Domain-specific exceptions
│   └── repositories.py         # Abstract repository interfaces
├── application/                # Application logic layer
│   ├── services/               # Application services (orchestrate domain logic)
│   │   ├── lead_service.py
│   │   ├── email_service.py
│   │   ├── dashboard_service.py
│   │   └── tracking_service.py
│   └── dto/                    # Data transfer objects
│       ├── requests.py
│       └── responses.py
├── infrastructure/             # Technical implementations
│   ├── database/               # Database access
│   │   ├── session.py          # SQLAlchemy session factory
│   │   └── models.py           # SQLAlchemy ORM models
│   ├── repositories/           # Concrete repository implementations
│   ├── queue/                  # Background job queue
│   ├── integrations/           # External service adapters
│   ├── security/               # Authentication and encryption
│   └── observability/          # Logging, tracing, metrics
├── core/                       # Shared utilities (being refactored)
│   ├── logging.py
│   ├── auth.py
│   ├── errors.py
│   └── ...
├── middleware/                 # HTTP middleware
│   ├── request_context.py
│   └── error_handler.py
└── workers/                    # Background workers

Dependency Flow (Dependency Rule):
- api/ depends on application/
- application/ depends on domain/
- domain/ has no dependencies on other layers
- infrastructure/ can be swapped without affecting domain/

This enforces testability and maintainability by ensuring
business logic is independent of technical implementations.
"""
