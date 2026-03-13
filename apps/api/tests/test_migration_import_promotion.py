from pathlib import Path


def test_migration_workbook_import_and_promote_kpis(client, tmp_path: Path):
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "workbook@dataviz.com",
            "full_name": "Workbook User",
            "password": "Password123!",
            "organization_name": "Workbook Org",
            "workspace_name": "Workbook Workspace",
        },
    )
    assert signup.status_code == 200, signup.text
    auth = signup.json()

    token = auth["access_token"]
    workspace_id = auth["workspaces"][0]["workspace_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": workspace_id}

    csv = tmp_path / "finance.csv"
    csv.write_text(
        "date,region,revenue,cost\n"
        "2025-01-01,North,100,60\n"
        "2025-02-01,North,120,70\n"
        "2025-03-01,South,140,80\n",
        encoding="utf-8",
    )

    connection = client.post(
        "/api/v1/connections",
        headers=headers,
        json={
            "name": "Finance CSV",
            "connector_type": "csv",
            "config": {"file_path": str(csv)},
        },
    )
    assert connection.status_code == 200, connection.text
    connection_id = connection.json()["id"]
    assert client.post(f"/api/v1/connections/{connection_id}/sync", headers=headers).status_code == 200

    datasets = client.get("/api/v1/semantic/datasets", headers=headers)
    dataset_id = datasets.json()[0]["id"]

    draft = client.post("/api/v1/semantic/models/draft", headers=headers, json={"dataset_id": dataset_id})
    assert draft.status_code == 200, draft.text
    create_model = client.post(
        "/api/v1/semantic/models",
        headers=headers,
        json={key: value for key, value in draft.json().items() if key != "inference_notes"},
    )
    assert create_model.status_code == 200, create_model.text
    semantic_model_id = create_model.json()["id"]

    twb = tmp_path / "finance_workbook.twb"
    twb.write_text(
        """
        <workbook name=\"Finance Workbook\">
          <dashboard name=\"Executive Finance Scorecard\" />
          <worksheet name=\"Monthly Board Pack\" />
          <datasources>
            <datasource>
              <column name=\"[revenue]\" caption=\"Revenue\" role=\"measure\" datatype=\"real\" />
              <column name=\"[cost]\" caption=\"Cost\" role=\"measure\" datatype=\"real\" />
              <column name=\"[gross_margin]\" caption=\"Gross Margin\" role=\"measure\" datatype=\"real\">
                <calculation formula=\"[revenue] - [cost]\" />
              </column>
              <column name=\"[net_retained_revenue]\" caption=\"Net Retained Revenue\" role=\"measure\" datatype=\"real\">
                <calculation formula=\"revenue - cost - 5\" />
              </column>
              <column name=\"[region]\" caption=\"Region\" role=\"dimension\" datatype=\"string\" />
            </datasource>
          </datasources>
        </workbook>
        """,
        encoding="utf-8",
    )

    with twb.open("rb") as handle:
        imported = client.post(
            "/api/v1/onboarding/migration-assistant/import-workbook?source_tool=tableau",
            headers=headers,
            files={"file": (twb.name, handle, "text/xml")},
        )
    assert imported.status_code == 200, imported.text
    imported_payload = imported.json()
    assert imported_payload["source_tool"] == "tableau"
    assert "Executive Finance Scorecard" in imported_payload["dashboard_names"]
    assert "Gross Margin" in imported_payload["kpi_names"]
    assert any(item["source_name"] == "Net Retained Revenue" and item["formula"] == "revenue - cost - 5" for item in imported_payload["kpi_definitions"])

    review = client.post(
        "/api/v1/onboarding/migration-assistant/review-kpis",
        headers=headers,
        json={
            "semantic_model_id": semantic_model_id,
            "source_tool": imported_payload["source_tool"],
            "selected_source_names": ["Gross Margin", "Net Retained Revenue"],
            "imported_kpis": imported_payload["kpi_definitions"],
            "benchmark_rows": [],
            "owner_name": "Finance Systems",
            "certification_status": "review",
            "notes": imported_payload["notes"],
        },
    )
    assert review.status_code == 200, review.text
    review_payload = review.json()
    assert review_payload["summary"]["total_items"] == 2
    assert review_payload["summary"]["blocked_count"] == 0
    actions = {item["source_name"]: item["recommended_action"] for item in review_payload["items"]}
    assert actions["Gross Margin"] == "promote_calculated_field"
    assert actions["Net Retained Revenue"] == "create_metric_from_import"

    promote = client.post(
        "/api/v1/onboarding/migration-assistant/promote-kpis",
        headers=headers,
        json={
            "semantic_model_id": semantic_model_id,
            "source_tool": imported_payload["source_tool"],
            "selected_source_names": ["Gross Margin", "Net Retained Revenue"],
            "imported_kpis": imported_payload["kpi_definitions"],
            "owner_name": "Finance Systems",
            "certification_status": "review",
            "notes": imported_payload["notes"],
            "review_items": review_payload["items"],
        },
    )
    assert promote.status_code == 200, promote.text
    promote_payload = promote.json()
    assert promote_payload["promoted_count"] == 2
    statuses = {item["source_name"]: item["status"] for item in promote_payload["results"]}
    assert statuses["Gross Margin"] == "promoted_from_calculated_field"
    assert statuses["Net Retained Revenue"] == "created_from_import_definition"
    assert promote_payload["semantic_model"]["version"] == 2

    versions = client.get(f"/api/v1/semantic/models/{promote_payload['semantic_model']['id']}/versions", headers=headers)
    assert versions.status_code == 200, versions.text
    assert versions.json()[0]["version"] == 2

    semantic_detail = client.get(f"/api/v1/semantic/models/{promote_payload['semantic_model']['id']}", headers=headers)
    assert semantic_detail.status_code == 200, semantic_detail.text
    metrics = {item["label"]: item for item in semantic_detail.json()["metrics"]}
    assert metrics["Gross Margin"]["owner_name"] == "Finance Systems"
    assert metrics["Gross Margin"]["certification_status"] == "review"
    assert metrics["Gross Margin"]["lineage"]["source_tool"] == "tableau"
    assert metrics["Net Retained Revenue"]["lineage"]["migration_source_name"] == "Net Retained Revenue"

    audit = client.get("/api/v1/admin/audit-logs", headers=headers)
    assert audit.status_code == 200, audit.text
    audit_actions = [entry["action"] for entry in audit.json()]
    assert "migration_assistant.review_kpis" in audit_actions
