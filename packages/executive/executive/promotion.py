from __future__ import annotations

import re
from typing import Any

from executive.migration import labelize, lookup_match


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "metric"


def _unique_metric_name(base_name: str, existing_names: set[str]) -> str:
    candidate = _slugify(base_name)
    if candidate not in existing_names:
        existing_names.add(candidate)
        return candidate
    index = 2
    while f"{candidate}_{index}" in existing_names:
        index += 1
    final_name = f"{candidate}_{index}"
    existing_names.add(final_name)
    return final_name


def _infer_aggregation(formula: str | None) -> str:
    if not formula:
        return "sum"
    upper = formula.strip().upper()
    if upper.startswith("AVG("):
        return "avg"
    if upper.startswith("COUNT("):
        return "count"
    if upper.startswith("MIN("):
        return "min"
    if upper.startswith("MAX("):
        return "max"
    return "sum"


def _merge_synonyms(*groups: list[str] | None) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for group in groups:
        for value in group or []:
            item = str(value or "").strip()
            if not item:
                continue
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            values.append(item)
    return values


def _review_index(review_items: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("source_name") or "").strip().lower(): dict(item)
        for item in review_items or []
        if str(item.get("source_name") or "").strip()
    }


def _lineage_payload(
    *,
    source_tool: str,
    source_name: str,
    review_item: dict[str, Any] | None,
    imported: dict[str, Any],
    recommended_action: str,
) -> dict[str, Any]:
    lineage = dict(review_item.get("lineage_preview") or {}) if review_item else {}
    lineage.setdefault("source_tool", source_tool)
    lineage.setdefault("migration_source_name", source_name)
    lineage.setdefault("recommended_action", recommended_action)
    formula = str(imported.get("formula") or "").strip()
    if formula:
        lineage.setdefault("import_formula", formula)
    return lineage


def prepare_metric_promotions(
    *,
    semantic_detail: dict[str, Any],
    selected_source_names: list[str],
    imported_kpis: list[dict[str, Any]],
    kpi_matches: list[dict[str, Any]],
    owner_name: str | None,
    certification_status: str,
    source_tool: str,
    review_items: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    metrics = [dict(item) for item in semantic_detail["metrics"]]
    calculated_fields = {str(item["name"]).lower(): dict(item) for item in semantic_detail["calculated_fields"]}
    imported_index = {str(item.get("source_name") or "").strip().lower(): dict(item) for item in imported_kpis}
    review_index = _review_index(review_items)
    existing_names = {str(metric["name"]).lower() for metric in metrics}
    results: list[dict[str, Any]] = []

    for source_name in selected_source_names:
        source_key = source_name.strip().lower()
        if not source_key:
            continue
        imported = imported_index.get(source_key, {})
        review_item = review_index.get(source_key)
        match = lookup_match(kpi_matches, source_name)
        label = str(imported.get("label") or labelize(source_name))
        effective_owner = str(review_item.get("proposed_owner_name") or owner_name or "").strip() or None if review_item else owner_name
        effective_status = str(review_item.get("proposed_certification_status") or certification_status) if review_item else certification_status
        effective_synonyms = _merge_synonyms(
            review_item.get("suggested_synonyms") if review_item else None,
            [label, source_name],
        )
        effective_note = str(review_item.get("certification_note") or imported.get("description") or "").strip() or None if review_item else str(imported.get("description") or "").strip() or None
        readiness_status = str(review_item.get("readiness_status") or "") if review_item else ""
        blockers = [str(item) for item in review_item.get("blockers", [])] if review_item else []

        if readiness_status == "blocked" or blockers:
            results.append(
                {
                    "source_name": source_name,
                    "status": "blocked_by_review",
                    "target_name": match.get("target_name") if match else None,
                    "target_label": match.get("target_label") if match else None,
                    "owner_name": effective_owner,
                    "certification_status": effective_status,
                    "rationale": blockers[0] if blockers else "Migration review blocked promotion for this KPI.",
                }
            )
            continue

        if match and match.get("status") == "matched" and match.get("target_type") == "metric":
            target_name = str(match.get("target_name") or "")
            updated = False
            for metric in metrics:
                if str(metric["name"]).lower() == target_name.lower():
                    if effective_owner:
                        metric["owner_name"] = effective_owner
                    metric["certification_status"] = effective_status
                    metric["synonyms"] = _merge_synonyms(metric.get("synonyms"), effective_synonyms)
                    metric["certification_note"] = effective_note
                    metric["lineage"] = _lineage_payload(
                        source_tool=source_tool,
                        source_name=source_name,
                        review_item=review_item,
                        imported=imported,
                        recommended_action="update_existing_metric",
                    )
                    updated = True
                    results.append(
                        {
                            "source_name": source_name,
                            "status": "governance_updated",
                            "target_name": metric["name"],
                            "target_label": metric["label"],
                            "owner_name": metric.get("owner_name"),
                            "certification_status": metric["certification_status"],
                            "rationale": "Matched governed KPI metadata was updated for migration certification.",
                        }
                    )
                    break
            if updated:
                continue

        if match and match.get("status") == "promote" and match.get("target_type") == "calculated_field":
            calc_name = str(match.get("target_name") or "").lower()
            calc = calculated_fields.get(calc_name)
            if calc:
                new_name = _unique_metric_name(imported.get("label") or source_name, existing_names)
                metrics.append(
                    {
                        "name": new_name,
                        "label": label,
                        "formula": calc["expression"],
                        "aggregation": str(imported.get("aggregation") or _infer_aggregation(calc["expression"])),
                        "value_format": imported.get("value_format"),
                        "visibility": "public",
                        "description": imported.get("description") or f"Promoted from calculated field {calc['name']} during migration.",
                        "synonyms": effective_synonyms,
                        "owner_name": effective_owner,
                        "certification_status": effective_status,
                        "certification_note": effective_note,
                        "lineage": _lineage_payload(
                            source_tool=source_tool,
                            source_name=source_name,
                            review_item=review_item,
                            imported=imported,
                            recommended_action="promote_calculated_field",
                        ),
                    }
                )
                results.append(
                    {
                        "source_name": source_name,
                        "status": "promoted_from_calculated_field",
                        "target_name": new_name,
                        "target_label": label,
                        "owner_name": effective_owner,
                        "certification_status": effective_status,
                        "rationale": f"Created governed KPI from calculated field '{calc['name']}'.",
                    }
                )
                continue

        imported_formula = imported.get("formula")
        if imported_formula:
            new_name = _unique_metric_name(imported.get("label") or source_name, existing_names)
            metrics.append(
                {
                    "name": new_name,
                    "label": label,
                    "formula": str(imported_formula),
                    "aggregation": str(imported.get("aggregation") or _infer_aggregation(str(imported_formula))),
                    "value_format": imported.get("value_format"),
                    "visibility": "public",
                    "description": imported.get("description") or "Imported from incumbent workbook during migration.",
                    "synonyms": effective_synonyms,
                    "owner_name": effective_owner,
                    "certification_status": effective_status,
                    "certification_note": effective_note,
                    "lineage": _lineage_payload(
                        source_tool=source_tool,
                        source_name=source_name,
                        review_item=review_item,
                        imported=imported,
                        recommended_action="create_metric_from_import",
                    ),
                }
            )
            results.append(
                {
                    "source_name": source_name,
                    "status": "created_from_import_definition",
                    "target_name": new_name,
                    "target_label": label,
                    "owner_name": effective_owner,
                    "certification_status": effective_status,
                    "rationale": "Created governed KPI from imported workbook definition.",
                }
            )
            continue

        results.append(
            {
                "source_name": source_name,
                "status": "skipped",
                "target_name": None,
                "target_label": None,
                "owner_name": effective_owner,
                "certification_status": effective_status,
                "rationale": "No promotable calculated field or imported formula was available for this KPI.",
            }
        )

    return metrics, results
