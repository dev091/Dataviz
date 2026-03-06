import pandas as pd

from connectors.base import Connector
from connectors.schemas import GoogleSheetsConfig
from connectors.types import DiscoveredDataset, FieldInfo, SyncResult


class GoogleSheetsConnector(Connector):
    connector_type = "google_sheets"

    def validate_config(self, config: dict) -> None:
        GoogleSheetsConfig.model_validate(config)

    def discover(self, config: dict) -> list[DiscoveredDataset]:
        payload = GoogleSheetsConfig.model_validate(config)
        df = pd.read_csv(payload.csv_export_url, nrows=200)
        fields = [FieldInfo(name=col, data_type=str(df[col].dtype), nullable=True) for col in df.columns]
        return [DiscoveredDataset(name="google_sheet", source_table="google_sheet", fields=fields)]

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
        payload = GoogleSheetsConfig.model_validate(config)
        df = pd.read_csv(payload.csv_export_url)
        return [SyncResult(dataset_name="google_sheet", row_count=len(df), dataframe=df, logs={"source": payload.csv_export_url})]
