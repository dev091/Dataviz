from datetime import datetime
from typing import Any

from pydantic import BaseModel


class NLQueryRequest(BaseModel):
    semantic_model_id: str
    question: str


class NLQueryResponse(BaseModel):
    ai_query_session_id: str
    plan: dict[str, Any]
    agent_trace: list[dict[str, Any]]
    sql: str
    rows: list[dict[str, Any]]
    chart: dict[str, Any]
    summary: str
    insights: list[dict[str, Any]]
    follow_up_questions: list[str]
    related_queries: list[dict[str, Any]]
    created_at: datetime
