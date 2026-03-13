from __future__ import annotations

from typing import Any
import warnings

import pandas as pd


def generate_cleaning_steps(
    *,
    quality_profile: dict[str, Any],
    frame: pd.DataFrame,
    feedback_map: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    def boost_confidence(base: float, feedback: dict[str, int] | None) -> float:
        feedback = feedback or {"approved": 0, "rejected": 0}
        approved = int(feedback.get("approved", 0))
        rejected = int(feedback.get("rejected", 0))
        adjusted = base + (approved * 0.04) - (rejected * 0.05)
        return round(max(0.05, min(0.99, adjusted)), 2)

    field_profiles = quality_profile.get("field_profiles", [])
    steps: list[dict[str, Any]] = []
    duplicate_rows = int(quality_profile.get("duplicate_rows", 0) or 0)
    if duplicate_rows > 0:
        feedback = feedback_map.get("dedupe_rows")
        steps.append(
            {
                "step_id": "dedupe_rows",
                "title": "Remove duplicate rows",
                "step_type": "deduplicate",
                "target_fields": [],
                "explanation": f"Detected {duplicate_rows} duplicate rows. Deduplicating before modeling will reduce noisy KPI inflation.",
                "reversible": True,
                "revert_strategy": "Keep the raw synced table unchanged and materialize a cleaned working copy without duplicate rows.",
                "sql_preview": "SELECT DISTINCT * FROM source_dataset",
                "confidence": boost_confidence(0.91, feedback),
                "feedback": feedback or {"approved": 0, "rejected": 0},
            }
        )

    for profile in field_profiles:
        name = str(profile.get("name"))
        null_ratio = float(profile.get("null_ratio", 0) or 0)
        data_type = str(profile.get("data_type", "string"))
        field_warnings = [str(item) for item in profile.get("warnings", [])]
        series = frame[name] if name in frame.columns else pd.Series(dtype="object")
        non_null = series.dropna().astype(str) if len(series) else pd.Series(dtype="object")
        feedback = feedback_map.get(f"trim_whitespace:{name}")
        if len(non_null) and (non_null != non_null.str.strip()).any():
            steps.append(
                {
                    "step_id": f"trim_whitespace:{name}",
                    "title": f"Trim whitespace in {name}",
                    "step_type": "normalize_text",
                    "target_fields": [name],
                    "explanation": f"Values in {name} contain leading or trailing whitespace that can break joins, grouping, and filter behavior.",
                    "reversible": True,
                    "revert_strategy": f"Preserve the raw {name} column and materialize a cleaned shadow column for standardized queries.",
                    "sql_preview": f"TRIM({name}) AS {name}",
                    "confidence": boost_confidence(0.88, feedback),
                    "feedback": feedback or {"approved": 0, "rejected": 0},
                }
            )

        feedback = feedback_map.get(f"normalize_case:{name}")
        if len(non_null) and data_type == "string" and non_null.nunique() != non_null.str.lower().nunique() and non_null.nunique() <= 50:
            steps.append(
                {
                    "step_id": f"normalize_case:{name}",
                    "title": f"Normalize casing in {name}",
                    "step_type": "normalize_case",
                    "target_fields": [name],
                    "explanation": f"{name} contains case variants that likely represent the same business value. Standardizing them improves grouping accuracy.",
                    "reversible": True,
                    "revert_strategy": f"Keep the original {name} values and generate a normalized semantic field for governed use.",
                    "sql_preview": f"LOWER({name}) AS {name}_normalized",
                    "confidence": boost_confidence(0.76, feedback),
                    "feedback": feedback or {"approved": 0, "rejected": 0},
                }
            )

        feedback = feedback_map.get(f"coerce_number:{name}")
        if data_type == "string" and len(non_null):
            numeric_ratio = float(pd.to_numeric(non_null.str.replace(",", "", regex=False), errors="coerce").notna().mean())
            if numeric_ratio >= 0.8:
                steps.append(
                    {
                        "step_id": f"coerce_number:{name}",
                        "title": f"Coerce {name} to number",
                        "step_type": "type_coercion",
                        "target_fields": [name],
                        "explanation": f"{name} is currently stored as string, but {numeric_ratio:.0%} of sampled values parse as numbers. Converting it will unlock metric inference.",
                        "reversible": True,
                        "revert_strategy": f"Retain the raw {name} field and create a typed numeric projection for semantic modeling.",
                        "sql_preview": f'CAST(REPLACE({name}, ",", "") AS DOUBLE PRECISION) AS {name}_number',
                        "confidence": boost_confidence(0.84, feedback),
                        "feedback": feedback or {"approved": 0, "rejected": 0},
                    }
                )

        feedback = feedback_map.get(f"coerce_date:{name}")
        if data_type == "string" and len(non_null):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                date_ratio = float(pd.to_datetime(non_null, errors="coerce").notna().mean())
            if date_ratio >= 0.8:
                steps.append(
                    {
                        "step_id": f"coerce_date:{name}",
                        "title": f"Coerce {name} to date",
                        "step_type": "type_coercion",
                        "target_fields": [name],
                        "explanation": f"{name} is stored as string, but {date_ratio:.0%} of sampled values parse as dates. Converting it will improve time-grain logic.",
                        "reversible": True,
                        "revert_strategy": f"Retain the raw {name} text field and materialize a typed date field for governed use.",
                        "sql_preview": f"CAST({name} AS DATE) AS {name}_date",
                        "confidence": boost_confidence(0.81, feedback),
                        "feedback": feedback or {"approved": 0, "rejected": 0},
                    }
                )

        feedback = feedback_map.get(f"fill_missing:{name}")
        if null_ratio >= 0.2:
            strategy = "median" if data_type in {"integer", "number"} else "Unknown"
            steps.append(
                {
                    "step_id": f"fill_missing:{name}",
                    "title": f"Apply missing-value strategy for {name}",
                    "step_type": "missing_value_strategy",
                    "target_fields": [name],
                    "explanation": f"{name} has {null_ratio:.0%} missing values. A governed fill strategy can stabilize downstream metrics and dimensions.",
                    "reversible": True,
                    "revert_strategy": f"Keep the raw nulls and layer the fill behavior in a reversible semantic prep model.",
                    "sql_preview": f"COALESCE({name}, {strategy}) AS {name}_filled",
                    "confidence": boost_confidence(0.69, feedback),
                    "feedback": feedback or {"approved": 0, "rejected": 0},
                }
            )

        if any("high-cardinality identifier" in warning for warning in field_warnings):
            feedback = feedback_map.get(f"mark_identifier:{name}")
            steps.append(
                {
                    "step_id": f"mark_identifier:{name}",
                    "title": f"Mark {name} as identifier-only",
                    "step_type": "semantic_annotation",
                    "target_fields": [name],
                    "explanation": f"{name} behaves like an identifier and should not be used as a grouped executive dimension by default.",
                    "reversible": True,
                    "revert_strategy": f"Keep {name} visible in the raw dataset but restrict its default semantic visibility.",
                    "sql_preview": None,
                    "confidence": boost_confidence(0.73, feedback),
                    "feedback": feedback or {"approved": 0, "rejected": 0},
                }
            )

    return steps


def _normalized_name(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")


def _type_compatible(left_type: str, right_type: str) -> bool:
    left = left_type.lower()
    right = right_type.lower()
    if left == right:
        return True
    numeric = {"integer", "number", "int64", "float64"}
    if left in numeric and right in numeric:
        return True
    if "date" in left and "date" in right:
        return True
    return False


def generate_join_suggestions(*, dataset_name: str, current_fields: dict[str, str], current_samples: dict[str, dict[str, Any]], other_datasets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    for candidate in other_datasets:
        candidate_fields = candidate.get("fields", {})
        candidate_samples = candidate.get("samples", {})
        for left_name, left_type in current_fields.items():
            left_profile = current_samples.get(left_name, {})
            left_values = {str(value).lower() for value in left_profile.get("sample_values", []) if str(value).strip()}
            for right_name, right_type in candidate_fields.items():
                if not _type_compatible(left_type, right_type):
                    continue
                score = 0.0
                if _normalized_name(left_name) == _normalized_name(right_name):
                    score += 0.65
                elif _normalized_name(left_name).split("_")[-1] == _normalized_name(right_name).split("_")[-1]:
                    score += 0.4
                right_profile = candidate_samples.get(right_name, {})
                right_values = {str(value).lower() for value in right_profile.get("sample_values", []) if str(value).strip()}
                if left_values and right_values:
                    overlap = len(left_values & right_values) / max(1, min(len(left_values), len(right_values)))
                    score += overlap * 0.35
                if score >= 0.55:
                    suggestions.append(
                        {
                            "target_dataset_id": candidate["id"],
                            "target_dataset_name": candidate["name"],
                            "left_field": left_name,
                            "right_field": right_name,
                            "score": round(min(score, 0.99), 2),
                            "rationale": f"{left_name} in {dataset_name} aligns with {right_name} in {candidate['name']} by name and sampled value overlap.",
                        }
                    )

    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in sorted(suggestions, key=lambda row: row["score"], reverse=True):
        key = (item["target_dataset_id"], item["left_field"], item["right_field"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
        if len(unique) == 5:
            break
    return unique


def generate_union_suggestions(*, dataset_name: str, current_fields: set[str], other_datasets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    for candidate in other_datasets:
        candidate_fields = set(candidate.get("fields", {}).keys())
        shared = sorted(current_fields & candidate_fields)
        if len(shared) < 2:
            continue
        union_score = len(shared) / max(1, len(current_fields | candidate_fields))
        if union_score >= 0.55:
            suggestions.append(
                {
                    "target_dataset_id": candidate["id"],
                    "target_dataset_name": candidate["name"],
                    "shared_fields": shared,
                    "score": round(union_score, 2),
                    "rationale": f"{dataset_name} and {candidate['name']} share {len(shared)} fields and can likely be stacked into a unified reporting table.",
                }
            )
    return sorted(suggestions, key=lambda row: row["score"], reverse=True)[:5]


def generate_calculated_field_suggestions(field_names: list[str]) -> list[dict[str, Any]]:
    fields = [field.lower() for field in field_names]
    suggestions: list[dict[str, Any]] = []
    if any(name in fields for name in {"revenue", "sales", "amount"}) and any(name in fields for name in {"cost", "expense", "spend"}):
        revenue_name = next(name for name in fields if name in {"revenue", "sales", "amount"})
        cost_name = next(name for name in fields if name in {"cost", "expense", "spend"})
        suggestions.append(
            {
                "name": "gross_margin",
                "expression": f"{revenue_name} - {cost_name}",
                "data_type": "number",
                "rationale": "Revenue and cost columns exist, so gross margin should be materialized as a reusable governed field.",
            }
        )
    if "target" in fields and "actual" in fields:
        suggestions.append(
            {
                "name": "variance_to_target",
                "expression": "actual - target",
                "data_type": "number",
                "rationale": "Actual and target columns exist, so variance is a likely recurring executive KPI input.",
            }
        )
    return suggestions


def build_transformation_lineage(quality_profile: dict[str, Any]) -> list[dict[str, Any]]:
    cleaning = quality_profile.get("cleaning", {}) if isinstance(quality_profile.get("cleaning"), dict) else {}
    lineage: list[dict[str, Any]] = []
    renamed = cleaning.get("renamed_columns") or {}
    if isinstance(renamed, dict) and renamed:
        lineage.append(
            {
                "source": "ingestion_cleaning",
                "description": "Column names were standardized during ingestion.",
                "affected_fields": [str(value) for value in renamed.values()],
                "status": "applied",
                "recorded_at": None,
            }
        )
    rows_dropped = int(cleaning.get("rows_dropped", 0) or 0)
    if rows_dropped:
        lineage.append(
            {
                "source": "ingestion_cleaning",
                "description": f"Removed {rows_dropped} fully empty rows during ingestion.",
                "affected_fields": [],
                "status": "applied",
                "recorded_at": None,
            }
        )
    unnamed = cleaning.get("unnamed_columns_removed") or []
    if unnamed:
        lineage.append(
            {
                "source": "ingestion_cleaning",
                "description": "Removed empty unnamed columns during ingestion.",
                "affected_fields": [str(item) for item in unnamed],
                "status": "applied",
                "recorded_at": None,
            }
        )

    autopilot = quality_profile.get("autopilot") if isinstance(quality_profile.get("autopilot"), dict) else {}
    history = autopilot.get("history") if isinstance(autopilot.get("history"), list) else []
    for item in history[:20]:
        if not isinstance(item, dict):
            continue
        lineage.append(
            {
                "source": str(item.get("source") or "ai_data_prep_autopilot"),
                "description": str(item.get("description") or "Applied governed prep action."),
                "affected_fields": [str(field) for field in item.get("affected_fields", [])] if isinstance(item.get("affected_fields"), list) else [],
                "status": str(item.get("status") or "applied"),
                "recorded_at": item.get("recorded_at"),
            }
        )
    return lineage
