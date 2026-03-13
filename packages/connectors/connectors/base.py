from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, TypeVar

from connectors.retry import RetryMetadata, execute_with_retry
from connectors.types import DiscoveredDataset, SyncResult


T = TypeVar("T")


class Connector(ABC):
    connector_type: str
    max_retries: int = 2
    retry_backoff_seconds: float = 0.25

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def discover(self, config: dict[str, Any]) -> list[DiscoveredDataset]:
        raise NotImplementedError

    @abstractmethod
    def preview_schema(self, config: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def sync(self, config: dict[str, Any], dataset_name: str | None = None) -> list[SyncResult]:
        raise NotImplementedError

    def is_retryable_error(self, exc: Exception) -> bool:
        return True

    def call_with_retry(self, operation_name: str, fn: Callable[[], T]) -> tuple[T, RetryMetadata]:
        return execute_with_retry(
            operation_name,
            fn,
            max_attempts=max(1, self.max_retries + 1),
            base_delay_seconds=self.retry_backoff_seconds,
            should_retry=self.is_retryable_error,
        )
