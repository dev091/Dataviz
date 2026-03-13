"""Tests for artifact feedback (usefulness instrumentation) endpoints."""

from pathlib import Path

from fastapi.testclient import TestClient


def _auth_headers(client: TestClient) -> dict:
    """Quick signup and return auth headers."""
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "feedback-qa@dataviz.com",
            "full_name": "Feedback QA",
            "password": "Password123!",
            "organization_name": "Feedback Org",
            "workspace_name": "Feedback WS",
        },
    )
    assert signup.status_code == 200, signup.text
    auth = signup.json()
    return {
        "Authorization": f"Bearer {auth['access_token']}",
        "X-Workspace-Id": auth["workspaces"][0]["workspace_id"],
    }


def test_submit_feedback_useful(client: TestClient):
    """Should accept valid useful feedback."""
    headers = _auth_headers(client)

    resp = client.post(
        "/api/v1/feedback",
        headers=headers,
        json={
            "artifact_type": "nl_query",
            "artifact_id": "00000000-0000-0000-0000-000000000001",
            "rating": "useful",
            "comment": "Very helpful answer",
        },
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["rating"] == "useful"
    assert payload["artifact_type"] == "nl_query"
    assert payload["comment"] == "Very helpful answer"
    assert payload["id"]


def test_submit_feedback_not_useful(client: TestClient):
    """Should accept not_useful feedback."""
    headers = _auth_headers(client)

    resp = client.post(
        "/api/v1/feedback",
        headers=headers,
        json={
            "artifact_type": "alert",
            "artifact_id": "00000000-0000-0000-0000-000000000002",
            "rating": "not_useful",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["rating"] == "not_useful"


def test_submit_feedback_dismissed(client: TestClient):
    """Should accept dismissed feedback."""
    headers = _auth_headers(client)

    resp = client.post(
        "/api/v1/feedback",
        headers=headers,
        json={
            "artifact_type": "insight",
            "artifact_id": "00000000-0000-0000-0000-000000000003",
            "rating": "dismissed",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["rating"] == "dismissed"


def test_feedback_invalid_artifact_type(client: TestClient):
    """Should reject invalid artifact type."""
    headers = _auth_headers(client)

    resp = client.post(
        "/api/v1/feedback",
        headers=headers,
        json={
            "artifact_type": "unknown_thing",
            "artifact_id": "test-id",
            "rating": "useful",
        },
    )
    assert resp.status_code == 400


def test_feedback_invalid_rating(client: TestClient):
    """Should reject invalid rating."""
    headers = _auth_headers(client)

    resp = client.post(
        "/api/v1/feedback",
        headers=headers,
        json={
            "artifact_type": "nl_query",
            "artifact_id": "test-id",
            "rating": "amazing",
        },
    )
    assert resp.status_code == 400


def test_feedback_stats(client: TestClient):
    """Stats endpoint should return aggregated feedback statistics."""
    headers = _auth_headers(client)

    # Submit several feedbacks
    for rating in ["useful", "useful", "not_useful", "dismissed"]:
        client.post(
            "/api/v1/feedback",
            headers=headers,
            json={
                "artifact_type": "nl_query",
                "artifact_id": f"artifact-{rating}",
                "rating": rating,
            },
        )

    client.post(
        "/api/v1/feedback",
        headers=headers,
        json={
            "artifact_type": "alert",
            "artifact_id": "alert-1",
            "rating": "useful",
        },
    )

    stats = client.get("/api/v1/feedback/stats", headers=headers)
    assert stats.status_code == 200, stats.text
    payload = stats.json()

    assert payload["total_feedback"] >= 5
    assert "nl_query" in payload["by_artifact_type"]
    nl_stats = payload["by_artifact_type"]["nl_query"]
    assert nl_stats["useful"] >= 2
    assert nl_stats["not_useful"] >= 1
    assert nl_stats["usefulness_rate"] is not None
    assert nl_stats["false_positive_rate"] is not None

    assert "alert" in payload["by_artifact_type"]
    assert payload["by_artifact_type"]["alert"]["useful"] >= 1
