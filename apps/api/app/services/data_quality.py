from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd
from pandas.api import types as pd_types


def _sample_values(series: pd.Series, limit: int = 5) -> list[str]:
    values: list[str] = []
    for value in series.dropna().head(limit).tolist():
        values.append(str(value))
    return values


def _status_for_score(score: int) -> str:
    if score >= 90:
        return "excellent"
    if score >= 75:
        return "good"
    if score >= 55:
        return "warning"
    return "critical"


def _field_type(series: pd.Series) -> str:
    if pd_types.is_bool_dtype(series):
        return "boolean"
    if pd_types.is_integer_dtype(series):
        return "integer"
    if pd_types.is_float_dtype(series):
        return "number"
    if pd_types.is_datetime64_any_dtype(series):
        return "datetime"
    return "string"


def _series_warnings(name: str, series: pd.Series, row_count: int) -> list[str]:
    warnings: list[str] = []
    null_ratio = float(series.isna().mean()) if row_count else 0.0
    distinct_count = int(series.nunique(dropna=True))

    if null_ratio >= 0.4:
        warnings.append(f"{name} has high missingness ({null_ratio:.0%}).")
    if row_count and distinct_count <= 1 and null_ratio < 1:
        warnings.append(f"{name} is near-constant.")
    if row_count and distinct_count == row_count and _field_type(series) == "string":
        warnings.append(f"{name} looks like a high-cardinality identifier.")
    return warnings


def profile_dataframe(frame: pd.DataFrame, *, cleaning: dict[str, Any] | None = None) -> dict[str, Any]:
    row_count = len(frame)
    duplicate_rows = int(frame.duplicated().sum()) if row_count else 0
    duplicate_ratio = (duplicate_rows / row_count) if row_count else 0.0

    field_profiles: list[dict[str, Any]] = []
    warnings: list[str] = []
    completeness_scores: list[float] = []

    for column in frame.columns:
        series = frame[column]
        null_count = int(series.isna().sum())
        null_ratio = (null_count / row_count) if row_count else 0.0
        distinct_count = int(series.nunique(dropna=True))
        unique_ratio = (distinct_count / row_count) if row_count else 0.0
        completeness_scores.append(1.0 - null_ratio)
        field_warning_list = _series_warnings(str(column), series, row_count)
        warnings.extend(field_warning_list)
        field_profiles.append(
            {
                "name": str(column),
                "data_type": _field_type(series),
                "null_count": null_count,
                "null_ratio": round(null_ratio, 4),
                "distinct_count": distinct_count,
                "unique_ratio": round(unique_ratio, 4),
                "sample_values": _sample_values(series),
                "warnings": field_warning_list,
            }
        )

    completeness_score = int(round((sum(completeness_scores) / len(completeness_scores)) * 100)) if completeness_scores else 100
    duplicate_score = int(round(max(0.0, 1.0 - min(duplicate_ratio, 0.5) * 2) * 100))
    cleaning_score = 100
    cleaning_rows_dropped = 0
    if cleaning:
        cleaning_rows_dropped = int(cleaning.get("rows_dropped", 0) or 0)
        rows_before = int(cleaning.get("rows_before", row_count + cleaning_rows_dropped) or 0)
        cleaning_ratio = (cleaning_rows_dropped / rows_before) if rows_before else 0.0
        cleaning_score = int(round(max(0.0, 1.0 - min(cleaning_ratio, 0.25) * 2.5) * 100))
        if cleaning.get("renamed_columns"):
            warnings.append("Column names were standardized during ingestion.")
        if cleaning_rows_dropped:
            warnings.append(f"Removed {cleaning_rows_dropped} fully empty rows during ingestion.")
        unnamed_removed = cleaning.get("unnamed_columns_removed") or []
        if isinstance(unnamed_removed, Iterable) and list(unnamed_removed):
            warnings.append("Removed empty unnamed columns during ingestion.")

    overall_score = int(round((completeness_score * 0.5) + (duplicate_score * 0.25) + (cleaning_score * 0.25)))
    status = _status_for_score(overall_score)

    if duplicate_ratio >= 0.05:
        warnings.append(f"Dataset has duplicate rows ({duplicate_ratio:.0%}).")

    deduped_warnings = list(dict.fromkeys(warnings))

    return {
        "overall_score": overall_score,
        "status": status,
        "row_count": row_count,
        "duplicate_rows": duplicate_rows,
        "duplicate_ratio": round(duplicate_ratio, 4),
        "completeness_score": completeness_score,
        "duplicate_score": duplicate_score,
        "cleaning_score": cleaning_score,
        "cleaning": cleaning or {},
        "warnings": deduped_warnings,
        "field_profiles": field_profiles,
    }
