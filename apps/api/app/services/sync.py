import re
from datetime import datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.bootstrap import bootstrap_package_paths
from app.models.entities import DataConnection, Dataset, DatasetField, SyncJob, SyncRun
from app.services.data_quality import profile_dataframe

bootstrap_package_paths()
from connectors.registry import get_connector  # noqa: E402
from connectors.retry import ConnectorExecutionError  # noqa: E402


def _safe_table_name(raw: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]", "_", raw).lower()
    return value[:60]


def _next_run(job: SyncJob, now: datetime | None = None) -> datetime | None:
    if job.schedule_type == "manual":
        return None

    now = now or datetime.now(timezone.utc)
    schedule_time = job.schedule_time or "09:00"
    hour, minute = [int(part) for part in schedule_time.split(":")]

    if job.schedule_type == "daily":
        candidate = datetime.combine(now.date(), time(hour=hour, minute=minute, tzinfo=timezone.utc))
        if candidate <= now:
            candidate = candidate + timedelta(days=1)
        return candidate

    if job.schedule_type == "weekly":
        weekday = 0 if job.weekday is None else job.weekday
        candidate = datetime.combine(now.date(), time(hour=hour, minute=minute, tzinfo=timezone.utc))
        days = (weekday - candidate.weekday()) % 7
        candidate = candidate + timedelta(days=days)
        if candidate <= now:
            candidate = candidate + timedelta(days=7)
        return candidate

    return None


def discover_connection(connection: DataConnection) -> dict[str, Any]:
    connector = get_connector(connection.connector_type)
    connector.validate_config(connection.config)
    preview, retry_metadata = connector.call_with_retry("preview_schema", lambda: connector.preview_schema(connection.config))
    if isinstance(preview, dict):
        preview.setdefault("meta", {})
        preview["meta"]["retry"] = retry_metadata.to_dict()
    return preview


def create_or_update_sync_job(db: Session, connection: DataConnection, schedule_type: str, schedule_time: str | None, weekday: int | None) -> SyncJob:
    stmt = select(SyncJob).where(SyncJob.connection_id == connection.id)
    job = db.scalar(stmt)
    if not job:
        job = SyncJob(connection_id=connection.id)
        db.add(job)

    job.schedule_type = schedule_type
    job.schedule_time = schedule_time
    job.weekday = weekday
    job.enabled = schedule_type != "manual"
    job.next_run_at = _next_run(job)
    db.flush()
    return job


def run_sync(db: Session, connection: DataConnection, *, job_id: str | None = None, dataset_name: str | None = None) -> SyncRun:
    connector = get_connector(connection.connector_type)
    connector.validate_config(connection.config)

    run = SyncRun(connection_id=connection.id, job_id=job_id, status="running", logs={})
    db.add(run)
    db.flush()

    try:
        sync_results, retry_metadata = connector.call_with_retry(
            "sync",
            lambda: connector.sync(connection.config, dataset_name=dataset_name),
        )
        total_rows = 0
        logs: dict[str, Any] = {"datasets": [], "retry": retry_metadata.to_dict()}

        for result in sync_results:
            total_rows += result.row_count
            physical_table = f"ws_{connection.workspace_id.replace('-', '')[:8]}_{_safe_table_name(result.dataset_name)}"
            quality_profile = profile_dataframe(
                result.dataframe,
                cleaning=result.logs.get("cleaning") if isinstance(result.logs, dict) else None,
            )

            existing_dataset = db.scalar(
                select(Dataset).where(
                    Dataset.workspace_id == connection.workspace_id,
                    Dataset.connection_id == connection.id,
                    Dataset.name == result.dataset_name,
                )
            )
            if not existing_dataset:
                dataset = Dataset(
                    workspace_id=connection.workspace_id,
                    connection_id=connection.id,
                    name=result.dataset_name,
                    source_table=result.dataset_name,
                    physical_table=physical_table,
                    row_count=result.row_count,
                    quality_status=quality_profile["status"],
                    quality_profile=quality_profile,
                    last_sync_run_id=run.id,
                )
                db.add(dataset)
                db.flush()
            else:
                dataset = existing_dataset
                dataset.physical_table = physical_table
                dataset.row_count = result.row_count
                dataset.quality_status = quality_profile["status"]
                dataset.quality_profile = quality_profile
                dataset.last_sync_run_id = run.id
                db.flush()

            bind = db.get_bind()
            if bind.dialect.name == "sqlite":
                db.commit()
            result.dataframe.to_sql(physical_table, bind, if_exists="replace", index=False)

            db.execute(delete(DatasetField).where(DatasetField.dataset_id == dataset.id))
            for column in result.dataframe.columns:
                dtype = str(result.dataframe[column].dtype)
                is_metric = dtype.startswith("int") or dtype.startswith("float")
                db.add(
                    DatasetField(
                        dataset_id=dataset.id,
                        name=str(column),
                        data_type=dtype,
                        nullable=True,
                        is_dimension=not is_metric,
                        is_metric=is_metric,
                    )
                )

            logs["datasets"].append(
                {
                    "name": result.dataset_name,
                    "rows": result.row_count,
                    "physical_table": physical_table,
                    "quality_profile": quality_profile,
                    **result.logs,
                }
            )

        run.status = "success"
        run.records_synced = total_rows
        run.logs = logs
        run.finished_at = datetime.now(timezone.utc)

        connection.last_synced_at = run.finished_at
        connection.status = "ready"

    except ConnectorExecutionError as exc:
        run.status = "failed"
        run.message = str(exc)
        run.logs = {"retry": exc.to_dict()}
        run.finished_at = datetime.now(timezone.utc)
        connection.status = "error"
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.message = str(exc)
        run.logs = {"error": str(exc)}
        run.finished_at = datetime.now(timezone.utc)
        connection.status = "error"

    db.flush()
    return run


def mark_job_executed(db: Session, job: SyncJob) -> None:
    now = datetime.now(timezone.utc)
    job.last_run_at = now
    job.next_run_at = _next_run(job, now=now)
    db.flush()
