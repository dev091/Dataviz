import hashlib
import hmac
import json

from fastapi.testclient import TestClient


class StubSession:
    def __init__(self, provider: str, session_id: str, url: str, plan_tier: str) -> None:
        self.provider = provider
        self.session_id = session_id
        self.url = url
        self.plan_tier = plan_tier

    def as_dict(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "session_id": self.session_id,
            "url": self.url,
            "plan_tier": self.plan_tier,
        }


class StubBillingProvider:
    name = "stripe"

    def create_checkout_session(self, organization, *, plan_tier: str, success_url: str, cancel_url: str) -> StubSession:
        organization.billing_provider = "stripe"
        organization.billing_customer_id = organization.billing_customer_id or "cus_test_123"
        organization.billing_price_id = "price_growth"
        return StubSession(
            provider="stripe",
            session_id="cs_test_123",
            url=f"{success_url}&session=cs_test_123",
            plan_tier=plan_tier,
        )

    def create_portal_session(self, organization, *, return_url: str) -> StubSession:
        organization.billing_provider = "stripe"
        organization.billing_customer_id = organization.billing_customer_id or "cus_test_123"
        return StubSession(
            provider="stripe",
            session_id="bps_test_123",
            url=f"{return_url}&portal_session=bps_test_123",
            plan_tier=organization.plan_tier,
        )


def _signup(client: TestClient, email: str) -> tuple[dict[str, str], str]:
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "full_name": "Billing Flow",
            "password": "Password123!",
            "organization_name": "Billing Flow Org",
            "workspace_name": "Billing Workspace",
        },
    )
    assert signup.status_code == 200, signup.text
    auth = signup.json()
    headers = {
        "Authorization": f"Bearer {auth['access_token']}",
        "X-Workspace-Id": auth["workspaces"][0]["workspace_id"],
    }
    return headers, auth["workspaces"][0]["workspace_id"]


def _stripe_signature(secret: str, payload: str) -> str:
    timestamp = "1700000000"
    signed_payload = f"{timestamp}.{payload}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def test_billing_checkout_portal_and_webhook_flow(client: TestClient, monkeypatch):
    from app.api.routes import billing as billing_route
    from app.core.config import settings

    headers, _workspace_id = _signup(client, "billing-flow@dataviz.com")

    monkeypatch.setattr(billing_route, "get_billing_provider", lambda: StubBillingProvider())
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    monkeypatch.setattr(settings, "stripe_price_growth", "price_growth")

    checkout = client.post(
        "/api/v1/billing/checkout-session",
        headers=headers,
        json={"plan_tier": "growth"},
    )
    assert checkout.status_code == 200, checkout.text
    checkout_payload = checkout.json()
    assert checkout_payload["provider"] == "stripe"
    assert checkout_payload["session_id"] == "cs_test_123"
    assert checkout_payload["organization"]["billing_customer_id"] == "cus_test_123"

    webhook_payload = json.dumps(
        {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "object": "subscription",
                    "id": "sub_test_123",
                    "customer": "cus_test_123",
                    "status": "active",
                    "items": {"data": [{"price": {"id": "price_growth"}}]},
                }
            },
        }
    )
    webhook = client.post(
        "/api/v1/billing/webhooks/stripe",
        content=webhook_payload,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": _stripe_signature(settings.stripe_webhook_secret, webhook_payload),
        },
    )
    assert webhook.status_code == 200, webhook.text
    assert webhook.json()["subscription_status"] == "active"

    portal = client.post(
        "/api/v1/billing/portal-session",
        headers=headers,
        json={},
    )
    assert portal.status_code == 200, portal.text
    assert portal.json()["session_id"] == "bps_test_123"

    subscription = client.get("/api/v1/admin/subscription", headers=headers)
    assert subscription.status_code == 200, subscription.text
    subscription_payload = subscription.json()
    assert subscription_payload["plan_tier"] == "growth"
    assert subscription_payload["subscription_status"] == "active"
    assert subscription_payload["billing_provider"] == "stripe"
    assert subscription_payload["billing_customer_id"] == "cus_test_123"
    assert subscription_payload["billing_subscription_id"] == "sub_test_123"
    assert subscription_payload["billing_price_id"] == "price_growth"

    audit = client.get("/api/v1/admin/audit-logs", headers=headers)
    assert audit.status_code == 200, audit.text
    actions = [entry["action"] for entry in audit.json()]
    assert "billing.checkout_session.created" in actions
    assert "billing.portal_session.created" in actions
    assert "billing.webhook.processed" in actions


def test_stripe_webhook_rejects_invalid_signature(client: TestClient, monkeypatch):
    from app.api.routes import billing as billing_route
    from app.core.config import settings

    headers, _workspace_id = _signup(client, "billing-security@dataviz.com")

    monkeypatch.setattr(billing_route, "get_billing_provider", lambda: StubBillingProvider())
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")

    checkout = client.post(
        "/api/v1/billing/checkout-session",
        headers=headers,
        json={"plan_tier": "growth"},
    )
    assert checkout.status_code == 200, checkout.text

    webhook = client.post(
        "/api/v1/billing/webhooks/stripe",
        content=json.dumps(
            {
                "type": "customer.subscription.updated",
                "data": {"object": {"object": "subscription", "customer": "cus_test_123", "id": "sub_bad"}},
            }
        ),
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": "t=1700000000,v1=bad",
        },
    )
    assert webhook.status_code == 400, webhook.text
    assert "verification failed" in webhook.text.lower()
