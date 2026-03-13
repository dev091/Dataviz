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

test("connection setup exposes typed forms for each connector", async ({ page }) => {
  await page.addInitScript((state) => {
    window.localStorage.setItem("auth-store-v1", JSON.stringify({ state, version: 0 }));
  }, authState);

  await page.route("**/api/v1/connections", async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.goto("/connections");

  await expect(page.getByText("Local file source")).toBeVisible();
  await expect(page.getByText("Supported: CSV, TSV, TXT, JSON, JSONL, Excel, ODS, Parquet, and XML.")).toBeVisible();

  await page.locator("select").nth(1).selectOption("postgresql");
  await expect(page.getByText("Connect a transactional or warehouse Postgres source.")).toBeVisible();
  await expect(page.getByText("Connection URI")).toBeVisible();

  await page.locator("select").nth(1).selectOption("google_sheets");
  await expect(page.getByText("Published CSV export URL")).toBeVisible();

  await page.locator("select").nth(1).selectOption("salesforce");
  await expect(page.getByText("Security token")).toBeVisible();
  await expect(page.getByText("Object name")).toBeVisible();
});
