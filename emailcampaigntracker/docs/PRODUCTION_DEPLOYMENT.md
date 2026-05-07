# Production Deployment Guide

This document describes a simple, reliable deployment topology for `emailcampaigntracker`.

## Topology

- `frontend` (Nginx static assets, port `8080`)
- `backend` (FastAPI + Alembic startup migration, port `8001`)
- `worker` (RQ worker for scraper jobs)
- `postgres` (primary database)
- `redis` (queue + short-lived coordination state)

All services are orchestrated by `docker-compose.yml`.

## Containers & Responsibilities

- **backend**
  - serves API endpoints
  - exposes `/api/health`, `/api/health/readiness`, `/metrics`
  - runs `alembic upgrade head` at startup
- **worker**
  - executes queued scraper jobs
  - handles retries/timeouts/cancellations
- **frontend**
  - serves React static build (no runtime app behavior changes)
- **postgres**
  - persistent relational data (`leads`, `events`, `email_sequences`, `scraper_jobs`)
- **redis**
  - RQ queue backend
  - distributed lock for duplicate scraper-run protection

## Monitoring & Observability

- **Request metrics:** Prometheus endpoint at `/metrics` (backend)
- **Request tracing:** OpenTelemetry FastAPI instrumentation (enable with `OTEL_ENABLED=true`)
- **Structured logs:** set `LOG_JSON=true` for JSON logs
- **Readiness:** `/api/health/readiness` validates DB/Redis/queue
- **Queue visibility:** `/api/health/queue` and `/api/scraper/queue/status`
- **Worker visibility:** `/api/health/workers`

## Environment Setup (Production)

Use `.env.example` as baseline. Minimum production changes:

- use strong secrets for:
  - `JWT_SECRET_KEY`
  - `JWT_REFRESH_SECRET_KEY`
  - `TRACKING_SIGNING_SECRET`
  - API keys
- set `APP_ENV=production`
- set `LOG_JSON=true`
- provide real `DATABASE_URL` and `REDIS_URL`
- enable tracing if collector exists:
  - `OTEL_ENABLED=true`
  - `OTEL_EXPORTER_OTLP_ENDPOINT=<collector-endpoint>`

## CI/CD Flow

GitHub Actions workflow `.github/workflows/ci.yml` runs:

1. backend dependency install
2. migration validation (`alembic upgrade head`)
3. backend compile/lint check
4. backend tests (`pytest`)
5. frontend install
6. frontend lint (`npm run lint`)
7. frontend build (`npm run build`)

## Scaling Strategy

- Scale API horizontally with multiple `backend` replicas behind a load balancer
- Scale workers independently based on queue length and processing latency
- Keep Redis and Postgres managed/high-availability in production
- Use queue depth + worker count + job latency as autoscaling signals

## Rollback Strategy

- Deploy image tags (immutable) per release
- Rollback by redeploying previous backend/frontend/worker image tags
- Keep Alembic migrations forward-safe and additive where possible
- For risky DB changes: deploy code that supports both old/new schema, migrate, then clean up later

