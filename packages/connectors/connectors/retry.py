from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from pydantic import ValidationError


T = TypeVar("T")

NON_RETRYABLE_EXCEPTIONS = (ValidationError, ValueError)


@dataclass
class RetryMetadata:
    operation: str
    attempts: int
    retried: bool
    backoff_seconds: float

    def to_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "attempts": self.attempts,
            "retried": self.retried,
            "backoff_seconds": round(self.backoff_seconds, 3),
        }


class ConnectorExecutionError(RuntimeError):
    def __init__(self, *, operation: str, attempts: int, last_error: Exception) -> None:
        self.operation = operation
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"Connector {operation} failed after {attempts} attempt(s): {last_error}")

    def to_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "attempts": self.attempts,
            "error": str(self.last_error),
        }


def execute_with_retry(
    operation_name: str,
    fn: Callable[[], T],
    *,
    max_attempts: int,
    base_delay_seconds: float,
    should_retry: Callable[[Exception], bool],
) -> tuple[T, RetryMetadata]:
    total_backoff = 0.0

    for attempt in range(1, max_attempts + 1):
        try:
            value = fn()
            return value, RetryMetadata(
                operation=operation_name,
                attempts=attempt,
                retried=attempt > 1,
                backoff_seconds=total_backoff,
            )
        except Exception as exc:  # noqa: BLE001
            retryable = should_retry(exc) and not isinstance(exc, NON_RETRYABLE_EXCEPTIONS)
            if attempt >= max_attempts or not retryable:
                raise ConnectorExecutionError(operation=operation_name, attempts=attempt, last_error=exc) from exc

            delay = base_delay_seconds * attempt
            total_backoff += delay
            time.sleep(delay)

    raise RuntimeError(f"Retry loop exited unexpectedly for {operation_name}")
