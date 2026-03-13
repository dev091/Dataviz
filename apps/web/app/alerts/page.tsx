"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge, Button, Card, CardContent, CardHeader, CardTitle, EmptyState, EmptyStateBody, EmptyStateTitle, Input, Skeleton } from "@/components/ui";
import { apiRequest } from "@/lib/api";
import { FeedbackButton } from "@/components/feedback-button";

type Dashboard = { id: string; name: string };
type SemanticModel = { id: string; name: string };
type MetricOption = { id: string; name: string };

type Rule = {
  id: string;
  name: string;
  condition: string;
  threshold: number;
  enabled: boolean;
};

type ReportSchedule = {
  id: string;
  name: string;
  schedule_type: string;
  email_to: string[];
};

type AlertEvent = {
  id: string;
  rule_name: string;
  status: string;
  value: number;
  message: string;
  triggered_at: string;
};

type DeliveryLog = {
  id: string;
  schedule_id: string;
  schedule_name: string;
  dashboard_id: string;
  dashboard_name?: string | null;
  status: string;
  provider?: string | null;
  message_id?: string | null;
  recipients: string[];
  error?: string | null;
  created_at: string;
};

type ProactiveEscalationPolicy = {
  level: string;
  owner: string;
  route: string;
  sla: string;
  routing_depth?: string | null;
  tier_l1?: string | null;
  tier_l2?: string | null;
  tier_l3?: string | null;
};

type ProactiveInsight = {
  id: string;
  insight_type: string;
  title: string;
  body: string;
  severity: string;
  audiences: string[];
  investigation_paths: string[];
  suggested_actions: string[];
  escalation_policy?: ProactiveEscalationPolicy | null;
  metric_name?: string | null;
  created_at: string;
};

type ProactiveDigest = {
  audience: string;
  generated_at: string;
  summary: string;
  recommended_recipients: string[];
  top_insights: Array<{
    title: string;
    insight_type: string;
    severity: string;
  }>;
  suggested_actions: string[];
  escalation_policies: ProactiveEscalationPolicy[];
};

function toneFromStatus(status: string): "default" | "success" | "warning" | "danger" {
  if (status === "delivered" || status === "triggered") return "success";
  if (status === "failed") return "danger";
  return "default";
}

function toneFromInsightSeverity(status: string): "default" | "success" | "warning" | "danger" {
  if (status === "success") return "success";
  if (status === "critical") return "danger";
  if (status === "warning") return "warning";
  return "default";
}

export default function AlertsPage() {
  const queryClient = useQueryClient();
  const [dashboardId, setDashboardId] = useState("");
  const [scheduleName, setScheduleName] = useState("Weekly Executive Digest");
  const [ruleName, setRuleName] = useState("Revenue drop alert");
  const [semanticModelId, setSemanticModelId] = useState("");
  const [metricId, setMetricId] = useState("");
  const [threshold, setThreshold] = useState("10000");
  const [digestAudience, setDigestAudience] = useState("Executive leadership");
  const [pageError, setPageError] = useState<string | null>(null);
  const [pageNotice, setPageNotice] = useState<string | null>(null);

  const dashboardsQuery = useQuery({
    queryKey: ["dashboards"],
    queryFn: () => apiRequest<Dashboard[]>("/api/v1/dashboards"),
  });
  const modelsQuery = useQuery({
    queryKey: ["semantic-models"],
    queryFn: () => apiRequest<SemanticModel[]>("/api/v1/semantic/models"),
  });
  const schedulesQuery = useQuery({
    queryKey: ["report-schedules"],
    queryFn: () => apiRequest<ReportSchedule[]>("/api/v1/alerts/report-schedules"),
  });
  const rulesQuery = useQuery({
    queryKey: ["alert-rules"],
    queryFn: () => apiRequest<Rule[]>("/api/v1/alerts/rules"),
  });
  const eventsQuery = useQuery({
    queryKey: ["alert-events"],
    queryFn: () => apiRequest<AlertEvent[]>("/api/v1/alerts/events"),
  });
  const deliveryLogsQuery = useQuery({
    queryKey: ["delivery-logs"],
    queryFn: () => apiRequest<DeliveryLog[]>("/api/v1/alerts/delivery-logs"),
  });
  const proactiveInsightsQuery = useQuery({
    queryKey: ["proactive-insights"],
    queryFn: () => apiRequest<ProactiveInsight[]>("/api/v1/alerts/proactive-insights"),
  });
  const proactiveDigestQuery = useQuery({
    queryKey: ["proactive-digest", digestAudience],
    queryFn: () => apiRequest<ProactiveDigest>(`/api/v1/alerts/proactive-digest?audience=${encodeURIComponent(digestAudience)}`),
  });
  const metricsQuery = useQuery({
    queryKey: ["semantic-model-metrics", semanticModelId],
    enabled: Boolean(semanticModelId),
    queryFn: () => apiRequest<MetricOption[]>(`/api/v1/semantic/models/${semanticModelId}/metrics`),
  });

  useEffect(() => {
    if (!dashboardId && dashboardsQuery.data?.[0]) {
      setDashboardId(dashboardsQuery.data[0].id);
    }
  }, [dashboardId, dashboardsQuery.data]);

  useEffect(() => {
    if (!semanticModelId && modelsQuery.data?.[0]) {
      setSemanticModelId(modelsQuery.data[0].id);
    }
  }, [semanticModelId, modelsQuery.data]);

  useEffect(() => {
    if (!metricId && metricsQuery.data?.[0]) {
      setMetricId(metricsQuery.data[0].id);
      return;
    }
    if (metricId && metricsQuery.data && !metricsQuery.data.some((metric) => metric.id === metricId)) {
      setMetricId(metricsQuery.data[0]?.id ?? "");
    }
  }, [metricId, metricsQuery.data]);

  const refreshAll = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["report-schedules"] }),
      queryClient.invalidateQueries({ queryKey: ["alert-rules"] }),
      queryClient.invalidateQueries({ queryKey: ["alert-events"] }),
      queryClient.invalidateQueries({ queryKey: ["delivery-logs"] }),
      queryClient.invalidateQueries({ queryKey: ["proactive-insights"] }),
      queryClient.invalidateQueries({ queryKey: ["proactive-digest"] }),
    ]);
  };

  const createSchedule = useMutation({
    mutationFn: async () =>
      apiRequest("/api/v1/alerts/report-schedules", {
        method: "POST",
        body: JSON.stringify({
          dashboard_id: dashboardId,
          name: scheduleName,
          email_to: ["ops@dataviz.com"],
          schedule_type: "weekly",
          daily_time: "09:00",
          weekday: 1,
          enabled: true,
        }),
      }),
    onSuccess: async () => {
      setPageError(null);
      setPageNotice("Report schedule created.");
      await refreshAll();
    },
    onError: (error) => setPageError(error instanceof Error ? error.message : "Failed to create report schedule"),
  });

  const createRule = useMutation({
    mutationFn: async () => {
      if (!metricId) {
        throw new Error("Select a semantic metric before creating an alert.");
      }
      return apiRequest("/api/v1/alerts/rules", {
        method: "POST",
        body: JSON.stringify({
          semantic_model_id: semanticModelId,
          metric_id: metricId,
          name: ruleName,
          condition: "<",
          threshold: Number(threshold),
          schedule_type: "daily",
          enabled: true,
        }),
      });
    },
    onSuccess: async () => {
      setPageError(null);
      setPageNotice("Alert rule created.");
      await refreshAll();
    },
    onError: (error) => setPageError(error instanceof Error ? error.message : "Failed to create alert rule"),
  });

  const evaluateRule = useMutation({
    mutationFn: (ruleId: string) => apiRequest(`/api/v1/alerts/rules/${ruleId}/evaluate`, { method: "POST" }),
    onSuccess: async () => {
      setPageError(null);
      setPageNotice("Alert rule evaluated.");
      await refreshAll();
    },
    onError: (error) => setPageError(error instanceof Error ? error.message : "Failed to evaluate alert rule"),
  });

  const runProactiveSweep = useMutation({
    mutationFn: () => apiRequest<{ created: number }>("/api/v1/alerts/proactive-insights/run", { method: "POST" }),
    onSuccess: async (result) => {
      setPageError(null);
      setPageNotice(result.created ? `Proactive sweep generated ${result.created} insight artifacts.` : "Proactive sweep completed with no new artifacts.");
      await refreshAll();
    },
    onError: (error) => setPageError(error instanceof Error ? error.message : "Failed to run proactive intelligence sweep"),
  });

  const isLoading = useMemo(
    () =>
      dashboardsQuery.isLoading ||
      modelsQuery.isLoading ||
      schedulesQuery.isLoading ||
      rulesQuery.isLoading ||
      eventsQuery.isLoading ||
      deliveryLogsQuery.isLoading ||
      proactiveInsightsQuery.isLoading ||
      proactiveDigestQuery.isLoading,
    [
      dashboardsQuery.isLoading,
      deliveryLogsQuery.isLoading,
      eventsQuery.isLoading,
      modelsQuery.isLoading,
      proactiveDigestQuery.isLoading,
      proactiveInsightsQuery.isLoading,
      rulesQuery.isLoading,
      schedulesQuery.isLoading,
    ],
  );

  const queryError = [
    dashboardsQuery.error,
    modelsQuery.error,
    schedulesQuery.error,
    rulesQuery.error,
    eventsQuery.error,
    deliveryLogsQuery.error,
    proactiveInsightsQuery.error,
    proactiveDigestQuery.error,
    metricsQuery.error,
  ].find(Boolean);

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">Alerts and Scheduling</h2>
        <p className="text-sm text-slate-500">Create report schedules, threshold alerts, and review delivery history in one governed workspace view.</p>
      </div>

      {pageError ? <p className="text-sm text-red-600">{pageError}</p> : null}
      {pageNotice ? <p className="text-sm text-emerald-700">{pageNotice}</p> : null}
      {queryError ? <p className="text-sm text-red-600">{queryError instanceof Error ? queryError.message : "Failed to load alerts workspace"}</p> : null}

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Schedule dashboard email</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-3"
              onSubmit={(event: FormEvent) => {
                event.preventDefault();
                createSchedule.mutate();
              }}
            >
              <select
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                value={dashboardId}
                onChange={(event) => setDashboardId(event.target.value)}
              >
                {(dashboardsQuery.data ?? []).map((dashboard) => (
                  <option key={dashboard.id} value={dashboard.id}>
                    {dashboard.name}
                  </option>
                ))}
              </select>
              <Input value={scheduleName} onChange={(event) => setScheduleName(event.target.value)} />
              <Button type="submit" disabled={createSchedule.isPending || !dashboardId}>
                {createSchedule.isPending ? "Creating..." : "Create schedule"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Create threshold alert</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-3"
              onSubmit={(event: FormEvent) => {
                event.preventDefault();
                createRule.mutate();
              }}
            >
              <select
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                value={semanticModelId}
                onChange={(event) => setSemanticModelId(event.target.value)}
              >
                {(modelsQuery.data ?? []).map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name}
                  </option>
                ))}
              </select>
              <select
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                value={metricId}
                onChange={(event) => setMetricId(event.target.value)}
              >
                {(metricsQuery.data ?? []).map((metric) => (
                  <option key={metric.id} value={metric.id}>
                    {metric.name}
                  </option>
                ))}
              </select>
              <Input value={ruleName} onChange={(event) => setRuleName(event.target.value)} />
              <Input value={threshold} onChange={(event) => setThreshold(event.target.value)} />
              <Button type="submit" disabled={createRule.isPending || !semanticModelId || !metricId}>
                {createRule.isPending ? "Creating..." : "Create alert rule"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <Skeleton className="h-44" />
          <Skeleton className="h-44" />
          <Skeleton className="h-44" />
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Report schedules</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {(schedulesQuery.data ?? []).map((schedule) => (
              <div key={schedule.id} className="rounded-xl border border-slate-200 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium">{schedule.name}</p>
                  <Badge tone="default">{schedule.schedule_type}</Badge>
                </div>
                <p className="mt-1 text-xs text-slate-500">{schedule.email_to.join(", ")}</p>
              </div>
            ))}
            {!schedulesQuery.data?.length ? (
              <EmptyState className="p-6 text-left">
                <EmptyStateTitle>No schedules yet</EmptyStateTitle>
                <EmptyStateBody>Create the first recurring report to start delivery tracking.</EmptyStateBody>
              </EmptyState>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Create proactive digest</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <select className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" value={digestAudience} onChange={(event) => setDigestAudience(event.target.value)}>
              <option value="Executive leadership">Executive leadership</option>
              <option value="Finance">Finance</option>
              <option value="RevOps">RevOps</option>
              <option value="Operations">Operations</option>
              <option value="Analytics owner">Analytics owner</option>
            </select>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="font-medium">{proactiveDigestQuery.data?.audience ?? digestAudience}</p>
              <p className="mt-2 text-xs text-slate-600">{proactiveDigestQuery.data?.summary ?? "No proactive digest available yet."}</p>
              <p className="mt-2 text-xs text-slate-500">Recipients: {(proactiveDigestQuery.data?.recommended_recipients ?? []).join(", ") || "-"}</p>
              {proactiveDigestQuery.data?.suggested_actions.length ? (
                <div className="mt-3 space-y-1 text-xs text-slate-600">
                  <p className="font-medium text-slate-700">Suggested actions</p>
                  {proactiveDigestQuery.data.suggested_actions.map((action) => (
                    <p key={action}>- {action}</p>
                  ))}
                </div>
              ) : null}
              {proactiveDigestQuery.data?.escalation_policies.length ? (
                <div className="mt-3 space-y-2 text-xs text-slate-500">
                  <p className="font-medium text-slate-700">Escalation guidance</p>
                  {proactiveDigestQuery.data.escalation_policies.map((policy) => (
                    <div key={`${policy.level}-${policy.owner}-${policy.sla}`} className="rounded-lg bg-slate-50 p-2">
                      <p>
                        <span className="font-medium text-slate-700">{policy.level}</span> | Owner: {policy.owner} | SLA: {policy.sla}
                        {policy.routing_depth ? ` | Depth: ${policy.routing_depth}` : ""}
                      </p>
                      <p className="mt-1">{policy.route}</p>
                    </div>
                  ))}
                </div>
              ) : null}
              {proactiveDigestQuery.data?.top_insights.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {proactiveDigestQuery.data.top_insights.map((insight) => (
                    <Badge key={`${insight.title}-${insight.insight_type}`} tone={toneFromInsightSeverity(insight.severity)}>{insight.insight_type}</Badge>
                  ))}
                </div>
              ) : null}
              {proactiveDigestQuery.data ? (
                <div className="mt-4 border-t border-slate-100 pt-3 flex justify-end">
                  <FeedbackButton artifactType="alert" artifactId={digestAudience} />
                </div>
              ) : null}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>Proactive intelligence</CardTitle>
              <p className="text-sm text-slate-500">Run pacing, freshness, anomaly, and trend-break monitoring against governed metrics.</p>
            </div>
            <Button type="button" variant="secondary" onClick={() => runProactiveSweep.mutate()} disabled={runProactiveSweep.isPending}>
              {runProactiveSweep.isPending ? "Running sweep..." : "Run proactive sweep"}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {(proactiveInsightsQuery.data ?? []).map((insight) => (
            <div key={insight.id} className="rounded-xl border border-slate-200 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-medium">{insight.title}</p>
                  <p className="text-xs text-slate-500">
                    {insight.metric_name ?? "Workspace-wide"} | {new Date(insight.created_at).toLocaleString()}
                  </p>
                </div>
                <Badge tone={toneFromInsightSeverity(insight.severity)}>{insight.insight_type}</Badge>
              </div>
              <p className="mt-2 text-xs text-slate-600">{insight.body}</p>
              <p className="mt-2 text-xs text-slate-500">Audience routing: {insight.audiences.join(", ") || "-"}</p>
              {insight.suggested_actions.length ? (
                <div className="mt-2 space-y-1 text-xs text-slate-600">
                  <p className="font-medium text-slate-700">Suggested actions</p>
                  {insight.suggested_actions.map((action) => (
                    <p key={action}>- {action}</p>
                  ))}
                </div>
              ) : null}
              {insight.escalation_policy ? (
                <div className="mt-2 rounded-lg bg-slate-50 p-2 text-xs text-slate-500">
                  <p>
                    <span className="font-medium text-slate-700">Escalation</span> | {insight.escalation_policy.level} | Owner: {insight.escalation_policy.owner} | SLA: {insight.escalation_policy.sla}
                    {insight.escalation_policy.routing_depth ? ` | Depth: ${insight.escalation_policy.routing_depth}` : ""}
                  </p>
                  <p className="mt-1">{insight.escalation_policy.route}</p>
                </div>
              ) : null}
              {insight.investigation_paths.length ? (
                <div className="mt-2 space-y-1 text-xs text-slate-500">
                  {insight.investigation_paths.map((path) => (
                    <p key={path}>{path}</p>
                  ))}
                </div>
              ) : null}
              <div className="mt-3 border-t border-slate-100 pt-3 flex justify-end">
                <FeedbackButton artifactType="insight" artifactId={insight.id} />
              </div>
            </div>
          ))}
          {!proactiveInsightsQuery.data?.length ? (
            <EmptyState className="p-6 text-left">
              <EmptyStateTitle>No proactive intelligence yet</EmptyStateTitle>
              <EmptyStateBody>Run a proactive sweep or wait for the worker schedule to generate monitoring artifacts.</EmptyStateBody>
            </EmptyState>
          ) : null}
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle>Delivery log</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {(deliveryLogsQuery.data ?? []).map((log) => (
              <div key={log.id} className="rounded-xl border border-slate-200 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-medium">{log.schedule_name}</p>
                    <p className="text-xs text-slate-500">{log.dashboard_name ?? "Dashboard unavailable"}</p>
                  </div>
                  <Badge tone={toneFromStatus(log.status)}>{log.status}</Badge>
                </div>
                <div className="mt-2 grid gap-2 text-xs text-slate-500 md:grid-cols-2">
                  <p>Provider: {log.provider ?? "-"}</p>
                  <p>Recipients: {log.recipients.join(", ") || "-"}</p>
                  <p>Message ID: {log.message_id ?? "-"}</p>
                  <p>{new Date(log.created_at).toLocaleString()}</p>
                </div>
                {log.error ? <p className="mt-2 text-xs text-rose-600">{log.error}</p> : null}
              </div>
            ))}
            {!deliveryLogsQuery.data?.length ? (
              <EmptyState className="p-6 text-left">
                <EmptyStateTitle>No deliveries recorded</EmptyStateTitle>
                <EmptyStateBody>Once a schedule runs, this workspace will show each delivery or failure with provider details.</EmptyStateBody>
              </EmptyState>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Alert events</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {(eventsQuery.data ?? []).map((event) => (
              <div key={event.id} className="rounded-xl border border-slate-200 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium">{event.rule_name}</p>
                  <Badge tone={toneFromStatus(event.status)}>{event.status}</Badge>
                </div>
                <p className="mt-1 text-xs text-slate-500">Value: {event.value}</p>
                <p className="text-xs text-slate-500">{new Date(event.triggered_at).toLocaleString()}</p>
                <p className="mt-2 text-xs text-slate-600">{event.message}</p>
              </div>
            ))}
            {!eventsQuery.data?.length ? (
              <EmptyState className="p-6 text-left">
                <EmptyStateTitle>No alert events yet</EmptyStateTitle>
                <EmptyStateBody>Evaluate a rule or wait for the worker schedule to generate event history.</EmptyStateBody>
              </EmptyState>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </section>
  );
}