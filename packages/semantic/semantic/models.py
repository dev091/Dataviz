from typing import Any

from pydantic import BaseModel, Field


class QueryFilter(BaseModel):
    field: str
    operator: str
    value: Any


class SortSpec(BaseModel):
    field: str
    direction: str = Field(default="desc", pattern="^(asc|desc)$")


class QueryPlan(BaseModel):
    intent: str = "analyze"
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[QueryFilter] = Field(default_factory=list)
    time_grain: str | None = None
    sort: list[SortSpec] = Field(default_factory=list)
    limit: int = 50
