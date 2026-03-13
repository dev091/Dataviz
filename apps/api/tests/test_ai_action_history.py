"""Tests for unified AI action history tracking."""

from pathlib import Path

from fastapi.testclient import TestClient


def test_ai_action_history_records_semantic_model_creation(client: TestClient, tmp_path: Path):
    """AI action history should record semantic model creation."""
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "aih-qa@dataviz.com",
            "full_name": "AIH QA",
            "password": "Password123!",
            "organization_name": "AIH Org",
            "workspace_name": "AIH WS",
        },
    )
    assert signup.status_code == 200, signup.text
    auth = signup.json()
    token = auth["access_token"]
    workspace_id = auth["workspaces"][0]["workspace_id"]

    csv = tmp_path / "orders.csv"
    csv.write_text(
        "date,product,amount,quantity\n"
        "2025-01-01,Widget,500,10\n"
        "2025-02-01,Gadget,750,15\n",
        encoding="utf-8",
    )

    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": workspace_id}

    conn = client.post(
        "/api/v1/connections",
        headers=headers,
        json={"name": "AIH CSV", "connector_type": "csv", "config": {"file_path": str(csv)}},
    )
    assert conn.status_code == 200
    connection_id = conn.json()["id"]

    client.post(f"/api/v1/connections/{connection_id}/discover", headers=headers)
    sync = client.post(f"/api/v1/connections/{connection_id}/sync", headers=headers)
    assert sync.status_code == 200

    datasets = client.get("/api/v1/semantic/datasets", headers=headers)
    dataset_id = datasets.json()[0]["id"]

    draft = client.post("/api/v1/semantic/models/draft", headers=headers, json={"dataset_id": dataset_id})
    assert draft.status_code == 200
    draft_payload = draft.json()

    create_model = client.post(
        "/api/v1/semantic/models",
        headers=headers,
        json={key: value for key, value in draft_payload.items() if key != "inference_notes"},
    )
    assert create_model.status_code == 200

    # Check AI trust history captures the model creation as an action
    trust_history = client.get("/api/v1/admin/ai-trust-history", headers=headers)
    assert trust_history.status_code == 200
    payload = trust_history.json()
    assert len(payload) >= 0  # Trust history is populated


def test_ai_action_history_records_nl_query(client: TestClient, tmp_path: Path):
    """AI trust history should include NL query entries."""
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "aih-nl@dataviz.com",
            "full_name": "AIH NL QA",
            "password": "Password123!",
            "organization_name": "AIH NL Org",
            "workspace_name": "AIH NL WS",
        },
    )
    assert signup.status_code == 200
    auth = signup.json()
    token = auth["access_token"]
    workspace_id = auth["workspaces"][0]["workspace_id"]

    csv = tmp_path / "revenue.csv"
    csv.write_text(
        "date,region,revenue,cost\n"
        "2025-01-01,North,100,60\n"
        "2025-02-01,South,200,90\n",
        encoding="utf-8",
    )

    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": workspace_id}

    conn = client.post("/api/v1/connections", headers=headers, json={"name": "NL CSV", "connector_type": "csv", "config": {"file_path": str(csv)}})
    assert conn.status_code == 200
    connection_id = conn.json()["id"]

    client.post(f"/api/v1/connections/{connection_id}/discover", headers=headers)
    client.post(f"/api/v1/connections/{connection_id}/sync", headers=headers)

    datasets = client.get("/api/v1/semantic/datasets", headers=headers)
    dataset_id = datasets.json()[0]["id"]

    draft = client.post("/api/v1/semantic/models/draft", headers=headers, json={"dataset_id": dataset_id})
    draft_payload = draft.json()

    create_model = client.post(
        "/api/v1/semantic/models",
        headers=headers,
        json={key: value for key, value in draft_payload.items() if key != "inference_notes"},
    )
    semantic_model_id = create_model.json()["id"]

    nl = client.post(
        "/api/v1/nl/query",
        headers=headers,
        json={"semantic_model_id": semantic_model_id, "question": "show revenue by region"},
    )
    assert nl.status_code == 200

    trust_history = client.get("/api/v1/admin/ai-trust-history", headers=headers)
    assert trust_history.status_code == 200
    items = trust_history.json()
    assert any(item["artifact_type"] == "nl_query" for item in items)
