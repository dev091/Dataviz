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
    assert discover.json().get("meta", {}).get("retry", {}).get("operation") == "preview_schema"

    sync = client.post(f"/api/v1/connections/{connection_id}/sync", headers=headers)
    assert sync.status_code == 200, sync.text
    assert sync.json()["status"] == "success"
    assert sync.json()["logs"]["retry"]["operation"] == "sync"

    datasets = client.get("/api/v1/semantic/datasets", headers=headers)
    assert datasets.status_code == 200, datasets.text
    dataset_payload = datasets.json()[0]
    dataset_id = dataset_payload["id"]
    assert dataset_payload["quality_status"] in {"excellent", "good", "warning", "critical"}
    assert dataset_payload["quality_profile"]["overall_score"] >= 0
    assert dataset_payload["quality_profile"]["field_profiles"]

    draft = client.post(
        "/api/v1/semantic/models/draft",
        headers=headers,
        json={"dataset_id": dataset_id},
    )
    assert draft.status_code == 200, draft.text
    draft_payload = draft.json()
    assert draft_payload["metrics"]
    assert any(metric["name"] == "revenue" for metric in draft_payload["metrics"])
    assert any(dimension["name"] == "region" for dimension in draft_payload["dimensions"])
    assert any(field["name"] == "gross_margin" for field in draft_payload["calculated_fields"])

    create_model = client.post(
        "/api/v1/semantic/models",
        headers=headers,
        json={key: value for key, value in draft_payload.items() if key != "inference_notes"},
    )
    assert create_model.status_code == 200, create_model.text
    semantic_model_id = create_model.json()["id"]

    model_detail = client.get(f"/api/v1/semantic/models/{semantic_model_id}", headers=headers)
    assert model_detail.status_code == 200, model_detail.text
    detail_payload = model_detail.json()
    assert any(metric["name"] == "revenue" and metric["value_format"] == "currency" for metric in detail_payload["metrics"])
    assert any(field["name"] == "gross_margin" for field in detail_payload["calculated_fields"])

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
    assert payload["related_queries"] == []

    follow_up = client.post(
        "/api/v1/nl/query",
        headers=headers,
        json={
            "semantic_model_id": semantic_model_id,
            "question": "summarize revenue trend by region",
        },
    )
    assert follow_up.status_code == 200, follow_up.text
    follow_up_payload = follow_up.json()
    assert follow_up_payload["related_queries"]
    assert follow_up_payload["related_queries"][0]["question"] == "show revenue by region"

    dashboards = client.post(
        "/api/v1/dashboards",
        headers=headers,
        json={"name": "QA Dashboard", "description": "", "layout": {}},
    )
    assert dashboards.status_code == 200, dashboards.text
    dashboard_id = dashboards.json()["id"]

    auto_compose = client.post(
        f"/api/v1/dashboards/{dashboard_id}/auto-compose",
        headers=headers,
        json={
            "semantic_model_id": semantic_model_id,
            "goal": "Executive overview",
            "max_widgets": 6,
        },
    )
    assert auto_compose.status_code == 200, auto_compose.text
    assert auto_compose.json()["widgets_added"] >= 4

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

    manual_widget = client.post(
        f"/api/v1/dashboards/{dashboard_id}/widgets",
        headers=headers,
        json={
            "title": "North Revenue KPI",
            "widget_type": "kpi",
            "config": {
                "summary": "North remains ahead of plan.",
                "chart": {"type": "kpi", "metric": "Revenue", "value": "59800", "delta": "+12%"},
            },
            "position": {"x": 6, "y": 0, "w": 4, "h": 3},
        },
    )
    assert manual_widget.status_code == 200, manual_widget.text
    widget_id = manual_widget.json()["id"]

    update_widget = client.put(
        f"/api/v1/dashboards/{dashboard_id}/widgets/{widget_id}",
        headers=headers,
        json={
            "title": "North Revenue KPI Updated",
            "widget_type": "kpi",
            "config": {
                "summary": "North remains the lead segment after the latest refresh.",
                "chart": {"type": "kpi", "metric": "Revenue", "value": "60200", "delta": "+13%"},
            },
            "position": {"x": 7, "y": 0, "w": 4, "h": 3},
        },
    )
    assert update_widget.status_code == 200, update_widget.text
    assert update_widget.json()["title"] == "North Revenue KPI Updated"

    dashboard_detail = client.get(f"/api/v1/dashboards/{dashboard_id}", headers=headers)
    assert dashboard_detail.status_code == 200, dashboard_detail.text
    assert len(dashboard_detail.json()["widgets"]) >= 6

    report_pack = client.post(
        f"/api/v1/dashboards/{dashboard_id}/report-pack",
        headers=headers,
        json={
            "audience": "Executive leadership",
            "goal": "Board-ready summary with risk and action framing",
        },
    )
    assert report_pack.status_code == 200, report_pack.text
    report_pack_payload = report_pack.json()
    assert report_pack_payload["executive_summary"]
    assert report_pack_payload["sections"]
    assert report_pack_payload["next_actions"]

    delete_widget = client.delete(f"/api/v1/dashboards/{dashboard_id}/widgets/{widget_id}", headers=headers)
    assert delete_widget.status_code == 204, delete_widget.text

    trust_history = client.get("/api/v1/admin/ai-trust-history", headers=headers)
    assert trust_history.status_code == 200, trust_history.text
    trust_payload = trust_history.json()
    assert any(item["artifact_type"] == "nl_query" for item in trust_payload)
    assert any(item["artifact_type"] == "report_pack" for item in trust_payload)

    audit = client.get("/api/v1/admin/audit-logs", headers=headers)
    assert audit.status_code == 200, audit.text
    assert len(audit.json()) > 0
