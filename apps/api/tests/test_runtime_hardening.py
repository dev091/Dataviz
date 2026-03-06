import pytest

from app.core.config import settings
from app.core.observability import RuntimeMetricsRegistry
from app.core.security_runtime import InMemoryRateLimiter, validate_security_settings


def test_metrics_registry_renders_prometheus_snapshot():
    registry = RuntimeMetricsRegistry()
    registry.increment_inflight()
    registry.decrement_inflight()
    registry.observe(method="GET", route="/health", status_code=200, duration_seconds=0.04)

    text = registry.to_prometheus()
    assert "app_requests_total 1" in text
    assert "app_requests_route_total" in text
    assert "app_request_latency_seconds_bucket" in text


def test_inmemory_rate_limiter_blocks_after_threshold():
    limiter = InMemoryRateLimiter(requests_per_window=2, window_seconds=60)

    assert limiter.allow("client-a")[0] is True
    assert limiter.allow("client-a")[0] is True

    allowed, retry_after = limiter.allow("client-a")
    assert allowed is False
    assert retry_after >= 1


def test_security_validation_can_enforce_in_production(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "enforce_secure_config", True)
    monkeypatch.setattr(settings, "jwt_secret_key", "weak-secret")

    with pytest.raises(RuntimeError):
        validate_security_settings()
