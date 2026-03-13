from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.agents.base import BaseAgent
from app.core.bootstrap import bootstrap_package_paths
from app.services.ai_orchestrator import ai_orchestrator

bootstrap_package_paths()
from analytics.charting import recommend_chart  # noqa: E402
from analytics.insights import detect_insights  # noqa: E402
from semantic.models import QueryPlan  # noqa: E402
from semantic.safety import validate_plan  # noqa: E402
from semantic.sql_builder import build_sql  # noqa: E402


class PlannerAgent(BaseAgent):
    name = "planner_agent"

    def run(self, *, question: str, metric_names: list[str], dimension_names: list[str]) -> tuple[QueryPlan, dict[str, Any]]:
        step = self.make_step({"question": question, "metrics": metric_names, "dimensions": dimension_names})
        step.start()
        try:
            plan = ai_orchestrator.plan_query(question=question, metric_names=metric_names, dimension_names=dimension_names)
            step.complete({"plan": plan.model_dump()})
            return plan, step.to_dict()
        except Exception as exc:  # noqa: BLE001
            step.fail(exc)
            raise


class SafetyAgent(BaseAgent):
    name = "safety_agent"

    def run(self, *, plan: QueryPlan, allowed_metrics: set[str], allowed_dimensions: set[str]) -> dict[str, Any]:
        step = self.make_step({"plan": plan.model_dump()})
        step.start()

        errors = validate_plan(plan, allowed_metrics, allowed_dimensions)
        if errors:
            error_text = "; ".join(errors)
            step.fail(error_text)
            raise ValueError(error_text)

        step.complete({"validated": True})
        return step.to_dict()


class SQLAgent(BaseAgent):
    name = "sql_agent"

    def run(
        self,
        *,
        plan: QueryPlan,
        base_table: str,
        base_alias: str,
        joins: list[dict[str, str]],
        metric_sql: dict[str, str],
        dimension_sql: dict[str, str],
    ) -> tuple[str, dict[str, Any]]:
        step = self.make_step({"plan": plan.model_dump(), "base_table": base_table, "base_alias": base_alias})
        step.start()
        try:
            sql = build_sql(
                plan,
                base_table=base_table,
                base_alias=base_alias,
                joins=joins,
                metric_sql=metric_sql,
                dimension_sql=dimension_sql,
            )
            step.complete({"sql": sql})
            return sql, step.to_dict()
        except Exception as exc:  # noqa: BLE001
            step.fail(exc)
            raise


class QueryExecutionAgent(BaseAgent):
    name = "query_execution_agent"

    def run(self, *, db: Session, sql: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        step = self.make_step({"sql": sql})
        step.start()
        try:
            result = db.execute(text(sql))
            rows = [dict(row._mapping) for row in result.fetchall()]
            step.complete({"row_count": len(rows)})
            return rows, step.to_dict()
        except Exception as exc:  # noqa: BLE001
            step.fail(exc)
            raise


class VisualizationAgent(BaseAgent):
    name = "visualization_agent"

    def run(self, *, question: str, plan: QueryPlan, rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
        step = self.make_step({"question": question, "plan": plan.model_dump(), "row_count": len(rows)})
        step.start()
        try:
            chart = recommend_chart({**plan.model_dump(), "question": question}, rows)
            step.complete({"chart_type": chart.get("type", "unknown")})
            return chart, step.to_dict()
        except Exception as exc:  # noqa: BLE001
            step.fail(exc)
            raise


class InsightAgent(BaseAgent):
    name = "insight_agent"

    def run(
        self,
        *,
        rows: list[dict[str, Any]],
        metrics: list[str],
        dimensions: list[str],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        step = self.make_step({"row_count": len(rows), "metrics": metrics, "dimensions": dimensions})
        step.start()
        try:
            insights = detect_insights(rows, metrics, dimensions)
            step.complete({"insight_count": len(insights)})
            return insights, step.to_dict()
        except Exception as exc:  # noqa: BLE001
            step.fail(exc)
            raise


class NarrativeAgent(BaseAgent):
    name = "narrative_agent"

    def run(
        self,
        *,
        question: str,
        rows: list[dict[str, Any]],
        metrics: list[str],
        dimensions: list[str],
        insights: list[dict[str, Any]],
        related_queries: list[dict[str, Any]] | None = None,
    ) -> tuple[str, list[str], dict[str, Any]]:
        step = self.make_step({"question": question, "metrics": metrics, "dimensions": dimensions, "row_count": len(rows)})
        step.start()
        try:
            summary = ai_orchestrator.summarize(
                question=question,
                rows=rows,
                metrics=metrics,
                dimensions=dimensions,
                insights=insights,
                related_queries=related_queries,
            )
            followups = ai_orchestrator.suggest_followups(
                question=question,
                rows=rows,
                metrics=metrics,
                dimensions=dimensions,
                related_queries=related_queries,
            )
            step.complete({"summary_len": len(summary), "followup_count": len(followups), "related_queries": len(related_queries or [])})
            return summary, followups, step.to_dict()
        except Exception as exc:  # noqa: BLE001
            step.fail(exc)
            raise

