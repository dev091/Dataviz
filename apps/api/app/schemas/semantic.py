from datetime import datetime

from pydantic import BaseModel, Field


class MetricInput(BaseModel):
    name: str
    label: str
    formula: str
    aggregation: str = "sum"
    value_format: str | None = None
    visibility: str = "public"


class DimensionInput(BaseModel):
    name: str
    label: str
    field_ref: str
    data_type: str
    time_grain: str | None = None
    visibility: str = "public"


class CalculatedFieldInput(BaseModel):
    name: str
    expression: str
    data_type: str


class CreateSemanticModelRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    model_key: str = Field(min_length=2, max_length=255)
    description: str | None = None
    base_dataset_id: str
    joins: list[dict] = Field(default_factory=list)
    metrics: list[MetricInput]
    dimensions: list[DimensionInput]
    calculated_fields: list[CalculatedFieldInput] = Field(default_factory=list)


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


class ValidateSemanticModelResponse(BaseModel):
    valid: bool
    errors: list[str]
