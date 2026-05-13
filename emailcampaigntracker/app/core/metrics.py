"""Metrics collection for application monitoring

Collects basic metrics for requests, errors, and performance tracking.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class RequestMetrics:
    """Metrics for a single request"""

    path: str
    method: str
    status_code: int
    duration_ms: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class AggregatedMetrics:
    """Aggregated metrics for monitoring"""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time_ms: float = 0.0
    error_count: int = 0
    endpoint_stats: Dict[str, Dict[str, any]] = field(default_factory=dict)


class MetricsCollector:
    """Collects and aggregates application metrics"""

    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self.requests: list[RequestMetrics] = []
        self.errors: int = 0
        self.endpoint_metrics: Dict[str, Dict[str, any]] = defaultdict(
            lambda: {"requests": 0, "errors": 0, "total_time_ms": 0}
        )

    def record_request(
        self,
        path: str,
        method: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Record a request metric"""
        metric = RequestMetrics(
            path=path,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
        )
        self.requests.append(metric)

        # Keep only recent samples
        if len(self.requests) > self.max_samples:
            self.requests.pop(0)

        # Update endpoint stats
        endpoint_key = f"{method} {path}"
        stats = self.endpoint_metrics[endpoint_key]
        stats["requests"] += 1
        stats["total_time_ms"] += duration_ms

        # Track errors
        if status_code >= 400:
            stats["errors"] += 1
            self.errors += 1

    def get_summary(self) -> AggregatedMetrics:
        """Get aggregated metrics summary"""
        total_requests = len(self.requests)
        successful = sum(1 for r in self.requests if r.status_code < 400)
        failed = total_requests - successful

        avg_time = (
            sum(r.duration_ms for r in self.requests) / total_requests
            if total_requests > 0
            else 0
        )

        return AggregatedMetrics(
            total_requests=total_requests,
            successful_requests=successful,
            failed_requests=failed,
            avg_response_time_ms=avg_time,
            error_count=self.errors,
            endpoint_stats=dict(self.endpoint_metrics),
        )

    def get_endpoint_stats(self, path: str, method: str) -> Optional[Dict]:
        """Get stats for a specific endpoint"""
        key = f"{method} {path}"
        return self.endpoint_metrics.get(key)


# Global metrics collector instance
_metrics_collector = MetricsCollector()


def record_request_metric(
    path: str, method: str, status_code: int, duration_ms: float
) -> None:
    """Record a request metric"""
    _metrics_collector.record_request(path, method, status_code, duration_ms)


def get_metrics_summary() -> AggregatedMetrics:
    """Get current metrics summary"""
    return _metrics_collector.get_summary()


def get_endpoint_metrics(path: str, method: str) -> Optional[Dict]:
    """Get metrics for a specific endpoint"""
    return _metrics_collector.get_endpoint_stats(path, method)
