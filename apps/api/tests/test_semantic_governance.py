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


def test_semantic_governance_roundtrip_and_trust_panel(client: TestClient, tmp_path: Path):
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "governance@dataviz.com",
            "full_name": "Semantic Governor",
            "password": "Password123!",
            "organization_name": "Governance Org",
            "workspace_name": "Governance Workspace",
        },
    )
    assert signup.status_code == 200, signup.text
    auth = signup.json()

    headers = {
        "Authorization": f"Bearer {auth['access_token']}",
        "X-Workspace-Id": auth["workspaces"][0]["workspace_id"],
    }

    csv = tmp_path / "revenue_governance.csv"
    csv.write_text(
        "order_date,region,revenue,cost\n"
        "2025-01-01,North,100,60\n"
        "2025-02-01,North,120,70\n"
        "2025-03-01,South,140,80\n",
        encoding="utf-8",
    )
    _create_and_sync_csv(client, headers, "Revenue Governance", csv)

    datasets = client.get("/api/v1/semantic/datasets", headers=headers)
    assert datasets.status_code == 200, datasets.text
    dataset_id = datasets.json()[0]["id"]

    draft = client.post("/api/v1/semantic/models/draft", headers=headers, json={"dataset_id": dataset_id})
    assert draft.status_code == 200, draft.text
    payload = draft.json()

    payload["governance"] = {
        "owner_name": "Alex Rivera",
        "owner_email": "alex@dataviz.com",
        "certification_status": "certified",
        "certification_note": "Validated against the finance close package.",
        "trusted_for_nl": True,
    }

    for metric in payload["metrics"]:
        metric["description"] = f"Governed metric for {metric['label']}."
        metric["synonyms"] = [metric["label"], f"{metric['label']} total"]
        metric["owner_name"] = "Alex Rivera"
        metric["certification_status"] = "certified"

    for dimension in payload["dimensions"]:
        dimension["description"] = f"Governed dimension for {dimension['label']}."
        dimension["synonyms"] = [dimension["label"]]
        dimension["owner_name"] = "Alex Rivera"
        dimension["certification_status"] = "certified"
        if dimension["name"] == "region":
            dimension["hierarchy"] = ["region_group", "region"]
        else:
            dimension["hierarchy"] = ["year", "quarter", "month"] if dimension.get("time_grain") else [dimension["name"]]

    create_model = client.post("/api/v1/semantic/models", headers=headers, json={key: value for key, value in payload.items() if key != "inference_notes"})
    assert create_model.status_code == 200, create_model.text
    semantic_model_id = create_model.json()["id"]

    detail = client.get(f"/api/v1/semantic/models/{semantic_model_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    detail_payload = detail.json()
    assert detail_payload["governance"]["owner_name"] == "Alex Rivera"
    assert detail_payload["governance"]["certification_status"] == "certified"
    assert any(metric["synonyms"] for metric in detail_payload["metrics"])
    assert any(dimension["hierarchy"] for dimension in detail_payload["dimensions"])

    nl = client.post(
        "/api/v1/nl/query",
        headers=headers,
        json={
            "semantic_model_id": semantic_model_id,
            "question": "show revenue by region",
        },
    )
    assert nl.status_code == 200, nl.text

    trust_panel = client.get(f"/api/v1/semantic/models/{semantic_model_id}/trust-panel", headers=headers)
    assert trust_panel.status_code == 200, trust_panel.text
    trust_payload = trust_panel.json()
    assert trust_payload["governance"]["owner_name"] == "Alex Rivera"
    assert trust_payload["governance"]["certification_status"] == "certified"
    assert trust_payload["lineage_summary"]["metrics_governed"] >= 1
    assert trust_payload["lineage_summary"]["dimensions_governed"] >= 1
    assert any(activity["activity_type"] in {"audit", "nl_query"} for activity in trust_payload["recent_activity"])
    assert all("Assign a semantic owner" not in gap for gap in trust_payload["open_gaps"])
    assert all("Certification is still incomplete" not in gap for gap in trust_payload["open_gaps"])