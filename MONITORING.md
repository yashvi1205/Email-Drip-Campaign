# Monitoring & Observability Guide

This document describes monitoring, logging, and observability features.

## Built-in Health Checks

### Health Status
```bash
curl https://your-domain.com/health/status
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2026-05-13T10:30:00.000Z",
  "database": "healthy"
}
```

### Application Metrics
```bash
curl https://your-domain.com/health/metrics
```

Response:
```json
{
  "timestamp": "2026-05-13T10:30:00.000Z",
  "total_requests": 1234,
  "successful_requests": 1200,
  "failed_requests": 34,
  "avg_response_time_ms": 125.5,
  "error_count": 34
}
```

## Structured Logging

Application logs are structured in JSON format (production) or human-readable (development).

Each log entry includes:
- `timestamp`: ISO format timestamp
- `level`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `logger`: Logger name/module
- `message`: Log message
- `correlation_id`: Request correlation ID for tracing
- `request_id`: Unique request identifier
- `job_id`: Background job identifier

Example:
```json
{
  "timestamp": "2026-05-13T10:30:00.000Z",
  "level": "INFO",
  "logger": "app.api.routes.auth",
  "message": "User login successful",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Distributed Tracing

All requests include a correlation ID (X-Correlation-ID header) for tracing:

```bash
curl -H "X-Correlation-ID: my-trace-id" https://your-domain.com/api/auth/me
```

The correlation ID propagates through:
- Request logs
- Database queries
- External API calls
- Response headers

## Performance Monitoring

### Slow Queries
The application logs queries taking >1 second:
```json
{
  "message": "Slow query: get_leads_by_status took 1234.56 ms",
  "level": "WARNING"
}
```

### Slow Endpoints
Endpoints taking >5 seconds are logged as warnings:
```json
{
  "message": "Slow endpoint: fetch_profiles took 5234.56 ms",
  "level": "WARNING"
}
```

## Integration with External Monitoring

### Prometheus
The `/health/metrics` endpoint provides metrics compatible with Prometheus scraping.

Setup Prometheus scrape config:
```yaml
scrape_configs:
  - job_name: 'emailcampaign'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/health/metrics'
    scrape_interval: 15s
```

### Datadog
Export logs to Datadog:
```python
from datadog import api
api.api_key = os.getenv("DATADOG_API_KEY")
```

### Sentry (Error Tracking)
Set SENTRY_DSN in environment for automatic error tracking:
```bash
SENTRY_DSN=https://key@sentry.io/project-id
```

### OpenTelemetry
For distributed tracing with Jaeger/Datadog:

1. Set environment variables:
```bash
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME=emailcampaign-api
```

2. Send traces to collector:
```
Requests → Application → OpenTelemetry SDK → OTLP Collector → Jaeger/Datadog
```

## Log Aggregation

### ELK Stack (Elasticsearch, Logstash, Kibana)
Logstash configuration to ingest JSON logs:
```
input {
  tcp {
    port => 5000
    codec => json
  }
}

filter {
  mutate {
    add_field => { "[@metadata][index_name]" => "emailcampaign-%{+YYYY.MM.dd}" }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "%{[@metadata][index_name]}"
  }
}
```

### Splunk
Forward logs to Splunk HTTP Event Collector:
```bash
curl -k https://splunk-host:8088/services/collector \
  -H "Authorization: Splunk YOUR_HEC_TOKEN" \
  -d '{"event": "log message"}'
```

## Alerting

### Alert Conditions
Set up alerts for:
- Error rate > 5% of requests
- Response time > 5 seconds (p95)
- Database connection errors
- Redis connection errors
- Disk space < 10%
- Memory usage > 80%

### Alert Channels
Configure notifications via:
- Email
- Slack
- PagerDuty
- SNS/SQS

## Performance Baselines

Expected performance metrics:
- API response time: < 200ms (p95)
- Health check: < 50ms
- Error rate: < 0.1%
- Cache hit rate: > 70% (with Redis)
- Database connection pool: 20-40 connections

## Troubleshooting

### High Error Rate
1. Check error logs for patterns
2. Review correlation IDs for affected requests
3. Check database and Redis connectivity
4. Review rate limiting configuration

### Slow Responses
1. Check slow query logs
2. Review database execution plans
3. Check cache hit rate
4. Monitor CPU/memory usage

### Missing Logs
1. Verify logging is enabled (LOG_LEVEL)
2. Check log destination (stdout/file)
3. Verify JSON formatter is configured
4. Check disk space
