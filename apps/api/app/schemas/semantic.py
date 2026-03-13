from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


CertificationStatus = Literal["draft", "review", "certified", "deprecated"]


class GovernanceInput(BaseModel):
    owner_name: str | None = None
    owner_email: str | None = None
    certification_status: CertificationStatus = "draft"
    certification_note: str | None = None
    trusted_for_nl: bool = True


class JoinInput(BaseModel):
    left_dataset_id: str
    right_dataset_id: str
    left_field: str
    right_field: str
    join_type: str = "left"
    left_alias: str | None = None
    right_alias: str | None = None


class MetricInput(BaseModel):
    name: str
    label: str
    formula: str
    aggregation: str = "sum"
    value_format: str | None = None
    visibility: str = "public"
    description: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    owner_name: str | None = None
    certification_status: CertificationStatus = "draft"
    certification_note: str | None = None
    lineage: dict | None = None


class DimensionInput(BaseModel):
    name: str
    label: str
    field_ref: str
    data_type: str
    time_grain: str | None = None
    visibility: str = "public"
    description: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    hierarchy: list[str] = Field(default_factory=list)
    owner_name: str | None = None
    certification_status: CertificationStatus = "draft"


class CalculatedFieldInput(BaseModel):
    name: str
    expression: str
    data_type: str


class DraftSemanticModelRequest(BaseModel):
    dataset_id: str
    name: str | None = None
    model_key: str | None = None
    description: str | None = None


class CreateSemanticModelRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    model_key: str = Field(min_length=2, max_length=255)
    description: str | None = None
    base_dataset_id: str
    joins: list[JoinInput] = Field(default_factory=list)
    metrics: list[MetricInput]
    dimensions: list[DimensionInput]
    calculated_fields: list[CalculatedFieldInput] = Field(default_factory=list)
    governance: GovernanceInput = Field(default_factory=GovernanceInput)


class DraftSemanticModelResponse(CreateSemanticModelRequest):
    inference_notes: list[str] = Field(default_factory=list)


class SemanticModelResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    model_key: str
    version: int
    is_active: bool
    base_dataset_id: str
    description: str | None
    created_at: datetime


class TrustActivityItem(BaseModel):
    activity_type: str
    title: str
    detail: str | None = None
    created_at: datetime


class TrustLineageSummary(BaseModel):
    base_dataset_name: str
    base_quality_status: str
    joins_configured: int
    datasets_in_scope: list[str] = Field(default_factory=list)
    metrics_governed: int
    dimensions_governed: int
    metrics_with_lineage: int = 0


class SemanticTrustPanelResponse(BaseModel):
    model_id: str
    model_name: str
    model_key: str
    version: int
    governance: GovernanceInput
    lineage_summary: TrustLineageSummary
    recent_activity: list[TrustActivityItem] = Field(default_factory=list)
    open_gaps: list[str] = Field(default_factory=list)


class SemanticModelDetailResponse(SemanticModelResponse):
    joins: list[JoinInput]
    metrics: list[MetricInput]
    dimensions: list[DimensionInput]
    calculated_fields: list[CalculatedFieldInput]
    governance: GovernanceInput = Field(default_factory=GovernanceInput)


class ValidateSemanticModelResponse(BaseModel):
    valid: bool
    errors: list[str]

