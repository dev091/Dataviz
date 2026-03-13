from __future__ import annotations

from datetime import date, datetime
from importlib.util import find_spec
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd
from pandas.api import types as pd_types

from connectors.base import Connector
from connectors.schemas import CSVConfig
from connectors.types import DiscoveredDataset, FieldInfo, SyncResult


SUPPORTED_FILE_FORMATS = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".txt": "txt",
    ".json": "json",
    ".jsonl": "jsonl",
    ".ndjson": "jsonl",
    ".xlsx": "xlsx",
    ".xls": "xls",
    ".ods": "ods",
    ".parquet": "parquet",
    ".xml": "xml",
}

OPTIONAL_DEPENDENCIES = {
    "xlsx": "openpyxl",
    "xls": "xlrd",
    "ods": "odfpy",
    "parquet": "pyarrow",
    "xml": "lxml",
}


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", value.strip().lower()).strip("_") or "dataset"


def _infer_format(file_path: str, explicit_format: str | None = None) -> str:
    if explicit_format:
        normalized = explicit_format.strip().lower()
        if normalized in SUPPORTED_FILE_FORMATS.values():
            return normalized
    suffix = Path(file_path).suffix.lower()
    detected = SUPPORTED_FILE_FORMATS.get(suffix)
    if not detected:
        raise ValueError(
            "Unsupported file format. Supported formats: csv, tsv, txt, json, jsonl, ndjson, xlsx, xls, ods, parquet, xml."
        )
    return detected


def _ensure_dependency(file_format: str) -> None:
    dependency = OPTIONAL_DEPENDENCIES.get(file_format)
    if dependency and find_spec(dependency) is None:
        raise ValueError(f"Support for {file_format} files requires the optional dependency '{dependency}' to be installed.")


def _frame_type(series: pd.Series) -> str:
    if pd_types.is_bool_dtype(series):
        return "boolean"
    if pd_types.is_integer_dtype(series):
        return "integer"
    if pd_types.is_float_dtype(series):
        return "float"
    if pd_types.is_datetime64_any_dtype(series):
        return "datetime"

    sample = [value for value in series.dropna().head(10).tolist() if value is not None]
    if sample and all(isinstance(value, date) and not isinstance(value, datetime) for value in sample):
        return "date"
    return "string"


def _dedupe_columns(columns: list[str]) -> tuple[list[str], dict[str, str]]:
    seen: dict[str, int] = {}
    renamed: dict[str, str] = {}
    cleaned: list[str] = []
    for index, original in enumerate(columns):
        base = re.sub(r"\s+", "_", str(original).strip()) or f"column_{index + 1}"
        candidate = base
        suffix = 2
        while candidate in seen:
            candidate = f"{base}_{suffix}"
            suffix += 1
        seen[candidate] = 1
        cleaned.append(candidate)
        if candidate != str(original):
            renamed[str(original)] = candidate
    return cleaned, renamed


def _maybe_convert_object_series(name: str, series: pd.Series) -> pd.Series:
    non_null = series.dropna()
    if non_null.empty:
        return series

    normalized_name = name.lower()
    text_values = non_null.astype(str)

    if any(token in normalized_name for token in ["date", "time", "month", "year"]):
        converted = pd.to_datetime(non_null, errors="coerce")
        if converted.notna().sum() >= max(1, int(len(non_null) * 0.8)):
            result = pd.to_datetime(series, errors="coerce")
            return result

    numeric = pd.to_numeric(text_values.str.replace(",", "", regex=False), errors="coerce")
    if numeric.notna().sum() >= max(1, int(len(non_null) * 0.8)):
        converted = pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce")
        return converted

    return series


def _clean_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    original_rows = len(frame)
    original_columns = list(frame.columns)
    cleaned = frame.copy()

    cleaned.columns, renamed_columns = _dedupe_columns([str(column) for column in cleaned.columns])
    unnamed_columns = [column for column in cleaned.columns if column.lower().startswith("unnamed") and cleaned[column].isna().all()]
    if unnamed_columns:
        cleaned = cleaned.drop(columns=unnamed_columns)

    for column in cleaned.columns:
        if pd_types.is_object_dtype(cleaned[column]) or pd_types.is_string_dtype(cleaned[column]):
            cleaned[column] = cleaned[column].map(lambda value: value.strip() if isinstance(value, str) else value)
            cleaned[column] = cleaned[column].replace({"": None})
            cleaned[column] = _maybe_convert_object_series(column, cleaned[column])

    cleaned = cleaned.dropna(how="all")

    return cleaned, {
        "rows_before": original_rows,
        "rows_after": len(cleaned),
        "rows_dropped": max(0, original_rows - len(cleaned)),
        "columns_before": original_columns,
        "columns_after": list(cleaned.columns),
        "unnamed_columns_removed": unnamed_columns,
        "renamed_columns": renamed_columns,
    }


def _load_json_records(file_path: str, lines: bool, nrows: int | None = None) -> pd.DataFrame:
    path = Path(file_path)
    if lines:
        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                value = line.strip()
                if not value:
                    continue
                records.append(json.loads(value))
                if nrows and len(records) >= nrows:
                    break
        return pd.json_normalize(records)

    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    if isinstance(raw, dict) and isinstance(raw.get("data"), list):
        frame = pd.json_normalize(raw["data"])
    elif isinstance(raw, list):
        frame = pd.json_normalize(raw)
    elif isinstance(raw, dict):
        frame = pd.json_normalize([raw])
    else:
        raise ValueError("JSON upload must contain an object, an array of objects, or a top-level 'data' array.")

    return frame.head(nrows) if nrows else frame


def _load_single_frame(file_path: str, file_format: str, *, nrows: int | None = None, sheet_name: str | int | None = None) -> pd.DataFrame:
    if file_format == "csv":
        return pd.read_csv(file_path, nrows=nrows)
    if file_format == "tsv":
        return pd.read_csv(file_path, sep="\t", nrows=nrows)
    if file_format == "txt":
        return pd.read_csv(file_path, sep=None, engine="python", nrows=nrows)
    if file_format == "json":
        return _load_json_records(file_path, lines=False, nrows=nrows)
    if file_format == "jsonl":
        return _load_json_records(file_path, lines=True, nrows=nrows)
    if file_format in {"xlsx", "xls", "ods"}:
        _ensure_dependency(file_format)
        target_sheet = 0 if sheet_name is None else sheet_name
        return pd.read_excel(file_path, sheet_name=target_sheet, nrows=nrows)
    if file_format == "parquet":
        _ensure_dependency(file_format)
        frame = pd.read_parquet(file_path)
        return frame.head(nrows) if nrows else frame
    if file_format == "xml":
        _ensure_dependency(file_format)
        frame = pd.read_xml(file_path)
        return frame.head(nrows) if nrows else frame
    raise ValueError(f"Unsupported file format: {file_format}")


def _sheet_datasets(file_path: str, file_format: str, sheet_name: str | None = None) -> list[tuple[str | None, str]]:
    base_name = _normalize_name(Path(file_path).stem)
    if file_format not in {"xlsx", "xls", "ods"}:
        return [(None, base_name)]

    _ensure_dependency(file_format)
    if sheet_name:
        return [(sheet_name, _normalize_name(f"{base_name}_{sheet_name}"))]

    workbook = pd.ExcelFile(file_path)
    return [(workbook_sheet_name, _normalize_name(f"{base_name}_{workbook_sheet_name}")) for workbook_sheet_name in workbook.sheet_names]


class CSVConnector(Connector):
    connector_type = "csv"

    def validate_config(self, config: dict) -> None:
        payload = CSVConfig.model_validate(config)
        file_path = Path(payload.file_path)
        if not file_path.exists():
            raise ValueError("Uploaded file does not exist")
        _ensure_dependency(_infer_format(payload.file_path, payload.file_format))

    def discover(self, config: dict) -> list[DiscoveredDataset]:
        payload = CSVConfig.model_validate(config)
        file_format = _infer_format(payload.file_path, payload.file_format)

        datasets: list[DiscoveredDataset] = []
        for sheet_name, dataset_name in _sheet_datasets(payload.file_path, file_format, payload.sheet_name):
            frame = _load_single_frame(payload.file_path, file_format, nrows=200, sheet_name=sheet_name)
            frame, _ = _clean_frame(frame)
            fields = [FieldInfo(name=str(column), data_type=_frame_type(frame[column]), nullable=True) for column in frame.columns]
            source_name = sheet_name if sheet_name else dataset_name
            datasets.append(DiscoveredDataset(name=dataset_name, source_table=str(source_name), fields=fields))
        return datasets

    def preview_schema(self, config: dict) -> dict:
        payload = CSVConfig.model_validate(config)
        file_format = _infer_format(payload.file_path, payload.file_format)
        datasets = self.discover(config)
        return {
            "datasets": [
                {
                    "name": dataset.name,
                    "source_table": dataset.source_table,
                    "fields": [field.__dict__ for field in dataset.fields],
                }
                for dataset in datasets
            ],
            "meta": {"file_format": file_format, "source": payload.file_path},
        }

    def sync(self, config: dict, dataset_name: str | None = None) -> list[SyncResult]:
        payload = CSVConfig.model_validate(config)
        file_format = _infer_format(payload.file_path, payload.file_format)

        results: list[SyncResult] = []
        for sheet_name, normalized_dataset_name in _sheet_datasets(payload.file_path, file_format, payload.sheet_name):
            if dataset_name and normalized_dataset_name != dataset_name:
                continue
            frame = _load_single_frame(payload.file_path, file_format, sheet_name=sheet_name)
            frame, cleaning = _clean_frame(frame)
            results.append(
                SyncResult(
                    dataset_name=normalized_dataset_name,
                    row_count=len(frame),
                    dataframe=frame,
                    logs={
                        "source": payload.file_path,
                        "file_format": file_format,
                        "sheet_name": sheet_name,
                        "cleaning": cleaning,
                    },
                )
            )
        return results
