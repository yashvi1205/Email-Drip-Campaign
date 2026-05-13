"""Phase 1: Infrastructure layer (persistence, external services, technical implementations)

This layer contains:
- Database: SQLAlchemy models, session management
- Repositories: Concrete data access implementations
- Queue: Background job queue (RQ, celery, etc.)
- Integrations: External service adapters (Google Sheets, SMTP, webhooks)
- Security: JWT, API keys, password hashing
- Observability: Logging, tracing, metrics

The infrastructure layer depends on the domain and application layers
but the domain layer does not depend on it (dependency inversion).
"""
