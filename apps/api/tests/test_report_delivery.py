import os
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def setup_env(tmp_path_factory: pytest.TempPathFactory):
    tmp_dir = tmp_path_factory.mktemp("reports")
    db_path = tmp_dir / "reports.db"
    storage = tmp_dir / "storage"

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["REDIS_URL"] = "redis://localhost:6379/8"
    os.environ["STORAGE_ROOT"] = str(storage)
    os.environ["JWT_SECRET_KEY"] = "test-secret"
    os.environ["EMAIL_PROVIDER"] = "log"


@pytest.fixture()
def client(setup_env):
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def test_report_schedule_delivery_logs(client: TestClient):
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "reports@dataviz.com",
            "full_name": "Reports User",
            "password": "Password123!",
            "organization_name": "Reports Org",
            "workspace_name": "Reports Workspace",
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

    dashboard = client.post(
        "/api/v1/dashboards",
        headers=headers,
        json={"name": "Reports Dashboard", "description": "", "layout": {}},
    )
    assert dashboard.status_code == 200, dashboard.text
    dashboard_id = dashboard.json()["id"]

    schedule = client.post(
        "/api/v1/alerts/report-schedules",
        headers=headers,
        json={
            "name": "Daily Exec Report",
            "dashboard_id": dashboard_id,
            "email_to": ["exec@dataviz.com"],
            "schedule_type": "daily",
            "daily_time": None,
            "weekday": None,
            "enabled": True,
        },
    )
    assert schedule.status_code == 200, schedule.text

    root = Path(__file__).resolve().parents[3]
    worker_path = root / "apps" / "worker"
    if str(worker_path) not in sys.path:
        sys.path.append(str(worker_path))

    from worker.tasks import run_due_reports

    result = run_due_reports()
    assert result["delivered"] >= 1

    audit = client.get("/api/v1/admin/audit-logs", headers=headers)
    assert audit.status_code == 200, audit.text
    actions = [row["action"] for row in audit.json()]
    assert "report_schedule.delivered" in actions
