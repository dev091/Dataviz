from fastapi.testclient import TestClient


def test_admin_subscription_read_and_update(client: TestClient):
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "billing@dataviz.com",
            "full_name": "Billing Owner",
            "password": "Password123!",
            "organization_name": "Billing Org",
            "workspace_name": "Billing Workspace",
        },
    )
    assert signup.status_code == 200, signup.text
    payload = signup.json()

    headers = {
        "Authorization": f"Bearer {payload['access_token']}",
        "X-Workspace-Id": payload["workspaces"][0]["workspace_id"],
    }

    current = client.get("/api/v1/admin/subscription", headers=headers)
    assert current.status_code == 200, current.text
    current_payload = current.json()
    assert current_payload["plan_tier"] == "starter"
    assert current_payload["subscription_status"] == "trial"
    assert current_payload["billing_email"] == "billing@dataviz.com"

    updated = client.put(
        "/api/v1/admin/subscription",
        headers=headers,
        json={
            "plan_tier": "growth",
            "subscription_status": "active",
            "billing_email": "finance@dataviz.com",
            "seat_limit": 25,
        },
    )
    assert updated.status_code == 200, updated.text
    updated_payload = updated.json()
    assert updated_payload["plan_tier"] == "growth"
    assert updated_payload["subscription_status"] == "active"
    assert updated_payload["billing_email"] == "finance@dataviz.com"
    assert updated_payload["seat_limit"] == 25

    audit = client.get("/api/v1/admin/audit-logs", headers=headers)
    assert audit.status_code == 200, audit.text
    assert any(entry["action"] == "organization.subscription.update" for entry in audit.json())
