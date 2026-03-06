from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_workspace_id, require_role
from app.models.entities import Organization, User, Workspace
from app.services.audit import write_audit_log
from app.services.billing import (
    BillingProviderError,
    billing_snapshot,
    default_checkout_cancel_url,
    default_checkout_success_url,
    default_portal_return_url,
    get_billing_provider,
    process_stripe_webhook,
)


router = APIRouter()


class CheckoutSessionRequest(BaseModel):
    plan_tier: str = Field(pattern="^(starter|growth|enterprise)$")
    success_url: str | None = Field(default=None, min_length=8, max_length=1024)
    cancel_url: str | None = Field(default=None, min_length=8, max_length=1024)


class PortalSessionRequest(BaseModel):
    return_url: str | None = Field(default=None, min_length=8, max_length=1024)


def _workspace(db: Session, workspace_id: str) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


def _organization_for_workspace(db: Session, workspace_id: str) -> tuple[Workspace, Organization]:
    workspace = _workspace(db, workspace_id)
    organization = db.get(Organization, workspace.organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return workspace, organization


@router.post("/checkout-session")
def create_checkout_session(
    payload: CheckoutSessionRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Owner")),
    db: Session = Depends(get_db),
) -> dict:
    workspace, organization = _organization_for_workspace(db, workspace_id)

    try:
        provider = get_billing_provider()
        session = provider.create_checkout_session(
            organization,
            plan_tier=payload.plan_tier,
            success_url=payload.success_url or default_checkout_success_url(),
            cancel_url=payload.cancel_url or default_checkout_cancel_url(),
        )
    except BillingProviderError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    write_audit_log(
        db,
        action="billing.checkout_session.created",
        entity_type="organization",
        entity_id=organization.id,
        user=current_user,
        organization_id=organization.id,
        workspace_id=workspace.id,
        metadata={
            "provider": session.provider,
            "plan_tier": payload.plan_tier,
            "session_id": session.session_id,
            "billing_customer_id": organization.billing_customer_id,
        },
    )
    db.commit()
    return {
        **session.as_dict(),
        "organization": billing_snapshot(organization),
    }


@router.post("/portal-session")
def create_portal_session(
    payload: PortalSessionRequest,
    workspace_id: str = Depends(get_workspace_id),
    current_user: User = Depends(require_role("Owner")),
    db: Session = Depends(get_db),
) -> dict:
    workspace, organization = _organization_for_workspace(db, workspace_id)

    try:
        provider = get_billing_provider()
        session = provider.create_portal_session(
            organization,
            return_url=payload.return_url or default_portal_return_url(),
        )
    except BillingProviderError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    write_audit_log(
        db,
        action="billing.portal_session.created",
        entity_type="organization",
        entity_id=organization.id,
        user=current_user,
        organization_id=organization.id,
        workspace_id=workspace.id,
        metadata={
            "provider": session.provider,
            "session_id": session.session_id,
            "billing_customer_id": organization.billing_customer_id,
        },
    )
    db.commit()
    return {
        **session.as_dict(),
        "organization": billing_snapshot(organization),
    }


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    payload = await request.body()
    signature_header = request.headers.get("Stripe-Signature", "")

    try:
        result = process_stripe_webhook(db, payload=payload, signature_header=signature_header)
    except BillingProviderError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    return result
