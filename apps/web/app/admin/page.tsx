"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, EmptyState, EmptyStateBody, EmptyStateTitle, Input, Skeleton } from "@/components/ui";

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

type TrustHistoryItem = {
  id: string;
  artifact_type: string;
  title: string;
  summary: string;
  source_label?: string | null;
  prompt_or_trigger?: string | null;
  trust_signals: string[];
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

function toneForSubscription(status: string): "default" | "success" | "warning" | "danger" {
  if (status === "active") return "success";
  if (status === "past_due") return "warning";
  if (status === "canceled") return "danger";
  return "default";
}

export default function AdminPage() {
  const queryClient = useQueryClient();
  const [billingEmail, setBillingEmail] = useState("");
  const [planTier, setPlanTier] = useState("starter");
  const [subscriptionStatus, setSubscriptionStatus] = useState("trial");
  const [seatLimit, setSeatLimit] = useState("10");
  const [notice, setNotice] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);

  const usageQuery = useQuery({ queryKey: ["admin-usage"], queryFn: () => apiRequest<Usage>("/api/v1/admin/usage") });
  const insightsQuery = useQuery({ queryKey: ["admin-insights"], queryFn: () => apiRequest<Insight[]>("/api/v1/admin/insights") });
  const aiTrustHistoryQuery = useQuery({
    queryKey: ["admin-ai-trust-history"],
    queryFn: () => apiRequest<TrustHistoryItem[]>("/api/v1/admin/ai-trust-history"),
  });
  const subscriptionQuery = useQuery({
    queryKey: ["admin-subscription"],
    queryFn: () => apiRequest<Subscription>("/api/v1/admin/subscription"),
  });

  useEffect(() => {
    if (!subscriptionQuery.data) {
      return;
    }
    setBillingEmail(subscriptionQuery.data.billing_email ?? "");
    setPlanTier(subscriptionQuery.data.plan_tier);
    setSubscriptionStatus(subscriptionQuery.data.subscription_status);
    setSeatLimit(String(subscriptionQuery.data.seat_limit));
  }, [subscriptionQuery.data]);

  const refreshSubscription = async () => {
    await queryClient.invalidateQueries({ queryKey: ["admin-subscription"] });
  };

  const updateSubscription = useMutation({
    mutationFn: () =>
      apiRequest<Subscription>("/api/v1/admin/subscription", {
        method: "PUT",
        body: JSON.stringify({
          billing_email: billingEmail,
          plan_tier: planTier,
          subscription_status: subscriptionStatus,
          seat_limit: Number(seatLimit),
        }),
      }),
    onSuccess: async (payload) => {
      queryClient.setQueryData(["admin-subscription"], payload);
      setNotice("Subscription settings updated.");
      setPageError(null);
      await refreshSubscription();
    },
    onError: (error) => {
      setNotice(null);
      setPageError(error instanceof Error ? error.message : "Failed to update subscription settings");
    },
  });

  const launchCheckout = useMutation({
    mutationFn: () =>
      apiRequest<BillingSessionResponse>("/api/v1/billing/checkout-session", {
        method: "POST",
        body: JSON.stringify({ plan_tier: planTier }),
      }),
    onSuccess: async (payload) => {
      queryClient.setQueryData(["admin-subscription"], payload.organization);
      setNotice(`Checkout session created with ${payload.provider}.`);
      setPageError(null);
      await refreshSubscription();
      window.open(payload.url, "_blank", "noopener,noreferrer");
    },
    onError: (error) => {
      setNotice(null);
      setPageError(error instanceof Error ? error.message : "Failed to create checkout session");
    },
  });

  const openPortal = useMutation({
    mutationFn: () => apiRequest<BillingSessionResponse>("/api/v1/billing/portal-session", { method: "POST", body: JSON.stringify({}) }),
    onSuccess: async (payload) => {
      queryClient.setQueryData(["admin-subscription"], payload.organization);
      setNotice(`Billing portal opened through ${payload.provider}.`);
      setPageError(null);
      await refreshSubscription();
      window.open(payload.url, "_blank", "noopener,noreferrer");
    },
    onError: (error) => {
      setNotice(null);
      setPageError(error instanceof Error ? error.message : "Failed to open billing portal");
    },
  });

  const subscription = subscriptionQuery.data;
  const queryError = [usageQuery.error, insightsQuery.error, aiTrustHistoryQuery.error, subscriptionQuery.error].find(Boolean);
  const isLoading = usageQuery.isLoading || insightsQuery.isLoading || aiTrustHistoryQuery.isLoading || subscriptionQuery.isLoading;
  const usageCards = useMemo(
    () => [
      { label: "Datasets", value: usageQuery.data?.datasets ?? "-" },
      { label: "Semantic Models", value: usageQuery.data?.semantic_models ?? "-" },
      { label: "Dashboards", value: usageQuery.data?.dashboards ?? "-" },
      { label: "Connections", value: usageQuery.data?.connections ?? "-" },
    ],
    [usageQuery.data],
  );

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">Admin Settings</h2>
        <p className="text-sm text-slate-500">Governance, usage, billing posture, and proactive AI monitoring for the active workspace.</p>
      </div>

      {pageError ? <p className="text-sm text-red-600">{pageError}</p> : null}
      {notice ? <p className="text-sm text-emerald-700">{notice}</p> : null}
      {queryError ? <p className="text-sm text-red-600">{queryError instanceof Error ? queryError.message : "Failed to load admin metrics"}</p> : null}

      <div className="grid gap-4 md:grid-cols-4">
        {isLoading
          ? Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-28" />)
          : usageCards.map((card) => (
              <Card key={card.label}>
                <CardHeader>
                  <CardTitle>{card.label}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-semibold">{card.value}</p>
                </CardContent>
              </Card>
            ))}
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle>Subscription and Entitlements</CardTitle>
            {subscription ? <Badge tone={toneForSubscription(subscription.subscription_status)}>{subscription.subscription_status}</Badge> : null}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Organization</p>
              <p className="mt-1 text-sm font-semibold">{subscription?.organization_name ?? "-"}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Commercial mode</p>
              <p className="mt-1 text-sm font-semibold">{subscription?.commercial_mode ?? "-"}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Billing provider</p>
              <p className="mt-1 text-sm font-semibold">{subscription?.billing_provider ?? "-"}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Trial Ends</p>
              <p className="mt-1 text-sm font-semibold">{subscription?.trial_ends_at ? new Date(subscription.trial_ends_at).toLocaleDateString() : "-"}</p>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Customer ID</p>
              <p className="mt-1 text-sm font-semibold text-slate-700">{subscription?.billing_customer_id ?? "Not linked yet"}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Subscription ID</p>
              <p className="mt-1 text-sm font-semibold text-slate-700">{subscription?.billing_subscription_id ?? "Not linked yet"}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Price ID</p>
              <p className="mt-1 text-sm font-semibold text-slate-700">{subscription?.billing_price_id ?? "Not linked yet"}</p>
            </div>
          </div>

          <form
            className="grid gap-3 md:grid-cols-2"
            onSubmit={(event: FormEvent) => {
              event.preventDefault();
              updateSubscription.mutate();
            }}
          >
            <div>
              <label className="mb-1 block text-sm text-slate-600">Billing email</label>
              <Input value={billingEmail} onChange={(event) => setBillingEmail(event.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-600">Seat limit</label>
              <Input type="number" min="1" value={seatLimit} onChange={(event) => setSeatLimit(event.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-600">Plan tier</label>
              <select className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" value={planTier} onChange={(event) => setPlanTier(event.target.value)}>
                <option value="starter">Starter</option>
                <option value="growth">Growth</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-600">Subscription status</label>
              <select className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" value={subscriptionStatus} onChange={(event) => setSubscriptionStatus(event.target.value)}>
                <option value="trial">Trial</option>
                <option value="active">Active</option>
                <option value="past_due">Past due</option>
                <option value="canceled">Canceled</option>
              </select>
            </div>
            <div className="flex flex-wrap gap-3 md:col-span-2">
              <Button type="submit" disabled={updateSubscription.isPending}>{updateSubscription.isPending ? "Saving..." : "Update subscription settings"}</Button>
              <Button type="button" variant="secondary" disabled={launchCheckout.isPending || !subscription?.self_serve_checkout_enabled} onClick={() => launchCheckout.mutate()}>
                {launchCheckout.isPending ? "Preparing checkout..." : "Start self-serve checkout"}
              </Button>
              <Button type="button" variant="secondary" disabled={openPortal.isPending || !subscription?.billing_portal_enabled} onClick={() => openPortal.mutate()}>
                {openPortal.isPending ? "Opening portal..." : "Open billing portal"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[0.9fr,1.1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Recent AI Insights (Multi-Agent)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {(insightsQuery.data ?? []).slice(0, 8).map((insight) => (
              <div key={insight.id} className="rounded-xl border border-slate-200 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold">{insight.title}</p>
                  <Badge tone="default">{insight.insight_type}</Badge>
                </div>
                <p className="mt-2 text-sm text-slate-700">{insight.body}</p>
              </div>
            ))}
            {!insightsQuery.data?.length ? (
              <EmptyState>
                <EmptyStateTitle>No insights generated yet</EmptyStateTitle>
                <EmptyStateBody>Run NL analytics or wait for the worker to produce proactive artifacts for this workspace.</EmptyStateBody>
              </EmptyState>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>AI Trust History</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {(aiTrustHistoryQuery.data ?? []).slice(0, 10).map((item) => (
              <div key={`${item.artifact_type}-${item.id}`} className="rounded-xl border border-slate-200 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold">{item.title}</p>
                    <p className="text-xs text-slate-500">{item.source_label ?? "Workspace artifact"} | {new Date(item.created_at).toLocaleString()}</p>
                  </div>
                  <Badge tone="default">{item.artifact_type}</Badge>
                </div>
                <p className="mt-2 text-sm text-slate-700">{item.summary}</p>
                {item.prompt_or_trigger ? <p className="mt-2 text-xs text-slate-500">Prompt or trigger: {item.prompt_or_trigger}</p> : null}
                {item.trust_signals.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {item.trust_signals.map((signal) => (
                      <Badge key={`${item.id}-${signal}`} tone="default">{signal}</Badge>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
            {!aiTrustHistoryQuery.data?.length ? (
              <EmptyState>
                <EmptyStateTitle>No AI trust history yet</EmptyStateTitle>
                <EmptyStateBody>Generate NL analyses, report packs, or proactive sweeps to populate governed AI artifact history.</EmptyStateBody>
              </EmptyState>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </section>
  );
}

