import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[3]
for rel in [
    "apps/api",
    "apps/worker",
    "packages/connectors",
    "packages/semantic",
    "packages/analytics",
]:
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.append(path)


@pytest.fixture(scope="session", autouse=True)
def setup_env(tmp_path_factory: pytest.TempPathFactory):
    tmp_dir = tmp_path_factory.mktemp("data")
    db_path = tmp_dir / "test.db"
    storage = tmp_dir / "storage"

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["REDIS_URL"] = "redis://localhost:6379/7"
    os.environ["STORAGE_ROOT"] = str(storage)
    os.environ["JWT_SECRET_KEY"] = "test-secret"


@pytest.fixture()
def client(setup_env):
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
