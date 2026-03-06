from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class FieldInfo:
    name: str
    data_type: str
    nullable: bool = True


@dataclass
class DiscoveredDataset:
    name: str
    source_table: str
    fields: list[FieldInfo]


@dataclass
class SyncResult:
    dataset_name: str
    row_count: int
    dataframe: pd.DataFrame
    logs: dict[str, Any]
