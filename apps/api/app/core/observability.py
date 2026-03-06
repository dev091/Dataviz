from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict
from threading import Lock

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import PlainTextResponse, Response

from app.core.config import settings


logger = logging.getLogger("analytics.api")


class RuntimeMetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._request_total = 0
        self._inflight = 0
        self._by_status: dict[str, int] = defaultdict(int)
        self._by_route: dict[str, int] = defaultdict(int)
        self._latency_buckets = (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0)
        self._latency_histogram: dict[str, int] = defaultdict(int)

    def observe(self, *, method: str, route: str, status_code: int, duration_seconds: float) -> None:
        labels = f'method="{_escape_label(method)}",route="{_escape_label(route)}",status="{status_code}"'
        with self._lock:
            self._request_total += 1
            self._by_status[str(status_code)] += 1
            self._by_route[route] += 1

            for bucket in self._latency_buckets:
                if duration_seconds <= bucket:
                    self._latency_histogram[f'{labels},le="{bucket:g}"'] += 1
            self._latency_histogram[f'{labels},le="+Inf"'] += 1

    def increment_inflight(self) -> None:
        with self._lock:
            self._inflight += 1

    def decrement_inflight(self) -> None:
        with self._lock:
            self._inflight = max(self._inflight - 1, 0)

    def to_prometheus(self) -> str:
        with self._lock:
            lines = [
                "# HELP app_requests_total Total number of HTTP requests handled.",
                "# TYPE app_requests_total counter",
                f"app_requests_total {self._request_total}",
                "# HELP app_requests_inflight Current in-flight HTTP requests.",
                "# TYPE app_requests_inflight gauge",
                f"app_requests_inflight {self._inflight}",
                "# HELP app_requests_by_status Total HTTP requests by status code.",
                "# TYPE app_requests_by_status counter",
            ]
            lines.extend(
                f'app_requests_by_status{{status="{_escape_label(status)}"}} {count}'
                for status, count in sorted(self._by_status.items())
            )

            lines.extend(
                [
                    "# HELP app_requests_route_total Total HTTP requests by route.",
                    "# TYPE app_requests_route_total counter",
                ]
            )
            lines.extend(
                f'app_requests_route_total{{route="{_escape_label(route)}"}} {count}'
                for route, count in sorted(self._by_route.items())
            )

            lines.extend(
                [
                    "# HELP app_request_latency_seconds HTTP request latency buckets.",
                    "# TYPE app_request_latency_seconds histogram",
                ]
            )
            lines.extend(
                f"app_request_latency_seconds_bucket{{{labels}}} {count}"
                for labels, count in sorted(self._latency_histogram.items())
            )
            return "\n".join(lines) + "\n"


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def route_label(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        return str(getattr(route, "path"))
    return request.url.path


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(level=level, format="%(message)s")
    root_logger.setLevel(level)


metrics_registry = RuntimeMetricsRegistry()


class RequestContextLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.state.request_id = request_id

        started = time.perf_counter()
        metrics_registry.increment_inflight()
        response: Response | None = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-Id"] = request_id
            return response
        finally:
            metrics_registry.decrement_inflight()
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            payload = {
                "event": "http.request",
                "request_id": request_id,
                "method": request.method,
                "route": route_label(request),
                "status_code": status_code,
                "duration_ms": duration_ms,
            }
            logger.info(json.dumps(payload))


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_seconds = max(time.perf_counter() - started, 0.0)
            metrics_registry.observe(
                method=request.method,
                route=route_label(request),
                status_code=status_code,
                duration_seconds=duration_seconds,
            )


def metrics_text_response() -> PlainTextResponse:
    return PlainTextResponse(metrics_registry.to_prometheus(), media_type="text/plain; version=0.0.4")
