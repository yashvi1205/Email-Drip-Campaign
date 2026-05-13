# Deployment Guide

This guide covers deploying the LinkedIn Email Campaign Tracker to production.

## Prerequisites

- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+
- GitHub Actions (for CI/CD)
- Cloud provider (AWS, GCP, Azure, etc.)

## Local Development

### Start all services:
```bash
docker-compose up -d
```

Services will be available at:
- API: http://localhost:8000
- Frontend: http://localhost:5173
- Database: localhost:5432
- Redis: localhost:6379

### Stop services:
```bash
docker-compose down
```

### View logs:
```bash
docker-compose logs -f api
```

## Production Deployment

### 1. Environment Configuration

Create `.env.production`:
```
DATABASE_URL=postgresql://user:password@db-host:5432/emailcampaign
REDIS_URL=redis://redis-host:6379/0
APP_ENV=production
SECRET_KEY=your-secret-key-here
CORS_ALLOW_ORIGINS=https://your-domain.com
```

### 2. Database Migration

Before deploying, run migrations:
```bash
alembic upgrade head
```

### 3. Docker Build

Build production image:
```bash
docker build -t emailcampaign-api:latest .
```

### 4. Cloud Deployment

#### AWS ECS/Fargate
```bash
# Push to ECR
aws ecr get-login-password | docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com
docker tag emailcampaign-api:latest $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/emailcampaign:latest
docker push $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/emailcampaign:latest

# Update ECS service
aws ecs update-service --cluster production --service emailcampaign --force-new-deployment
```

#### Kubernetes (K8s)
```bash
# Apply deployments
kubectl apply -f k8s/

# Check rollout status
kubectl rollout status deployment/emailcampaign-api -n production
```

#### Docker Compose (Single Server)
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### 5. Health Checks

Verify deployment:
```bash
curl https://your-domain.com/health/status
curl https://your-domain.com/health/metrics
```

### 6. Monitoring

Monitor logs and metrics:
- **Logs**: Check CloudWatch (AWS), Stackdriver (GCP), or container logs
- **Metrics**: Access `/health/metrics` endpoint
- **Errors**: Check application error logs

### 7. Scaling

For high load, scale horizontally:
- Run multiple API instances behind a load balancer
- Use managed database service (AWS RDS, Cloud SQL)
- Use managed Redis (ElastiCache, Memorystore)

## Rollback Procedure

If issues occur:

```bash
# AWS ECS
aws ecs update-service --cluster production --service emailcampaign --task-definition emailcampaign:PREVIOUS_VERSION

# Kubernetes
kubectl rollout undo deployment/emailcampaign-api -n production

# Docker Compose
docker-compose down
# Restore previous image and restart
docker-compose -f docker-compose.prod.yml up -d
```

## Security Checklist

- [ ] Use HTTPS/TLS for all connections
- [ ] Set strong SECRET_KEY (use OpenSSL: `openssl rand -hex 32`)
- [ ] Enable database encryption at rest
- [ ] Use environment variables for secrets (never commit to git)
- [ ] Enable rate limiting on all endpoints
- [ ] Configure CORS to specific trusted origins
- [ ] Use database connection pooling
- [ ] Enable logging and monitoring
- [ ] Regular security patches and updates
- [ ] Backup database regularly

## Performance Tuning

- Database: Enable query caching, use connection pooling
- Redis: Monitor memory usage, set eviction policy
- Frontend: Enable CDN for static assets
- API: Use caching headers, compression, pagination
- Container: Set appropriate CPU/memory limits

## Troubleshooting

### Database Connection Errors
```bash
# Check database is accessible
psql -h db-host -U emailcampaign -d emailcampaign

# Check migrations
alembic current
alembic history
```

### Redis Connection Errors
```bash
# Check Redis is accessible
redis-cli -h redis-host ping
```

### Performance Issues
```bash
# Check metrics
curl https://your-domain.com/health/metrics

# View slow logs
redis-cli --latency
```

## Support

For issues, check:
1. Application logs
2. Database logs
3. Redis logs
4. System resources (CPU, memory, disk)
