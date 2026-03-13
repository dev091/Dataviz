import json
from pathlib import Path
from typing import Any

from app.ai.providers.factory import get_provider
from app.core.bootstrap import bootstrap_package_paths

bootstrap_package_paths()
from analytics.summaries import deterministic_summary  # noqa: E402
from semantic.models import QueryPlan  # noqa: E402
from semantic.planner import heuristic_plan  # noqa: E402


class AIOrchestrator:
    def __init__(self) -> None:
        self.provider = get_provider()
        self.prompts_dir = Path(__file__).resolve().parents[4] / "packages" / "prompts"

    def _load_prompt(self, name: str) -> str:
        path = self.prompts_dir / name
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def plan_query(self, *, question: str, metric_names: list[str], dimension_names: list[str]) -> QueryPlan:
        base_plan = heuristic_plan(question, metric_names, dimension_names)

        planner_prompt = self._load_prompt("query_plan.txt")
        if not planner_prompt:
            return base_plan

        prompt = (
            f"{planner_prompt}\n"
            f"Question: {question}\n"
            f"Metrics: {metric_names}\n"
            f"Dimensions: {dimension_names}\n"
            "Return JSON only."
        )

        try:
            raw = self.provider.complete(prompt, json_mode=True)
            payload = json.loads(raw)
            plan = QueryPlan.model_validate(payload)
            if not plan.metrics and base_plan.metrics:
                return base_plan
            return plan
        except Exception:
            return base_plan

    def summarize(
        self,
        *,
        question: str,
        rows: list[dict[str, Any]],
        metrics: list[str],
        dimensions: list[str],
        insights: list[dict[str, Any]],
        related_queries: list[dict[str, Any]] | None = None,
    ) -> str:
        summary_prompt = self._load_prompt("summary.txt")
        related = related_queries or []
        if not summary_prompt:
            return deterministic_summary(question, rows, metrics, dimensions)

        prompt = (
            f"{summary_prompt}\n"
            f"Question: {question}\n"
            f"Metrics: {metrics}\n"
            f"Dimensions: {dimensions}\n"
            f"Rows: {json.dumps(rows[:30], default=str)}\n"
            f"Insights: {json.dumps(insights[:5], default=str)}\n"
            f"Related prior analyses: {json.dumps(related[:3], default=str)}"
        )

        try:
            text = self.provider.complete(prompt, json_mode=False)
            if text:
                return text
        except Exception:
            pass

        return deterministic_summary(question, rows, metrics, dimensions)

    def suggest_followups(
        self,
        *,
        question: str,
        rows: list[dict[str, Any]],
        metrics: list[str],
        dimensions: list[str],
        related_queries: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        followups_prompt = self._load_prompt("followups.txt")

        default = [
            f"What changed most for {metrics[0]} this period?" if metrics else "What changed most this period?",
            f"Break this down further by {dimensions[0]}." if dimensions else "Can we break this down by region?",
            "Which segment is at highest risk next period?",
        ]

        related = related_queries or []
        if related:
            prior_questions = []
            for item in related:
                prior_question = str(item.get("question", "")).strip()
                if not prior_question:
                    continue
                if prior_question.lower() == question.strip().lower():
                    continue
                if prior_question in prior_questions:
                    continue
                prior_questions.append(prior_question)
            if prior_questions:
                default = [prior_questions[0], *default][:3]

        if not followups_prompt:
            return default

        prompt = (
            f"{followups_prompt}\n"
            f"Question: {question}\n"
            f"Metrics: {metrics}\n"
            f"Dimensions: {dimensions}\n"
            f"Rows: {json.dumps(rows[:20], default=str)}\n"
            f"Related prior analyses: {json.dumps(related[:3], default=str)}\n"
            "Return JSON array only."
        )

        try:
            raw = self.provider.complete(prompt, json_mode=True)
            value = json.loads(raw)
            if isinstance(value, list) and value:
                merged = [str(item) for item in value if str(item).strip()]
                for item in default:
                    if item not in merged:
                        merged.append(item)
                return merged[:3]
        except Exception:
            pass

        return default


ai_orchestrator = AIOrchestrator()
