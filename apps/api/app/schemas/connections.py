from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConnectionCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    connector_type: str
    config: dict[str, Any]


class ConnectionResponse(BaseModel):
    id: str
    workspace_id: str
    organization_id: str
    name: str
    connector_type: str
    status: str
    sync_frequency: str
    last_synced_at: datetime | None


class SyncJobRequest(BaseModel):
    schedule_type: str = Field(pattern="^(manual|daily|weekly)$")
    schedule_time: str | None = None
    weekday: int | None = Field(default=None, ge=0, le=6)


class SyncRunResponse(BaseModel):
    id: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    records_synced: int
    message: str | None
    logs: dict[str, Any]


class CsvUploadResponse(BaseModel):
    file_path: str
