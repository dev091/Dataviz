from pathlib import Path

from fastapi.testclient import TestClient


def test_migration_assistant_analyze_and_bootstrap(client: TestClient, tmp_path: Path):
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "migrate@dataviz.com",
            "full_name": "Migration User",
            "password": "Password123!",
            "organization_name": "Migration Org",
            "workspace_name": "Migration Workspace",
        },
    )
    assert signup.status_code == 200, signup.text
    auth = signup.json()

    token = auth["access_token"]
    workspace_id = auth["workspaces"][0]["workspace_id"]

    csv = tmp_path / "finance.csv"
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

    connection = client.post(
        "/api/v1/connections",
        headers=headers,
        json={
            "name": "Finance CSV",
            "connector_type": "csv",
            "config": {"file_path": str(csv)},
        },
    )
    assert connection.status_code == 200, connection.text
    connection_id = connection.json()["id"]

    discover = client.post(f"/api/v1/connections/{connection_id}/discover", headers=headers)
    assert discover.status_code == 200, discover.text

    sync = client.post(f"/api/v1/connections/{connection_id}/sync", headers=headers)
    assert sync.status_code == 200, sync.text

    datasets = client.get("/api/v1/semantic/datasets", headers=headers)
    assert datasets.status_code == 200, datasets.text
    dataset_id = datasets.json()[0]["id"]

    draft = client.post(
        "/api/v1/semantic/models/draft",
        headers=headers,
        json={"dataset_id": dataset_id},
    )
    assert draft.status_code == 200, draft.text
    draft_payload = draft.json()

    create_model = client.post(
        "/api/v1/semantic/models",
        headers=headers,
        json={key: value for key, value in draft_payload.items() if key != "inference_notes"},
    )
    assert create_model.status_code == 200, create_model.text
    semantic_model_id = create_model.json()["id"]

    benchmark_rows = [
        {"label": "Total revenue", "kpi_name": "Revenue", "expected_value": 360},
        {"label": "North revenue", "kpi_name": "Revenue", "dimension_name": "Region", "dimension_value": "North", "expected_value": 220},
        {"label": "Total cost", "kpi_name": "Cost", "expected_value": 210},
    ]

    analyze = client.post(
        "/api/v1/onboarding/migration-assistant/analyze",
        headers=headers,
        json={
            "source_tool": "power_bi",
            "semantic_model_id": semantic_model_id,
            "dashboard_names": ["Executive Finance Scorecard"],
            "report_names": ["Monthly Board Pack"],
            "kpi_names": ["Revenue", "Cost", "Gross Margin"],
            "dimension_names": ["Region", "Date"],
            "benchmark_rows": benchmark_rows,
            "notes": "Replace the incumbent finance reporting bundle.",
        },
    )
    assert analyze.status_code == 200, analyze.text
    analysis_payload = analyze.json()
    assert analysis_payload["recommended_launch_pack_id"] == "finance_exec"
    assert any(match["source_name"] == "Revenue" and match["status"] == "matched" for match in analysis_payload["kpi_matches"])
    assert any(match["source_name"] == "Gross Margin" and match["status"] == "promote" for match in analysis_payload["kpi_matches"])
    assert any(match["source_name"] == "Region" and match["status"] == "matched" for match in analysis_payload["dimension_matches"])
    assert analysis_payload["trust_validation_checks"]
    assert analysis_payload["automated_trust_comparison"]["summary"]["pass_count"] == 3
    assert analysis_payload["automated_trust_comparison"]["summary"]["fail_count"] == 0
    assert all(row["status"] == "pass" for row in analysis_payload["automated_trust_comparison"]["rows"])

    bootstrap = client.post(
        "/api/v1/onboarding/migration-assistant/bootstrap",
        headers=headers,
        json={
            "source_tool": "power_bi",
            "semantic_model_id": semantic_model_id,
            "dashboard_names": ["Executive Finance Scorecard"],
            "report_names": ["Monthly Board Pack"],
            "kpi_names": ["Revenue", "Cost", "Gross Margin"],
            "dimension_names": ["Region", "Date"],
            "benchmark_rows": benchmark_rows,
            "notes": "Replace the incumbent finance reporting bundle.",
            "email_to": ["finance@example.com"],
            "create_schedule": True,
        },
    )
    assert bootstrap.status_code == 200, bootstrap.text
    bootstrap_payload = bootstrap.json()
    assert bootstrap_payload["analysis"]["recommended_launch_pack_id"] == "finance_exec"
    assert bootstrap_payload["analysis"]["automated_trust_comparison"]["summary"]["pass_count"] == 3
    assert bootstrap_payload["provisioned_pack"]["widgets_added"] >= 4
    assert bootstrap_payload["provisioned_pack"]["report_schedule_id"]
    assert bootstrap_payload["provisioned_pack"]["report_pack"]["executive_summary"]
    assert bootstrap_payload["provisioned_pack"]["report_pack"]["exception_report"]

    audit = client.get("/api/v1/admin/audit-logs", headers=headers)
    assert audit.status_code == 200, audit.text
    actions = [entry["action"] for entry in audit.json()]
    assert "migration_assistant.analyze" in actions
    assert "migration_assistant.bootstrap" in actions
