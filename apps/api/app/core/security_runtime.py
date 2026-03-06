from __future__ import annotations

import logging
import time
from threading import Lock

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.core.config import settings


logger = logging.getLogger("analytics.security")

_WEAK_SECRETS = {
    "change-me",
    "change-me-in-production",
    "replace-with-strong-secret",
    "secret",
    "password",
}


def validate_security_settings() -> None:
    env = settings.app_env.lower()
    issues: list[str] = []

    secret = settings.jwt_secret_key.strip()
    if secret in _WEAK_SECRETS or len(secret) < 32:
        issues.append("JWT_SECRET_KEY is weak or too short (minimum 32 chars)")

    if env in {"production", "staging"} and not settings.cors_origin_list:
        issues.append("CORS_ORIGINS must be configured in staging/production")

    if settings.access_token_minutes > 60:
        issues.append("ACCESS_TOKEN_MINUTES should be <= 60 for stronger token rotation")

    if settings.billing_provider == "stripe":
        if not settings.stripe_secret_key.strip():
            issues.append("STRIPE_SECRET_KEY must be configured when BILLING_PROVIDER=stripe")
        if not settings.stripe_webhook_secret.strip():
            issues.append("STRIPE_WEBHOOK_SECRET must be configured when BILLING_PROVIDER=stripe")
        missing_prices = [
            name
            for name, value in {
                "STRIPE_PRICE_STARTER": settings.stripe_price_starter,
                "STRIPE_PRICE_GROWTH": settings.stripe_price_growth,
                "STRIPE_PRICE_ENTERPRISE": settings.stripe_price_enterprise,
            }.items()
            if not value.strip()
        ]
        if missing_prices:
            issues.append(f"Missing Stripe price IDs: {', '.join(missing_prices)}")

    if not issues:
        return

    message = "; ".join(issues)
    if settings.enforce_secure_config and env in {"production", "staging"}:
        raise RuntimeError(f"Security configuration check failed: {message}")

    logger.warning("Security configuration warning: %s", message)


class InMemoryRateLimiter:
    def __init__(self, requests_per_window: int, window_seconds: int = 60) -> None:
        self.requests_per_window = max(requests_per_window, 1)
        self.window_seconds = max(window_seconds, 1)
        self._lock = Lock()
        self._state: dict[str, tuple[float, int]] = {}

    def allow(self, key: str) -> tuple[bool, int]:
        now = time.time()
        with self._lock:
            started_at, count = self._state.get(key, (now, 0))
            elapsed = now - started_at
            if elapsed >= self.window_seconds:
                started_at, count = now, 0

            if count >= self.requests_per_window:
                retry_after = max(int(self.window_seconds - elapsed), 1)
                self._state[key] = (started_at, count)
                return False, retry_after

            self._state[key] = (started_at, count + 1)
            return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._limiter = InMemoryRateLimiter(settings.rate_limit_requests_per_minute, 60)
        self._exempt_paths = {
            "/health",
            "/metrics",
            "/openapi.json",
            "/docs",
            "/redoc",
        }

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if (
            not settings.rate_limit_enabled
            or request.method.upper() == "OPTIONS"
            or request.url.path in self._exempt_paths
            or request.url.path.startswith("/docs")
        ):
            return await call_next(request)

        key = self._client_key(request)
        allowed, retry_after = self._limiter.allow(key)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)

    @staticmethod
    def _client_key(request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "unknown"
