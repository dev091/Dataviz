from typing import Any

import pandas as pd

from connectors.base import Connector
from connectors.schemas import SalesforceConfig
from connectors.types import DiscoveredDataset, FieldInfo, SyncResult


class SalesforceConnector(Connector):
    connector_type = "salesforce"

    def validate_config(self, config: dict[str, Any]) -> None:
        SalesforceConfig.model_validate(config)

    def _client(self, payload: SalesforceConfig):
        try:
            from simple_salesforce import Salesforce  # type: ignore
        except ImportError as exc:
            raise ValueError("simple-salesforce package is required for Salesforce connector") from exc
        return Salesforce(
            username=payload.username,
            password=payload.password,
            security_token=payload.security_token,
            domain=payload.domain,
        )

    def discover(self, config: dict[str, Any]) -> list[DiscoveredDataset]:
        payload = SalesforceConfig.model_validate(config)
        sf = self._client(payload)
        description = sf.__getattr__(payload.object_name).describe()
        fields = [
            FieldInfo(name=field["name"], data_type=field.get("type", "string"), nullable=not bool(field.get("nillable") is False))
            for field in description.get("fields", [])
        ]
        return [DiscoveredDataset(name=payload.object_name.lower(), source_table=payload.object_name, fields=fields)]

    def preview_schema(self, config: dict[str, Any]) -> dict[str, Any]:
        datasets = self.discover(config)
        return {
            "datasets": [
                {
                    "name": ds.name,
                    "source_table": ds.source_table,
                    "fields": [field.__dict__ for field in ds.fields],
                }
                for ds in datasets
            ]
        }

    def sync(self, config: dict[str, Any], dataset_name: str | None = None) -> list[SyncResult]:
        payload = SalesforceConfig.model_validate(config)
        sf = self._client(payload)
        fields = [field.name for field in self.discover(config)[0].fields][:50]
        query = f"SELECT {', '.join(fields)} FROM {payload.object_name} LIMIT 50000"
        records = sf.query_all(query).get("records", [])
        for record in records:
            record.pop("attributes", None)
        df = pd.DataFrame(records)
        return [SyncResult(dataset_name=payload.object_name.lower(), row_count=len(df), dataframe=df, logs={"source": payload.object_name})]
