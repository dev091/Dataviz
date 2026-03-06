import pandas as pd
from sqlalchemy import create_engine, inspect

from connectors.base import Connector
from connectors.schemas import PostgresConfig
from connectors.types import DiscoveredDataset, FieldInfo, SyncResult


class PostgresConnector(Connector):
    connector_type = "postgresql"

    def validate_config(self, config: dict) -> None:
        PostgresConfig.model_validate(config)

    def discover(self, config: dict) -> list[DiscoveredDataset]:
        payload = PostgresConfig.model_validate(config)
        engine = create_engine(payload.uri)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        datasets: list[DiscoveredDataset] = []
        for table in tables:
            columns = inspector.get_columns(table)
            fields = [FieldInfo(name=col["name"], data_type=str(col.get("type", "string")), nullable=bool(col.get("nullable", True))) for col in columns]
            datasets.append(DiscoveredDataset(name=table, source_table=table, fields=fields))
        return datasets

    def preview_schema(self, config: dict) -> dict:
        return {
            "datasets": [
                {
                    "name": ds.name,
                    "source_table": ds.source_table,
                    "fields": [field.__dict__ for field in ds.fields],
                }
                for ds in self.discover(config)
            ]
        }

    def sync(self, config: dict, dataset_name: str | None = None) -> list[SyncResult]:
        payload = PostgresConfig.model_validate(config)
        engine = create_engine(payload.uri)
        datasets = self.discover(config)
        if dataset_name:
            datasets = [ds for ds in datasets if ds.name == dataset_name]
        results: list[SyncResult] = []
        for dataset in datasets:
            df = pd.read_sql(f'SELECT * FROM "{dataset.source_table}" LIMIT 50000', engine)
            results.append(SyncResult(dataset_name=dataset.name, row_count=len(df), dataframe=df, logs={"source": dataset.source_table}))
        return results
