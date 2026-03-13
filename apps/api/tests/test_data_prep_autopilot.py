from pathlib import Path

from fastapi.testclient import TestClient


def _create_and_sync_csv(client: TestClient, headers: dict[str, str], name: str, file_path: Path) -> str:
    create_connection = client.post(
        "/api/v1/connections",
        headers=headers,
        json={
            "name": name,
            "connector_type": "csv",
            "config": {"file_path": str(file_path)},
        },
    )
    assert create_connection.status_code == 200, create_connection.text
    connection_id = create_connection.json()["id"]

    discover = client.post(f"/api/v1/connections/{connection_id}/discover", headers=headers)
    assert discover.status_code == 200, discover.text

    sync = client.post(f"/api/v1/connections/{connection_id}/sync", headers=headers)
    assert sync.status_code == 200, sync.text
    assert sync.json()["status"] == "success"
    return connection_id


def test_data_prep_autopilot_builds_reversible_plan_and_captures_feedback(client: TestClient, tmp_path: Path):
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "prep@dataviz.com",
            "full_name": "Prep Analyst",
            "password": "Password123!",
            "organization_name": "Prep Org",
            "workspace_name": "Prep Workspace",
        },
    )
    assert signup.status_code == 200, signup.text
    auth = signup.json()

    headers = {
        "Authorization": f"Bearer {auth['access_token']}",
        "X-Workspace-Id": auth["workspaces"][0]["workspace_id"],
    }

    orders_current = tmp_path / "orders_current.csv"
    orders_current.write_text(
        "Order Date,Customer_ID,Region,Revenue,Cost\n"
        "2025-01-01,C-100,North,100,60\n"
        "2025-01-01,C-100,North,100,60\n"
        "2025-02-01,C-101,north,120,70\n"
        "2025-03-01,C-102,South,140,80\n",
        encoding="utf-8",
    )

    orders_archive = tmp_path / "orders_archive.csv"
    orders_archive.write_text(
        "Order Date,Customer_ID,Region,Revenue,Cost\n"
        "2024-10-01,C-090,West,90,55\n"
        "2024-11-01,C-091,North,95,58\n"
        "2024-12-01,C-092,South,110,64\n",
        encoding="utf-8",
    )

    customers = tmp_path / "customers.csv"
    customers.write_text(
        "Customer_ID,Segment,Region\n"
        "C-100,Enterprise,North\n"
        "C-101,Mid Market,North\n"
        "C-102,Enterprise,South\n",
        encoding="utf-8",
    )

    _create_and_sync_csv(client, headers, "Orders Current", orders_current)
    _create_and_sync_csv(client, headers, "Orders Archive", orders_archive)
    _create_and_sync_csv(client, headers, "Customers", customers)

    datasets = client.get("/api/v1/semantic/datasets", headers=headers)
    assert datasets.status_code == 200, datasets.text
    dataset_payload = {item["name"]: item for item in datasets.json()}
    orders_dataset = dataset_payload["orders_current"]

    plan_response = client.get(f"/api/v1/semantic/datasets/{orders_dataset['id']}/prep-plan", headers=headers)
    assert plan_response.status_code == 200, plan_response.text
    plan = plan_response.json()

    step_ids = {step["step_id"] for step in plan["cleaning_steps"]}
    assert "dedupe_rows" in step_ids
    assert "normalize_case:Region" in step_ids
    assert any(step["reversible"] for step in plan["cleaning_steps"])
    assert any("cleaned working copy" in step["revert_strategy"] for step in plan["cleaning_steps"] if step["step_id"] == "dedupe_rows")
    assert any(suggestion["target_dataset_name"] == "customers" for suggestion in plan["join_suggestions"])
    assert any(suggestion["target_dataset_name"] == "orders_archive" for suggestion in plan["union_suggestions"])
    assert any(field["name"] == "gross_margin" for field in plan["calculated_field_suggestions"])
    assert any(item["source"] == "ingestion_cleaning" for item in plan["transformation_lineage"])

    feedback = client.post(
        f"/api/v1/semantic/datasets/{orders_dataset['id']}/prep-feedback",
        headers=headers,
        json={"step_id": "dedupe_rows", "decision": "approve", "comment": "Keep this as the default plan."},
    )
    assert feedback.status_code == 200, feedback.text
    feedback_payload = feedback.json()
    assert feedback_payload["approved"] == 1
    assert feedback_payload["rejected"] == 0

    apply_step = client.post(
        f"/api/v1/semantic/datasets/{orders_dataset['id']}/prep-actions",
        headers=headers,
        json={"step_id": "dedupe_rows", "action": "apply"},
    )
    assert apply_step.status_code == 200, apply_step.text
    assert apply_step.json()["status"] == "applied"

    refreshed_plan = client.get(f"/api/v1/semantic/datasets/{orders_dataset['id']}/prep-plan", headers=headers)
    assert refreshed_plan.status_code == 200, refreshed_plan.text
    refreshed_step = next(step for step in refreshed_plan.json()["cleaning_steps"] if step["step_id"] == "dedupe_rows")
    assert refreshed_step["feedback"]["approved"] == 1
    assert refreshed_step["applied"] is True
    assert refreshed_step["applied_at"]
    assert any(item["source"] == "ai_data_prep_autopilot" and item["status"] == "applied" for item in refreshed_plan.json()["transformation_lineage"])

    rollback_step = client.post(
        f"/api/v1/semantic/datasets/{orders_dataset['id']}/prep-actions",
        headers=headers,
        json={"step_id": "dedupe_rows", "action": "rollback"},
    )
    assert rollback_step.status_code == 200, rollback_step.text
    assert rollback_step.json()["status"] == "rolled_back"

    rolled_back_plan = client.get(f"/api/v1/semantic/datasets/{orders_dataset['id']}/prep-plan", headers=headers)
    assert rolled_back_plan.status_code == 200, rolled_back_plan.text
    rolled_back_step = next(step for step in rolled_back_plan.json()["cleaning_steps"] if step["step_id"] == "dedupe_rows")
    assert rolled_back_step["applied"] is False
    assert any(item["source"] == "ai_data_prep_autopilot" and item["status"] == "rolled_back" for item in rolled_back_plan.json()["transformation_lineage"])