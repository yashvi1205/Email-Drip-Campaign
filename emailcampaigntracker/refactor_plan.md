# Refactoring Blueprint (FastAPI + React) — `emailcampaigntracker`

## 1. Executive Summary

### Overall health
This repository is **functional but not production-grade**. It has strong “single-developer prototype” traits: business logic, integration code (Google Sheets), persistence, caching, and orchestration are all embedded directly inside the API entrypoints. The frontend is effectively a **single-page, single-component app** with hardcoded environment values.

The fastest path to a maintainable production system is a **stabilize → modularize → secure → observe → scale** sequence, with explicit API contracts and consistent persistence patterns.

### Top 10 critical issues (highest impact / risk)
1. **Secret handling is unsafe**: `.env` and `credentials.json` exist in repo root; `google_sheets.py` falls back to reading `credentials.json`. This is a major breach risk.
2. **Hardcoded DB credentials fallback**: `database/db.py` uses a literal Postgres URL if `DATABASE_URL` is missing.
3. **No authentication or authorization**: operational endpoints (e.g., `/api/scrape`, dashboards) and tracking endpoints are unauthenticated.
4. **Permissive CORS**: backend allows all origins/methods/headers; this is a default-prod footgun.
5. **Unsafe process orchestration from HTTP**: `/api/scrape` spawns a subprocess via `subprocess.Popen` inside request handling—no job model, no queue, no access control, no throttle.
6. **Mixed database access patterns**: ORM `SessionLocal` and raw psycopg2 `get_db_conn()` are used in the same system, with inconsistent transactions and concurrency behavior.
7. **Async misuse and blocking I/O in async endpoints**: `api/tracking.py` uses `async def` endpoints but performs blocking DB operations and spawns threads inside requests.
8. **Schema drift / inconsistencies**: code references sequence fields (e.g., open/click counters and timestamps) not represented in `database/models.py`—indicates DB schema/ORM mismatch risk.
9. **No API contracts**: responses are ad-hoc dicts/lists; no Pydantic request/response models, no consistent error format, no versioning.
10. **Frontend monolith and hardcoded runtime config**: `frontend/src/App.jsx` contains UI, orchestration, polling, view routing, and API calls with `API_BASE='http://localhost:8001/api'`.

---

## 2. Target Architecture (Future State)

### Backend target architecture (FastAPI; layered + modular)
**Goal**: isolate HTTP concerns from business logic, isolate business logic from persistence, isolate persistence from external integrations.

#### Recommended layers
- **API layer** (`app/api`): routers, dependencies, request/response models, HTTP error mapping.
- **Application services** (`app/services`): use cases orchestrating work (e.g., “log tracking event”, “compute drip dashboard”).
- **Domain** (`app/domain`): enums + policies (e.g., status derivation rules, event types).
- **Repositories** (`app/repositories`): DB access behind interfaces; no SQL in routers.
- **Integrations** (`app/integrations`): Google Sheets, scraper job runner.
- **Core** (`app/core`): settings, logging, security primitives, error codes.
- **Middleware** (`app/middleware`): request-id, logging, auth, CORS.

#### Non-negotiable target properties
- **Single DB access strategy**: choose SQLAlchemy 2.x (sync or async) and remove raw psycopg2 access from request paths.
- **Explicit contracts**: Pydantic v2 schemas for every endpoint input/output.
- **Secure by default**: authn/authz for operational endpoints, signed tokens + rate limiting for public tracking endpoints.
- **Observable by default**: JSON logs, correlation IDs, tracing (OpenTelemetry).

### Frontend target architecture (React; feature-based)
**Goal**: split app by business capabilities, use a dedicated API/data layer, and standardize state management.

#### Recommended structure
- **Features** (`src/features/*`): `monitor`, `drip`, `scraper`, `auth`.
- **Shared** (`src/shared/*`): reusable UI components, formatting utilities, generic hooks, types.
- **Services** (`src/services/*`): HTTP client, API modules.
- **Routes** (`src/app/routes/*`): router configuration + code splitting boundaries.

#### Recommended tech upgrades (pragmatic 2025 baseline)
- Data fetching/state: **TanStack Query** (query caching, polling, dedupe)
- Routing: **React Router** (or TanStack Router)
- Forms + validation: **React Hook Form + Zod**
- Testing: **Vitest + React Testing Library**, E2E: **Playwright**

---

## 3. Refactoring Strategy (Phased Plan)

### Phase 0 – Safety & Baseline (stabilize, reduce incident risk)
**Outcome**: no secrets in repo; fail-fast config; basic observability; minimal tests; guardrails on high-risk endpoints.

- **Secrets & credential hygiene**
  - Remove `.env` and `credentials.json` from git tracking; rotate all leaked secrets.
  - Stop runtime fallback to `credentials.json` in production; require env-injected credentials or secret manager integration.
- **Configuration**
  - Introduce validated Settings object; app should **fail fast** if `DATABASE_URL` or required secrets are missing.
  - Remove hardcoded DB fallback in `database/db.py`.
- **Logging**
  - Implement structured JSON logging; add request-id middleware; log inbound requests and response status/latency.
- **Security guardrails**
  - Add temporary API-key guard for `/api/scrape` and dashboards.
  - Add rate limiting on tracking endpoints (`/api/tracking/*`) and scraper trigger.
  - Restrict CORS origins to known hosts; keep permissive only in local dev.
- **Tests (beachhead)**
  - Backend: smoke tests for `/api/health`, one tracking call, one dashboard call (seeded DB or mocked repository).
  - Frontend: a single render test + mocked API responses.

### Phase 1 – Structural Refactor (boundaries, naming, module layout)
**Outcome**: codebase becomes navigable; routers/services/integrations separated; no behavior changes beyond wiring.

- **Backend**
  - Convert to proper `app/` package; remove `sys.path.append(...)` hacks.
  - Split `api/main.py` into:
    - `app/main.py` (app factory, middleware, router registration)
    - `app/api/routes/*` (health, profiles, leads, dashboard, tracking, scraper)
  - Extract Google Sheets code into `app/integrations/google_sheets/*`.
  - Extract scraper orchestration into `app/integrations/scraper/*` (still subprocess initially, but behind an interface).
  - Introduce consistent response envelope and error model (see standards below).
- **Frontend**
  - Split `frontend/src/App.jsx` into feature pages/components.
  - Add `services/httpClient` + `services/api/*` modules; no raw axios calls inside UI components.
  - Introduce basic route structure even if only two pages initially (`/monitor`, `/drip`).

### Phase 2 – Backend Improvements (auth, DI, schemas, DB)
**Outcome**: production-grade API layer, consistent DB access, correct async behavior, hardened endpoints.

- **Auth & authorization**
  - Implement JWT (access + refresh) for operators/admin.
  - Add RBAC permissions; protect dashboards and scraper operations.
  - For tracking endpoints: implement **signed tracking tokens** (HMAC) + expiry to prevent event spam.
- **Schemas and validation**
  - Create Pydantic request/response models for every endpoint.
  - Replace ad-hoc `dict` inputs (e.g., update-status) with explicit models.
- **Database**
  - Choose a single approach: SQLAlchemy 2.x with one-session-per-request.
  - Add Alembic migrations; align DB schema with features (sequence counters and timestamps).
  - Eliminate N+1 patterns in dashboard queries by using aggregates/joins.
- **Async correctness**
  - If endpoints remain async, use async DB stack; otherwise keep endpoints sync.
  - Remove thread spawning from request handlers; use BackgroundTasks or a queue.

### Phase 3 – Frontend Improvements (state, architecture, API layer)
**Outcome**: maintainable feature modules with predictable data flows and minimal re-render overhead.

- Introduce TanStack Query for:
  - profiles raw data polling
  - drip dashboard polling
  - scraper status polling (prefer job-based)
- Add a typed API layer and standardize error handling in UI.
- Add routing + code splitting at route boundaries.
- Improve performance with memoization + virtualization if profile lists grow.

### Phase 4 – Cross-Cutting Enhancements (logging, errors, config)
**Outcome**: consistent engineering quality and operations readiness.

- Global exception handlers; stable error codes; no raw exception leakage.
- Correlation IDs across backend and frontend; surface `request_id` in UI error displays.
- Documented API contracts; consider OpenAPI → TypeScript client generation.

### Phase 5 – Performance & Scalability (caching, async optimization, load handling)
**Outcome**: controlled DB load, predictable latencies, safe public endpoints.

- Introduce Redis caching for heavy read endpoints (short TTL).
- Move sheet sync to queued jobs with batching and retries.
- Optimize dashboard queries; add indexes for `events` and `email_sequences`.
- Harden tracking endpoints with token+IP rate limiting and abuse detection.

### Phase 6 – DevOps & Production Readiness (Docker, CI/CD, observability)
**Outcome**: reproducible builds/deployments, automated quality gates, monitoring/alerts.

- Dockerize backend/frontend; docker-compose for local dev (DB + cache + workers).
- CI pipeline: lint + unit tests + integration tests + build.
- OpenTelemetry instrumentation; dashboards and alerts on error rates, queue depth, and latency.

---

## 4. Recommended Folder Structures

### Backend (FastAPI)
```text
app/
  api/
    routes/
      health.py
      profiles.py
      leads.py
      dashboard.py
      tracking.py
      scraper.py
    deps.py
  core/
    settings.py
    logging.py
    security.py
    errors.py
  models/
    lead.py
    event.py
    email_sequence.py
  schemas/
    common.py
    lead.py
    event.py
    email_sequence.py
    tracking.py
    dashboard.py
  services/
    tracking_service.py
    dashboard_service.py
    scraper_service.py
  repositories/
    lead_repo.py
    event_repo.py
    sequence_repo.py
  db/
    session.py
    migrations/
  middleware/
    request_id.py
    logging.py
    auth.py
    rate_limit.py
  integrations/
    google_sheets/
      client.py
      sync.py
    scraper/
      runner.py
main.py
tests/
  unit/
  integration/
```

### Frontend (React)
```text
src/
  app/
    App.tsx
    routes/
      index.tsx
    providers/
      queryClient.ts
  features/
    monitor/
      api/
      components/
      hooks/
      pages/
      types.ts
    drip/
      api/
      components/
      hooks/
      pages/
      types.ts
    scraper/
      api/
      components/
      hooks/
      types.ts
  shared/
    components/
    hooks/
    lib/
      httpClient.ts
      env.ts
      format.ts
    styles/
    types/
  services/
    api/
  routes/
  components/
  hooks/
tests/
```

---

## 5. Coding Standards

### Naming conventions
- **Backend**
  - Files/modules: `snake_case.py`
  - Classes: `PascalCase`
  - Functions/variables: `snake_case`
  - API path: `/api/v1/...` (introduce versioning early)
- **Frontend**
  - Components: `PascalCase.tsx`
  - Hooks: `useXyz`
  - Feature modules: `kebab-case` or `camelCase` (pick one and enforce)

### File organization rules
- No DB access in routers; routers call services; services use repositories.
- No external integration calls in routers; integrations live under `app/integrations`.
- No `print()` in production paths; use structured logging only.
- Frontend UI components do not call axios directly; use API hooks/services.
- No hardcoded URLs; all runtime endpoints use environment config.

### API response format (standard)
- **Success**
  - `{ "data": <payload>, "meta": { "request_id": "...", "version": "v1" } }`
- **Error**
  - `{ "error": { "code": "AUTH_001", "message": "...", "details": {...} }, "meta": { "request_id": "...", "version": "v1" } }`

### Error format standard
- Stable error codes by domain: `AUTH_*`, `DB_*`, `TRACK_*`, `SHEETS_*`, `SCRAPER_*`.
- Never return raw exception strings in prod responses.
- Always include `request_id` for debugging.

### Logging format
Structured JSON fields:
- `timestamp`, `level`, `service`, `env`, `request_id`, `method`, `path`, `status_code`, `latency_ms`, `user_id` (if applicable)

---

## 6. Authentication & Security Plan

### JWT/OAuth strategy
- **Phase 2 baseline**: JWT access + refresh for UI operators/admin.
- **Storage**: prefer HttpOnly cookies for refresh; access tokens in memory (or cookie-based sessions if preferred).
- **OAuth**: optional later (Google/Microsoft) if operator SSO is needed.

### Role-based access control (RBAC)
Roles:
- `admin`: full access
- `operator`: run scraper, view dashboards, manage leads
- `viewer`: read-only dashboards

Permissions examples:
- `scraper:run`, `scraper:view`
- `dashboard:read`
- `leads:read`, `leads:write`
- `tracking:read`

### Secure headers
- HSTS (prod), `X-Content-Type-Options: nosniff`, `Referrer-Policy`, CSP as appropriate.
- Cookies: `Secure`, `HttpOnly`, `SameSite=Lax/Strict` as required.

### Rate limiting
- Tracking endpoints: per-IP + per-token + per-tracking-id limits (Redis-backed).
- Scraper trigger: strict limits + audit logs.

### Input validation
- Pydantic models for all request bodies/params where non-trivial.
- Size limits for payloads; timeouts for outbound HTTP calls.

### Specific anti-patterns to remove (from current repo)
- Wildcard CORS in production.
- Any “read credentials.json from disk” fallback.
- Subprocess spawning from HTTP without authorization and job model.
- Async routes performing blocking DB work.

---

## 7. Logging & Monitoring Plan

### Structured logging (JSON)
- Add request-id middleware; propagate `X-Request-Id` to downstream calls.
- Add audit logs for:
  - scraper runs (start/stop/failure)
  - lead status changes
  - tracking events (aggregated counters, not raw PII spam)

### Correlation IDs
- Backend generates `request_id` if missing.
- Frontend reads `request_id` from responses and includes it when reporting errors.

### Tools
- **Logs**: ELK/OpenSearch (self-hosted) or managed logging.
- **Tracing/Metrics**: OpenTelemetry → Prometheus/Grafana (or hosted APM).
- Alerts on:
  - error rate spikes
  - latency regressions (p95)
  - job queue depth/failures

---

## 8. Testing Strategy

### Backend (pytest)
Structure:
- `tests/unit`: services, token signing/verification, policy logic.
- `tests/integration`: API routes with DB (migrations applied).

Minimum tests to add first:
- `/api/health` returns 200 and expected payload structure.
- One tracking endpoint logs an event (using a test DB or mocked repository).
- `/api/dashboard/drip` returns stable shape with seeded rows.

Recommended tooling:
- `pytest`, `httpx` test client, `testcontainers` (Postgres) for integration tests.

### Frontend (unit + integration)
- Vitest + React Testing Library.
- Mock API with MSW.
- Minimum test:
  - renders app and shows “loading → loaded” states with mocked responses.

### E2E recommendations
- Playwright:
  - monitor page load and profile cards render
  - drip dashboard renders with status badges

---

## 9. Migration Risks & Mitigation

### Risks
- **Secrets already leaked**: requires immediate rotation; may require git history rewrite to fully remediate.
- **DB schema drift**: code references fields not represented in ORM model; risk of breaking tracking/dashboard logic during cleanup.
- **Tracking correctness**: status derivation is entangled with DB updates and sheet sync; easy to introduce regressions.
- **Scraper runtime constraints**: Selenium profile/cookies rely on local filesystem; production execution needs isolation.

### Mitigation
- Add observability before major refactors (request-id + JSON logs + error codes).
- Use Alembic migrations with rollbacks; DB backups before releases.
- Strangler pattern: introduce `/api/v1` alongside existing endpoints; migrate frontend gradually.
- Feature flags for new auth and job orchestration.

---

## 10. Step-by-Step Execution Plan (small, implementable tasks)

### Phase 0 – Safety & Baseline
1. Remove `.env` and `credentials.json` from git tracking; rotate all secrets and regenerate service account key(s).
2. Update `.gitignore` to exclude secrets, cookie jars (`cookies.pkl`), logs (`*.log`, `requests.log`), and local artifacts.
3. Add a validated `Settings` layer; fail fast on missing `DATABASE_URL`, `JWT_SECRET`, `TRACKING_HMAC_SECRET`, and required `GOOGLE_*`.
4. Remove hardcoded DB URL fallback from `database/db.py`; ensure startup fails clearly if DB config missing.
5. Add request-id middleware and structured JSON logging (no `print()` in request paths).
6. Add temporary API-key guard for `/api/scrape` and `/api/dashboard/*` endpoints.
7. Add rate limiting for `/api/tracking/*` endpoints and scraper trigger.
8. Add backend smoke tests: health, one tracking call, one dashboard call (seed DB or mock repositories).
9. Add frontend test: render app + mocked API responses; verify it transitions out of loading and shows expected UI elements.

### Phase 1 – Structural Refactor
10. Create `app/` package; move FastAPI initialization to `app/main.py`; remove `sys.path` manipulation.
11. Split routes into `app/api/routes/*`; keep old route paths stable initially.
12. Introduce Pydantic schemas and standard response envelope across endpoints.
13. Extract Google Sheets and scraper orchestration behind `integrations` interfaces.
14. Frontend: create `services/httpClient` and move API calls out of UI components; split `App.jsx` into feature pages.

### Phase 2 – Backend Improvements
15. Implement JWT auth + RBAC and protect operational endpoints.
16. Implement signed tracking tokens + expiry; enforce on tracking endpoints.
17. Standardize DB access via repositories; remove psycopg2 usage from request paths.
18. Add Alembic migrations; reconcile `EmailSequence` counters/timestamps schema.
19. Move sheet sync and scraper execution to a job system (queue + worker).

### Phase 3 – Frontend Improvements
20. Add routing (`/monitor`, `/drip`) with layout shell.
21. Introduce TanStack Query; replace manual polling with query refetch intervals.
22. Add centralized error handling and request-id surfacing in the UI.
23. Add modular feature folders and shared component library.

### Phase 4 – Cross-Cutting Enhancements
24. Add global exception handlers with stable error codes.
25. Publish versioned OpenAPI and optionally generate a typed TS client.
26. Add audit logs for security-critical operations.

### Phase 5 – Performance & Scalability
27. Optimize dashboard DB queries to avoid N+1 counts; add proper indexes.
28. Add Redis caching to heavy endpoints with TTL.
29. Batch and retry sheet sync jobs; add dead-letter handling.

### Phase 6 – DevOps & Production Readiness
30. Add Dockerfiles and docker-compose (Postgres + Redis + worker) for local dev parity.
31. Add CI workflows for lint/tests/build and migration checks.
32. Add OpenTelemetry export + dashboards + alerts.

