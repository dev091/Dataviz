from pathlib import Path

import pandas as pd

from connectors.base import Connector
from connectors.schemas import CSVConfig
from connectors.types import DiscoveredDataset, FieldInfo, SyncResult


PANDAS_DTYPE_MAP = {
    "object": "string",
    "int64": "integer",
    "float64": "float",
    "bool": "boolean",
    "datetime64[ns]": "datetime",
}


class CSVConnector(Connector):
    connector_type = "csv"

    def validate_config(self, config: dict) -> None:
        payload = CSVConfig.model_validate(config)
        if not Path(payload.file_path).exists():
            raise ValueError("CSV file does not exist")

    def discover(self, config: dict) -> list[DiscoveredDataset]:
        payload = CSVConfig.model_validate(config)
        df = pd.read_csv(payload.file_path, nrows=200)
        fields = [
            FieldInfo(name=col, data_type=PANDAS_DTYPE_MAP.get(str(df[col].dtype), "string"), nullable=True)
            for col in df.columns
        ]
        name = Path(payload.file_path).stem.replace(" ", "_").lower()
        return [DiscoveredDataset(name=name, source_table=name, fields=fields)]

    def preview_schema(self, config: dict) -> dict:
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

    def sync(self, config: dict, dataset_name: str | None = None) -> list[SyncResult]:
        payload = CSVConfig.model_validate(config)
        df = pd.read_csv(payload.file_path)
        name = dataset_name or Path(payload.file_path).stem.replace(" ", "_").lower()
        return [SyncResult(dataset_name=name, row_count=len(df), dataframe=df, logs={"source": payload.file_path})]
