from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PrepFeedbackSummary(BaseModel):
    approved: int = 0
    rejected: int = 0


class PrepPlanStep(BaseModel):
    step_id: str
    title: str
    step_type: str
    target_fields: list[str] = Field(default_factory=list)
    explanation: str
    reversible: bool = True
    revert_strategy: str
    sql_preview: str | None = None
    confidence: float = Field(ge=0, le=1)
    feedback: PrepFeedbackSummary = Field(default_factory=PrepFeedbackSummary)
    applied: bool = False
    applied_at: datetime | None = None


class PrepJoinSuggestion(BaseModel):
    target_dataset_id: str
    target_dataset_name: str
    left_field: str
    right_field: str
    score: float = Field(ge=0, le=1)
    rationale: str


class PrepUnionSuggestion(BaseModel):
    target_dataset_id: str
    target_dataset_name: str
    shared_fields: list[str] = Field(default_factory=list)
    score: float = Field(ge=0, le=1)
    rationale: str


class PrepCalculatedFieldSuggestion(BaseModel):
    name: str
    expression: str
    data_type: str
    rationale: str


class PrepTransformationLineageItem(BaseModel):
    source: str
    description: str
    affected_fields: list[str] = Field(default_factory=list)
    status: str | None = None
    recorded_at: datetime | None = None


class DataPrepPlanResponse(BaseModel):
    dataset_id: str
    dataset_name: str
    dataset_quality_status: str
    generated_at: datetime
    cleaning_steps: list[PrepPlanStep] = Field(default_factory=list)
    join_suggestions: list[PrepJoinSuggestion] = Field(default_factory=list)
    union_suggestions: list[PrepUnionSuggestion] = Field(default_factory=list)
    calculated_field_suggestions: list[PrepCalculatedFieldSuggestion] = Field(default_factory=list)
    transformation_lineage: list[PrepTransformationLineageItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DataPrepFeedbackRequest(BaseModel):
    step_id: str
    decision: Literal["approve", "reject"]
    comment: str | None = None


class DataPrepFeedbackResponse(BaseModel):
    dataset_id: str
    step_id: str
    decision: str
    approved: int
    rejected: int
    note: str


class DataPrepActionRequest(BaseModel):
    step_id: str
    action: Literal["apply", "rollback"]


class DataPrepActionResponse(BaseModel):
    dataset_id: str
    step_id: str
    action: str
    status: str
    note: str
