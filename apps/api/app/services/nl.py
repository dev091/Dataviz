from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.entities import AIQuerySession, InsightArtifact, SemanticMetric, User
from app.services.multi_agent_orchestrator import multi_agent_orchestrator
from app.services.semantic import semantic_context


def execute_nl_query(db: Session, *, workspace_id: str, user: User, semantic_model_id: str, question: str) -> AIQuerySession:
    context = semantic_context(db, semantic_model_id)

    metrics = context["metrics"]
    dimensions = context["dimensions"]

    metric_names = [metric.name for metric in metrics if metric.visibility == "public"]
    dimension_names = [dimension.name for dimension in dimensions if dimension.visibility == "public"]

    result = multi_agent_orchestrator.run_query(
        db=db,
        question=question,
        metric_names=metric_names,
        dimension_names=dimension_names,
        base_table=context["base_table"],
        base_alias=context["base_alias"],
        joins=context["joins"],
        metric_sql=context["metric_sql"],
        dimension_sql=context["dimension_sql"],
    )

    session = AIQuerySession(
        workspace_id=workspace_id,
        user_id=user.id,
        semantic_model_id=semantic_model_id,
        question=question,
        plan={
            "query_plan": result.plan.model_dump(),
            "agent_trace": result.agent_trace,
        },
        sql_text=result.sql,
        result={"rows": result.rows, "agent_trace": result.agent_trace},
        chart=result.chart,
        summary=result.summary,
        created_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.flush()

    metric_index = {metric.name: metric.id for metric in metrics}
    primary_metric_id = metric_index.get(result.plan.metrics[0]) if result.plan.metrics else None

    for insight in result.insights[:5]:
        db.add(
            InsightArtifact(
                workspace_id=workspace_id,
                dashboard_id=None,
                metric_id=primary_metric_id,
                insight_type=insight.get("type", "insight"),
                title=insight.get("title", "Insight"),
                body=insight.get("body", ""),
                data=insight.get("data", {}),
            )
        )

    db.flush()
    session._followups = result.followups  # type: ignore[attr-defined]
    session._insights = result.insights  # type: ignore[attr-defined]
    session._agent_trace = result.agent_trace  # type: ignore[attr-defined]
    return session


def evaluate_alert_metric(db: Session, *, semantic_model_id: str, metric_id: str) -> float:
    context = semantic_context(db, semantic_model_id)
    metric = db.get(SemanticMetric, metric_id)
    if not metric:
        raise ValueError("Metric not found")

    sql = f"SELECT {metric.formula} AS value FROM {context['base_table']} AS {context['base_alias']}"
    row = db.execute(text(sql)).first()
    if not row:
        return 0.0
    value = row._mapping.get("value")
    return float(value or 0)
