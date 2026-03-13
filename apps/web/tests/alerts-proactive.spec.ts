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

test("alerts page shows proactive intelligence and manual sweep", async ({ page }) => {
  await page.addInitScript((state) => {
    window.localStorage.setItem("auth-store-v1", JSON.stringify({ state, version: 0 }));
  }, authState);

  await page.route("**/api/v1/dashboards", async (route) => {
    await route.fulfill({ json: [{ id: "dashboard-1", name: "Executive Overview" }] });
  });

  await page.route("**/api/v1/semantic/models", async (route) => {
    await route.fulfill({ json: [{ id: "model-1", name: "Revenue Model" }] });
  });

  await page.route("**/api/v1/semantic/models/model-1/metrics", async (route) => {
    await route.fulfill({ json: [{ id: "metric-1", name: "revenue" }] });
  });

  await page.route("**/api/v1/alerts/report-schedules", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ json: { id: "schedule-1" } });
      return;
    }
    await route.fulfill({ json: [] });
  });

  await page.route("**/api/v1/alerts/rules", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ json: { id: "rule-1" } });
      return;
    }
    await route.fulfill({ json: [] });
  });

  await page.route("**/api/v1/alerts/events", async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.route("**/api/v1/alerts/delivery-logs", async (route) => {
    await route.fulfill({ json: [] });
  });

  let insights = [
    {
      id: "insight-1",
      insight_type: "trend_break",
      title: "Trend break: Revenue",
      body: "Revenue shifted down by 22.5% versus the prior rolling window.",
      severity: "warning",
      audiences: ["Executive leadership", "RevOps", "Finance"],
      investigation_paths: [
        "Review Revenue over the latest periods using Order Date.",
        "Break down Revenue by Region to isolate contributing segments.",
      ],
      suggested_actions: [
        "Review the last two reporting windows for Revenue to explain the trend break before the next business review.",
      ],
      escalation_policy: {
        level: "warning",
        owner: "Executive leadership",
        route: "Route to Executive leadership for review and include RevOps, Finance before the next leadership cadence.",
        sla: "1 business day",
      },
      metric_name: "Revenue",
      created_at: "2026-03-07T13:00:00Z",
    },
  ];

  await page.route("**/api/v1/alerts/proactive-insights", async (route) => {
    await route.fulfill({ json: insights });
  });

  await page.route("**/api/v1/alerts/proactive-digest**", async (route) => {
    await route.fulfill({
      json: {
        audience: "Executive leadership",
        generated_at: "2026-03-07T13:00:00Z",
        summary: "Executive leadership should review the revenue trend break before the next operating review.",
        recommended_recipients: ["Executive leadership", "Finance", "RevOps"],
        suggested_actions: [
          "Review the last two reporting windows for Revenue to explain the trend break before the next business review.",
          "Assign an owner and due date before the next reporting cadence.",
        ],
        escalation_policies: [
          {
            level: "warning",
            owner: "Executive leadership",
            route: "Route to Executive leadership for review and include RevOps, Finance before the next leadership cadence.",
            sla: "1 business day",
          },
        ],
        top_insights: [
          { title: "Trend break: Revenue", insight_type: "trend_break", severity: "warning" },
        ],
      },
    });
  });

  await page.route("**/api/v1/alerts/proactive-insights/run", async (route) => {
    insights = [
      ...insights,
      {
        id: "insight-2",
        insight_type: "freshness",
        title: "Freshness watch: Revenue Orders",
        body: "Dataset Revenue Orders has not been refreshed within the expected window.",
        severity: "critical",
        audiences: ["Analytics owner", "Data steward"],
        investigation_paths: ["Validate freshness and quality warnings on dataset Revenue Orders before escalation."],
        suggested_actions: [
          "Run a sync health check for Revenue Orders and confirm upstream connector access.",
        ],
        escalation_policy: {
          level: "critical",
          owner: "Analytics owner",
          route: "Immediate escalation to Analytics owner; notify Data steward in the same operating window.",
          sla: "4 hours",
        },
        metric_name: "Workspace-wide",
        created_at: "2026-03-07T13:05:00Z",
      },
    ];
    await route.fulfill({ json: { created: 1 } });
  });

  await page.goto("/alerts");

  await expect(page.getByRole("heading", { name: "Create proactive digest" })).toBeVisible();
  await expect(page.getByText("Executive leadership should review the revenue trend break before the next operating review.")).toBeVisible();
  await expect(page.getByText("Suggested actions").first()).toBeVisible();
  await expect(page.getByText("Assign an owner and due date before the next reporting cadence.")).toBeVisible();
  await expect(page.getByText("Route to Executive leadership for review and include RevOps, Finance before the next leadership cadence.").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Proactive intelligence", exact: true })).toBeVisible();
  await expect(page.getByText("Trend break: Revenue")).toBeVisible();
  await expect(page.getByText("Audience routing: Executive leadership, RevOps, Finance")).toBeVisible();

  await page.getByRole("button", { name: "Run proactive sweep" }).click();

  await expect(page.getByText("Proactive sweep generated 1 insight artifacts.")).toBeVisible();
  await expect(page.getByText("Freshness watch: Revenue Orders")).toBeVisible();
  await expect(page.getByText("Analytics owner, Data steward")).toBeVisible();
  await expect(page.getByText("Immediate escalation to Analytics owner; notify Data steward in the same operating window.")).toBeVisible();
});