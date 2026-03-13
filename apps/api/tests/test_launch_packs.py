from pathlib import Path

from fastapi.testclient import TestClient


def test_launch_pack_provisioning_flow(client: TestClient, tmp_path: Path):
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "launch@dataviz.com",
            "full_name": "Launch User",
            "password": "Password123!",
            "organization_name": "Launch Org",
            "workspace_name": "Launch Workspace",
        },
    )
    assert signup.status_code == 200, signup.text
    auth = signup.json()

    headers = {
        "Authorization": f"Bearer {auth['access_token']}",
        "X-Workspace-Id": auth["workspaces"][0]["workspace_id"],
    }

    csv = tmp_path / "finance.csv"
    csv.write_text(
        "month,region,revenue,cost,profit\n"
        "2025-01,North,1000,700,300\n"
        "2025-02,North,1100,720,380\n"
        "2025-03,South,1200,760,440\n",
        encoding="utf-8",
    )

    create_connection = client.post(
        "/api/v1/connections",
        headers=headers,
        json={
            "name": "Finance CSV",
            "connector_type": "csv",
            "config": {"file_path": str(csv)},
        },
    )
    assert create_connection.status_code == 200, create_connection.text
    connection_id = create_connection.json()["id"]

    sync = client.post(f"/api/v1/connections/{connection_id}/sync", headers=headers)
    assert sync.status_code == 200, sync.text

    datasets = client.get("/api/v1/semantic/datasets", headers=headers)
    assert datasets.status_code == 200, datasets.text
    dataset_id = datasets.json()[0]["id"]

    draft = client.post(
        "/api/v1/semantic/models/draft",
        headers=headers,
        json={"dataset_id": dataset_id, "name": "Finance Model", "model_key": "finance_model"},
    )
    assert draft.status_code == 200, draft.text

    create_model = client.post(
        "/api/v1/semantic/models",
        headers=headers,
        json={key: value for key, value in draft.json().items() if key != "inference_notes"},
    )
    assert create_model.status_code == 200, create_model.text
    semantic_model_id = create_model.json()["id"]

    templates = client.get("/api/v1/onboarding/launch-packs", headers=headers)
    assert templates.status_code == 200, templates.text
    finance_template = next(item for item in templates.json() if item["id"] == "finance_exec")
    assert finance_template["operating_views"]
    assert finance_template["exception_report_title"] == "Finance Variance Exceptions"

    provision = client.post(
        "/api/v1/onboarding/launch-packs/provision",
        headers=headers,
        json={
            "template_id": "finance_exec",
            "semantic_model_id": semantic_model_id,
            "email_to": ["finance@example.com", "ceo@example.com"],
            "create_schedule": True,
        },
    )
    assert provision.status_code == 200, provision.text
    payload = provision.json()
    assert payload["dashboard_id"]
    assert payload["widgets_added"] > 0
    assert payload["report_schedule_id"]
    assert payload["report_pack"]["executive_summary"]
    assert payload["report_pack"]["report_type"] == "weekly_business_review"
    assert payload["report_pack"]["operating_views"]
    assert payload["report_pack"]["exception_report"]
    assert payload["suggested_alerts"]

    audit = client.get("/api/v1/admin/audit-logs", headers=headers)
    assert audit.status_code == 200, audit.text
    assert any(entry["action"] == "launch_pack.provision" for entry in audit.json())

