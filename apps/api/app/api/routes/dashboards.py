from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_db, get_workspace_id, require_role
from app.models.entities import AIQuerySession, Dashboard, DashboardWidget, User
from app.schemas.dashboards import DashboardCreateRequest, DashboardResponse, SaveAIWidgetRequest, WidgetInput
from app.services.audit import write_audit_log


router = APIRouter()


def _dashboard_or_404(db: Session, workspace_id: str, dashboard_id: str) -> Dashboard:
    dashboard = db.scalar(select(Dashboard).where(Dashboard.id == dashboard_id, Dashboard.workspace_id == workspace_id))
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return dashboard


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


@router.post("/{dashboard_id}/widgets")
def add_widget(
    dashboard_id: str,
    payload: WidgetInput,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> dict:
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
        metadata={"dashboard_id": dashboard_id},
    )
    db.commit()

    return {
        "id": widget.id,
        "dashboard_id": widget.dashboard_id,
        "title": widget.title,
        "widget_type": widget.widget_type,
        "config": widget.config,
        "position": widget.position,
    }


@router.post("/{dashboard_id}/widgets/from-ai")
def save_ai_widget(
    dashboard_id: str,
    payload: SaveAIWidgetRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> dict:
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
    return {
        "id": widget.id,
        "title": widget.title,
        "widget_type": widget.widget_type,
        "position": widget.position,
    }

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
