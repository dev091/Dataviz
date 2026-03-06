from abc import ABC, abstractmethod
from typing import Any

from connectors.types import DiscoveredDataset, SyncResult


class Connector(ABC):
    connector_type: str

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
