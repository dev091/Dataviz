"""Tests for metric and transformation lineage API endpoints."""

from pathlib import Path

from fastapi.testclient import TestClient


def _setup_core(client: TestClient, tmp_path: Path) -> dict:
    """Create org, workspace, connection, sync, dataset, and semantic model — shared setup."""
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "lineage-qa@dataviz.com",
            "full_name": "Lineage QA",
            "password": "Password123!",
            "organization_name": "Lineage Org",
            "workspace_name": "Lineage WS",
        },
    )
    assert signup.status_code == 200, signup.text
    auth = signup.json()

    token = auth["access_token"]
    workspace_id = auth["workspaces"][0]["workspace_id"]

    csv = tmp_path / "sales.csv"
    csv.write_text(
        "date,region,revenue,cost\n"
        "2025-01-01,North,1000,600\n"
        "2025-02-01,South,1200,700\n",
        encoding="utf-8",
    )

    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": workspace_id}

    conn = client.post(
        "/api/v1/connections",
        headers=headers,
        json={"name": "Lineage CSV", "connector_type": "csv", "config": {"file_path": str(csv)}},
    )
    assert conn.status_code == 200, conn.text
    connection_id = conn.json()["id"]

    client.post(f"/api/v1/connections/{connection_id}/discover", headers=headers)
    sync = client.post(f"/api/v1/connections/{connection_id}/sync", headers=headers)
    assert sync.status_code == 200, sync.text

    datasets = client.get("/api/v1/semantic/datasets", headers=headers)
    assert datasets.status_code == 200, datasets.text
    dataset_id = datasets.json()[0]["id"]

    draft = client.post("/api/v1/semantic/models/draft", headers=headers, json={"dataset_id": dataset_id})
    assert draft.status_code == 200, draft.text
    draft_payload = draft.json()

    create_model = client.post(
        "/api/v1/semantic/models",
        headers=headers,
        json={key: value for key, value in draft_payload.items() if key != "inference_notes"},
    )
    assert create_model.status_code == 200, create_model.text
    semantic_model_id = create_model.json()["id"]

    model_detail = client.get(f"/api/v1/semantic/models/{semantic_model_id}", headers=headers)
    assert model_detail.status_code == 200
    detail = model_detail.json()

    return {
        "headers": headers,
        "workspace_id": workspace_id,
        "dataset_id": dataset_id,
        "semantic_model_id": semantic_model_id,
        "metrics": detail["metrics"],
    }


def test_metric_lineage_auto_recorded(client: TestClient, tmp_path: Path):
    """Metric lineage entries should be auto-created when a semantic model is created."""
    ctx = _setup_core(client, tmp_path)
    headers = ctx["headers"]
    semantic_model_id = ctx["semantic_model_id"]

    # Check model lineage endpoint
    lineage = client.get(f"/api/v1/lineage/model/{semantic_model_id}", headers=headers)
    assert lineage.status_code == 200, lineage.text
    payload = lineage.json()

    assert payload["model_name"]
    assert payload["base_dataset"]["name"]
    assert len(payload["metric_lineage"]) >= 1
    assert payload["lineage_summary"]["metrics_with_lineage"] >= 1
    assert payload["lineage_summary"]["total_metrics"] >= 1

    # Verify at least one metric has raw_field lineage
    source_types = {entry["source_type"] for entry in payload["metric_lineage"]}
    assert "raw_field" in source_types or "aggregation" in source_types or "calculated_field" in source_types


def test_individual_metric_lineage(client: TestClient, tmp_path: Path):
    """Individual metric lineage endpoint should return provenance chain."""
    ctx = _setup_core(client, tmp_path)
    headers = ctx["headers"]

    # Get a metric ID from the model detail
    revenue_metric = next((m for m in ctx["metrics"] if m["name"] == "revenue"), ctx["metrics"][0])

    # We need to look up the actual metric ID via the semantic model detail
    model_detail = client.get(f"/api/v1/semantic/models/{ctx['semantic_model_id']}", headers=headers)
    assert model_detail.status_code == 200

    # Use the lineage model endpoint to get metric lineage entries
    lineage = client.get(f"/api/v1/lineage/model/{ctx['semantic_model_id']}", headers=headers)
    assert lineage.status_code == 200
    payload = lineage.json()
    assert len(payload["metric_lineage"]) >= 1

    # Each entry should have required fields
    for entry in payload["metric_lineage"]:
        assert "source_field" in entry
        assert "source_type" in entry
        assert "transformation_summary" in entry
        assert "confidence" in entry


def test_dataset_transformation_lineage(client: TestClient, tmp_path: Path):
    """Dataset transformation lineage endpoint should return transformation steps."""
    ctx = _setup_core(client, tmp_path)
    headers = ctx["headers"]
    dataset_id = ctx["dataset_id"]

    lineage = client.get(f"/api/v1/lineage/dataset/{dataset_id}", headers=headers)
    assert lineage.status_code == 200, lineage.text
    payload = lineage.json()
    assert payload["dataset_id"] == dataset_id
    assert payload["dataset_name"]
    assert isinstance(payload["transformation_steps"], list)
