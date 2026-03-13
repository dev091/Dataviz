from __future__ import annotations

import os
from typing import Any

from locust import HttpUser, between, task


DEFAULT_QUESTION = os.getenv("LOAD_TEST_QUESTION", "show monthly revenue by region")
DEFAULT_EMAIL = os.getenv("DEMO_EMAIL", "")
DEFAULT_PASSWORD = os.getenv("DEMO_PASSWORD", "")


class PlatformUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.access_token: str | None = None
        self.workspace_id: str | None = None
        self.semantic_model_id: str | None = None
        self.dashboard_id: str | None = None
        self._login_if_configured()
        self._bootstrap_workspace_state()

    def _login_if_configured(self) -> None:
        if not (DEFAULT_EMAIL and DEFAULT_PASSWORD):
            return

        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD},
            name="auth_login",
        )
        if response.status_code != 200:
            response.failure(f"login failed: {response.status_code}")
            return

        payload = response.json()
        self.access_token = payload.get("access_token")
        workspaces = payload.get("workspaces") or []
        if workspaces:
            self.workspace_id = workspaces[0].get("workspace_id")

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if self.workspace_id:
            headers["X-Workspace-Id"] = self.workspace_id
        return headers

    def _bootstrap_workspace_state(self) -> None:
        if not self.access_token or not self.workspace_id:
            return

        models = self.client.get("/api/v1/semantic/models", headers=self._headers(), name="semantic_models_bootstrap")
        if models.status_code == 200:
            payload = models.json() or []
            if payload:
                self.semantic_model_id = payload[0].get("id")

        dashboards = self.client.get("/api/v1/dashboards", headers=self._headers(), name="dashboards_bootstrap")
        if dashboards.status_code == 200:
            payload = dashboards.json() or []
            if payload:
                self.dashboard_id = payload[0].get("id")

    @task(5)
    def health(self) -> None:
        self.client.get("/health", name="health")

    @task(3)
    def metrics(self) -> None:
        self.client.get("/metrics", name="metrics")

    @task(3)
    def dashboards(self) -> None:
        if not self.access_token:
            self.client.get("/openapi.json", name="openapi")
            return
        self.client.get("/api/v1/dashboards", headers=self._headers(), name="dashboards")

    @task(3)
    def semantic_models(self) -> None:
        if not self.access_token:
            self.client.get("/openapi.json", name="openapi")
            return
        self.client.get("/api/v1/semantic/models", headers=self._headers(), name="semantic_models")

    @task(2)
    def subscription(self) -> None:
        if not self.access_token:
            return
        self.client.get("/api/v1/admin/subscription", headers=self._headers(), name="admin_subscription")

    @task(1)
    def nl_query(self) -> None:
        if not (self.access_token and self.semantic_model_id):
            return

        self.client.post(
            "/api/v1/nl/query",
            headers=self._headers(),
            json={
                "semantic_model_id": self.semantic_model_id,
                "question": DEFAULT_QUESTION,
            },
            name="nl_query",
        )

    @task(1)
    def dashboard_summary(self) -> None:
        if not (self.access_token and self.dashboard_id):
            return
        self.client.get(
            f"/api/v1/dashboards/{self.dashboard_id}/executive-summary",
            headers=self._headers(),
            name="dashboard_summary",
        )
