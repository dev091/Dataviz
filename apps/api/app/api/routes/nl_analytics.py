from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_workspace_id, require_role
from app.models.entities import User
from app.schemas.nl import NLQueryRequest, NLQueryResponse
from app.services.audit import write_audit_log
from app.services.nl import execute_nl_query
from app.models.entities import AIActionHistory


router = APIRouter()


@router.post("/query", response_model=NLQueryResponse)
def run_nl_query(
    payload: NLQueryRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> NLQueryResponse:
    try:
        session = execute_nl_query(
            db,
            workspace_id=workspace_id,
            user=current_user,
            semantic_model_id=payload.semantic_model_id,
            question=payload.question,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    write_audit_log(
        db,
        action="nl.query.execute",
        entity_type="ai_query_session",
        entity_id=session.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={"question": payload.question},
    )

    action_history = AIActionHistory(
        workspace_id=workspace_id,
        actor_id=current_user.id,
        action_type="nl_query",
        input_summary=payload.question,
        output_summary=session.summary,
        artifact_ref=session.id,
        artifact_type="ai_query_session",
        confidence_score=1.0,
        status="completed",
        metadata_json={"question": payload.question, "sql": session.sql_text}
    )
    db.add(action_history)
    db.commit()

    followups = getattr(session, "_followups", [])
    insights = getattr(session, "_insights", [])
    trace = getattr(session, "_agent_trace", session.result.get("agent_trace", []))
    related_queries = getattr(session, "_related_queries", session.result.get("related_queries", []))
    plan = session.plan.get("query_plan", session.plan) if isinstance(session.plan, dict) else {}

    return NLQueryResponse(
        ai_query_session_id=session.id,
        plan=plan,
        agent_trace=trace,
        sql=session.sql_text,
        rows=session.result.get("rows", []),
        chart=session.chart,
        summary=session.summary,
        insights=insights,
        follow_up_questions=followups,
        related_queries=related_queries,
        created_at=session.created_at,
    )
