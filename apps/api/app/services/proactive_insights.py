from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.bootstrap import bootstrap_package_paths
from app.models.entities import InsightArtifact, SemanticDimension, SemanticMetric, SemanticModel
from app.services.ai_orchestrator import ai_orchestrator

bootstrap_package_paths()
from analytics.insights import detect_insights  # noqa: E402


def run_proactive_insight_agents(db: Session) -> int:
    created = 0

    models = db.scalars(select(SemanticModel).where(SemanticModel.is_active.is_(True))).all()
    for model in models:
        metrics = db.scalars(
            select(SemanticMetric).where(SemanticMetric.semantic_model_id == model.id, SemanticMetric.visibility == "public")
        ).all()
        dimensions = db.scalars(
            select(SemanticDimension).where(
                SemanticDimension.semantic_model_id == model.id,
                SemanticDimension.visibility == "public",
            )
        ).all()

        time_dimension = next((dim for dim in dimensions if "date" in dim.name.lower()), None)
        dataset_table = None
        if model.base_dataset_id:
            dataset_row = db.execute(
                text("SELECT physical_table FROM datasets WHERE id = :dataset_id"),
                {"dataset_id": model.base_dataset_id},
            ).first()
            if dataset_row:
                dataset_table = dataset_row._mapping.get("physical_table")

        if not dataset_table:
            continue

        for metric in metrics:
            try:
                if time_dimension:
                    sql = (
                        f"SELECT {time_dimension.field_ref} AS {time_dimension.name}, "
                        f"{metric.formula} AS {metric.name} "
                        f"FROM {dataset_table} "
                        f"GROUP BY {time_dimension.field_ref} "
                        f"ORDER BY {time_dimension.field_ref} DESC LIMIT 24"
                    )
                    dim_names = [time_dimension.name]
                else:
                    sql = f"SELECT {metric.formula} AS {metric.name} FROM {dataset_table}"
                    dim_names = []

                rows = [dict(row._mapping) for row in db.execute(text(sql)).fetchall()]
                if not rows:
                    continue

                insights = detect_insights(rows, [metric.name], dim_names)
                if not insights:
                    continue

                summary = ai_orchestrator.summarize(
                    question=f"Proactive monitoring for {metric.name}",
                    rows=rows,
                    metrics=[metric.name],
                    dimensions=dim_names,
                    insights=insights,
                )

                db.add(
                    InsightArtifact(
                        workspace_id=model.workspace_id,
                        dashboard_id=None,
                        metric_id=metric.id,
                        insight_type="proactive_summary",
                        title=f"Proactive update: {metric.label}",
                        body=summary,
                        data={"metric": metric.name, "insights": insights[:3]},
                    )
                )
                created += 1

            except Exception:
                continue

    db.flush()
    return created
