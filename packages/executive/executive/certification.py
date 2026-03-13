from __future__ import annotations

from typing import Any

from executive.migration import labelize, lookup_match


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
    return items


def _benchmark_rows_for_source(source_name: str, trust_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    key = source_name.strip().lower()
    return [row for row in trust_rows if str(row.get("source_name") or "").strip().lower() == key]


def _evidence_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = [str(row.get("status") or "pending").lower() for row in rows]
    return {
        "compared_rows": len(rows),
        "pass_count": sum(1 for status in statuses if status == "pass"),
        "review_count": sum(1 for status in statuses if status == "review"),
        "fail_count": sum(1 for status in statuses if status == "fail"),
        "pending_count": sum(1 for status in statuses if status == "pending"),
    }


def _recommended_action(match: dict[str, Any] | None, imported: dict[str, Any]) -> str:
    formula = str(imported.get("formula") or "").strip()
    if match and match.get("status") == "matched" and match.get("target_type") == "metric":
        return "update_existing_metric"
    if match and match.get("status") == "promote" and match.get("target_type") == "calculated_field":
        return "promote_calculated_field"
    if formula:
        return "create_metric_from_import"
    return "manual_mapping_required"


def _suggested_synonyms(source_name: str, imported: dict[str, Any], match: dict[str, Any] | None) -> list[str]:
    candidates = [
        str(imported.get("label") or ""),
        source_name,
        str(match.get("target_label") or "") if match else "",
        labelize(source_name),
    ]
    return _dedupe(candidates)


def _build_blockers(
    *,
    recommended_action: str,
    evidence_summary: dict[str, Any],
    owner_name: str | None,
    requested_certification_status: str,
) -> list[str]:
    blockers: list[str] = []
    if recommended_action == "manual_mapping_required":
        blockers.append("No governed match or import formula is available. A human must map or define this KPI before promotion.")
    if evidence_summary["fail_count"]:
        blockers.append("Automated trust comparison found material variance against incumbent benchmark values.")
    if requested_certification_status == "certified" and evidence_summary["pending_count"]:
        blockers.append("Certification cannot be marked complete while benchmark comparison is still pending.")
    if requested_certification_status == "certified" and not owner_name:
        blockers.append("Assign an owner before certifying migrated KPIs.")
    return blockers


def _build_review_notes(
    *,
    recommended_action: str,
    evidence_summary: dict[str, Any],
    match: dict[str, Any] | None,
    imported: dict[str, Any],
) -> list[str]:
    notes: list[str] = []
    if match and match.get("status") == "matched":
        notes.append("A governed KPI already exists. Review metadata, ownership, and benchmark parity before cutover.")
    if recommended_action == "promote_calculated_field":
        notes.append("A governed calculated field can be promoted directly into a KPI without recreating the workbook logic.")
    if recommended_action == "create_metric_from_import":
        notes.append("The workbook exposes a formula that can be promoted into the semantic layer.")
    if evidence_summary["pass_count"]:
        notes.append("Benchmark comparison passed for at least one incumbent reference slice.")
    if evidence_summary["review_count"]:
        notes.append("Some benchmark slices are close but still warrant manual review before broader rollout.")
    if evidence_summary["pending_count"] and not evidence_summary["compared_rows"]:
        notes.append("No benchmark export was supplied. Promotion can proceed, but certification should stay in review.")
    description = str(imported.get("description") or "").strip()
    if description:
        notes.append(description)
    return _dedupe(notes)


def _readiness_status(blockers: list[str], evidence_summary: dict[str, Any], requested_certification_status: str) -> str:
    if blockers:
        return "blocked"
    if requested_certification_status == "certified" and evidence_summary["pass_count"] and not evidence_summary["review_count"] and not evidence_summary["pending_count"]:
        return "ready"
    return "review"


def _proposed_status(readiness_status: str, requested_certification_status: str) -> str:
    if readiness_status == "ready":
        return requested_certification_status
    if readiness_status == "blocked":
        return "draft"
    return "review"


def _readiness_score(
    *,
    recommended_action: str,
    evidence_summary: dict[str, Any],
    owner_name: str | None,
    requested_certification_status: str,
    blockers: list[str],
) -> int:
    score = 35
    if recommended_action == "update_existing_metric":
        score += 30
    elif recommended_action == "promote_calculated_field":
        score += 25
    elif recommended_action == "create_metric_from_import":
        score += 18
    score += evidence_summary["pass_count"] * 12
    score -= evidence_summary["review_count"] * 8
    score -= evidence_summary["fail_count"] * 20
    score -= evidence_summary["pending_count"] * 6
    if owner_name:
        score += 8
    if requested_certification_status == "certified":
        score += 5
    score -= len(blockers) * 15
    return max(0, min(100, score))


def build_migration_certification_review(
    *,
    semantic_model_id: str,
    source_tool: str,
    selected_source_names: list[str],
    imported_kpis: list[dict[str, Any]],
    kpi_matches: list[dict[str, Any]],
    automated_trust_comparison: dict[str, Any],
    requested_owner_name: str | None,
    requested_certification_status: str,
    notes: str | None = None,
) -> dict[str, Any]:
    imported_index = {str(item.get("source_name") or "").strip().lower(): dict(item) for item in imported_kpis}
    trust_rows = list(automated_trust_comparison.get("rows") or [])
    items: list[dict[str, Any]] = []

    requested_sources = selected_source_names or [str(item.get("source_name") or "") for item in imported_kpis]
    for source_name in requested_sources:
        source_key = source_name.strip().lower()
        if not source_key:
            continue

        imported = imported_index.get(source_key, {"source_name": source_name})
        match = lookup_match(kpi_matches, source_name)
        benchmark_rows = _benchmark_rows_for_source(source_name, trust_rows)
        evidence_summary = _evidence_summary(benchmark_rows)
        recommended_action = _recommended_action(match, imported)
        blockers = _build_blockers(
            recommended_action=recommended_action,
            evidence_summary=evidence_summary,
            owner_name=requested_owner_name,
            requested_certification_status=requested_certification_status,
        )
        readiness_status = _readiness_status(blockers, evidence_summary, requested_certification_status)
        proposed_status = _proposed_status(readiness_status, requested_certification_status)
        synonyms = _suggested_synonyms(source_name, imported, match)
        review_notes = _build_review_notes(
            recommended_action=recommended_action,
            evidence_summary=evidence_summary,
            match=match,
            imported=imported,
        )
        readiness_score = _readiness_score(
            recommended_action=recommended_action,
            evidence_summary=evidence_summary,
            owner_name=requested_owner_name,
            requested_certification_status=requested_certification_status,
            blockers=blockers,
        )
        certification_note = "; ".join(review_notes[:3])
        lineage_preview = {
            "source_tool": source_tool,
            "migration_source_name": source_name,
            "recommended_action": recommended_action,
            "matched_target_name": str(match.get("target_name") or "") if match else "",
            "matched_target_type": str(match.get("target_type") or "") if match else "",
            "import_formula": str(imported.get("formula") or "").strip() or None,
            "benchmark_pass_count": evidence_summary["pass_count"],
            "benchmark_fail_count": evidence_summary["fail_count"],
        }
        items.append(
            {
                "source_name": source_name,
                "label": str(imported.get("label") or labelize(source_name)),
                "target_name": match.get("target_name") if match else None,
                "target_label": match.get("target_label") if match else None,
                "target_type": match.get("target_type") if match else None,
                "match_status": match.get("status") if match else "unmatched",
                "recommended_action": recommended_action,
                "readiness_status": readiness_status,
                "readiness_score": readiness_score,
                "proposed_owner_name": requested_owner_name,
                "proposed_certification_status": proposed_status,
                "suggested_synonyms": synonyms,
                "benchmark_evidence": evidence_summary,
                "blockers": blockers,
                "review_notes": review_notes,
                "certification_note": certification_note or None,
                "lineage_preview": lineage_preview,
            }
        )

    summary = {
        "total_items": len(items),
        "ready_count": sum(1 for item in items if item["readiness_status"] == "ready"),
        "review_count": sum(1 for item in items if item["readiness_status"] == "review"),
        "blocked_count": sum(1 for item in items if item["readiness_status"] == "blocked"),
        "benchmark_fail_count": sum(item["benchmark_evidence"]["fail_count"] for item in items),
    }

    return {
        "semantic_model_id": semantic_model_id,
        "source_tool": source_tool,
        "requested_owner_name": requested_owner_name,
        "requested_certification_status": requested_certification_status,
        "notes": str(notes or "").strip() or None,
        "summary": summary,
        "items": items,
    }
