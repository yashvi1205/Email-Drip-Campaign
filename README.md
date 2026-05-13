# LinkedIn Email Campaign Tracker

A production-ready full-stack application for tracking LinkedIn profiles and managing email drip campaigns. Built with modern best practices including clean architecture, TypeScript, Docker, and Kubernetes support.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Local Development](#local-development)
- [Production Deployment](#production-deployment)
- [Configuration](#configuration)
- [Testing](#testing)
- [Monitoring & Observability](#monitoring--observability)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Overview

LinkedIn Email Campaign Tracker is a comprehensive system for:
- **LinkedIn Profile Scraping**: Automatically track LinkedIn profiles
- **Email Campaigns**: Manage drip email sequences
- **Contact Management**: Store and track contact information
- **Engagement Tracking**: Monitor email opens, clicks, and replies
- **Analytics Dashboard**: View campaign metrics and performance

### Key Features

✅ **Clean Architecture** - Separated concerns with domain, application, and infrastructure layers
✅ **Type-Safe** - Full TypeScript on frontend, type hints throughout backend
✅ **Scalable** - Horizontal scaling with load balancing and auto-scaling
✅ **Monitored** - Built-in logging, metrics, and health checks
✅ **Secure** - JWT authentication, bcrypt hashing, HTTPS/TLS support
✅ **Cached** - Redis caching with automatic invalidation
✅ **Optimized** - Code splitting, query optimization, connection pooling
✅ **Production-Ready** - Docker, Kubernetes, CI/CD, monitoring setup

## Architecture

### Technology Stack

**Backend**
- Python 3.11
- FastAPI (async web framework)
- SQLAlchemy (ORM)
- PostgreSQL (relational database)
- Redis (caching layer)
- Alembic (database migrations)

**Frontend**
- React 19
- TypeScript
- Vite (build tool)
- TailwindCSS (styling)
- React Query (data fetching)
- React Router (routing)

**Infrastructure**
- Docker & Docker Compose
- Nginx (reverse proxy)
- Kubernetes (optional)
- GitHub Actions (CI/CD)

### System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Client (Browser)                      │
│                 React + TypeScript App                   │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  Nginx Reverse Proxy                     │
│              (Load Balancing, Caching, TLS)              │
└────────────────────────┬────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
    ┌────────┐     ┌────────┐     ┌────────┐
    │  API   │     │  API   │     │  API   │
    │Instance│     │Instance│     │Instance│
    │   #1   │     │   #2   │     │   #3   │
    └────┬───┘     └───┬────┘     └────┬───┘
         │             │              │
         └─────────────┼──────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
    ┌────────┐   ┌────────┐   ┌────────────┐
    │ postgres│   │ Redis  │   │ Monitoring │
    │   DB    │   │ Cache  │   │  (Metrics) │
    └────────┘   └────────┘   └────────────┘
```

## Prerequisites

### Local Development

- **Docker** 20.10+
- **Docker Compose** 2.0+
- **Git** 2.30+
- **Node.js** 20+ (optional, for frontend-only development)
- **Python** 3.11+ (optional, for backend-only development)

### Production

- **Docker** 20.10+
- **PostgreSQL** 15+ (managed service or self-hosted)
- **Redis** 7+ (managed service or self-hosted)
- **Nginx** or load balancer
- **4GB+ RAM**, **2+ CPU cores** minimum

## Quick Start

### Option 1: Docker Compose (Recommended) - macOS/Linux/Windows

**Requirements**: Docker Desktop 4.0+ (includes Docker Compose)

```bash
# Navigate to the project directory
cd emailcampaigntracker

# Start all services (PostgreSQL, Redis, API, Frontend)
# Modern syntax (Docker Desktop 4.0+) - works on all platforms
docker compose up -d

# Run migrations (apply database schema)
docker compose exec api alembic upgrade head

# View logs in real-time
docker compose logs -f

# View logs for specific service
docker compose logs -f api      # API logs
docker compose logs -f db       # Database logs
docker compose logs -f redis    # Redis logs
docker compose logs -f frontend # Frontend logs

# Stop all services
docker compose down

# Stop and remove data (clean slate)
docker compose down -v
```

**macOS/Linux Troubleshooting**: If `docker compose` command not found:
- Upgrade Docker Desktop to 4.0+
- Or use legacy syntax: `docker-compose up -d` (requires separate installation)
- Check: `docker --version` should be 20.10+

**Windows PowerShell**: Use the same commands above. If `docker compose` fails:
- Restart Docker Desktop
- Or use Docker Desktop UI instead

**Services will be available at**:
- **Frontend**: http://localhost:5173
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs
- **API Health**: http://localhost:8000/health/status
- **Database**: localhost:5432 (user: `emailcampaign`, password: `emailcampaign_dev_pass`)
- **Redis**: localhost:6379

### Option 2: Manual Setup (Local Development)

See [Local Development](#local-development) section below.

## Local Development

### Backend Setup

```bash
cd emailcampaigntracker

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env

# Start PostgreSQL and Redis (using Docker)
docker run -d -p 5432:5432 \
  -e POSTGRES_USER=emailcampaign \
  -e POSTGRES_PASSWORD=dev_pass \
  -e POSTGRES_DB=emailcampaign \
  postgres:15-alpine

docker run -d -p 6379:6379 redis:7-alpine

# Run migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API will be available at http://localhost:8000

### Frontend Setup

```bash
cd emailcampaigntracker/frontend

# Install dependencies
npm install

# Set up environment
echo "VITE_API_BASE_URL=http://localhost:8000/api/" > .env.local

# Start dev server
npm run dev
```

Frontend will be available at http://localhost:5173

### Development with Docker Compose

```bash
# Start development environment
docker compose up -d
# Legacy: docker-compose up -d

# View logs (all services)
docker compose logs -f
# Legacy: docker-compose logs -f

# View logs for specific service
docker compose logs -f api
# Legacy: docker-compose logs -f api

# Run migrations
docker compose exec api alembic upgrade head
# Legacy: docker-compose exec api alembic upgrade head

# Access services
# - Frontend: http://localhost:5173
# - API: http://localhost:8000
# - Database: localhost:5432 (user: emailcampaign, password: emailcampaign_dev_pass)
# - Redis: localhost:6379

# Stop services
docker compose down
# Legacy: docker-compose down

# Remove containers and volumes (clean slate)
docker compose down -v
```

### Running Tests

```bash
# Backend tests
cd emailcampaigntracker
pytest tests/ -v --cov=app

# Frontend tests (TypeScript, linting)
cd frontend
npm run lint
npx tsc --noEmit
```

## Production Deployment

### Option 1: Docker Compose (Single Server)

```bash
# Navigate to project directory
cd emailcampaigntracker

# Create environment file
cp .env.production.example .env.production
# Edit .env.production with production values

# Build application image
docker build -t emailcampaign-api:latest .

# Start services using docker compose
docker compose -f docker-compose.prod.yml up -d
# Legacy: docker-compose -f docker-compose.prod.yml up -d

# Run database migrations
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
# Legacy: docker-compose -f docker-compose.prod.yml exec api alembic upgrade head

# View logs
docker compose -f docker-compose.prod.yml logs -f api
# Legacy: docker-compose -f docker-compose.prod.yml logs -f api

# Check service health
curl http://localhost:8000/health/status

# For HTTPS:
curl https://your-domain.com/health/status

# Stop services
docker compose -f docker-compose.prod.yml down
# Legacy: docker-compose -f docker-compose.prod.yml down
```

**Important Notes**:
- Run all commands from the `emailcampaigntracker/` directory
- Use `docker compose` (modern, all platforms) or `docker-compose` (legacy)

### Option 2: Kubernetes (Cloud-Native)

```bash
# Create namespace
kubectl create namespace production

# Create secrets
kubectl create secret generic emailcampaign-secrets \
  --from-literal=database-url=$DATABASE_URL \
  --from-literal=redis-url=$REDIS_URL \
  --from-literal=secret-key=$SECRET_KEY \
  -n production

# Deploy application
kubectl apply -f k8s/deployment.yaml

# Check rollout status
kubectl rollout status deployment/emailcampaign-api -n production

# View pods
kubectl get pods -n production

# View logs
kubectl logs -f deployment/emailcampaign-api -n production
```

### Option 3: AWS ECS/Fargate

```bash
# Push to ECR
aws ecr get-login-password | docker login \
  --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com

docker tag emailcampaign-api:latest \
  $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/emailcampaign:latest

docker push \
  $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/emailcampaign:latest

# Update ECS service
aws ecs update-service \
  --cluster production \
  --service emailcampaign \
  --force-new-deployment
```

### Environment Configuration

Create `.env.production` with:

```env
# Database
DATABASE_URL=postgresql://user:password@db-host:5432/emailcampaign

# Redis
REDIS_URL=redis://redis-host:6379/0

# Application
APP_ENV=production
SECRET_KEY=your-secret-key-here
DEBUG=False

# CORS
CORS_ALLOW_ORIGINS=https://your-domain.com

# Rate Limiting
TRACKING_RATE_LIMIT_PER_MINUTE=100
SCRAPER_RATE_LIMIT_PER_MINUTE=10

# Observability
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
LOG_LEVEL=INFO
```

See `.env.production.example` for all available options.

## Configuration

### Application Settings

All configuration is managed through environment variables. Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Environment (development/production) | development |
| `DEBUG` | Debug mode | true |
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection string | optional |
| `SECRET_KEY` | JWT secret key | Required in production |
| `CORS_ALLOW_ORIGINS` | CORS origins | localhost:3000,localhost:5173 |
| `LOG_LEVEL` | Logging level | INFO |
| `WORKERS` | Uvicorn worker count | 4 |

### Database

Database is automatically initialized with migrations on startup:

```bash
# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "Add column description"

# Rollback
alembic downgrade -1
```

### Caching

The application uses Redis for caching with automatic fallback to in-memory cache:

```python
# Enable caching in repositories
from app.infrastructure.repositories.cached_repository import cached

@cached(ttl=3600, key_prefix="profile")
def get_profile(profile_id: int):
    # Query logic
    pass
```

## Testing

### Backend Tests

```bash
cd emailcampaigntracker

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test
pytest tests/unit/test_auth.py -v

# Run integration tests
pytest tests/integration/ -v
```

### Frontend Tests

```bash
cd emailcampaigntracker/frontend

# Type checking
npx tsc --noEmit

# Linting
npm run lint

# Build
npm run build
```

### CI/CD Testing

Tests run automatically on:
- Push to main/develop
- Pull requests
- Manual workflow dispatch

Check `.github/workflows/ci-cd.yml` for pipeline configuration.

## Monitoring & Observability

### Health Checks

```bash
# Application health
curl http://localhost:8000/health/status

# Application metrics
curl http://localhost:8000/health/metrics
```

### Structured Logging

Logs are output as JSON in production:

```json
{
  "timestamp": "2026-05-13T10:30:00.000Z",
  "level": "INFO",
  "logger": "app.api.routes.auth",
  "message": "User login successful",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Request Tracing

All requests include correlation IDs (X-Correlation-ID header):

```bash
curl -H "X-Correlation-ID: my-trace-id" http://localhost:8000/api/auth/me
```

### Performance Monitoring

The application tracks:
- Request response times
- Database query performance
- Cache hit/miss rates
- Error rates

Access metrics at: `/health/metrics`

### Log Aggregation

Integrate with:
- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **Datadog** (Set DATADOG_API_KEY)
- **Splunk** (HTTP Event Collector)
- **CloudWatch** (AWS)
- **Stackdriver** (GCP)

See [MONITORING.md](MONITORING.md) for detailed setup.

## Troubleshooting

### macOS Docker Issues

**Problem: `command not found: docker-compose`**
```bash
# Solution 1: Use modern syntax (Docker Desktop 4.0+)
docker compose up -d
# Not: docker-compose up -d

# Solution 2: Check Docker Desktop version
docker --version  # Should be 20.10+
docker compose version  # If this fails, upgrade Docker Desktop

# Solution 3: Reinstall Docker Desktop
# Download latest from: https://www.docker.com/products/docker-desktop/
```

**Problem: Docker runs out of disk space (macOS)**
```bash
# Check Docker disk usage
docker system df

# Clean up unused resources
docker system prune -a

# Reset Docker Desktop completely
# Open Docker → Preferences → Reset → Reset to factory defaults
```

**Problem: Slow performance on macOS (Intel Macs)**
```bash
# Edit docker-compose.yml and reduce resource limits:
# services:
#   api:
#     deploy:
#       resources:
#         limits:
#           memory: 512M  # Reduce from 2G
```

**Problem: Network connectivity issues**
```bash
# Test connectivity
docker compose exec api curl http://db:5432 -v
docker compose exec api redis-cli -h redis ping

# Restart Docker Desktop
# Preferences → Reset → Restart Docker
```

### Database Connection Errors

```bash
# Check database is running
docker compose ps db
# or: docker-compose ps db

# Test database connection
psql -h localhost -U emailcampaign -d emailcampaign -c "SELECT 1"

# Check connection pooling
docker compose logs db | grep "connection"
# or: docker-compose logs db | grep "connection"
```

### Redis Connection Errors

```bash
# Check Redis is running
docker compose ps redis
# or: docker-compose ps redis

# Test Redis connection
redis-cli -h localhost ping

# Monitor Redis memory
redis-cli info memory
```

### API Not Responding

```bash
# Check API logs
docker compose logs api
# or: docker-compose logs api

# Check health status
curl http://localhost:8000/health/status

# Restart API
docker compose restart api
# or: docker-compose restart api
```

### High Memory Usage

```bash
# Check container stats
docker stats

# Reduce cache size in docker-compose.yml
# Increase database connection pool recycling
# Review slow queries in logs
```

### Frontend Build Issues

```bash
# Clear cache and reinstall
cd frontend
rm -rf node_modules .next
npm install
npm run build

# Check Node version
node --version  # Should be 20+
```

### Slow API Responses

```bash
# Check metrics
curl http://localhost:8000/health/metrics

# Review slow query logs
docker-compose logs api | grep "Slow query"

# Monitor database
docker-compose exec db psql -U emailcampaign -c "\d+"
```

## Contributing

### Development Workflow

1. Create feature branch from `develop`
2. Make changes and test locally
3. Run tests: `pytest tests/` and `npm run lint`
4. Create pull request to `develop`
5. Code review and CI/CD checks
6. Merge to `develop`
7. Release to production via `main` branch

### Code Style

- **Backend**: Follow PEP 8, use `black` for formatting
- **Frontend**: Use ESLint and Prettier configuration
- **Git**: Use conventional commit messages

### Testing Requirements

- Backend: >80% code coverage
- Frontend: TypeScript strict mode
- All tests must pass before merge

## Support & Documentation

- **API Documentation**: http://localhost:8000/api/docs
- **Deployment Guide**: See [DEPLOYMENT.md](DEPLOYMENT.md)
- **Monitoring Guide**: See [MONITORING.md](MONITORING.md)
- **Production Checklist**: See [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)
- **Architecture**: See [ARCHITECTURE.md](emailcampaigntracker/ARCHITECTURE.md)

## Performance Metrics

Expected performance in production:

| Metric | Target | Notes |
|--------|--------|-------|
| API Response Time (p95) | < 200ms | With caching |
| Health Check | < 50ms | Simple probe |
| Error Rate | < 0.1% | Per 10k requests |
| Cache Hit Rate | > 70% | With Redis |
| Uptime | 99.9% | With auto-scaling |

## Security

- HTTPS/TLS 1.2+ required in production
- JWT-based authentication
- Bcrypt password hashing
- CORS restricted to trusted origins
- Rate limiting on all endpoints
- SQL injection protection (SQLAlchemy ORM)
- XSS protection (React)
- CSRF protection enabled

See [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md) for full security checklist.

## License

Proprietary - All rights reserved

## Changelog

### Version 1.0.0 (2026-05-13)

- Complete 6-phase architectural refactoring
- Clean Architecture implementation
- TypeScript migration on frontend
- Production-ready deployment setup
- Comprehensive monitoring and logging
- Database optimization and caching
- CI/CD pipeline with GitHub Actions
- Kubernetes manifests for cloud deployment

---

**Questions?** Check the documentation files or review the GitHub Issues.

**Ready to deploy?** Follow [DEPLOYMENT.md](DEPLOYMENT.md) and complete [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md).
