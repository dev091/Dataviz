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

test("semantic editor exposes governance controls and trust panel", async ({ page }) => {
  await page.addInitScript((state) => {
    window.localStorage.setItem("auth-store-v1", JSON.stringify({ state, version: 0 }));
  }, authState);

  await page.route("**/api/v1/semantic/datasets", async (route) => {
    await route.fulfill({
      json: [
        {
          id: "dataset-1",
          name: "Revenue Orders",
          source_table: "orders.csv",
          physical_table: "ws_orders",
          row_count: 1200,
          quality_status: "healthy",
          quality_profile: {
            warnings: ["Date fields were standardized during sync."],
          },
          fields: [
            { id: "field-1", name: "order_date", data_type: "date", is_dimension: true, is_metric: false },
            { id: "field-2", name: "region", data_type: "string", is_dimension: true, is_metric: false },
            { id: "field-3", name: "revenue", data_type: "number", is_dimension: false, is_metric: true },
          ],
        },
      ],
    });
  });

  await page.route("**/api/v1/semantic/models", async (route) => {
    await route.fulfill({
      json: [
        {
          id: "model-1",
          name: "Revenue Model",
          model_key: "revenue_model",
          version: 3,
          created_at: "2026-03-07T12:00:00Z",
        },
      ],
    });
  });

  await page.route("**/api/v1/semantic/models/model-1/trust-panel", async (route) => {
    await route.fulfill({
      json: {
        model_id: "model-1",
        model_name: "Revenue Model",
        model_key: "revenue_model",
        version: 3,
        governance: {
          owner_name: "Alex Rivera",
          owner_email: "alex@dataviz.com",
          certification_status: "certified",
          certification_note: "Validated against finance close outputs.",
          trusted_for_nl: true,
        },
        lineage_summary: {
          base_dataset_name: "Revenue Orders",
          base_quality_status: "healthy",
          joins_configured: 1,
          datasets_in_scope: ["Revenue Orders", "Customers"],
          metrics_governed: 2,
          dimensions_governed: 3,
        },
        recent_activity: [
          {
            activity_type: "audit",
            title: "semantic_model.create",
            detail: null,
            created_at: "2026-03-07T12:05:00Z",
          },
        ],
        open_gaps: [],
      },
    });
  });

  await page.goto("/semantic");

  await expect(page.getByRole("heading", { name: "Semantic Model Editor" })).toBeVisible();
  await expect(page.getByText("Governance and trust")).toBeVisible();
  await expect(page.getByPlaceholder("Owner name")).toBeVisible();
  await expect(page.getByPlaceholder("Owner email")).toBeVisible();
  await expect(page.getByPlaceholder("Synonyms: revenue, sales, bookings")).toBeVisible();
  await expect(page.getByPlaceholder("Hierarchy: year, quarter, month")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Trust Panel" })).toBeVisible();
  await expect(page.getByText("Alex Rivera")).toBeVisible();
  await expect(page.getByText("Validated against finance close outputs.")).toBeVisible();
  await expect(page.locator("div").filter({ hasText: /^Trusted for NL$/ }).first()).toBeVisible();
  await expect(page.getByText("No immediate trust gaps detected for the current governance settings.")).toBeVisible();
});