from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.ai.agents.query_agents import (
    InsightAgent,
    NarrativeAgent,
    PlannerAgent,
    QueryExecutionAgent,
    SQLAgent,
    SafetyAgent,
    VisualizationAgent,
)
from app.core.bootstrap import bootstrap_package_paths

bootstrap_package_paths()
from semantic.models import QueryPlan  # noqa: E402


@dataclass
class MultiAgentQueryResult:
    plan: QueryPlan
    sql: str
    rows: list[dict[str, Any]]
    chart: dict[str, Any]
    insights: list[dict[str, Any]]
    summary: str
    followups: list[str]
    agent_trace: list[dict[str, Any]]


class MultiAgentOrchestrator:
    def __init__(self) -> None:
        self.planner = PlannerAgent()
        self.safety = SafetyAgent()
        self.sql = SQLAgent()
        self.execution = QueryExecutionAgent()
        self.visualization = VisualizationAgent()
        self.insight = InsightAgent()
        self.narrative = NarrativeAgent()

    @staticmethod
    def _with_time_grain(plan: QueryPlan, dimension_sql: dict[str, str]) -> dict[str, str]:
        cloned = dimension_sql.copy()
        if not plan.time_grain:
            return cloned

        for dim_name in plan.dimensions:
            dim_expr = cloned.get(dim_name)
            if dim_expr and "date" in dim_name.lower() and "date_trunc" not in dim_expr.lower():
                cloned[dim_name] = f"DATE_TRUNC('{plan.time_grain}', {dim_expr})"
        return cloned

    def run_query(
        self,
        *,
        db: Session,
        question: str,
        metric_names: list[str],
        dimension_names: list[str],
        base_table: str,
        base_alias: str,
        joins: list[dict[str, str]],
        metric_sql: dict[str, str],
        dimension_sql: dict[str, str],
    ) -> MultiAgentQueryResult:
        trace: list[dict[str, Any]] = []

        plan, plan_step = self.planner.run(
            question=question,
            metric_names=metric_names,
            dimension_names=dimension_names,
        )
        trace.append(plan_step)

        safety_step = self.safety.run(
            plan=plan,
            allowed_metrics=set(metric_names),
            allowed_dimensions=set(dimension_names),
        )
        trace.append(safety_step)

        dimension_sql_grained = self._with_time_grain(plan, dimension_sql)

        sql_text, sql_step = self.sql.run(
            plan=plan,
            base_table=base_table,
            base_alias=base_alias,
            joins=joins,
            metric_sql=metric_sql,
            dimension_sql=dimension_sql_grained,
        )
        trace.append(sql_step)

        rows, execution_step = self.execution.run(db=db, sql=sql_text)
        trace.append(execution_step)

        chart, viz_step = self.visualization.run(plan=plan, rows=rows)
        trace.append(viz_step)

        insights, insight_step = self.insight.run(rows=rows, metrics=plan.metrics, dimensions=plan.dimensions)
        trace.append(insight_step)

        summary, followups, narrative_step = self.narrative.run(
            question=question,
            rows=rows,
            metrics=plan.metrics,
            dimensions=plan.dimensions,
            insights=insights,
        )
        trace.append(narrative_step)

        return MultiAgentQueryResult(
            plan=plan,
            sql=sql_text,
            rows=rows,
            chart=chart,
            insights=insights,
            summary=summary,
            followups=followups,
            agent_trace=trace,
        )


multi_agent_orchestrator = MultiAgentOrchestrator()
