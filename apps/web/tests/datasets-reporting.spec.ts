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

test("dataset catalog shows quality scoring and field warnings", async ({ page }) => {
  await page.addInitScript((state) => {
    window.localStorage.setItem("auth-store-v1", JSON.stringify({ state, version: 0 }));
  }, authState);

  await page.route("**/api/v1/semantic/datasets", async (route) => {
    await route.fulfill({
      json: [
        {
          id: "dataset-1",
          name: "Orders",
          source_table: "orders.csv",
          physical_table: "ws_orders",
          row_count: 1200,
          quality_status: "excellent",
          quality_profile: {
            overall_score: 94,
            status: "excellent",
            duplicate_rows: 2,
            duplicate_ratio: 0.0017,
            completeness_score: 97,
            duplicate_score: 99,
            cleaning_score: 90,
            cleaning: {
              rows_before: 1210,
              rows_after: 1200,
              rows_dropped: 10,
              renamed_columns: { OrderDate: "order_date" },
              unnamed_columns_removed: ["Unnamed: 0"],
            },
            warnings: ["Column names were standardized during ingestion."],
            field_profiles: [
              {
                name: "customer_id",
                data_type: "string",
                null_count: 0,
                null_ratio: 0,
                distinct_count: 1180,
                unique_ratio: 0.9833,
                sample_values: ["C-100", "C-101"],
                warnings: ["customer_id looks like a high-cardinality identifier."],
              },
            ],
          },
          fields: [
            {
              id: "field-1",
              name: "customer_id",
              data_type: "string",
              is_dimension: true,
              is_metric: false,
            },
          ],
        },
      ],
    });
  });

  await page.goto("/datasets");

  await expect(page.getByRole("heading", { name: "Dataset Catalog" })).toBeVisible();
  await expect(page.getByText("Score 94")).toBeVisible();
  await expect(page.getByText("Column names were standardized during ingestion.")).toBeVisible();
  await expect(page.getByText("customer_id looks like a high-cardinality identifier.")).toBeVisible();
});

test("dashboard page generates AI report pack", async ({ page }) => {
  await page.addInitScript((state) => {
    window.localStorage.setItem("auth-store-v1", JSON.stringify({ state, version: 0 }));
  }, authState);

  await page.route("**/api/v1/dashboards/dashboard-1", async (route) => {
    await route.fulfill({
      json: {
        id: "dashboard-1",
        name: "Executive Overview",
        description: "Board dashboard",
        layout: {},
        widgets: [
          {
            id: "widget-1",
            title: "Revenue Trend",
            widget_type: "line",
            config: {
              summary: "Revenue is rising across the quarter.",
              chart: {
                type: "line",
                series: [
                  {
                    name: "Revenue",
                    data: [["Jan", 100], ["Feb", 120], ["Mar", 140]],
                  },
                ],
              },
            },
            position: { x: 0, y: 0, w: 6, h: 4 },
          },
        ],
      },
    });
  });

  await page.route("**/api/v1/semantic/models", async (route) => {
    await route.fulfill({ json: [{ id: "model-1", name: "Revenue Model", model_key: "revenue_model" }] });
  });

  await page.route("**/api/v1/dashboards/dashboard-1/report-pack", async (route) => {
    await route.fulfill({
      json: {
        dashboard_id: "dashboard-1",
        dashboard_name: "Executive Overview",
        generated_at: "2026-03-07T10:00:00Z",
        audience: "Executive leadership",
        goal: "Board-ready summary with key changes, risks, and recommended actions",
        executive_summary: "Revenue momentum remains positive and operational risk is contained.",
        sections: [
          { title: "Executive Summary", body: "Revenue is rising across the quarter." },
          { title: "Key Highlights", body: "The revenue trend widget shows sustained momentum." },
        ],
        next_actions: ["Review the strongest regions for repeatable growth drivers."],
      },
    });
  });

  await page.goto("/dashboards/dashboard-1");

  await expect(page.getByRole("heading", { name: "AI Report Pack" })).toBeVisible();
  await page.getByRole("button", { name: "Generate AI report pack" }).click();
  await expect(page.getByText("AI report pack generated.")).toBeVisible();
  await expect(page.getByText("Revenue momentum remains positive and operational risk is contained.")).toBeVisible();
  await expect(page.getByText("Review the strongest regions for repeatable growth drivers.")).toBeVisible();
});
