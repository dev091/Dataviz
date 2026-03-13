from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.core.bootstrap import bootstrap_package_paths
from app.core.deps import get_db, get_workspace_id, require_role
from app.models.entities import AIQuerySession, AlertRule, AuditLog, Dashboard, DashboardWidget, Dataset, ReportSchedule, SemanticMetric, SemanticModel, User
from app.schemas.migration import (
    ImportedWorkbookBundle,
    MigrationAnalysisRequest,
    MigrationAnalysisResponse,
    MigrationBootstrapRequest,
    MigrationBootstrapResponse,
    MigrationCertificationReviewRequest,
    MigrationCertificationReviewResponse,
    MigrationPromoteKpisRequest,
    MigrationPromoteKpisResponse,
)
from app.schemas.onboarding import (
    LaunchPackPlaybookResponse,
    LaunchPackProvisionRequest,
    LaunchPackProvisionResponse,
    LaunchPackTemplateResponse,
)
from app.schemas.semantic import SemanticModelResponse
from app.services.audit import write_audit_log
from app.services.launch_packs import get_launch_pack, list_launch_packs, provision_launch_pack
from app.services.migration_assistant import analyze_migration_bundle, bootstrap_migration_pack
from app.services.semantic import create_semantic_model, semantic_detail_payload, semantic_trust_panel, validate_semantic_payload

bootstrap_package_paths()
from executive.certification import build_migration_certification_review  # noqa: E402
from executive.importers import parse_workbook_bundle  # noqa: E402
from executive.onboarding import build_launch_pack_playbook  # noqa: E402
from executive.promotion import prepare_metric_promotions  # noqa: E402


router = APIRouter()


def _get_workspace_semantic_model(db: Session, workspace_id: str, semantic_model_id: str) -> SemanticModel:
    semantic_model = db.scalar(
        select(SemanticModel).where(SemanticModel.id == semantic_model_id, SemanticModel.workspace_id == workspace_id)
    )
    if not semantic_model:
        raise HTTPException(status_code=404, detail="Semantic model not found")
    return semantic_model


def _semantic_model_response(model: SemanticModel) -> SemanticModelResponse:
    return SemanticModelResponse(
        id=model.id,
        workspace_id=model.workspace_id,
        name=model.name,
        model_key=model.model_key,
        version=model.version,
        is_active=model.is_active,
        base_dataset_id=model.base_dataset_id,
        description=model.description,
        created_at=model.created_at,
    )


@router.get("/launch-packs", response_model=list[LaunchPackTemplateResponse])
def get_launch_packs(
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
) -> list[LaunchPackTemplateResponse]:
    _ = workspace_id
    _ = current_user
    return [LaunchPackTemplateResponse(**pack) for pack in list_launch_packs()]


@router.get("/launch-packs/{template_id}/playbook", response_model=LaunchPackPlaybookResponse)
def get_launch_pack_playbook_route(
    template_id: str,
    semantic_model_id: str,
    dashboard_id: str | None = None,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> LaunchPackPlaybookResponse:
    _ = current_user
    pack = get_launch_pack(template_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Launch pack not found")

    semantic_model = _get_workspace_semantic_model(db, workspace_id, semantic_model_id)
    trust_panel = semantic_trust_panel(db, semantic_model)

    dashboard_present = False
    widget_count = 0
    schedule_count = 0
    enabled_schedule_count = 0
    report_pack_runs = 0
    delivery_events = 0

    if dashboard_id:
        dashboard = db.scalar(select(Dashboard).where(Dashboard.id == dashboard_id, Dashboard.workspace_id == workspace_id))
        if not dashboard:
            raise HTTPException(status_code=404, detail="Dashboard not found")
        dashboard_present = True
        widget_count = db.scalar(select(func.count(DashboardWidget.id)).where(DashboardWidget.dashboard_id == dashboard.id)) or 0
        schedule_count = (
            db.scalar(
                select(func.count(ReportSchedule.id)).where(
                    ReportSchedule.workspace_id == workspace_id,
                    ReportSchedule.dashboard_id == dashboard.id,
                )
            )
            or 0
        )
        enabled_schedule_count = (
            db.scalar(
                select(func.count(ReportSchedule.id)).where(
                    ReportSchedule.workspace_id == workspace_id,
                    ReportSchedule.dashboard_id == dashboard.id,
                    ReportSchedule.enabled.is_(True),
                )
            )
            or 0
        )
        report_pack_runs = (
            db.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.workspace_id == workspace_id,
                    AuditLog.entity_id == dashboard.id,
                    AuditLog.action.in_([
                        "launch_pack.provision",
                        "migration_assistant.bootstrap",
                        "dashboard.report_pack.generate",
                    ]),
                )
            )
            or 0
        )
        delivery_events = (
            db.scalar(
                select(func.count(AuditLog.id))
                .join(ReportSchedule, ReportSchedule.id == AuditLog.entity_id)
                .where(
                    AuditLog.workspace_id == workspace_id,
                    AuditLog.action == "report_schedule.delivered",
                    ReportSchedule.dashboard_id == dashboard.id,
                )
            )
            or 0
        )

    focus_metric_ids = {
        metric.id
        for metric in db.scalars(select(SemanticMetric).where(SemanticMetric.semantic_model_id == semantic_model.id)).all()
        if any(hint in metric.name.lower() or hint in metric.label.lower() for hint in pack["focus_metrics"])
    }
    focus_alert_count = 0
    if focus_metric_ids:
        focus_alert_count = (
            db.scalar(
                select(func.count(AlertRule.id)).where(
                    AlertRule.workspace_id == workspace_id,
                    AlertRule.semantic_model_id == semantic_model.id,
                    AlertRule.metric_id.in_(focus_metric_ids),
                    AlertRule.enabled.is_(True),
                )
            )
            or 0
        )

    nl_query_count = (
        db.scalar(
            select(func.count(AIQuerySession.id)).where(
                AIQuerySession.workspace_id == workspace_id,
                AIQuerySession.semantic_model_id == semantic_model.id,
            )
        )
        or 0
    )
    onboarding_events = (
        db.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.workspace_id == workspace_id,
                AuditLog.action.in_([
                    "launch_pack.provision",
                    "migration_assistant.bootstrap",
                    "migration_assistant.promote_kpis",
                    "migration_assistant.import_workbook",
                ]),
            )
        )
        or 0
    )

    payload = build_launch_pack_playbook(
        pack=pack,
        trust_panel=trust_panel,
        dashboard_present=dashboard_present,
        widget_count=widget_count,
        schedule_count=schedule_count,
        enabled_schedule_count=enabled_schedule_count,
        focus_alert_count=focus_alert_count,
        report_pack_runs=report_pack_runs,
        delivery_events=delivery_events,
        nl_query_count=nl_query_count,
        onboarding_events=onboarding_events,
    )
    return LaunchPackPlaybookResponse(
        semantic_model_id=semantic_model.id,
        dashboard_id=dashboard_id,
        **payload,
    )


@router.post("/launch-packs/provision", response_model=LaunchPackProvisionResponse)
def create_launch_pack(
    payload: LaunchPackProvisionRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> LaunchPackProvisionResponse:
    pack = get_launch_pack(payload.template_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Launch pack not found")

    semantic_model = _get_workspace_semantic_model(db, workspace_id, payload.semantic_model_id)

    result = provision_launch_pack(
        db,
        workspace_id=workspace_id,
        semantic_model=semantic_model,
        pack=pack,
        created_by=current_user.id,
        email_to=payload.email_to,
        create_schedule=payload.create_schedule,
    )

    dashboard = result["dashboard"]
    schedule = result["report_schedule"]

    write_audit_log(
        db,
        action="launch_pack.provision",
        entity_type="dashboard",
        entity_id=dashboard.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={
            "template_id": payload.template_id,
            "semantic_model_id": payload.semantic_model_id,
            "widgets_added": result["widgets_added"],
            "schedule_created": bool(schedule),
            "report_type": pack["report_type"],
        },
    )

    if schedule is not None:
        write_audit_log(
            db,
            action="report_schedule.create",
            entity_type="report_schedule",
            entity_id=schedule.id,
            user=current_user,
            organization_id=None,
            workspace_id=workspace_id,
            metadata={"dashboard_id": dashboard.id, "schedule_type": schedule.schedule_type},
        )

    db.commit()
    return LaunchPackProvisionResponse(
        template_id=result["template_id"],
        dashboard_id=dashboard.id,
        dashboard_name=dashboard.name,
        widgets_added=result["widgets_added"],
        notes=result["notes"],
        report_schedule_id=schedule.id if schedule else None,
        report_schedule_name=schedule.name if schedule else None,
        report_pack=result["report_pack"],
        suggested_alerts=result["suggested_alerts"],
        generated_at=result["generated_at"],
    )


@router.post("/migration-assistant/import-workbook", response_model=ImportedWorkbookBundle)
async def import_migration_workbook(
    file: UploadFile = File(...),
    source_tool: str | None = Query(default=None),
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> ImportedWorkbookBundle:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded workbook is missing a filename")

    try:
        content = await file.read()
        parsed = parse_workbook_bundle(file.filename, content, source_tool)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    write_audit_log(
        db,
        action="migration_assistant.import_workbook",
        entity_type="workspace",
        entity_id=workspace_id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={
            "source_tool": parsed["source_tool"],
            "workbook_name": parsed["workbook_name"],
            "dashboard_count": len(parsed["dashboard_names"]),
            "report_count": len(parsed["report_names"]),
            "kpi_count": len(parsed["kpi_names"]),
            "dimension_count": len(parsed["dimension_names"]),
        },
    )
    db.commit()
    return ImportedWorkbookBundle(**parsed)


@router.post("/migration-assistant/analyze", response_model=MigrationAnalysisResponse)
def analyze_migration(
    payload: MigrationAnalysisRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Viewer")),
    db: Session = Depends(get_db),
) -> MigrationAnalysisResponse:
    semantic_model = _get_workspace_semantic_model(db, workspace_id, payload.semantic_model_id)
    result = analyze_migration_bundle(
        db,
        semantic_model=semantic_model,
        source_tool=payload.source_tool,
        dashboard_names=payload.dashboard_names,
        report_names=payload.report_names,
        kpi_names=payload.kpi_names,
        dimension_names=payload.dimension_names,
        benchmark_rows=[row.model_dump() for row in payload.benchmark_rows],
        notes=payload.notes,
    )

    write_audit_log(
        db,
        action="migration_assistant.analyze",
        entity_type="semantic_model",
        entity_id=semantic_model.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={
            "source_tool": payload.source_tool,
            "recommended_launch_pack_id": result["recommended_launch_pack_id"],
            "coverage": result["coverage"],
            "benchmark_rows": len(payload.benchmark_rows),
            "trust_summary": result["automated_trust_comparison"]["summary"],
        },
    )
    db.commit()
    return MigrationAnalysisResponse(**result)


@router.post("/migration-assistant/bootstrap", response_model=MigrationBootstrapResponse)
def bootstrap_migration(
    payload: MigrationBootstrapRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> MigrationBootstrapResponse:
    semantic_model = _get_workspace_semantic_model(db, workspace_id, payload.semantic_model_id)
    result = bootstrap_migration_pack(
        db,
        workspace_id=workspace_id,
        semantic_model=semantic_model,
        source_tool=payload.source_tool,
        dashboard_names=payload.dashboard_names,
        report_names=payload.report_names,
        kpi_names=payload.kpi_names,
        dimension_names=payload.dimension_names,
        benchmark_rows=[row.model_dump() for row in payload.benchmark_rows],
        notes=payload.notes,
        created_by=current_user.id,
        email_to=payload.email_to,
        create_schedule=payload.create_schedule,
        dashboard_name_override=payload.dashboard_name_override,
    )

    dashboard = result["provisioned"]["dashboard"]
    schedule = result["provisioned"]["report_schedule"]

    write_audit_log(
        db,
        action="migration_assistant.bootstrap",
        entity_type="dashboard",
        entity_id=dashboard.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={
            "source_tool": payload.source_tool,
            "semantic_model_id": semantic_model.id,
            "recommended_launch_pack_id": result["analysis"]["recommended_launch_pack_id"],
            "coverage": result["analysis"]["coverage"],
            "schedule_created": bool(schedule),
            "benchmark_rows": len(payload.benchmark_rows),
            "trust_summary": result["analysis"]["automated_trust_comparison"]["summary"],
        },
    )

    if schedule is not None:
        write_audit_log(
            db,
            action="report_schedule.create",
            entity_type="report_schedule",
            entity_id=schedule.id,
            user=current_user,
            organization_id=None,
            workspace_id=workspace_id,
            metadata={"dashboard_id": dashboard.id, "schedule_type": schedule.schedule_type},
        )

    db.commit()
    provisioned = result["provisioned"]
    launch_pack_response = LaunchPackProvisionResponse(
        template_id=provisioned["template_id"],
        dashboard_id=dashboard.id,
        dashboard_name=dashboard.name,
        widgets_added=provisioned["widgets_added"],
        notes=provisioned["notes"],
        report_schedule_id=schedule.id if schedule else None,
        report_schedule_name=schedule.name if schedule else None,
        report_pack=provisioned["report_pack"],
        suggested_alerts=provisioned["suggested_alerts"],
        generated_at=provisioned["generated_at"],
    )
    return MigrationBootstrapResponse(
        analysis=MigrationAnalysisResponse(**result["analysis"]),
        provisioned_pack=launch_pack_response,
    )


@router.post("/migration-assistant/review-kpis", response_model=MigrationCertificationReviewResponse)
def review_migration_kpis(
    payload: MigrationCertificationReviewRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> MigrationCertificationReviewResponse:
    semantic_model = _get_workspace_semantic_model(db, workspace_id, payload.semantic_model_id)
    imported_kpis = [item.model_dump() for item in payload.imported_kpis]
    selected_source_names = payload.selected_source_names or [item["source_name"] for item in imported_kpis]

    analysis = analyze_migration_bundle(
        db,
        semantic_model=semantic_model,
        source_tool=payload.source_tool,
        dashboard_names=[],
        report_names=[],
        kpi_names=selected_source_names,
        dimension_names=[],
        benchmark_rows=[row.model_dump() for row in payload.benchmark_rows],
        notes=payload.notes,
    )
    review = build_migration_certification_review(
        semantic_model_id=semantic_model.id,
        source_tool=payload.source_tool,
        selected_source_names=selected_source_names,
        imported_kpis=imported_kpis,
        kpi_matches=analysis["kpi_matches"],
        automated_trust_comparison=analysis["automated_trust_comparison"],
        requested_owner_name=payload.owner_name,
        requested_certification_status=payload.certification_status,
        notes=payload.notes,
    )

    write_audit_log(
        db,
        action="migration_assistant.review_kpis",
        entity_type="semantic_model",
        entity_id=semantic_model.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={
            "source_tool": payload.source_tool,
            "selected_source_names": selected_source_names,
            "summary": review["summary"],
        },
    )
    db.commit()
    return MigrationCertificationReviewResponse(**review)

@router.post("/migration-assistant/promote-kpis", response_model=MigrationPromoteKpisResponse)
def promote_migration_kpis(
    payload: MigrationPromoteKpisRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Analyst")),
    db: Session = Depends(get_db),
) -> MigrationPromoteKpisResponse:
    semantic_model = _get_workspace_semantic_model(db, workspace_id, payload.semantic_model_id)
    imported_kpis = [item.model_dump() for item in payload.imported_kpis]
    selected_source_names = payload.selected_source_names or [item["source_name"] for item in imported_kpis]

    analysis = analyze_migration_bundle(
        db,
        semantic_model=semantic_model,
        source_tool=payload.source_tool,
        dashboard_names=[],
        report_names=[],
        kpi_names=[item["source_name"] for item in imported_kpis],
        dimension_names=[],
        benchmark_rows=[],
        notes=payload.notes,
    )

    current_detail = semantic_detail_payload(db, semantic_model)
    next_metrics, results = prepare_metric_promotions(
        semantic_detail=current_detail,
        selected_source_names=selected_source_names,
        imported_kpis=imported_kpis,
        kpi_matches=analysis["kpi_matches"],
        owner_name=payload.owner_name,
        certification_status=payload.certification_status,
        source_tool=payload.source_tool,
        review_items=[item.model_dump() for item in payload.review_items],
    )

    promoted_count = sum(1 for item in results if item["status"] not in {"skipped", "blocked_by_review"})
    if promoted_count == 0:
        raise HTTPException(status_code=400, detail="No promotable KPIs were found in the imported workbook bundle")

    errors = validate_semantic_payload(
        base_dataset=db.get(Dataset, semantic_model.base_dataset_id),
        joins=current_detail["joins"],
        metrics=next_metrics,
        dimensions=current_detail["dimensions"],
        calculated_fields=current_detail["calculated_fields"],
    )
    if errors:
        raise HTTPException(status_code=400, detail=errors)

    active_versions = db.scalars(
        select(SemanticModel).where(
            SemanticModel.workspace_id == workspace_id,
            SemanticModel.model_key == semantic_model.model_key,
            SemanticModel.is_active.is_(True),
        )
    ).all()
    for row in active_versions:
        row.is_active = False
        db.add(row)

    next_model = create_semantic_model(
        db,
        workspace_id=workspace_id,
        created_by=current_user.id,
        name=semantic_model.name,
        model_key=semantic_model.model_key,
        description=semantic_model.description,
        base_dataset_id=semantic_model.base_dataset_id,
        joins=current_detail["joins"],
        metrics=next_metrics,
        dimensions=current_detail["dimensions"],
        calculated_fields=current_detail["calculated_fields"],
        governance=current_detail["governance"],
    )

    write_audit_log(
        db,
        action="migration_assistant.promote_kpis",
        entity_type="semantic_model",
        entity_id=next_model.id,
        user=current_user,
        organization_id=None,
        workspace_id=workspace_id,
        metadata={
            "source_tool": payload.source_tool,
            "promoted_count": promoted_count,
            "selected_source_names": selected_source_names,
            "results": results,
            "review_items": [item.model_dump() for item in payload.review_items],
        },
    )
    db.commit()

    return MigrationPromoteKpisResponse(
        semantic_model=_semantic_model_response(next_model),
        promoted_count=promoted_count,
        results=results,
    )











