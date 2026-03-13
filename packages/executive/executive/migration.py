from __future__ import annotations

import re
from typing import Any

from executive.launch_packs import recommend_pack


STOPWORDS = {
    "dashboard",
    "report",
    "pack",
    "scorecard",
    "summary",
    "business",
    "review",
    "weekly",
    "monthly",
    "quarterly",
    "executive",
    "leadership",
    "kpi",
    "metrics",
    "metric",
    "view",
    "page",
}


def labelize(value: str) -> str:
    cleaned = re.sub(r"[_\-.]+", " ", value).strip()
    return re.sub(r"\s+", " ", cleaned).title() or "Field"


def tool_label(source_tool: str) -> str:
    return source_tool.replace("_", " ").replace("-", " ").title()


def _tokenize(*values: str | None) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        if not value:
            continue
        for token in re.findall(r"[a-z0-9]+", value.lower()):
            if len(token) <= 1 or token in STOPWORDS:
                continue
            tokens.add(token)
    return tokens


def _normalized(value: str) -> str:
    return " ".join(sorted(_tokenize(value)))


def score_name_match(source_name: str, candidate_name: str, candidate_label: str | None = None) -> tuple[float, str]:
    source_tokens = _tokenize(source_name)
    candidate_tokens = _tokenize(candidate_name, candidate_label)
    if not source_tokens or not candidate_tokens:
        return 0.0, "No meaningful token overlap was available for matching."

    source_normalized = _normalized(source_name)
    candidate_normalized = _normalized(f"{candidate_name} {candidate_label or ''}")
    if source_normalized and source_normalized == candidate_normalized:
        return 1.0, "Exact normalized name match."

    shared = source_tokens & candidate_tokens
    jaccard = len(shared) / len(source_tokens | candidate_tokens)
    containment_bonus = 0.0
    source_joined = " ".join(sorted(source_tokens))
    candidate_joined = " ".join(sorted(candidate_tokens))
    if source_joined and source_joined in candidate_joined:
        containment_bonus = 0.2
    elif candidate_joined and candidate_joined in source_joined:
        containment_bonus = 0.15

    score = min(1.0, jaccard + containment_bonus)
    if shared:
        rationale = f"Shared tokens: {', '.join(sorted(shared))}."
    else:
        rationale = "Low semantic overlap; manual review recommended."
    return score, rationale


def match_candidates(
    source_names: list[str],
    candidates: list[dict[str, Any]],
    *,
    unmatched_rationale: str,
    dimension_mode: bool = False,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for source_name in source_names:
        best: dict[str, Any] | None = None
        best_score = 0.0
        best_rationale = "No candidate evaluated."
        for candidate in candidates:
            score, rationale = score_name_match(source_name, str(candidate["name"]), candidate.get("label"))
            if score > best_score:
                best = candidate
                best_score = score
                best_rationale = rationale

        if best is None or best_score < 0.35:
            matches.append(
                {
                    "source_name": source_name,
                    "target_id": None,
                    "target_name": None,
                    "target_label": None,
                    "target_type": None,
                    "score": round(best_score, 2),
                    "status": "unmatched",
                    "rationale": unmatched_rationale,
                }
            )
            continue

        status = "matched"
        rationale = best_rationale
        target_type = str(best.get("target_type") or "")
        if target_type == "calculated_field" and not dimension_mode:
            status = "promote"
            rationale = f"{best_rationale} Matching calculated field exists, but it should be promoted to a certified KPI before cutover."
        elif best_score < 0.55:
            status = "review"
            rationale = f"{best_rationale} Similarity is moderate, so analyst review is recommended before migration."

        matches.append(
            {
                "source_name": source_name,
                "target_id": best["id"],
                "target_name": best["name"],
                "target_label": best.get("label"),
                "target_type": best.get("target_type"),
                "score": round(best_score, 2),
                "status": status,
                "rationale": rationale,
            }
        )
    return matches


def matched_target_labels(matches: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    for match in matches:
        if match["status"] in {"matched", "promote"} and match.get("target_label"):
            labels.append(str(match["target_label"]))
    return labels


def build_output_suggestions(
    asset_names: list[str],
    *,
    source_tool: str,
    kpi_matches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    matched_targets = matched_target_labels(kpi_matches)[:3]
    suggestions: list[dict[str, Any]] = []
    for asset_name in asset_names:
        asset_pack = recommend_pack([asset_name], matched_targets, [], None)
        suggestions.append(
            {
                "source_name": asset_name,
                "recommended_launch_pack_id": asset_pack["id"],
                "recommended_launch_pack_title": asset_pack["title"],
                "recommended_dashboard_name": f"{asset_name.strip()} Migration Pack",
                "suggested_goal": f"Migrate the {tool_label(source_tool)} asset '{asset_name}' into a governed {asset_pack['department']} reporting flow focused on {', '.join(matched_targets) if matched_targets else 'core executive KPIs' }.",
                "matched_targets": matched_targets,
                "rationale": f"Maps the incumbent asset into the {asset_pack['title']} template to reduce manual rebuild work.",
            }
        )
    return suggestions


def build_trust_checks(
    *,
    kpi_matches: list[dict[str, Any]],
    dimension_matches: list[dict[str, Any]],
    dashboard_names: list[str],
    report_names: list[str],
    automated_trust_comparison: dict[str, Any],
) -> list[str]:
    checks: list[str] = []
    for match in kpi_matches[:3]:
        if match["status"] in {"matched", "promote", "review"} and match.get("target_label"):
            checks.append(
                f"Compare incumbent KPI '{match['source_name']}' to governed target '{match['target_label']}' over the last 3 closed periods with shared filters; accept <= 1.0% variance before cutover."
            )
    first_dimension = next((match for match in dimension_matches if match["status"] in {"matched", "review"}), None)
    if first_dimension and first_dimension.get("target_label"):
        checks.append(
            f"Validate top value rankings and filters for dimension '{first_dimension['source_name']}' against governed dimension '{first_dimension['target_label']}' before retiring the incumbent view."
        )
    summary = automated_trust_comparison.get("summary", {}) if isinstance(automated_trust_comparison, dict) else {}
    if summary.get("fail_count"):
        checks.append(f"Resolve {summary['fail_count']} automated trust comparison failures before certifying the migrated pack.")
    if summary.get("review_count"):
        checks.append(
            f"Review {summary['review_count']} benchmark comparisons that exceeded the strict variance threshold but may still be acceptable after business review."
        )
    if dashboard_names or report_names:
        checks.append(
            "Review audience, cadence, and exception handling on the migrated dashboard and report pack before replacing incumbent distribution."
        )
    if any(match["status"] == "unmatched" for match in kpi_matches + dimension_matches):
        checks.append(
            "Resolve unmatched KPI or dimension names before certifying the migrated pack as a trusted replacement for the incumbent asset."
        )
    return checks[:6]


def lookup_match(matches: list[dict[str, Any]], source_name: str) -> dict[str, Any] | None:
    normalized_source = source_name.strip().lower()
    return next((match for match in matches if str(match.get("source_name", "")).strip().lower() == normalized_source), None)


def comparison_status(variance_pct: float | None) -> str:
    if variance_pct is None:
        return "fail"
    if variance_pct <= 0.01:
        return "pass"
    if variance_pct <= 0.05:
        return "review"
    return "fail"
