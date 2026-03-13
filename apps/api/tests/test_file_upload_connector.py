from pathlib import Path

from fastapi.testclient import TestClient


def test_file_upload_connection_accepts_json_and_syncs(client: TestClient, tmp_path: Path):
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "file@dataviz.com",
            "full_name": "File Upload User",
            "password": "Password123!",
            "organization_name": "File Upload Org",
            "workspace_name": "File Upload Workspace",
        },
    )
    assert signup.status_code == 200, signup.text
    auth = signup.json()

    token = auth["access_token"]
    workspace_id = auth["workspaces"][0]["workspace_id"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-Id": workspace_id,
    }

    payload_path = tmp_path / "customers.json"
    payload_path.write_text(
        '[{"customer":"Acme","region":"North","revenue":1200},{"customer":"Globex","region":"West","revenue":900}]',
        encoding="utf-8",
    )

    connection = client.post(
        "/api/v1/connections",
        headers=headers,
        json={
            "name": "Customer JSON",
            "connector_type": "file_upload",
            "config": {"file_path": str(payload_path), "file_format": "json"},
        },
    )
    assert connection.status_code == 200, connection.text
    connection_id = connection.json()["id"]

    discover = client.post(f"/api/v1/connections/{connection_id}/discover", headers=headers)
    assert discover.status_code == 200, discover.text
    preview = discover.json()
    assert preview["meta"]["file_format"] == "json"
    assert preview["datasets"][0]["fields"][0]["name"] == "customer"

    sync = client.post(f"/api/v1/connections/{connection_id}/sync", headers=headers)
    assert sync.status_code == 200, sync.text
    logs = sync.json()["logs"]["datasets"][0]
    assert logs["file_format"] == "json"
    assert logs["rows"] == 2


def test_file_upload_endpoint_accepts_json_file(client: TestClient):
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "upload@dataviz.com",
            "full_name": "Upload User",
            "password": "Password123!",
            "organization_name": "Upload Org",
            "workspace_name": "Upload Workspace",
        },
    )
    assert signup.status_code == 200, signup.text
    auth = signup.json()

    headers = {
        "Authorization": f"Bearer {auth['access_token']}",
        "X-Workspace-Id": auth["workspaces"][0]["workspace_id"],
    }

    response = client.post(
        "/api/v1/connections/files/upload",
        headers=headers,
        files={"file": ("payload.json", b'[{"region":"North","revenue":100}]', "application/json")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["file_format"] == "json"
