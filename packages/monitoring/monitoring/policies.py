from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any


SAFE_SQL_REF = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
STALE_DATASET_HOURS = 36


def normalize_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def safe_column_ref(field_ref: str) -> str | None:
    candidate = str(field_ref or "").strip().split(".")[-1]
    if not candidate or not SAFE_SQL_REF.fullmatch(candidate):
        return None
    return candidate


def time_dimension(dimensions: list[Any]) -> Any | None:
    for dimension in dimensions:
        lowered = str(getattr(dimension, "data_type", "")).lower()
        if lowered in {"date", "datetime"}:
            return dimension
        if any(token in str(getattr(dimension, "name", "")).lower() for token in ["date", "time", "month", "week", "quarter", "year"]):
            return dimension
    return None


def breakdown_dimension(dimensions: list[Any], time_dimension_value: Any | None) -> Any | None:
    for dimension in dimensions:
        if time_dimension_value and getattr(dimension, "id", None) == getattr(time_dimension_value, "id", None):
            continue
        if str(getattr(dimension, "visibility", "public")) != "public":
            continue
        if str(getattr(dimension, "data_type", "")).lower() in {"string", "integer"}:
            return dimension
    return None


def audiences(metric_name: str | None, insight_type: str) -> list[str]:
    if insight_type == "freshness":
        return ["Analytics owner", "Data steward"]

    metric_name = (metric_name or "").lower()
    if any(token in metric_name for token in ["revenue", "sales", "arr", "mrr", "bookings", "pipeline"]):
        return ["Executive leadership", "RevOps", "Finance"]
    if any(token in metric_name for token in ["cost", "expense", "margin", "profit"]):
        return ["Finance", "Operations"]
    return ["Operations", "Analytics owner"]


def suggested_actions(*, insight_type: str, severity: str, metric_label: str, dataset_name: str, time_dimension_label: str | None, breakdown_dimension_label: str | None) -> list[str]:
    actions: list[str] = []

    if insight_type == "freshness":
        actions.append(f"Run a sync health check for {dataset_name} and confirm upstream connector access.")
        actions.append(f"Review dataset quality warnings for {dataset_name} before distributing executive outputs.")
        actions.append(f"Hold board or leadership distribution that depends on {dataset_name} until freshness is confirmed.")
        return actions[:3]

    if insight_type == "pacing":
        actions.append(f"Compare the latest {metric_label} period with the prior run-rate baseline to confirm the pacing shift.")
    elif insight_type == "trend_break":
        actions.append(f"Review the last two reporting windows for {metric_label} to explain the trend break before the next business review.")
    elif insight_type == "anomaly":
        actions.append(f"Validate whether the latest {metric_label} value is a true business anomaly or a data issue.")
    elif insight_type == "investigation_path":
        actions.append(f"Open a diagnostic drill path for {metric_label} and confirm the largest contributing segments.")
    else:
        actions.append(f"Review the latest governed output for {metric_label} and confirm whether follow-up is needed.")

    if breakdown_dimension_label:
        actions.append(f"Break down {metric_label} by {breakdown_dimension_label} to isolate the segments driving change.")
    if time_dimension_label:
        actions.append(f"Compare the latest values across {time_dimension_label} to determine whether the shift is accelerating or stabilizing.")
    if severity in {"warning", "critical"}:
        actions.append("Assign an owner and due date before the next reporting cadence.")

    deduped: list[str] = []
    for action in actions:
        if action not in deduped:
            deduped.append(action)
    return deduped[:4]


def escalation_policy(*, audiences_list: list[str], severity: str, insight_type: str) -> dict[str, str]:
    l1_owner: str = audiences_list[0] if audiences_list else "Analytics owner"
    l2_owner: str = audiences_list[1] if len(audiences_list) > 1 else l1_owner
    l3_owner: str = audiences_list[2] if len(audiences_list) > 2 else l2_owner

    if severity == "critical":
        return {
            "level": "critical",
            "owner": l1_owner,
            "route": f"Immediate escalation to L1 ({l1_owner}); L2 ({l2_owner}) and L3 ({l3_owner}) notified if SLA missed.",
            "sla": "4 hours",
            "routing_depth": "L3",
            "tier_l1": l1_owner,
            "tier_l2": l2_owner,
            "tier_l3": l3_owner,
        }
    if severity == "warning":
        return {
            "level": "warning",
            "owner": l1_owner,
            "route": f"Route to L1 ({l1_owner}) for review; L2 ({l2_owner}) included before next leadership cadence.",
            "sla": "1 business day",
            "routing_depth": "L2",
            "tier_l1": l1_owner,
            "tier_l2": l2_owner,
            "tier_l3": l3_owner,
        }
    if insight_type == "investigation_path":
        return {
            "level": "advisory",
            "owner": l1_owner,
            "route": f"Assign L1 ({l1_owner}) to verify the drill path before broad distribution.",
            "sla": "This week",
            "routing_depth": "L1",
            "tier_l1": l1_owner,
            "tier_l2": l2_owner,
            "tier_l3": l3_owner,
        }
    return {
        "level": "informational",
        "owner": l1_owner,
        "route": f"Include in the next scheduled digest for L1 ({l1_owner}) and monitor for repeat signals.",
        "sla": "Next scheduled digest",
        "routing_depth": "L1",
        "tier_l1": l1_owner,
        "tier_l2": l2_owner,
        "tier_l3": l3_owner,
    }


def investigation_paths(*, metric_label: str, time_dimension_label: str | None, breakdown_dimension_label: str | None, dataset_name: str) -> list[str]:
    paths: list[str] = []
    if time_dimension_label:
        paths.append(f"Review {metric_label} over the latest periods using {time_dimension_label}.")
    if breakdown_dimension_label:
        paths.append(f"Break down {metric_label} by {breakdown_dimension_label} to isolate contributing segments.")
    paths.append(f"Validate freshness and quality warnings on dataset {dataset_name} before escalation.")
    return paths
