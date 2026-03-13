from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.deps import get_db, get_workspace_id, require_role
from app.models.entities import AIActionHistory, AIQuerySession, Dashboard, DashboardWidget, SemanticModel, User
from app.schemas.dashboards import (
    AutoComposeDashboardRequest,
    AutoComposeDashboardResponse,
    DashboardCreateRequest,
    DashboardResponse,
    GenerateReportPackRequest,
    ReportPackResponse,
    SaveAIWidgetRequest,
    WidgetInput,
    WidgetResponse,
)
from app.services.audit import write_audit_log
from app.services.dashboard_composer import compose_dashboard_widgets
from app.services.reporting import generate_dashboard_report_pack


router = APIRouter()


def _dashboard_or_404(db: Session, workspace_id: str, dashboard_id: str) -> Dashboard:
    dashboard = db.scalar(select(Dashboard).where(Dashboard.id == dashboard_id, Dashboard.workspace_id == workspace_id))
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return dashboard


def _widget_or_404(db: Session, dashboard_id: str, widget_id: str) -> DashboardWidget:
    widget = db.scalar(select(DashboardWidget).where(DashboardWidget.id == widget_id, DashboardWidget.dashboard_id == dashboard_id))
    if not widget:
        raise HTTPException(status_code=404, detail="Dashboard widget not found")
    return widget


def _widget_response(widget: DashboardWidget) -> WidgetResponse:
    return WidgetResponse(
        id=widget.id,
        dashboard_id=widget.dashboard_id,
        title=widget.title,
        widget_type=widget.widget_type,
        config=widget.config,
        position=widget.position,
    )


@router.get("", response_model=list[DashboardResponse])
def list_dashboards(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> list[DashboardResponse]:
    rows = db.scalars(select(Dashboard).where(Dashboard.workspace_id == workspace_id).order_by(Dashboard.updated_at.desc())).all()
    return [
        DashboardResponse(
            id=row.id,
            workspace_id=row.workspace_id,
            name=row.name,
            description=row.description,
            layout=row.layout,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.post("", response_model=DashboardResponse)
def create_dashboard(
    payload: DashboardCreateRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> DashboardResponse:
    dashboard = Dashboard(
        workspace_id=workspace_id,
        created_by=current_user.id,
        name=payload.name,
        description=payload.description,
        layout=payload.layout,
    )
    db.add(dashboard)
    db.flush()

    write_audit_log(
        db,
        action="dashboard.create",
        entity_type="dashboard",
        entity_id=dashboard.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={"name": dashboard.name},
    )
    db.commit()

    return DashboardResponse(
        id=dashboard.id,
        workspace_id=dashboard.workspace_id,
        name=dashboard.name,
        description=dashboard.description,
        layout=dashboard.layout,
        created_at=dashboard.created_at,
        updated_at=dashboard.updated_at,
    )


@router.get("/{dashboard_id}")
def get_dashboard(
    dashboard_id: str,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> dict:
    dashboard = _dashboard_or_404(db, workspace_id, dashboard_id)
    widgets = db.scalars(select(DashboardWidget).where(DashboardWidget.dashboard_id == dashboard_id)).all()
    return {
        "id": dashboard.id,
        "name": dashboard.name,
        "description": dashboard.description,
        "layout": dashboard.layout,
        "widgets": [
            {
                "id": widget.id,
                "title": widget.title,
                "widget_type": widget.widget_type,
                "config": widget.config,
                "position": widget.position,
            }
            for widget in widgets
        ],
    }


@router.put("/{dashboard_id}", response_model=DashboardResponse)
def update_dashboard(
    dashboard_id: str,
    payload: DashboardCreateRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> DashboardResponse:
    dashboard = _dashboard_or_404(db, workspace_id, dashboard_id)
    dashboard.name = payload.name
    dashboard.description = payload.description
    dashboard.layout = payload.layout
    db.flush()

    write_audit_log(
        db,
        action="dashboard.update",
        entity_type="dashboard",
        entity_id=dashboard.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={"name": dashboard.name},
    )

    db.commit()
    return DashboardResponse(
        id=dashboard.id,
        workspace_id=dashboard.workspace_id,
        name=dashboard.name,
        description=dashboard.description,
        layout=dashboard.layout,
        created_at=dashboard.created_at,
        updated_at=dashboard.updated_at,
    )


@router.post("/{dashboard_id}/widgets", response_model=WidgetResponse)
def add_widget(
    dashboard_id: str,
    payload: WidgetInput,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> WidgetResponse:
    _dashboard_or_404(db, workspace_id, dashboard_id)
    widget = DashboardWidget(
        dashboard_id=dashboard_id,
        title=payload.title,
        widget_type=payload.widget_type,
        config=payload.config,
        position=payload.position,
    )
    db.add(widget)
    db.flush()

    write_audit_log(
        db,
        action="dashboard.widget.add",
        entity_type="dashboard_widget",
        entity_id=widget.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={"dashboard_id": dashboard_id, "widget_type": widget.widget_type},
    )
    db.commit()

    return _widget_response(widget)


@router.post("/{dashboard_id}/auto-compose", response_model=AutoComposeDashboardResponse)
def auto_compose_dashboard(
    dashboard_id: str,
    payload: AutoComposeDashboardRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> AutoComposeDashboardResponse:
    _dashboard_or_404(db, workspace_id, dashboard_id)
    semantic_model = db.scalar(
        select(SemanticModel).where(SemanticModel.id == payload.semantic_model_id, SemanticModel.workspace_id == workspace_id)
    )
    if not semantic_model:
        raise HTTPException(status_code=404, detail="Semantic model not found")

    widget_payloads, notes = compose_dashboard_widgets(
        db,
        dashboard_id=dashboard_id,
        semantic_model=semantic_model,
        goal=payload.goal,
        max_widgets=payload.max_widgets,
    )

    created_ids: list[str] = []
    for widget_payload in widget_payloads:
        widget = DashboardWidget(
            dashboard_id=dashboard_id,
            title=widget_payload["title"],
            widget_type=widget_payload["widget_type"],
            config=widget_payload["config"],
            position=widget_payload["position"],
        )
        db.add(widget)
        db.flush()
        created_ids.append(widget.id)

    write_audit_log(
        db,
        action="dashboard.auto_compose",
        entity_type="dashboard",
        entity_id=dashboard_id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={
            "semantic_model_id": payload.semantic_model_id,
            "goal": payload.goal,
            "widgets_added": len(created_ids),
            "widget_ids": created_ids,
        },
    )
    
    action_history = AIActionHistory(
        workspace_id=workspace_id,
        actor_id=current_user.id,
        action_type="auto_compose",
        input_summary=f"Compose dashboard for goal: {payload.goal}",
        output_summary=f"Added {len(created_ids)} widgets: {', '.join([w['title'] for w in widget_payloads])}",
        artifact_ref=dashboard_id,
        artifact_type="dashboard",
        confidence_score=0.9,
        status="completed",
        metadata_json={
            "semantic_model_id": payload.semantic_model_id,
            "goal": payload.goal,
            "widgets_added": len(created_ids),
        }
    )
    db.add(action_history)

    db.commit()
    return AutoComposeDashboardResponse(dashboard_id=dashboard_id, widgets_added=len(created_ids), notes=notes)


@router.put("/{dashboard_id}/widgets/{widget_id}", response_model=WidgetResponse)
def update_widget(
    dashboard_id: str,
    widget_id: str,
    payload: WidgetInput,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> WidgetResponse:
    _dashboard_or_404(db, workspace_id, dashboard_id)
    widget = _widget_or_404(db, dashboard_id, widget_id)
    widget.title = payload.title
    widget.widget_type = payload.widget_type
    widget.config = payload.config
    widget.position = payload.position
    db.flush()

    write_audit_log(
        db,
        action="dashboard.widget.update",
        entity_type="dashboard_widget",
        entity_id=widget.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={"dashboard_id": dashboard_id, "widget_type": widget.widget_type},
    )
    db.commit()
    return _widget_response(widget)


@router.delete("/{dashboard_id}/widgets/{widget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_widget(
    dashboard_id: str,
    widget_id: str,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> Response:
    _dashboard_or_404(db, workspace_id, dashboard_id)
    widget = _widget_or_404(db, dashboard_id, widget_id)

    write_audit_log(
        db,
        action="dashboard.widget.delete",
        entity_type="dashboard_widget",
        entity_id=widget.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={"dashboard_id": dashboard_id, "widget_type": widget.widget_type},
    )
    db.delete(widget)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{dashboard_id}/widgets/from-ai", response_model=WidgetResponse)
def save_ai_widget(
    dashboard_id: str,
    payload: SaveAIWidgetRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> WidgetResponse:
    _dashboard_or_404(db, workspace_id, dashboard_id)
    session = db.scalar(
        select(AIQuerySession).where(
            AIQuerySession.id == payload.ai_query_session_id,
            AIQuerySession.workspace_id == workspace_id,
        )
    )
    if not session:
        raise HTTPException(status_code=404, detail="AI query session not found")

    widget = DashboardWidget(
        dashboard_id=dashboard_id,
        title=payload.title,
        widget_type=session.chart.get("type", "table"),
        config={
            "chart": session.chart,
            "summary": session.summary,
            "rows": session.result.get("rows", []),
        },
        position=payload.position,
    )
    db.add(widget)
    db.flush()

    write_audit_log(
        db,
        action="dashboard.widget.save_ai",
        entity_type="dashboard_widget",
        entity_id=widget.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={"ai_query_session_id": session.id},
    )

    db.commit()
    return _widget_response(widget)


@router.post("/{dashboard_id}/report-pack", response_model=ReportPackResponse)
def generate_report_pack(
    dashboard_id: str,
    payload: GenerateReportPackRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> ReportPackResponse:
    dashboard = _dashboard_or_404(db, workspace_id, dashboard_id)
    report_pack = generate_dashboard_report_pack(
        db,
        dashboard=dashboard,
        audience=payload.audience,
        goal=payload.goal,
        report_type=payload.report_type,
        operating_views=payload.operating_views,
        exception_report_title=payload.exception_report_title,
    )

    write_audit_log(
        db,
        action="dashboard.report_pack.generate",
        entity_type="dashboard",
        entity_id=dashboard.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={
            "audience": payload.audience,
            "goal": payload.goal,
            "report_type": payload.report_type,
            "operating_views": payload.operating_views,
        },
    )

    action_history = AIActionHistory(
        workspace_id=workspace_id,
        actor_id=current_user.id,
        action_type="report_pack",
        input_summary=f"Generate {payload.report_type} report for {payload.audience}",
        output_summary=f"Executives summary generated for dashboard {dashboard.name}",
        artifact_ref=dashboard_id,
        artifact_type="dashboard_report",
        confidence_score=0.95,
        status="completed",
        metadata_json={
            "audience": payload.audience,
            "goal": payload.goal,
            "report_type": payload.report_type,
        }
    )
    db.add(action_history)

    db.commit()
    return ReportPackResponse(**report_pack)


@router.get("/{dashboard_id}/executive-summary")
def dashboard_executive_summary(
    dashboard_id: str,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> dict:
    dashboard = _dashboard_or_404(db, workspace_id, dashboard_id)
    widgets = db.scalars(select(DashboardWidget).where(DashboardWidget.dashboard_id == dashboard_id)).all()

    summaries: list[str] = []
    for widget in widgets:
        summary = widget.config.get("summary") if isinstance(widget.config, dict) else None
        if isinstance(summary, str) and summary.strip():
            summaries.append(summary.strip())

    if not summaries:
        return {
            "dashboard_id": dashboard.id,
            "summary": "No AI-generated widget summaries are available yet. Run NL analytics and save results to this dashboard.",
            "suggested_next_questions": [
                "Which segment changed most this week?",
                "Where are we underperforming vs last period?",
                "What is driving top-line movement?",
            ],
        }

    joined = " ".join(summaries[:4])
    return {
        "dashboard_id": dashboard.id,
        "summary": joined,
        "suggested_next_questions": [
            "How does this compare to previous period?",
            "Which regions are driving variance?",
            "What action should we prioritize this week?",
        ],
    }
