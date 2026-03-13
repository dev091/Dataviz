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

test("launch packs provision an executive dashboard from the dashboards screen", async ({ page }) => {
  await page.addInitScript((state) => {
    window.localStorage.setItem("auth-store-v1", JSON.stringify({ state, version: 0 }));
  }, authState);

  await page.route("**/api/v1/dashboards", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ json: { id: "dashboard-created", name: "Manual Dashboard", description: "Created manually" } });
      return;
    }
    await route.fulfill({ json: [] });
  });

  await page.route("**/api/v1/semantic/models", async (route) => {
    await route.fulfill({ json: [{ id: "model-1", name: "Revenue Model", model_key: "revenue_model" }] });
  });

  await page.route("**/api/v1/onboarding/launch-packs/provision", async (route) => {
    await route.fulfill({
      json: {
        template_id: "finance_exec",
        dashboard_id: "dashboard-1",
        dashboard_name: "Finance Executive Pack",
        widgets_added: 5,
        notes: ["Auto-composed 5 widgets from semantic model `Revenue Model`."],
        report_schedule_id: "schedule-1",
        report_schedule_name: "Finance Executive Pack Distribution",
        report_pack: {
          dashboard_id: "dashboard-1",
          dashboard_name: "Finance Executive Pack",
          generated_at: "2026-03-07T10:00:00Z",
          audience: "Finance leadership and executive team",
          goal: "Board-ready finance summary with KPI movement, risks, and follow-up actions",
          report_type: "weekly_business_review",
          executive_summary: "Finance performance is improving while cost pressure remains manageable.",
          sections: [
            { title: "Executive Summary", body: "Finance performance is improving." },
            { title: "Key Highlights", body: "Revenue and profit improved." },
            { title: "Operating Views", body: "This pack includes operating views for Revenue and Margin Overview, Expense Discipline." },
          ],
          operating_views: ["Revenue and Margin Overview", "Expense Discipline", "Regional Variance Review"],
          exception_report: {
            title: "Finance Variance Exceptions",
            body: "Finance Variance Exceptions is focused on the lowest-performing segments in the current governed output.",
          },
          next_actions: ["Review regional variance and preserve margin discipline."],
        },
        suggested_alerts: [
          {
            metric_id: "metric-1",
            metric_name: "profit",
            metric_label: "Profit",
            suggested_condition: "<",
            reason: "Monitor profit automatically as part of the launch pack watchlist.",
          },
        ],
        generated_at: "2026-03-07T10:00:00Z",
      },
    });
  });

  await page.route("**/api/v1/onboarding/launch-packs/finance_exec/playbook*", async (route) => {
    await route.fulfill({
      json: {
        template_id: "finance_exec",
        semantic_model_id: "model-1",
        dashboard_id: "dashboard-1",
        readiness_score: 71.4,
        readiness_summary: "Finance Executive Pack is 71.4% onboarding-ready. Open trust gaps: 1. Enabled schedules: 1. Focus-metric alerts: 1.",
        trust_gap_count: 1,
        recommended_stakeholders: ["Executive sponsor", "Analytics lead", "Business owner", "Operations or finance champion"],
        validation_checks: [
          {
            id: "launch_dashboard",
            title: "Provision launch dashboard",
            status: "done",
            detail: "5 widgets are currently provisioned for the launch dashboard.",
            owner_role: "Executive reporting agent",
            requires_human_review: false,
          },
          {
            id: "launch_schedule",
            title: "Enable recurring delivery",
            status: "done",
            detail: "1/1 schedules are enabled for this launch pack.",
            owner_role: "Customer success",
            requires_human_review: true,
          },
        ],
        milestones: [
          {
            title: "Provision first executive pack",
            status: "done",
            detail: "Target deliverables: Executive finance dashboard, Weekly finance report pack, Department operating views.",
            owner_role: "Executive reporting agent",
          },
        ],
        adoption_signals: [
          {
            signal: "dashboard_widgets",
            label: "Dashboard widgets provisioned",
            value: 5,
            target: 4,
            status: "done",
            detail: "Executive packs should launch with at least 4 useful widgets.",
          },
        ],
      },
    });
  });

  await page.route("**/api/v1/onboarding/launch-packs", async (route) => {
    await route.fulfill({
      json: [
        {
          id: "finance_exec",
          title: "Finance Executive Pack",
          department: "Finance",
          summary: "Board-ready finance reporting with KPI scorecards, variance trends, and weekly executive pack automation.",
          deliverables: ["Executive finance dashboard", "Weekly finance report pack", "Department operating views"],
          focus_metrics: ["revenue", "profit", "margin"],
          operating_views: ["Revenue and Margin Overview", "Expense Discipline", "Regional Variance Review"],
          exception_report_title: "Finance Variance Exceptions",
          report_type: "weekly_business_review",
          report_audience: "Finance leadership and executive team",
          default_dashboard_name: "Finance Executive Pack",
          default_schedule_type: "weekly",
          default_weekday: 0,
          default_daily_time: "08:00",
        },
      ],
    });
  });
  await page.goto("/dashboards");

  await expect(page.getByRole("heading", { name: "First Executive Pack Fast" })).toBeVisible();
  await expect(page.getByText("Finance Executive Pack")).toBeVisible();
  await expect(page.getByText("Onboarding Playbook")).toBeVisible();
  await expect(page.getByText("Finance Executive Pack is 71.4% onboarding-ready. Open trust gaps: 1. Enabled schedules: 1. Focus-metric alerts: 1.")).toBeVisible();
  await expect(page.getByText("Finance Variance Exceptions")).toBeVisible();
  await page.getByRole("button", { name: "Provision launch pack" }).click();
  await expect(page.getByText("Provisioned Launch Pack")).toBeVisible();
  await expect(page.getByText("Finance performance is improving while cost pressure remains manageable.")).toBeVisible();
  await expect(page.getByText("Revenue and Margin Overview").first()).toBeVisible();
  await expect(page.getByText("Finance Variance Exceptions").nth(1)).toBeVisible();
  await expect(page.getByText("Review regional variance and preserve margin discipline.")).toBeVisible();
});



