from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient


def _create_and_sync_csv(client: TestClient, headers: dict[str, str], name: str, file_path: Path) -> None:
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


def test_proactive_insights_capture_freshness_and_trend_break(client: TestClient, tmp_path: Path):
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "proactive@dataviz.com",
            "full_name": "Proactive User",
            "password": "Password123!",
            "organization_name": "Proactive Org",
            "workspace_name": "Proactive Workspace",
        },
    )
    assert signup.status_code == 200, signup.text
    auth = signup.json()

    headers = {
        "Authorization": f"Bearer {auth['access_token']}",
        "X-Workspace-Id": auth["workspaces"][0]["workspace_id"],
    }

    csv = tmp_path / "proactive_revenue.csv"
    csv.write_text(
        "date,region,revenue,cost\n"
        "2025-01-01,North,100,60\n"
        "2025-02-01,North,105,64\n"
        "2025-03-01,North,110,68\n"
        "2025-04-01,North,118,70\n"
        "2025-05-01,North,126,74\n"
        "2025-06-01,North,72,44\n",
        encoding="utf-8",
    )
    _create_and_sync_csv(client, headers, "Proactive Revenue", csv)

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

    from app.db.base import SessionLocal
    from app.models.entities import Dataset

    with SessionLocal() as db:
        dataset = db.get(Dataset, dataset_id)
        assert dataset is not None
        dataset.updated_at = datetime.now(timezone.utc) - timedelta(hours=48)
        dataset.quality_status = "warning"
        db.commit()

    run_response = client.post("/api/v1/alerts/proactive-insights/run", headers=headers)
    assert run_response.status_code == 200, run_response.text
    assert run_response.json()["created"] >= 2

    insights = client.get("/api/v1/alerts/proactive-insights", headers=headers)
    assert insights.status_code == 200, insights.text
    payload = insights.json()
    assert payload
    insight_types = {item["insight_type"] for item in payload}
    assert "freshness" in insight_types
    assert {"trend_break", "pacing"}.intersection(insight_types)
    assert any(item["audiences"] for item in payload)
    assert any(item["investigation_paths"] for item in payload)
    assert any(item["suggested_actions"] for item in payload)
    assert any(item["escalation_policy"] for item in payload)

    digest = client.get("/api/v1/alerts/proactive-digest?audience=Executive%20leadership", headers=headers)
    assert digest.status_code == 200, digest.text
    digest_payload = digest.json()
    assert digest_payload["audience"] == "Executive leadership"
    assert digest_payload["summary"]
    assert digest_payload["recommended_recipients"]
    assert digest_payload["top_insights"]
    assert digest_payload["suggested_actions"]
    assert digest_payload["escalation_policies"]