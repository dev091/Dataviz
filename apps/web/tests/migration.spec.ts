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

test("migration assistant analyzes incumbent assets and bootstraps a governed pack", async ({ page }) => {
  await page.addInitScript((state) => {
    window.localStorage.setItem("auth-store-v1", JSON.stringify({ state, version: 0 }));
  }, authState);

  await page.route("**/api/v1/semantic/models", async (route) => {
    await route.fulfill({ json: [{ id: "model-1", name: "Revenue Model", model_key: "revenue_model" }] });
  });

  await page.route("**/api/v1/onboarding/migration-assistant/analyze", async (route) => {
    await route.fulfill({
      json: {
        source_tool: "power_bi",
        semantic_model_id: "model-1",
        recommended_launch_pack_id: "finance_exec",
        recommended_launch_pack_title: "Finance Executive Pack",
        primary_asset_title: "Executive Finance Scorecard",
        dashboard_matches: [
          {
            source_name: "Executive Finance Scorecard",
            recommended_launch_pack_id: "finance_exec",
            recommended_launch_pack_title: "Finance Executive Pack",
            recommended_dashboard_name: "Executive Finance Scorecard Migration Pack",
            suggested_goal: "Migrate the Power Bi asset 'Executive Finance Scorecard' into a governed Finance reporting flow focused on Revenue, Cost.",
            matched_targets: ["Revenue", "Cost"],
            rationale: "Maps the incumbent asset into the Finance Executive Pack template to reduce manual rebuild work.",
          },
        ],
        report_matches: [
          {
            source_name: "Monthly Board Pack",
            recommended_launch_pack_id: "finance_exec",
            recommended_launch_pack_title: "Finance Executive Pack",
            recommended_dashboard_name: "Monthly Board Pack Migration Pack",
            suggested_goal: "Migrate the Power Bi asset 'Monthly Board Pack' into a governed Finance reporting flow focused on Revenue, Cost.",
            matched_targets: ["Revenue", "Cost"],
            rationale: "Maps the incumbent asset into the Finance Executive Pack template to reduce manual rebuild work.",
          },
        ],
        kpi_matches: [
          {
            source_name: "Revenue",
            target_id: "metric-1",
            target_name: "revenue",
            target_label: "Revenue",
            target_type: "metric",
            score: 1,
            status: "matched",
            rationale: "Exact normalized name match.",
          },
        ],
        dimension_matches: [
          {
            source_name: "Region",
            target_id: "dim-1",
            target_name: "region",
            target_label: "Region",
            target_type: "dimension",
            score: 1,
            status: "matched",
            rationale: "Exact normalized name match.",
          },
        ],
        trust_validation_checks: [
          "Compare incumbent KPI 'Revenue' to governed target 'Revenue' over the last 3 closed periods with shared filters; accept <= 1.0% variance before cutover.",
        ],
        automated_trust_comparison: {
          rows: [
            {
              label: "Total revenue",
              source_name: "Revenue",
              target_name: "revenue",
              target_label: "Revenue",
              dimension_name: null,
              dimension_value: null,
              expected_value: 360,
              governed_value: 360,
              variance: 0,
              variance_pct: 0,
              status: "pass",
              rationale: "Governed value is within the strict migration variance threshold.",
            },
          ],
          summary: {
            compared_rows: 1,
            pass_count: 1,
            review_count: 0,
            fail_count: 0,
            pending_count: 0,
          },
        },
        bootstrap_goal: "Rebuild the Power Bi asset 'Executive Finance Scorecard' as a governed executive reporting flow focused on Revenue using the Finance Executive Pack.",
        coverage: {
          matched_kpis: 1,
          total_kpis: 1,
          matched_dimensions: 1,
          total_dimensions: 1,
          unmatched_assets: 0,
        },
      },
    });
  });

  await page.route("**/api/v1/onboarding/migration-assistant/bootstrap", async (route) => {
    await route.fulfill({
      json: {
        analysis: {
          source_tool: "power_bi",
          semantic_model_id: "model-1",
          recommended_launch_pack_id: "finance_exec",
          recommended_launch_pack_title: "Finance Executive Pack",
          primary_asset_title: "Executive Finance Scorecard",
          dashboard_matches: [],
          report_matches: [],
          kpi_matches: [],
          dimension_matches: [],
          trust_validation_checks: ["Compare incumbent KPI 'Revenue' to governed target 'Revenue' over the last 3 closed periods with shared filters; accept <= 1.0% variance before cutover."],
          automated_trust_comparison: {
            rows: [
              {
                label: "Total revenue",
                source_name: "Revenue",
                target_name: "revenue",
                target_label: "Revenue",
                dimension_name: null,
                dimension_value: null,
                expected_value: 360,
                governed_value: 360,
                variance: 0,
                variance_pct: 0,
                status: "pass",
                rationale: "Governed value is within the strict migration variance threshold.",
              },
            ],
            summary: {
              compared_rows: 1,
              pass_count: 1,
              review_count: 0,
              fail_count: 0,
              pending_count: 0,
            },
          },
          bootstrap_goal: "Rebuild the Power Bi asset 'Executive Finance Scorecard' as a governed executive reporting flow focused on Revenue using the Finance Executive Pack.",
          coverage: {
            matched_kpis: 1,
            total_kpis: 1,
            matched_dimensions: 1,
            total_dimensions: 1,
            unmatched_assets: 0,
          },
        },
        provisioned_pack: {
          template_id: "finance_exec",
          dashboard_id: "dashboard-1",
          dashboard_name: "Executive Finance Scorecard Migration Pack",
          widgets_added: 5,
          notes: ["Auto-composed 5 widgets from semantic model `Revenue Model`."],
          report_schedule_id: "schedule-1",
          report_schedule_name: "Executive Finance Scorecard Migration Pack Distribution",
          report_pack: {
            executive_summary: "Finance performance is improving while cost discipline remains intact.",
            report_type: "weekly_business_review",
            operating_views: ["Revenue and Margin Overview", "Expense Discipline"],
            exception_report: {
              title: "Finance Variance Exceptions",
              body: "Finance Variance Exceptions is focused on the lowest-performing segments in the current governed output.",
            },
            sections: [{ title: "Executive Summary", body: "Finance performance is improving." }],
            next_actions: ["Validate variance against the incumbent board pack and retire the duplicate workflow."],
          },
          suggested_alerts: [
            {
              metric_id: "metric-1",
              metric_label: "Revenue",
              reason: "Monitor revenue automatically as part of the launch pack watchlist.",
            },
          ],
        },
      },
    });
  });

  await page.goto("/migration");

  await expect(page.getByRole("heading", { name: "Migration Assistant" })).toBeVisible();
  await page.getByRole("button", { name: "Analyze bundle" }).click();
  await expect(page.getByText("Migration Analysis")).toBeVisible();
  await expect(page.getByText("Finance Executive Pack").first()).toBeVisible();
  await expect(page.getByText("Automated trust comparison", { exact: true })).toBeVisible();
  await expect(page.getByText("Total revenue", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Bootstrap pack" }).click();
  await expect(page.getByText("Bootstrapped Migration Pack")).toBeVisible();
  await expect(page.getByText("Finance performance is improving while cost discipline remains intact.")).toBeVisible();
  await expect(page.getByText("Finance Variance Exceptions", { exact: true })).toBeVisible();
});



