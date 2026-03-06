"use client";

import { FormEvent, useEffect, useState } from "react";

import { Button, Card, CardContent, CardHeader, CardTitle, Input } from "@platform/ui";

import { apiRequest } from "@/lib/api";

type Usage = {
  datasets: number;
  semantic_models: number;
  dashboards: number;
  connections: number;
};

type Insight = {
  id: string;
  insight_type: string;
  title: string;
  body: string;
  created_at: string;
};

type Subscription = {
  organization_id: string;
  organization_name: string;
  plan_tier: string;
  subscription_status: string;
  billing_provider: string;
  billing_email: string;
  billing_customer_id?: string | null;
  billing_subscription_id?: string | null;
  billing_price_id?: string | null;
  seat_limit: number;
  trial_ends_at?: string;
  commercial_mode: string;
  self_serve_checkout_enabled: boolean;
  billing_portal_enabled: boolean;
};

type BillingSessionResponse = {
  provider: string;
  session_id: string;
  url: string;
  plan_tier: string;
  organization: Subscription;
};

export default function AdminPage() {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [billingEmail, setBillingEmail] = useState("");
  const [planTier, setPlanTier] = useState("starter");
  const [subscriptionStatus, setSubscriptionStatus] = useState("trial");
  const [seatLimit, setSeatLimit] = useState("10");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [portalLoading, setPortalLoading] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [usageData, insightData, subscriptionData] = await Promise.all([
          apiRequest<Usage>("/api/v1/admin/usage"),
          apiRequest<Insight[]>("/api/v1/admin/insights"),
          apiRequest<Subscription>("/api/v1/admin/subscription"),
        ]);
        setUsage(usageData);
        setInsights(insightData);
        syncSubscriptionState(subscriptionData);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load admin metrics");
      }
    }
    void load();
  }, []);

  function syncSubscriptionState(data: Subscription) {
    setSubscription(data);
    setBillingEmail(data.billing_email ?? "");
    setPlanTier(data.plan_tier);
    setSubscriptionStatus(data.subscription_status);
    setSeatLimit(String(data.seat_limit));
  }

  async function updateSubscription(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);

    try {
      const payload = await apiRequest<Subscription>("/api/v1/admin/subscription", {
        method: "PUT",
        body: JSON.stringify({
          billing_email: billingEmail,
          plan_tier: planTier,
          subscription_status: subscriptionStatus,
          seat_limit: Number(seatLimit),
        }),
      });
      syncSubscriptionState(payload);
      setNotice("Subscription settings updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update subscription settings");
    } finally {
      setSaving(false);
    }
  }

  async function launchCheckout() {
    setCheckoutLoading(true);
    setError(null);
    setNotice(null);

    try {
      const payload = await apiRequest<BillingSessionResponse>("/api/v1/billing/checkout-session", {
        method: "POST",
        body: JSON.stringify({ plan_tier: planTier }),
      });
      syncSubscriptionState(payload.organization);
      setNotice(`Checkout session created with ${payload.provider}.`);
      window.open(payload.url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create checkout session");
    } finally {
      setCheckoutLoading(false);
    }
  }

  async function openPortal() {
    setPortalLoading(true);
    setError(null);
    setNotice(null);

    try {
      const payload = await apiRequest<BillingSessionResponse>("/api/v1/billing/portal-session", {
        method: "POST",
        body: JSON.stringify({}),
      });
      syncSubscriptionState(payload.organization);
      setNotice(`Billing portal opened through ${payload.provider}.`);
      window.open(payload.url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open billing portal");
    } finally {
      setPortalLoading(false);
    }
  }

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Admin Settings</h2>
        <p className="text-sm text-slate-500">Workspace governance, usage metrics, commercial controls, and proactive AI insight monitoring.</p>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {notice ? <p className="text-sm text-emerald-700">{notice}</p> : null}

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle>Datasets</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{usage?.datasets ?? "-"}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Semantic Models</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{usage?.semantic_models ?? "-"}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Dashboards</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{usage?.dashboards ?? "-"}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Connections</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{usage?.connections ?? "-"}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Subscription and Entitlements</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-md border border-slate-200 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Organization</p>
              <p className="mt-1 text-sm font-semibold">{subscription?.organization_name ?? "-"}</p>
            </div>
            <div className="rounded-md border border-slate-200 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Commercial mode</p>
              <p className="mt-1 text-sm font-semibold">{subscription?.commercial_mode ?? "-"}</p>
            </div>
            <div className="rounded-md border border-slate-200 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Billing provider</p>
              <p className="mt-1 text-sm font-semibold">{subscription?.billing_provider ?? "-"}</p>
            </div>
            <div className="rounded-md border border-slate-200 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Trial Ends</p>
              <p className="mt-1 text-sm font-semibold">{subscription?.trial_ends_at ? new Date(subscription.trial_ends_at).toLocaleDateString() : "-"}</p>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-md border border-slate-200 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Customer ID</p>
              <p className="mt-1 text-sm font-semibold text-slate-700">{subscription?.billing_customer_id ?? "Not linked yet"}</p>
            </div>
            <div className="rounded-md border border-slate-200 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Subscription ID</p>
              <p className="mt-1 text-sm font-semibold text-slate-700">{subscription?.billing_subscription_id ?? "Not linked yet"}</p>
            </div>
            <div className="rounded-md border border-slate-200 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Price ID</p>
              <p className="mt-1 text-sm font-semibold text-slate-700">{subscription?.billing_price_id ?? "Not linked yet"}</p>
            </div>
          </div>

          <form className="grid gap-3 md:grid-cols-2" onSubmit={updateSubscription}>
            <div>
              <label className="mb-1 block text-sm text-slate-600">Billing email</label>
              <Input value={billingEmail} onChange={(e) => setBillingEmail(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-600">Seat limit</label>
              <Input type="number" min="1" value={seatLimit} onChange={(e) => setSeatLimit(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-600">Plan tier</label>
              <select className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" value={planTier} onChange={(e) => setPlanTier(e.target.value)}>
                <option value="starter">Starter</option>
                <option value="growth">Growth</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-600">Subscription status</label>
              <select className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" value={subscriptionStatus} onChange={(e) => setSubscriptionStatus(e.target.value)}>
                <option value="trial">Trial</option>
                <option value="active">Active</option>
                <option value="past_due">Past due</option>
                <option value="canceled">Canceled</option>
              </select>
            </div>
            <div className="md:col-span-2 flex flex-wrap gap-3">
              <Button type="submit" disabled={saving}>{saving ? "Saving..." : "Update subscription settings"}</Button>
              <Button type="button" variant="secondary" disabled={checkoutLoading || !subscription?.self_serve_checkout_enabled} onClick={launchCheckout}>
                {checkoutLoading ? "Preparing checkout..." : "Start self-serve checkout"}
              </Button>
              <Button type="button" variant="secondary" disabled={portalLoading || !subscription?.billing_portal_enabled} onClick={openPortal}>
                {portalLoading ? "Opening portal..." : "Open billing portal"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent AI Insights (Multi-Agent)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {insights.slice(0, 8).map((insight) => (
            <div key={insight.id} className="rounded-md border border-slate-200 p-3">
              <p className="text-sm font-semibold">{insight.title}</p>
              <p className="text-xs text-slate-500">{insight.insight_type}</p>
              <p className="mt-1 text-sm text-slate-700">{insight.body}</p>
            </div>
          ))}
          {!insights.length ? <p className="text-sm text-slate-500">No insights generated yet.</p> : null}
        </CardContent>
      </Card>
    </section>
  );
}
