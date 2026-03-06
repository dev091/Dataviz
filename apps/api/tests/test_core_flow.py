from pathlib import Path

from fastapi.testclient import TestClient


def test_core_flow_signup_connect_sync_semantic_nl(client: TestClient, tmp_path: Path):
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "qa@dataviz.com",
            "full_name": "QA User",
            "password": "Password123!",
            "organization_name": "QA Org",
            "workspace_name": "QA Workspace",
        },
    )
    assert signup.status_code == 200, signup.text
    auth = signup.json()

    token = auth["access_token"]
    workspace_id = auth["workspaces"][0]["workspace_id"]

    csv = tmp_path / "revenue.csv"
    csv.write_text(
        "date,region,revenue,cost\n"
        "2025-01-01,North,100,60\n"
        "2025-02-01,North,120,70\n"
        "2025-03-01,South,140,80\n",
        encoding="utf-8",
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-Id": workspace_id,
    }

    create_connection = client.post(
        "/api/v1/connections",
        headers=headers,
        json={
            "name": "CSV Revenue",
            "connector_type": "csv",
            "config": {"file_path": str(csv)},
        },
    )
    assert create_connection.status_code == 200, create_connection.text
    connection_id = create_connection.json()["id"]

    discover = client.post(f"/api/v1/connections/{connection_id}/discover", headers=headers)
    assert discover.status_code == 200, discover.text

    sync = client.post(f"/api/v1/connections/{connection_id}/sync", headers=headers)
    assert sync.status_code == 200, sync.text
    assert sync.json()["status"] == "success"

    datasets = client.get("/api/v1/semantic/datasets", headers=headers)
    assert datasets.status_code == 200, datasets.text
    dataset_id = datasets.json()[0]["id"]

    create_model = client.post(
        "/api/v1/semantic/models",
        headers=headers,
        json={
            "name": "Revenue Model",
            "model_key": "revenue_model",
            "description": "",
            "base_dataset_id": dataset_id,
            "joins": [],
            "metrics": [
                {
                    "name": "revenue",
                    "label": "Revenue",
                    "formula": "SUM(revenue)",
                    "aggregation": "sum",
                    "visibility": "public",
                }
            ],
            "dimensions": [
                {
                    "name": "region",
                    "label": "Region",
                    "field_ref": "region",
                    "data_type": "string",
                    "visibility": "public",
                }
            ],
            "calculated_fields": [],
        },
    )
    assert create_model.status_code == 200, create_model.text
    semantic_model_id = create_model.json()["id"]

    nl = client.post(
        "/api/v1/nl/query",
        headers=headers,
        json={
            "semantic_model_id": semantic_model_id,
            "question": "show revenue by region",
        },
    )
    assert nl.status_code == 200, nl.text
    payload = nl.json()
    assert payload["rows"]
    assert payload["summary"]
    assert payload["agent_trace"]
    assert len(payload["agent_trace"]) >= 3

    dashboards = client.post(
        "/api/v1/dashboards",
        headers=headers,
        json={"name": "QA Dashboard", "description": "", "layout": {}},
    )
    assert dashboards.status_code == 200, dashboards.text
    dashboard_id = dashboards.json()["id"]

    add_widget = client.post(
        f"/api/v1/dashboards/{dashboard_id}/widgets/from-ai",
        headers=headers,
        json={
            "ai_query_session_id": payload["ai_query_session_id"],
            "title": "QA Insight",
            "position": {"x": 0, "y": 0, "w": 6, "h": 4},
        },
    )
    assert add_widget.status_code == 200, add_widget.text

    audit = client.get("/api/v1/admin/audit-logs", headers=headers)
    assert audit.status_code == 200, audit.text
    assert len(audit.json()) > 0
