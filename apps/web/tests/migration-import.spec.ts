import { expect, test } from "@playwright/test";

const authState = {
  accessToken: "token-123",
  refreshToken: "refresh-123",
  email: "owner@dataviz.com",
  userId: "user-1",
  workspaces: [
    {
      workspace_id: "workspace-1",
      workspace_name: "Executive",
      organization_id: "org-1",
      organization_name: "Northstar Analytics",
      role: "Owner",
    },
  ],
  currentWorkspaceId: "workspace-1",
};

test("migration assistant imports a workbook and promotes KPIs", async ({ page }) => {
  await page.addInitScript((state) => {
    window.localStorage.setItem("auth-store-v1", JSON.stringify({ state, version: 0 }));
  }, authState);

  await page.route("**/api/v1/semantic/models", async (route) => {
    await route.fulfill({ json: [{ id: "model-1", name: "Revenue Model", model_key: "revenue_model" }] });
  });

  await page.route("**/api/v1/onboarding/migration-assistant/import-workbook*", async (route) => {
    await route.fulfill({
      json: {
        source_tool: "tableau",
        workbook_name: "Finance Workbook",
        dashboard_names: ["Executive Finance Scorecard"],
        report_names: ["Monthly Board Pack"],
        kpi_names: ["Revenue", "Gross Margin", "Average Revenue"],
        dimension_names: ["Region"],
        benchmark_rows: [],
        kpi_definitions: [
          {
            source_name: "Gross Margin",
            label: "Gross Margin",
            formula: "[revenue] - [cost]",
            aggregation: "sum",
            value_format: "currency",
            description: "Imported from Tableau workbook.",
          },
          {
            source_name: "Average Revenue",
            label: "Average Revenue",
            formula: "AVG(revenue)",
            aggregation: "avg",
            value_format: "currency",
            description: "Imported from Tableau workbook.",
          },
        ],
        notes: "Imported workbook metadata from Tableau workbook 'Finance Workbook'.",
      },
    });
  });
  await page.route("**/api/v1/onboarding/migration-assistant/review-kpis", async (route) => {
    await route.fulfill({
      json: {
        semantic_model_id: "model-1",
        source_tool: "tableau",
        requested_owner_name: "Business Systems Team",
        requested_certification_status: "review",
        notes: "Imported workbook metadata from Tableau workbook 'Finance Workbook'.",
        summary: {
          total_items: 2,
          ready_count: 0,
          review_count: 2,
          blocked_count: 0,
          benchmark_fail_count: 0,
        },
        items: [
          {
            source_name: "Gross Margin",
            label: "Gross Margin",
            target_name: "gross_margin",
            target_label: "Gross Margin",
            target_type: "calculated_field",
            match_status: "promote",
            recommended_action: "promote_calculated_field",
            readiness_status: "review",
            readiness_score: 78,
            proposed_owner_name: "Business Systems Team",
            proposed_certification_status: "review",
            suggested_synonyms: ["Gross Margin", "Margin"],
            benchmark_evidence: {
              compared_rows: 0,
              pass_count: 0,
              review_count: 0,
              fail_count: 0,
              pending_count: 0,
            },
            blockers: [],
            review_notes: ["A governed calculated field can be promoted directly into a KPI without recreating the workbook logic."],
            certification_note: "A governed calculated field can be promoted directly into a KPI without recreating the workbook logic.",
            lineage_preview: {
              source_tool: "tableau",
              migration_source_name: "Gross Margin",
              recommended_action: "promote_calculated_field",
            },
          },
          {
            source_name: "Average Revenue",
            label: "Average Revenue",
            target_name: null,
            target_label: null,
            target_type: null,
            match_status: "unmatched",
            recommended_action: "create_metric_from_import",
            readiness_status: "review",
            readiness_score: 64,
            proposed_owner_name: "Business Systems Team",
            proposed_certification_status: "review",
            suggested_synonyms: ["Average Revenue"],
            benchmark_evidence: {
              compared_rows: 0,
              pass_count: 0,
              review_count: 0,
              fail_count: 0,
              pending_count: 0,
            },
            blockers: [],
            review_notes: ["The workbook exposes a formula that can be promoted into the semantic layer."],
            certification_note: "The workbook exposes a formula that can be promoted into the semantic layer.",
            lineage_preview: {
              source_tool: "tableau",
              migration_source_name: "Average Revenue",
              recommended_action: "create_metric_from_import",
            },
          },
        ],
      },
    });
  });

  await page.route("**/api/v1/onboarding/migration-assistant/promote-kpis", async (route) => {
    await route.fulfill({
      json: {
        semantic_model: {
          id: "semantic-2",
          workspace_id: "workspace-1",
          name: "Revenue Model",
          model_key: "revenue_model",
          version: 2,
          is_active: true,
          base_dataset_id: "dataset-1",
          description: "Finance model",
          created_at: "2026-03-07T12:00:00Z",
        },
        promoted_count: 2,
        results: [
          {
            source_name: "Gross Margin",
            status: "promoted_from_calculated_field",
            target_name: "gross_margin",
            target_label: "Gross Margin",
            owner_name: "Business Systems Team",
            certification_status: "review",
            rationale: "Created governed KPI from calculated field 'gross_margin'.",
          },
          {
            source_name: "Average Revenue",
            status: "created_from_import_definition",
            target_name: "average_revenue",
            target_label: "Average Revenue",
            owner_name: "Business Systems Team",
            certification_status: "review",
            rationale: "Created governed KPI from imported workbook definition.",
          },
        ],
      },
    });
  });

  await page.goto("/migration");  await page.locator('input[type="file"]').setInputFiles({
    name: "finance_workbook.twb",
    mimeType: "text/xml",
    buffer: Buffer.from("<workbook name='Finance Workbook'></workbook>"),
  });

  await expect(page.getByText("Imported Workbook", { exact: true })).toBeVisible();
  await expect(page.getByText("Finance Workbook", { exact: true })).toBeVisible();
  await expect(page.getByText("Gross Margin", { exact: true }).first()).toBeVisible();

  await page.getByRole("button", { name: "Build certification review" }).click();

  await expect(page.getByText("Certification Review", { exact: true })).toBeVisible();
  await expect(page.getByText("promote calculated field", { exact: false })).toBeVisible();

  await page.getByRole("button", { name: "Promote KPIs" }).click();

  await expect(page.getByText("Bulk KPI Promotion", { exact: true })).toBeVisible();
  await expect(page.getByText("Revenue Model v2", { exact: false })).toBeVisible();
  await expect(page.getByText("promoted from calculated field", { exact: false })).toBeVisible();
  await expect(page.getByText("created from import definition", { exact: false })).toBeVisible();
  await expect(page.getByText("Owner Business Systems Team | Status review", { exact: false }).first()).toBeVisible();
});





