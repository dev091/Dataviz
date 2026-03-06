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

test("admin billing controls launch checkout and portal flows", async ({ page }) => {
  const subscription: any = {
    organization_id: "org-1",
    organization_name: "Northstar Analytics",
    plan_tier: "starter",
    subscription_status: "trial",
    billing_provider: "manual",
    billing_email: "finance@northstar.io",
    billing_customer_id: null,
    billing_subscription_id: null,
    billing_price_id: null,
    seat_limit: 25,
    trial_ends_at: "2026-03-20T00:00:00Z",
    commercial_mode: "stripe",
    self_serve_checkout_enabled: true,
    billing_portal_enabled: true,
  };

  await page.addInitScript((state) => {
    window.localStorage.setItem("auth-store-v1", JSON.stringify({ state, version: 0 }));
    Object.defineProperty(window, "open", {
      configurable: true,
      value: (url: string) => {
        Reflect.set(window, "__lastOpened", url);
        return null;
      },
    });
  }, authState);

  await page.route("**/api/v1/admin/usage", async (route) => {
    await route.fulfill({ json: { datasets: 12, semantic_models: 3, dashboards: 5, connections: 4 } });
  });

  await page.route("**/api/v1/admin/insights", async (route) => {
    await route.fulfill({ json: [{ id: "insight-1", insight_type: "trend", title: "Revenue accelerating", body: "Growth is strongest in enterprise accounts.", created_at: "2026-03-06T00:00:00Z" }] });
  });

  await page.route("**/api/v1/admin/subscription", async (route) => {
    if (route.request().method() === "PUT") {
      const body = JSON.parse(route.request().postData() ?? "{}");
      Object.assign(subscription, body);
      await route.fulfill({ json: subscription });
      return;
    }
    await route.fulfill({ json: subscription });
  });

  await page.route("**/api/v1/billing/checkout-session", async (route) => {
    subscription.plan_tier = "growth";
    subscription.billing_provider = "stripe";
    subscription.billing_customer_id = "cus_123";
    await route.fulfill({
      json: {
        provider: "stripe",
        session_id: "cs_123",
        url: "https://billing.example/checkout/cs_123",
        plan_tier: "growth",
        organization: subscription,
      },
    });
  });

  await page.route("**/api/v1/billing/portal-session", async (route) => {
    subscription.billing_subscription_id = "sub_123";
    await route.fulfill({
      json: {
        provider: "stripe",
        session_id: "bps_123",
        url: "https://billing.example/portal/bps_123",
        plan_tier: subscription.plan_tier,
        organization: subscription,
      },
    });
  });

  await page.goto("/admin");

  await expect(page.getByText("Subscription and Entitlements")).toBeVisible();
  await expect(page.getByText("Northstar Analytics", { exact: true })).toBeVisible();

  await page.locator("select").nth(1).selectOption("growth");
  await page.getByRole("button", { name: "Start self-serve checkout" }).click();
  await expect(page.getByText("Checkout session created with stripe.")).toBeVisible();
  await expect(page.getByText("cus_123")).toBeVisible();

  const checkoutUrl = await page.evaluate(() => Reflect.get(window, "__lastOpened"));
  expect(checkoutUrl).toBe("https://billing.example/checkout/cs_123");

  await page.getByRole("button", { name: "Open billing portal" }).click();
  await expect(page.getByText("Billing portal opened through stripe.")).toBeVisible();
  const portalUrl = await page.evaluate(() => Reflect.get(window, "__lastOpened"));
  expect(portalUrl).toBe("https://billing.example/portal/bps_123");
});



