from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.deps import get_db, get_workspace_id, require_role
from app.models.entities import DataConnection, SyncRun, User, Workspace
from app.schemas.connections import (
    ConnectionCreateRequest,
    ConnectionResponse,
    FileUploadResponse,
    SyncJobRequest,
    SyncRunResponse,
)
from app.services.audit import write_audit_log
from app.services.storage import storage
from app.services.sync import create_or_update_sync_job, discover_connection, run_sync


router = APIRouter()

SUPPORTED_UPLOAD_FORMATS = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".txt": "txt",
    ".json": "json",
    ".jsonl": "jsonl",
    ".ndjson": "jsonl",
    ".xlsx": "xlsx",
    ".xls": "xls",
    ".ods": "ods",
    ".parquet": "parquet",
    ".xml": "xml",
}


def _workspace(db: Session, workspace_id: str) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


def _connection_or_404(db: Session, workspace_id: str, connection_id: str) -> DataConnection:
    conn = db.scalar(select(DataConnection).where(DataConnection.id == connection_id, DataConnection.workspace_id == workspace_id))
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return conn


def _detect_upload_format(filename: str | None) -> str:
    if not filename:
        raise HTTPException(status_code=400, detail="Uploaded file is missing a filename")
    suffix = Path(filename).suffix.lower()
    file_format = SUPPORTED_UPLOAD_FORMATS.get(suffix)
    if not file_format:
        supported = ", ".join(sorted({value for value in SUPPORTED_UPLOAD_FORMATS.values()}))
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Supported formats: {supported}")
    return file_format


@router.post("/files/upload", response_model=FileUploadResponse)
@router.post("/csv/upload", response_model=FileUploadResponse, include_in_schema=False)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("Analyst")),
) -> FileUploadResponse:
    file_format = _detect_upload_format(file.filename)
    file_path = await storage.save_upload(file)
    return FileUploadResponse(file_path=file_path, file_name=file.filename or "upload", file_format=file_format)


@router.get("", response_model=list[ConnectionResponse])
def list_connections(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> list[ConnectionResponse]:
    rows = db.scalars(select(DataConnection).where(DataConnection.workspace_id == workspace_id)).all()
    return [
        ConnectionResponse(
            id=row.id,
            workspace_id=row.workspace_id,
            organization_id=row.organization_id,
            name=row.name,
            connector_type=row.connector_type,
            status=row.status,
            sync_frequency=row.sync_frequency,
            last_synced_at=row.last_synced_at,
        )
        for row in rows
    ]


@router.post("", response_model=ConnectionResponse)
def create_connection(
    payload: ConnectionCreateRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> ConnectionResponse:
    workspace = _workspace(db, workspace_id)

    connection = DataConnection(
        organization_id=workspace.organization_id,
        workspace_id=workspace_id,
        created_by=current_user.id,
        name=payload.name,
        connector_type=payload.connector_type,
        config=payload.config,
        status="ready",
        sync_frequency="manual",
    )
    db.add(connection)
    db.flush()

    write_audit_log(
        db,
        action="connection.create",
        entity_type="data_connection",
        entity_id=connection.id,
        user=current_user,
        organization_id=workspace.organization_id,
        workspace_id=workspace_id,
        metadata={"connector_type": connection.connector_type, "name": connection.name},
    )
    db.commit()

    return ConnectionResponse(
        id=connection.id,
        workspace_id=connection.workspace_id,
        organization_id=connection.organization_id,
        name=connection.name,
        connector_type=connection.connector_type,
        status=connection.status,
        sync_frequency=connection.sync_frequency,
        last_synced_at=connection.last_synced_at,
    )


@router.post("/{connection_id}/discover")
def discover(
    connection_id: str,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> dict:
    connection = _connection_or_404(db, workspace_id, connection_id)
    try:
        preview = discover_connection(connection)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return preview


@router.post("/{connection_id}/sync", response_model=SyncRunResponse)
def manual_sync(
    connection_id: str,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> SyncRunResponse:
    connection = _connection_or_404(db, workspace_id, connection_id)
    run = run_sync(db, connection)

    write_audit_log(
        db,
        action="connection.sync",
        entity_type="sync_run",
        entity_id=run.id,
        user=current_user,
        organization_id=connection.organization_id,
        workspace_id=workspace_id,
        metadata={"status": run.status, "records_synced": run.records_synced},
    )

    db.commit()
    return SyncRunResponse(
        id=run.id,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        records_synced=run.records_synced,
        message=run.message,
        logs=run.logs,
    )


@router.get("/{connection_id}/sync-runs", response_model=list[SyncRunResponse])
def list_sync_runs(
    connection_id: str,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> list[SyncRunResponse]:
    _connection_or_404(db, workspace_id, connection_id)
    rows = db.scalars(
        select(SyncRun).where(SyncRun.connection_id == connection_id).order_by(SyncRun.started_at.desc()).limit(50)
    ).all()

    return [
        SyncRunResponse(
            id=row.id,
            status=row.status,
            started_at=row.started_at,
            finished_at=row.finished_at,
            records_synced=row.records_synced,
            message=row.message,
            logs=row.logs,
        )
        for row in rows
    ]


@router.post("/{connection_id}/sync-jobs")
def upsert_sync_job(
    connection_id: str,
    payload: SyncJobRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
) -> dict:
    connection = _connection_or_404(db, workspace_id, connection_id)
    job = create_or_update_sync_job(db, connection, payload.schedule_type, payload.schedule_time, payload.weekday)
    connection.sync_frequency = payload.schedule_type

    write_audit_log(
        db,
        action="connection.schedule.update",
        entity_type="sync_job",
        entity_id=job.id,
        user=current_user,
        organization_id=connection.organization_id,
        workspace_id=workspace_id,
        metadata={
            "schedule_type": payload.schedule_type,
            "schedule_time": payload.schedule_time,
            "weekday": payload.weekday,
        },
    )

    db.commit()
    return {
        "id": job.id,
        "connection_id": connection.id,
        "schedule_type": job.schedule_type,
        "schedule_time": job.schedule_time,
        "weekday": job.weekday,
        "enabled": job.enabled,
        "next_run_at": job.next_run_at,
    }
