"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  EmptyStateBody,
  EmptyStateTitle,
  Input,
  Skeleton,
} from "@/components/ui";

import { apiRequest } from "@/lib/api";
import { FeedbackButton } from "@/components/feedback-button";

type Dashboard = {
  id: string;
  name: string;
  description?: string;
};

type SemanticModel = {
  id: string;
  name: string;
  model_key: string;
};

type LaunchPackTemplate = {
  id: string;
  title: string;
  department: string;
  summary: string;
  deliverables: string[];
  focus_metrics: string[];
  operating_views: string[];
  exception_report_title: string;
  report_type: string;
  report_audience: string;
  default_dashboard_name: string;
  default_schedule_type: string;
  default_weekday?: number | null;
  default_daily_time?: string | null;
};

type LaunchPackAlertSuggestion = {
  metric_id: string;
  metric_name: string;
  metric_label: string;
  suggested_condition: string;
  reason: string;
};

type ReportPackSection = {
  title: string;
  body: string;
};

type LaunchPackProvisionResult = {
  template_id: string;
  dashboard_id: string;
  dashboard_name: string;
  widgets_added: number;
  notes: string[];
  report_schedule_id?: string | null;
  report_schedule_name?: string | null;
  report_pack: {
    dashboard_id: string;
    dashboard_name: string;
    generated_at: string;
    audience: string;
    goal: string;
    report_type: string;
    executive_summary: string;
    sections: ReportPackSection[];
    operating_views: string[];
    exception_report?: ReportPackSection | null;
    next_actions: string[];
  };
  suggested_alerts: LaunchPackAlertSuggestion[];
  generated_at: string;
};

type LaunchPackPlaybook = {
  template_id: string;
  semantic_model_id: string;
  dashboard_id?: string | null;
  readiness_score: number;
  readiness_summary: string;
  trust_gap_count: number;
  recommended_stakeholders: string[];
  validation_checks: {
    id: string;
    title: string;
    status: string;
    detail: string;
    owner_role: string;
    requires_human_review: boolean;
  }[];
  milestones: {
    title: string;
    status: string;
    detail: string;
    owner_role: string;
  }[];
  adoption_signals: {
    signal: string;
    label: string;
    value: number;
    target: number;
    status: string;
    detail: string;
  }[];
};
function playbookTone(status: string): "default" | "success" | "warning" | "danger" {
  if (status === "done") return "success";
  if (status === "at_risk") return "warning";
  if (status === "pending") return "default";
  return "danger";
}

function prettyPlaybookStatus(status: string): string {
  return status.replace(/_/g, " ");
}

export default function DashboardsPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("Executive Overview");
  const [description, setDescription] = useState("Core executive KPIs and insights");
  const [pageError, setPageError] = useState<string | null>(null);
  const [selectedPackId, setSelectedPackId] = useState("");
  const [selectedModelId, setSelectedModelId] = useState("");
  const [launchEmails, setLaunchEmails] = useState("leadership@example.com");
  const [launchResult, setLaunchResult] = useState<LaunchPackProvisionResult | null>(null);

  const dashboardsQuery = useQuery({
    queryKey: ["dashboards"],
    queryFn: () => apiRequest<Dashboard[]>("/api/v1/dashboards"),
  });

  const semanticModelsQuery = useQuery({
    queryKey: ["launch-packs", "semantic-models"],
    queryFn: () => apiRequest<SemanticModel[]>("/api/v1/semantic/models"),
  });

  const launchPacksQuery = useQuery({
    queryKey: ["launch-packs", "templates"],
    queryFn: () => apiRequest<LaunchPackTemplate[]>("/api/v1/onboarding/launch-packs"),
  });

  const playbookQuery = useQuery({
    queryKey: ["launch-packs", "playbook", selectedPackId, selectedModelId, launchResult?.dashboard_id ?? ""],
    enabled: Boolean(selectedPackId && selectedModelId),
    queryFn: () => {
      const params = new URLSearchParams({ semantic_model_id: selectedModelId });
      if (launchResult?.dashboard_id) {
        params.set("dashboard_id", launchResult.dashboard_id);
      }
      return apiRequest<LaunchPackPlaybook>(`/api/v1/onboarding/launch-packs/${selectedPackId}/playbook?${params.toString()}`);
    },
  });
  useEffect(() => {
    if (!selectedPackId && launchPacksQuery.data?.[0]) {
      setSelectedPackId(launchPacksQuery.data[0].id);
    }
  }, [selectedPackId, launchPacksQuery.data]);

  useEffect(() => {
    if (!selectedModelId && semanticModelsQuery.data?.[0]) {
      setSelectedModelId(semanticModelsQuery.data[0].id);
    }
  }, [selectedModelId, semanticModelsQuery.data]);

  const createDashboard = useMutation({
    mutationFn: () =>
      apiRequest<Dashboard>("/api/v1/dashboards", {
        method: "POST",
        body: JSON.stringify({
          name,
          description,
          layout: { cols: 12, rowHeight: 32 },
        }),
      }),
    onSuccess: async () => {
      setPageError(null);
      await queryClient.invalidateQueries({ queryKey: ["dashboards"] });
    },
    onError: (error) => setPageError(error instanceof Error ? error.message : "Failed to create dashboard"),
  });

  const provisionLaunchPack = useMutation({
    mutationFn: () =>
      apiRequest<LaunchPackProvisionResult>("/api/v1/onboarding/launch-packs/provision", {
        method: "POST",
        body: JSON.stringify({
          template_id: selectedPackId,
          semantic_model_id: selectedModelId,
          email_to: launchEmails
            .split(",")
            .map((email) => email.trim())
            .filter(Boolean),
          create_schedule: true,
        }),
      }),
    onSuccess: async (payload) => {
      setPageError(null);
      setLaunchResult(payload);
      await queryClient.invalidateQueries({ queryKey: ["dashboards"] });
      await queryClient.invalidateQueries({ queryKey: ["launch-packs", "playbook"] });
    },    onError: (error) => setPageError(error instanceof Error ? error.message : "Failed to provision launch pack"),
  });

  const launchPacks = launchPacksQuery.data ?? [];
  const semanticModels = semanticModelsQuery.data ?? [];
  const selectedPack = launchPacks.find((pack) => pack.id === selectedPackId) ?? null;

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">Dashboards</h2>
        <p className="text-sm text-slate-500">
          Build, save, and operationalize governed dashboard views for each workspace. Use launch packs to create the first
          executive-ready reporting flow fast.
        </p>
      </div>

      <Card className="border-slate-900 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 text-white">
        <CardHeader>
          <CardTitle>First Executive Pack Fast</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="max-w-3xl text-sm text-slate-200">
            Select a launch pack, attach it to a governed semantic model, and provision an executive dashboard, AI report pack,
            department operating views, exception watchlist, suggested alert watchlist, and optional recurring schedule in one step.
          </p>

          {launchPacksQuery.isLoading || semanticModelsQuery.isLoading ? (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <Skeleton className="h-48 bg-white/10" />
              <Skeleton className="h-48 bg-white/10" />
              <Skeleton className="h-48 bg-white/10" />
              <Skeleton className="h-48 bg-white/10" />
            </div>
          ) : null}

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {launchPacks.map((pack) => {
              const selected = pack.id === selectedPackId;
              return (
                <button
                  type="button"
                  key={pack.id}
                  onClick={() => setSelectedPackId(pack.id)}
                  className={`rounded-2xl border p-4 text-left transition ${selected ? "border-white bg-white/10 shadow-lg" : "border-white/10 bg-white/5 hover:bg-white/8"}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-semibold">{pack.title}</p>
                    <Badge tone={selected ? "success" : "default"}>{pack.department}</Badge>
                  </div>
                  <p className="mt-3 text-xs leading-6 text-slate-300">{pack.summary}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {pack.focus_metrics.slice(0, 4).map((metric) => (
                      <Badge key={metric} tone="default">{metric}</Badge>
                    ))}
                  </div>
                </button>
              );
            })}
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <select
              className="rounded-md border border-white/15 bg-white/5 px-3 py-2 text-sm text-white"
              value={selectedModelId}
              onChange={(event) => setSelectedModelId(event.target.value)}
            >
              <option value="" className="text-slate-900">Select semantic model</option>
              {semanticModels.map((model) => (
                <option key={model.id} value={model.id} className="text-slate-900">
                  {model.name}
                </option>
              ))}
            </select>
            <Input value={launchEmails} onChange={(event) => setLaunchEmails(event.target.value)} placeholder="leadership@example.com, finance@example.com" className="bg-white text-slate-900" />
            <Button onClick={() => provisionLaunchPack.mutate()} disabled={provisionLaunchPack.isPending || !selectedPackId || !selectedModelId}>
              {provisionLaunchPack.isPending ? "Provisioning..." : "Provision launch pack"}
            </Button>
          </div>

          {selectedPack ? (
            <div className="grid gap-4 md:grid-cols-[2fr,1fr]">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-300">Included Deliverables</p>
                <ul className="mt-3 space-y-2 text-sm text-slate-100">
                  {selectedPack.deliverables.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <div className="space-y-4">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-wide text-slate-300">Operating Views</p>
                  <ul className="mt-2 space-y-2 text-sm text-slate-100">
                    {selectedPack.operating_views.map((view) => (
                      <li key={view}>{view}</li>
                    ))}
                  </ul>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-wide text-slate-300">Exception Report</p>
                  <p className="mt-2 text-sm text-slate-100">{selectedPack.exception_report_title}</p>
                  <p className="mt-4 text-xs uppercase tracking-wide text-slate-300">Report Type</p>
                  <p className="mt-2 text-sm text-slate-100">{selectedPack.report_type.replace(/_/g, " ")}</p>
                </div>
              </div>
            </div>
          ) : null}

          {playbookQuery.isLoading ? (
            <div className="grid gap-3 md:grid-cols-3">
              <Skeleton className="h-32 bg-white/10" />
              <Skeleton className="h-32 bg-white/10" />
              <Skeleton className="h-32 bg-white/10" />
            </div>
          ) : null}

          {playbookQuery.data ? (
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-300">Onboarding Playbook</p>
                  <p className="mt-2 text-sm text-slate-100">{playbookQuery.data.readiness_summary}</p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs">
                  <Badge tone="success">Readiness {playbookQuery.data.readiness_score}%</Badge>
                  <Badge tone={playbookQuery.data.trust_gap_count ? "warning" : "success"}>Trust gaps {playbookQuery.data.trust_gap_count}</Badge>
                </div>
              </div>

              <div className="mt-4 grid gap-4 xl:grid-cols-[1.3fr,1fr,1fr]">
                <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-wide text-slate-300">KPI Validation</p>
                  <div className="mt-3 space-y-3">
                    {playbookQuery.data.validation_checks.map((item) => (
                      <div key={item.id} className="rounded-lg border border-white/10 bg-slate-950/40 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-medium text-slate-100">{item.title}</p>
                          <Badge tone={playbookTone(item.status)}>{prettyPlaybookStatus(item.status)}</Badge>
                        </div>
                        <p className="mt-1 text-xs text-slate-300">{item.detail}</p>
                        <p className="mt-2 text-[11px] uppercase tracking-wide text-slate-400">Owner: {item.owner_role}{item.requires_human_review ? " | human review" : " | autonomous"}</p>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-wide text-slate-300">Adoption Signals</p>
                  <div className="mt-3 space-y-3">
                    {playbookQuery.data.adoption_signals.map((item) => (
                      <div key={item.signal} className="rounded-lg border border-white/10 bg-slate-950/40 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-medium text-slate-100">{item.label}</p>
                          <Badge tone={playbookTone(item.status)}>{item.value}/{item.target}</Badge>
                        </div>
                        <p className="mt-1 text-xs text-slate-300">{item.detail}</p>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="space-y-4">
                  <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                    <p className="text-xs uppercase tracking-wide text-slate-300">Milestones</p>
                    <div className="mt-3 space-y-3">
                      {playbookQuery.data.milestones.map((item) => (
                        <div key={item.title} className="rounded-lg border border-white/10 bg-slate-950/40 p-3">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="text-sm font-medium text-slate-100">{item.title}</p>
                            <Badge tone={playbookTone(item.status)}>{prettyPlaybookStatus(item.status)}</Badge>
                          </div>
                          <p className="mt-1 text-xs text-slate-300">{item.detail}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                    <p className="text-xs uppercase tracking-wide text-slate-300">Stakeholders</p>
                    <ul className="mt-3 space-y-2 text-sm text-slate-100">
                      {playbookQuery.data.recommended_stakeholders.map((stakeholder) => (
                        <li key={stakeholder}>{stakeholder}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          ) : null}

          {!semanticModels.length && !semanticModelsQuery.isLoading ? (
            <p className="text-sm text-amber-200">Create a semantic model first. Launch packs provision executive reporting from governed metric and dimension definitions.</p>
          ) : null}        </CardContent>
      </Card>

      {launchResult ? (
        <Card>
          <CardHeader>
            <CardTitle>Provisioned Launch Pack</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
              <span>Dashboard: <Link href={`/dashboards/${launchResult.dashboard_id}`} className="font-medium text-brand-600">{launchResult.dashboard_name}</Link></span>
              <span>Widgets: {launchResult.widgets_added}</span>
              <Badge tone="default">{launchResult.report_pack.report_type.replace(/_/g, " ")}</Badge>
              {launchResult.report_schedule_name ? <span>Schedule: {launchResult.report_schedule_name}</span> : null}
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500">Executive Summary</p>
              <p className="mt-2 text-sm text-slate-700">{launchResult.report_pack.executive_summary}</p>
              <div className="mt-3 pt-3 border-t border-slate-200">
                <FeedbackButton artifactType="dashboard_report" artifactId={launchResult.dashboard_id} />
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">Suggested Alert Watchlist</p>
                <ul className="mt-3 space-y-2 text-sm text-slate-700">
                  {launchResult.suggested_alerts.map((alert) => (
                    <li key={alert.metric_id}>{alert.metric_label}: {alert.reason}</li>
                  ))}
                </ul>
              </div>
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">Operating Views</p>
                <ul className="mt-3 space-y-2 text-sm text-slate-700">
                  {launchResult.report_pack.operating_views.map((view) => (
                    <li key={view}>{view}</li>
                  ))}
                </ul>
              </div>
            </div>
            {launchResult.report_pack.exception_report ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                <p className="text-xs uppercase tracking-wide text-amber-700">Exception Report</p>
                <p className="mt-2 text-sm font-medium text-amber-900">{launchResult.report_pack.exception_report.title}</p>
                <p className="mt-2 text-sm text-amber-900">{launchResult.report_pack.exception_report.body}</p>
              </div>
            ) : null}
            <div className="rounded-xl border border-slate-200 p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500">Report Pack Sections</p>
              <ul className="mt-3 space-y-2 text-sm text-slate-700">
                {launchResult.report_pack.sections.map((section) => (
                  <li key={section.title}>{section.title}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-xl border border-slate-200 p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500">Suggested Next Actions</p>
              <ul className="mt-3 space-y-2 text-sm text-slate-700">
                {launchResult.report_pack.next_actions.map((action) => (
                  <li key={action}>{action}</li>
                ))}
              </ul>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Create dashboard</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="grid grid-cols-1 gap-3 md:grid-cols-3"
            onSubmit={(event: FormEvent) => {
              event.preventDefault();
              createDashboard.mutate();
            }}
          >
            <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Dashboard name" />
            <Input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Description" />
            <Button type="submit" disabled={createDashboard.isPending}>{createDashboard.isPending ? "Creating..." : "Create"}</Button>
          </form>
          {pageError ? <p className="mt-2 text-sm text-red-600">{pageError}</p> : null}
        </CardContent>
      </Card>

      {dashboardsQuery.error ? <p className="text-sm text-red-600">{dashboardsQuery.error instanceof Error ? dashboardsQuery.error.message : "Failed to load dashboards"}</p> : null}

      {dashboardsQuery.isLoading ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <Skeleton className="h-44" />
          <Skeleton className="h-44" />
          <Skeleton className="h-44" />
        </div>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {(dashboardsQuery.data ?? []).map((dashboard) => (
          <Card key={dashboard.id}>
            <CardHeader>
              <CardTitle>{dashboard.name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-slate-600">{dashboard.description || "No description"}</p>
              <Link href={`/dashboards/${dashboard.id}`} className="text-sm font-medium text-brand-600">
                Open builder
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>

      {!dashboardsQuery.isLoading && !dashboardsQuery.data?.length ? (
        <EmptyState>
          <EmptyStateTitle>No dashboards yet</EmptyStateTitle>
          <EmptyStateBody>Create the first governed dashboard manually or provision a launch pack for a faster executive reporting setup.</EmptyStateBody>
        </EmptyState>
      ) : null}
    </section>
  );
}





