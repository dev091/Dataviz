from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import Organization
from app.services.audit import write_audit_log


class BillingProviderError(RuntimeError):
    pass


class StripeWebhookSignatureError(BillingProviderError):
    pass


@dataclass(slots=True)
class BillingSession:
    provider: str
    session_id: str
    url: str
    plan_tier: str

    def as_dict(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "session_id": self.session_id,
            "url": self.url,
            "plan_tier": self.plan_tier,
        }


class BillingProvider:
    name = "manual"

    def create_checkout_session(
        self,
        organization: Organization,
        *,
        plan_tier: str,
        success_url: str,
        cancel_url: str,
    ) -> BillingSession:
        raise NotImplementedError

    def create_portal_session(self, organization: Organization, *, return_url: str) -> BillingSession:
        raise NotImplementedError


class LogBillingProvider(BillingProvider):
    name = "log"

    def create_checkout_session(
        self,
        organization: Organization,
        *,
        plan_tier: str,
        success_url: str,
        cancel_url: str,
    ) -> BillingSession:
        organization.billing_provider = self.name
        organization.billing_customer_id = organization.billing_customer_id or f"local_cus_{organization.id}"
        organization.billing_price_id = price_id_for_plan(plan_tier)
        url = f"{success_url}?{urlencode({'checkout': 'simulated', 'org': organization.id, 'plan': plan_tier})}"
        return BillingSession(provider=self.name, session_id=f"local_checkout_{organization.id}", url=url, plan_tier=plan_tier)

    def create_portal_session(self, organization: Organization, *, return_url: str) -> BillingSession:
        organization.billing_provider = self.name
        url = f"{return_url}?{urlencode({'portal': 'simulated', 'org': organization.id})}"
        return BillingSession(provider=self.name, session_id=f"local_portal_{organization.id}", url=url, plan_tier=organization.plan_tier)


class StripeBillingProvider(BillingProvider):
    name = "stripe"

    def __init__(self) -> None:
        if not settings.stripe_secret_key.strip():
            raise BillingProviderError("Stripe billing is enabled but STRIPE_SECRET_KEY is missing")

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(
                f"{settings.stripe_api_base_url.rstrip('/')}/{path.lstrip('/')}",
                data=payload,
                headers={"Authorization": f"Bearer {settings.stripe_secret_key}"},
                timeout=20.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            detail = exc.response.text if getattr(exc, "response", None) is not None else str(exc)
            raise BillingProviderError(f"Stripe API request failed: {detail}") from exc

    def _ensure_customer(self, organization: Organization) -> str:
        if organization.billing_customer_id:
            return organization.billing_customer_id

        customer = self._post(
            "/customers",
            {
                "email": organization.billing_email or "",
                "name": organization.name,
                "metadata[organization_id]": organization.id,
                "metadata[organization_slug]": organization.slug,
            },
        )
        customer_id = customer.get("id")
        if not customer_id:
            raise BillingProviderError("Stripe customer creation returned no id")

        organization.billing_provider = self.name
        organization.billing_customer_id = str(customer_id)
        return str(customer_id)

    def create_checkout_session(
        self,
        organization: Organization,
        *,
        plan_tier: str,
        success_url: str,
        cancel_url: str,
    ) -> BillingSession:
        customer_id = self._ensure_customer(organization)
        price_id = price_id_for_plan(plan_tier)
        payload = self._post(
            "/checkout/sessions",
            {
                "mode": "subscription",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "customer": customer_id,
                "client_reference_id": organization.id,
                "allow_promotion_codes": "true",
                "metadata[organization_id]": organization.id,
                "metadata[plan_tier]": plan_tier,
                "line_items[0][price]": price_id,
                "line_items[0][quantity]": "1",
            },
        )
        session_id = payload.get("id")
        url = payload.get("url")
        if not session_id or not url:
            raise BillingProviderError("Stripe checkout session returned incomplete payload")

        organization.billing_provider = self.name
        organization.billing_price_id = price_id
        return BillingSession(provider=self.name, session_id=str(session_id), url=str(url), plan_tier=plan_tier)

    def create_portal_session(self, organization: Organization, *, return_url: str) -> BillingSession:
        customer_id = organization.billing_customer_id or self._ensure_customer(organization)
        payload = self._post(
            "/billing_portal/sessions",
            {
                "customer": customer_id,
                "return_url": return_url,
            },
        )
        session_id = payload.get("id")
        url = payload.get("url")
        if not session_id or not url:
            raise BillingProviderError("Stripe billing portal session returned incomplete payload")

        organization.billing_provider = self.name
        return BillingSession(provider=self.name, session_id=str(session_id), url=str(url), plan_tier=organization.plan_tier)


def get_billing_provider() -> BillingProvider:
    provider = settings.billing_provider.strip().lower()
    if provider == "stripe":
        return StripeBillingProvider()
    if provider == "log":
        return LogBillingProvider()
    raise BillingProviderError(f"Unsupported billing provider: {settings.billing_provider}")


def default_checkout_success_url() -> str:
    return f"{settings.app_public_url.rstrip('/')}/admin?billing=success"


def default_checkout_cancel_url() -> str:
    return f"{settings.app_public_url.rstrip('/')}/admin?billing=cancel"


def default_portal_return_url() -> str:
    return f"{settings.app_public_url.rstrip('/')}/admin?billing=portal"


def price_id_for_plan(plan_tier: str) -> str:
    mapping = {
        "starter": settings.stripe_price_starter,
        "growth": settings.stripe_price_growth,
        "enterprise": settings.stripe_price_enterprise,
    }
    price_id = mapping.get(plan_tier)
    if not price_id:
        raise BillingProviderError(f"Unsupported plan tier: {plan_tier}")
    return price_id


def plan_for_price_id(price_id: str | None) -> str | None:
    if not price_id:
        return None
    reverse = {
        settings.stripe_price_starter: "starter",
        settings.stripe_price_growth: "growth",
        settings.stripe_price_enterprise: "enterprise",
    }
    return reverse.get(price_id)


def normalize_subscription_status(raw_status: str | None) -> str:
    mapping = {
        "trialing": "trial",
        "active": "active",
        "past_due": "past_due",
        "unpaid": "past_due",
        "incomplete": "past_due",
        "canceled": "canceled",
        "cancelled": "canceled",
        "incomplete_expired": "canceled",
        "paused": "canceled",
    }
    if not raw_status:
        return "active"
    return mapping.get(raw_status, raw_status)


def verify_stripe_signature(payload: bytes, signature_header: str) -> None:
    if not settings.stripe_webhook_secret.strip():
        raise BillingProviderError("STRIPE_WEBHOOK_SECRET is required to validate Stripe webhooks")

    parts = {}
    for item in signature_header.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts[key.strip()] = value.strip()

    timestamp = parts.get("t")
    signature = parts.get("v1")
    if not timestamp or not signature:
        raise StripeWebhookSignatureError("Invalid Stripe signature header")

    signed_payload = f"{timestamp}.{payload.decode('utf-8')}".encode("utf-8")
    expected = hmac.new(
        settings.stripe_webhook_secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise StripeWebhookSignatureError("Stripe signature verification failed")


def process_stripe_webhook(db: Session, *, payload: bytes, signature_header: str) -> dict[str, Any]:
    verify_stripe_signature(payload, signature_header)
    event = json.loads(payload.decode("utf-8"))
    event_type = str(event.get("type") or "")
    data = event.get("data", {})
    obj = data.get("object", {})

    organization = _find_organization_for_event(db, obj)
    if organization is None:
        raise BillingProviderError("No organization matched the Stripe event")

    if event_type == "checkout.session.completed":
        _apply_checkout_completed(organization, obj)
    elif event_type in {"customer.subscription.updated", "customer.subscription.created"}:
        _apply_subscription_updated(organization, obj)
    elif event_type == "customer.subscription.deleted":
        _apply_subscription_deleted(organization, obj)
    else:
        return {"received": True, "event_type": event_type, "ignored": True}

    write_audit_log(
        db,
        action="billing.webhook.processed",
        entity_type="organization",
        entity_id=organization.id,
        user=None,
        organization_id=organization.id,
        workspace_id=None,
        metadata={
            "event_type": event_type,
            "billing_provider": organization.billing_provider,
            "subscription_status": organization.subscription_status,
            "plan_tier": organization.plan_tier,
            "billing_customer_id": organization.billing_customer_id,
            "billing_subscription_id": organization.billing_subscription_id,
        },
    )
    db.flush()
    return {
        "received": True,
        "event_type": event_type,
        "organization_id": organization.id,
        "subscription_status": organization.subscription_status,
        "plan_tier": organization.plan_tier,
    }


def _find_organization_for_event(db: Session, obj: dict[str, Any]) -> Organization | None:
    organization_id = obj.get("client_reference_id")
    if organization_id:
        organization = db.get(Organization, str(organization_id))
        if organization:
            return organization

    metadata = obj.get("metadata") or {}
    organization_id = metadata.get("organization_id")
    if organization_id:
        organization = db.get(Organization, str(organization_id))
        if organization:
            return organization

    customer_id = obj.get("customer")
    if customer_id:
        organization = db.scalar(select(Organization).where(Organization.billing_customer_id == str(customer_id)))
        if organization:
            return organization

    subscription_id = obj.get("id") if str(obj.get("object")) == "subscription" else obj.get("subscription")
    if subscription_id:
        organization = db.scalar(
            select(Organization).where(Organization.billing_subscription_id == str(subscription_id))
        )
        if organization:
            return organization

    return None


def _apply_checkout_completed(organization: Organization, obj: dict[str, Any]) -> None:
    metadata = obj.get("metadata") or {}
    organization.billing_provider = "stripe"
    organization.billing_customer_id = str(obj.get("customer") or organization.billing_customer_id or "") or None
    organization.billing_subscription_id = str(obj.get("subscription") or organization.billing_subscription_id or "") or None
    plan_tier = metadata.get("plan_tier")
    if plan_tier:
        organization.plan_tier = str(plan_tier)
        organization.billing_price_id = price_id_for_plan(str(plan_tier))
    organization.subscription_status = normalize_subscription_status(obj.get("status") or "active")
    organization.trial_ends_at = None


def _apply_subscription_updated(organization: Organization, obj: dict[str, Any]) -> None:
    items = ((obj.get("items") or {}).get("data") or [])
    price_id = None
    if items:
        price = items[0].get("price") or {}
        price_id = price.get("id")

    organization.billing_provider = "stripe"
    organization.billing_customer_id = str(obj.get("customer") or organization.billing_customer_id or "") or None
    organization.billing_subscription_id = str(obj.get("id") or organization.billing_subscription_id or "") or None
    organization.billing_price_id = str(price_id or organization.billing_price_id or "") or None
    organization.subscription_status = normalize_subscription_status(obj.get("status"))
    plan_tier = plan_for_price_id(organization.billing_price_id)
    if plan_tier:
        organization.plan_tier = plan_tier
    if organization.subscription_status == "active":
        organization.trial_ends_at = None


def _apply_subscription_deleted(organization: Organization, obj: dict[str, Any]) -> None:
    organization.billing_provider = "stripe"
    organization.billing_customer_id = str(obj.get("customer") or organization.billing_customer_id or "") or None
    organization.billing_subscription_id = str(obj.get("id") or organization.billing_subscription_id or "") or None
    organization.subscription_status = "canceled"


def billing_snapshot(organization: Organization) -> dict[str, Any]:
    return {
        "organization_id": organization.id,
        "organization_name": organization.name,
        "plan_tier": organization.plan_tier,
        "subscription_status": organization.subscription_status,
        "billing_provider": organization.billing_provider,
        "billing_email": organization.billing_email,
        "billing_customer_id": organization.billing_customer_id,
        "billing_subscription_id": organization.billing_subscription_id,
        "billing_price_id": organization.billing_price_id,
        "seat_limit": organization.seat_limit,
        "trial_ends_at": organization.trial_ends_at,
        "commercial_mode": settings.billing_provider,
        "self_serve_checkout_enabled": settings.billing_provider in {"log", "stripe"},
        "billing_portal_enabled": settings.billing_provider == "log" or bool(organization.billing_customer_id),
        "updated_at": organization.updated_at if hasattr(organization, "updated_at") else datetime.now(timezone.utc),
    }
