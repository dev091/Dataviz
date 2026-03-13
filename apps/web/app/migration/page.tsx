"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { useMutation, useQuery } from "@tanstack/react-query";
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
  Textarea,
} from "@/components/ui";

import { apiRequest } from "@/lib/api";
import { FeedbackButton } from "@/components/feedback-button";

type CertificationStatus = "draft" | "review" | "certified" | "deprecated";

type SemanticModel = {
  id: string;
  name: string;
  model_key: string;
};

type MigrationMatch = {
  source_name: string;
  target_id?: string | null;
  target_name?: string | null;
  target_label?: string | null;
  target_type?: string | null;
  score: number;
  status: string;
  rationale: string;
};

type MigrationOutputSuggestion = {
  source_name: string;
  recommended_launch_pack_id?: string | null;
  recommended_launch_pack_title?: string | null;
  recommended_dashboard_name: string;
  suggested_goal: string;
  matched_targets: string[];
  rationale: string;
};

type MigrationBenchmarkRow = {
  kpi_name: string;
  expected_value: number;
  dimension_name?: string | null;
  dimension_value?: string | number | null;
  label?: string | null;
  start_date?: string | null;
  end_date?: string | null;
};

type AutomatedTrustRow = {
  label: string;
  source_name: string;
  target_name?: string | null;
  target_label?: string | null;
  dimension_name?: string | null;
  dimension_value?: string | number | null;
  start_date?: string | null;
  end_date?: string | null;
  expected_value: number;
  governed_value?: number | null;
  variance?: number | null;
  variance_pct?: number | null;
  status: string;
  rationale: string;
};

type AutomatedTrustComparison = {
  rows: AutomatedTrustRow[];
  summary: {
    compared_rows: number;
    pass_count: number;
    review_count: number;
    fail_count: number;
    pending_count: number;
  };
};

type ImportedKpiDefinition = {
  source_name: string;
  label?: string | null;
  formula?: string | null;
  aggregation: string;
  value_format?: string | null;
  description?: string | null;
};

type ImportedWorkbookBundle = {
  source_tool: string;
  workbook_name: string;
  dashboard_names: string[];
  report_names: string[];
  kpi_names: string[];
  dimension_names: string[];
  benchmark_rows: MigrationBenchmarkRow[];
  kpi_definitions: ImportedKpiDefinition[];
  notes?: string | null;
};

type MigrationAnalysis = {
  source_tool: string;
  semantic_model_id: string;
  recommended_launch_pack_id?: string | null;
  recommended_launch_pack_title?: string | null;
  primary_asset_title: string;
  dashboard_matches: MigrationOutputSuggestion[];
  report_matches: MigrationOutputSuggestion[];
  kpi_matches: MigrationMatch[];
  dimension_matches: MigrationMatch[];
  trust_validation_checks: string[];
  automated_trust_comparison: AutomatedTrustComparison;
  bootstrap_goal: string;
  coverage: {
    matched_kpis: number;
    total_kpis: number;
    matched_dimensions: number;
    total_dimensions: number;
    unmatched_assets: number;
  };
};

type MigrationBootstrapResponse = {
  analysis: MigrationAnalysis;
  provisioned_pack: {
    template_id: string;
    dashboard_id: string;
    dashboard_name: string;
    widgets_added: number;
    notes: string[];
    report_schedule_id?: string | null;
    report_schedule_name?: string | null;
    report_pack: {
      executive_summary: string;
      report_type: string;
      operating_views: string[];
      exception_report?: { title: string; body: string } | null;
      sections: { title: string; body: string }[];
      next_actions: string[];
    };
    suggested_alerts: { metric_id: string; metric_label: string; reason: string }[];
  };
};

type MigrationReviewItem = {
  source_name: string;
  label: string;
  target_name?: string | null;
  target_label?: string | null;
  target_type?: string | null;
  match_status: string;
  recommended_action: string;
  readiness_status: string;
  readiness_score: number;
  proposed_owner_name?: string | null;
  proposed_certification_status: CertificationStatus;
  suggested_synonyms: string[];
  benchmark_evidence: {
    compared_rows: number;
    pass_count: number;
    review_count: number;
    fail_count: number;
    pending_count: number;
  };
  blockers: string[];
  review_notes: string[];
  certification_note?: string | null;
  lineage_preview: Record<string, unknown>;
};

type MigrationReviewResponse = {
  semantic_model_id: string;
  source_tool: string;
  requested_owner_name?: string | null;
  requested_certification_status: CertificationStatus;
  notes?: string | null;
  summary: {
    total_items: number;
    ready_count: number;
    review_count: number;
    blocked_count: number;
    benchmark_fail_count: number;
  };
  items: MigrationReviewItem[];
};

type MigrationPromoteResponse = {
  semantic_model: {
    id: string;
    workspace_id: string;
    name: string;
    model_key: string;
    version: number;
    is_active: boolean;
    base_dataset_id: string;
    description?: string | null;
    created_at: string;
  };
  promoted_count: number;
  results: {
    source_name: string;
    status: string;
    target_name?: string | null;
    target_label?: string | null;
    owner_name?: string | null;
    certification_status: CertificationStatus;
    rationale: string;
  }[];
};

const benchmarkPlaceholder = JSON.stringify(
  [
    { label: "Total revenue", kpi_name: "Revenue", expected_value: 360 },
    { label: "North revenue", kpi_name: "Revenue", dimension_name: "Region", dimension_value: "North", expected_value: 220 },
    { label: "Total cost", kpi_name: "Cost", expected_value: 210 },
    { label: "Q1 revenue", kpi_name: "Revenue", start_date: "2023-01-01", end_date: "2023-03-31", expected_value: 95 },
  ],
  null,
  2,
);

function parseList(value: string): string[] {
  return value
    .split(/\r?\n|,/) 
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseBenchmarkRows(value: string): MigrationBenchmarkRow[] {
  const trimmed = value.trim();
  if (!trimmed) {
    return [];
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    throw new Error("Benchmark export must be valid JSON.");
  }

  if (!Array.isArray(parsed)) {
    throw new Error("Benchmark export must be a JSON array of rows.");
  }

  return parsed.map((item, index) => {
    if (!item || typeof item !== "object") {
      throw new Error(`Benchmark row ${index + 1} must be an object.`);
    }
    const row = item as Record<string, unknown>;
    const kpi_name = String(row.kpi_name ?? "").trim();
    const expected_value = Number(row.expected_value);
    if (!kpi_name) {
      throw new Error(`Benchmark row ${index + 1} is missing kpi_name.`);
    }
    if (!Number.isFinite(expected_value)) {
      throw new Error(`Benchmark row ${index + 1} must include a numeric expected_value.`);
    }
    return {
      kpi_name,
      expected_value,
      dimension_name: row.dimension_name ? String(row.dimension_name) : undefined,
      dimension_value:
        row.dimension_value === undefined || row.dimension_value === null
          ? undefined
          : (row.dimension_value as string | number),
      label: row.label ? String(row.label) : undefined,
      start_date: row.start_date ? String(row.start_date) : undefined,
      end_date: row.end_date ? String(row.end_date) : undefined,
    };
  });
}

function statusTone(status: string): "default" | "success" | "warning" | "danger" {
  if (["matched", "pass", "governance_updated", "created_from_import_definition", "promoted_from_calculated_field"].includes(status)) {
    return "success";
  }
  if (["promote", "review", "pending", "blocked_by_review"].includes(status)) return "warning";
  if (["unmatched", "fail", "skipped", "blocked"].includes(status)) return "danger";
  return "default";
}

function prettyStatus(status: string): string {
  return status.replace(/_/g, " ");
}

function formatNumber(value?: number | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "-";
  }
  return value.toFixed(2);
}

function formatPercent(value?: number | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "-";
  }
  return `${(value * 100).toFixed(2)}%`;
}

export default function MigrationPage() {
  const [selectedModelId, setSelectedModelId] = useState("");
  const [sourceTool, setSourceTool] = useState("power_bi");
  const [dashboardNames, setDashboardNames] = useState("Executive Finance Scorecard\nRegional Revenue Review");
  const [reportNames, setReportNames] = useState("Monthly Board Pack");
  const [kpiNames, setKpiNames] = useState("Revenue\nCost\nGross Margin");
  const [dimensionNames, setDimensionNames] = useState("Region\nDate");
  const [benchmarkJson, setBenchmarkJson] = useState(benchmarkPlaceholder);
  const [notes, setNotes] = useState("Need a governed replacement for the incumbent leadership reporting flow.");
  const [emailTo, setEmailTo] = useState("leadership@example.com");
  const [pageError, setPageError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<MigrationAnalysis | null>(null);
  const [bootstrapResult, setBootstrapResult] = useState<MigrationBootstrapResponse | null>(null);
  const [importedBundle, setImportedBundle] = useState<ImportedWorkbookBundle | null>(null);
  const [selectedImportedKpis, setSelectedImportedKpis] = useState<string[]>([]);
  const [ownerName, setOwnerName] = useState("Business Systems Team");
  const [certificationStatus, setCertificationStatus] = useState<CertificationStatus>("review");
  const [promotionResult, setPromotionResult] = useState<MigrationPromoteResponse | null>(null);
  const [reviewResult, setReviewResult] = useState<MigrationReviewResponse | null>(null);

  const semanticModelsQuery = useQuery({
    queryKey: ["migration", "semantic-models"],
    queryFn: () => apiRequest<SemanticModel[]>("/api/v1/semantic/models"),
  });

  useEffect(() => {
    if (!selectedModelId && semanticModelsQuery.data?.[0]) {
      setSelectedModelId(semanticModelsQuery.data[0].id);
    }
  }, [selectedModelId, semanticModelsQuery.data]);

  const buildPayload = useMemo(
    () => () => ({
      source_tool: sourceTool,
      semantic_model_id: selectedModelId,
      dashboard_names: parseList(dashboardNames),
      report_names: parseList(reportNames),
      kpi_names: parseList(kpiNames),
      dimension_names: parseList(dimensionNames),
      benchmark_rows: parseBenchmarkRows(benchmarkJson),
      notes,
    }),
    [benchmarkJson, dashboardNames, dimensionNames, kpiNames, notes, reportNames, selectedModelId, sourceTool],
  );

  const importMutation = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return apiRequest<ImportedWorkbookBundle>(
        `/api/v1/onboarding/migration-assistant/import-workbook?source_tool=${encodeURIComponent(sourceTool)}`,
        { method: "POST", body: form },
      );
    },
    onSuccess: (result) => {
      setPageError(null);
      setImportedBundle(result);
      setPromotionResult(null);
      setAnalysis(null);
      setBootstrapResult(null);
      setReviewResult(null);
      setSourceTool(result.source_tool);
      setDashboardNames(result.dashboard_names.join("\n"));
      setReportNames(result.report_names.join("\n"));
      setKpiNames(result.kpi_names.join("\n"));
      setDimensionNames(result.dimension_names.join("\n"));
      setNotes(result.notes ?? "");
      setSelectedImportedKpis(result.kpi_definitions.map((item) => item.source_name));
      setBenchmarkJson(result.benchmark_rows.length ? JSON.stringify(result.benchmark_rows, null, 2) : "");
    },
    onError: (error) => setPageError(error instanceof Error ? error.message : "Failed to import workbook bundle"),
  });

  const analyzeMutation = useMutation({
    mutationFn: () =>
      apiRequest<MigrationAnalysis>("/api/v1/onboarding/migration-assistant/analyze", {
        method: "POST",
        body: JSON.stringify(buildPayload()),
      }),
    onSuccess: (result) => {
      setPageError(null);
      setAnalysis(result);
      setBootstrapResult(null);
      setReviewResult(null);
    },
    onError: (error) => setPageError(error instanceof Error ? error.message : "Failed to analyze migration bundle"),
  });

  const bootstrapMutation = useMutation({
    mutationFn: () =>
      apiRequest<MigrationBootstrapResponse>("/api/v1/onboarding/migration-assistant/bootstrap", {
        method: "POST",
        body: JSON.stringify({
          ...buildPayload(),
          email_to: parseList(emailTo),
          create_schedule: true,
          dashboard_name_override: analysis ? `${analysis.primary_asset_title} Migration Pack` : undefined,
        }),
      }),
    onSuccess: (result) => {
      setPageError(null);
      setBootstrapResult(result);
      setAnalysis(result.analysis);
    },
    onError: (error) => setPageError(error instanceof Error ? error.message : "Failed to bootstrap migration pack"),
  });

  const reviewMutation = useMutation({
    mutationFn: () => {
      if (!importedBundle) {
        throw new Error("Import a workbook first.");
      }
      return apiRequest<MigrationReviewResponse>("/api/v1/onboarding/migration-assistant/review-kpis", {
        method: "POST",
        body: JSON.stringify({
          semantic_model_id: selectedModelId,
          source_tool: importedBundle.source_tool,
          selected_source_names: selectedImportedKpis,
          imported_kpis: importedBundle.kpi_definitions,
          benchmark_rows: parseBenchmarkRows(benchmarkJson),
          owner_name: ownerName || undefined,
          certification_status: certificationStatus,
          notes: importedBundle.notes ?? notes,
        }),
      });
    },
    onSuccess: (result) => {
      setPageError(null);
      setReviewResult(result);
      setPromotionResult(null);
    },
    onError: (error) => setPageError(error instanceof Error ? error.message : "Failed to build certification review"),
  });
  const promoteMutation = useMutation({
    mutationFn: () => {
      if (!importedBundle) {
        throw new Error("Import a workbook first.");
      }
      return apiRequest<MigrationPromoteResponse>("/api/v1/onboarding/migration-assistant/promote-kpis", {
        method: "POST",
        body: JSON.stringify({
          semantic_model_id: selectedModelId,
          source_tool: importedBundle.source_tool,
          selected_source_names: selectedImportedKpis,
          imported_kpis: importedBundle.kpi_definitions,
          owner_name: ownerName || undefined,
          certification_status: certificationStatus,
          notes: importedBundle.notes ?? notes,
          review_items: (reviewResult?.items ?? []).map((item) => ({
            source_name: item.source_name,
            proposed_owner_name: item.proposed_owner_name,
            proposed_certification_status: item.proposed_certification_status,
            suggested_synonyms: item.suggested_synonyms,
            certification_note: item.certification_note,
            readiness_status: item.readiness_status,
            blockers: item.blockers,
            lineage_preview: item.lineage_preview,
          })),
        }),
      });
    },
    onSuccess: (result) => {
      setPageError(null);
      setPromotionResult(result);
    },
    onError: (error) => setPageError(error instanceof Error ? error.message : "Failed to promote imported KPIs"),
  });

  const importedSelectionCount = selectedImportedKpis.length;

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">Migration Assistant</h2>
        <p className="text-sm text-slate-500">
          Import incumbent BI workbooks, map dashboards and KPIs into the governed semantic layer, run automated trust comparisons
          against benchmark exports, then bootstrap or promote a governed executive reporting replacement without rebuilding everything manually.
        </p>
      </div>

      <Card className="border-slate-900 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 text-white">
        <CardHeader>
          <CardTitle>Incumbent BI to governed executive pack</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <select
              className="rounded-md border border-white/15 bg-white/5 px-3 py-2 text-sm text-white"
              value={sourceTool}
              onChange={(event) => setSourceTool(event.target.value)}
            >
              <option value="power_bi" className="text-slate-900">Power BI</option>
              <option value="tableau" className="text-slate-900">Tableau</option>
              <option value="domo" className="text-slate-900">Domo</option>
              <option value="generic" className="text-slate-900">Generic BI export</option>
            </select>
            <select
              className="rounded-md border border-white/15 bg-white/5 px-3 py-2 text-sm text-white"
              value={selectedModelId}
              onChange={(event) => setSelectedModelId(event.target.value)}
            >
              <option value="" className="text-slate-900">Select semantic model</option>
              {(semanticModelsQuery.data ?? []).map((model) => (
                <option key={model.id} value={model.id} className="text-slate-900">
                  {model.name}
                </option>
              ))}
            </select>
            <Input
              value={emailTo}
              onChange={(event) => setEmailTo(event.target.value)}
              placeholder="leadership@example.com"
              className="bg-white text-slate-900"
            />
            <Input
              type="file"
              accept=".twb,.twbx,.json,.pbip,.pbit"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (!file) {
                  return;
                }
                importMutation.mutate(file);
                event.currentTarget.value = "";
              }}
              className="bg-white text-slate-900 file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:text-white"
            />
          </div>

          <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
            <Button onClick={() => analyzeMutation.mutate()} disabled={analyzeMutation.isPending || !selectedModelId}>
              {analyzeMutation.isPending ? "Analyzing..." : "Analyze bundle"}
            </Button>
            <Button variant="secondary" onClick={() => bootstrapMutation.mutate()} disabled={bootstrapMutation.isPending || !selectedModelId}>
              {bootstrapMutation.isPending ? "Bootstrapping..." : "Bootstrap pack"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => reviewMutation.mutate()}
              disabled={reviewMutation.isPending || !selectedModelId || !importedBundle || importedSelectionCount === 0}
            >
              {reviewMutation.isPending ? "Reviewing..." : "Build certification review"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => promoteMutation.mutate()}
              disabled={promoteMutation.isPending || !selectedModelId || !importedBundle || importedSelectionCount === 0 || (reviewResult?.summary.blocked_count ?? 0) > 0}
            >
              {promoteMutation.isPending ? "Promoting..." : "Promote KPIs"}
            </Button>
            <Input
              value={ownerName}
              onChange={(event) => setOwnerName(event.target.value)}
              placeholder="Owner name"
              className="bg-white text-slate-900"
            />
            <select
              className="rounded-md border border-white/15 bg-white/5 px-3 py-2 text-sm text-white"
              value={certificationStatus}
              onChange={(event) => setCertificationStatus(event.target.value as CertificationStatus)}
            >
              <option value="draft" className="text-slate-900">Draft</option>
              <option value="review" className="text-slate-900">Review</option>
              <option value="certified" className="text-slate-900">Certified</option>
              <option value="deprecated" className="text-slate-900">Deprecated</option>
            </select>
          </div>

          {semanticModelsQuery.isLoading ? (
            <div className="grid gap-3 md:grid-cols-3">
              <Skeleton className="h-32 bg-white/10" />
              <Skeleton className="h-32 bg-white/10" />
              <Skeleton className="h-32 bg-white/10" />
            </div>
          ) : null}

          <div className="grid gap-3 md:grid-cols-2">
            <Textarea value={dashboardNames} onChange={(event) => setDashboardNames(event.target.value)} placeholder="Dashboard names, one per line" className="min-h-28 bg-white text-slate-900" />
            <Textarea value={reportNames} onChange={(event) => setReportNames(event.target.value)} placeholder="Report or pack names, one per line" className="min-h-28 bg-white text-slate-900" />
            <Textarea value={kpiNames} onChange={(event) => setKpiNames(event.target.value)} placeholder="KPI names, one per line" className="min-h-32 bg-white text-slate-900" />
            <Textarea value={dimensionNames} onChange={(event) => setDimensionNames(event.target.value)} placeholder="Dimension names, one per line" className="min-h-32 bg-white text-slate-900" />
          </div>
          <Textarea value={benchmarkJson} onChange={(event) => setBenchmarkJson(event.target.value)} placeholder={benchmarkPlaceholder} className="min-h-48 bg-white font-mono text-slate-900" />
          <Textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Migration context, filters, governance notes, or stakeholder expectations" className="min-h-24 bg-white text-slate-900" />

          {!semanticModelsQuery.isLoading && !semanticModelsQuery.data?.length ? (
            <p className="text-sm text-amber-200">Create a semantic model first. The migration assistant only maps incumbent assets into governed metrics and dimensions.</p>
          ) : null}
          {pageError ? <p className="text-sm text-rose-200">{pageError}</p> : null}
        </CardContent>
      </Card>

      {importedBundle ? (
        <Card>
          <CardHeader>
            <CardTitle>Imported Workbook</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
              <Badge tone="default">{importedBundle.source_tool.replace(/_/g, " ")}</Badge>
              <span>{importedBundle.workbook_name}</span>
              <Badge tone="success">Dashboards {importedBundle.dashboard_names.length}</Badge>
              <Badge tone="success">Reports {importedBundle.report_names.length}</Badge>
              <Badge tone="success">KPIs {importedBundle.kpi_definitions.length}</Badge>
              <Badge tone="default">Dimensions {importedBundle.dimension_names.length}</Badge>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">Imported assets</p>
                <div className="mt-3 space-y-3 text-sm text-slate-700">
                  <div>
                    <p className="font-medium text-slate-800">Dashboards</p>
                    <p>{importedBundle.dashboard_names.join(", ") || "-"}</p>
                  </div>
                  <div>
                    <p className="font-medium text-slate-800">Reports</p>
                    <p>{importedBundle.report_names.join(", ") || "-"}</p>
                  </div>
                  <div>
                    <p className="font-medium text-slate-800">Dimensions</p>
                    <p>{importedBundle.dimension_names.join(", ") || "-"}</p>
                  </div>
                </div>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Imported KPI definitions</p>
                  <Badge tone={importedSelectionCount ? "success" : "warning"}>{importedSelectionCount} selected</Badge>
                </div>
                <div className="mt-3 max-h-72 space-y-2 overflow-y-auto">
                  {importedBundle.kpi_definitions.length ? importedBundle.kpi_definitions.map((item) => {
                    const checked = selectedImportedKpis.includes(item.source_name);
                    return (
                      <label key={item.source_name} className="flex gap-3 rounded-lg border border-slate-200 bg-white p-3">
                        <input
                          type="checkbox"
                          className="mt-1 h-4 w-4 rounded border-slate-300"
                          checked={checked}
                          onChange={(event) => {
                            setSelectedImportedKpis((current) => {
                              if (event.target.checked) {
                                return current.includes(item.source_name) ? current : [...current, item.source_name];
                              }
                              return current.filter((value) => value !== item.source_name);
                            });
                          }}
                        />
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm font-medium text-slate-800">{item.label ?? item.source_name}</p>
                            <Badge tone="default">{item.aggregation}</Badge>
                            {item.value_format ? <Badge tone="default">{item.value_format}</Badge> : null}
                          </div>
                          <p className="mt-1 text-xs text-slate-500">Source name: {item.source_name}</p>
                          <p className="mt-1 text-xs text-slate-500">Formula: {item.formula ?? "No explicit workbook formula"}</p>
                          {item.description ? <p className="mt-1 text-xs text-slate-500">{item.description}</p> : null}
                        </div>
                      </label>
                    );
                  }) : <p className="text-sm text-slate-500">The imported workbook did not expose KPI definitions that can be promoted.</p>}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {reviewResult ? (
        <Card>
          <CardHeader>
            <CardTitle>Certification Review</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
              <Badge tone="success">Ready {reviewResult.summary.ready_count}</Badge>
              <Badge tone="warning">Review {reviewResult.summary.review_count}</Badge>
              <Badge tone={reviewResult.summary.blocked_count ? "danger" : "default"}>Blocked {reviewResult.summary.blocked_count}</Badge>
              <Badge tone={reviewResult.summary.benchmark_fail_count ? "danger" : "success"}>Benchmark fails {reviewResult.summary.benchmark_fail_count}</Badge>
            </div>
            <div className="space-y-3">
              {reviewResult.items.map((item) => (
                <div key={item.source_name} className="rounded-xl border border-slate-200 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-sm font-medium text-slate-800">{item.label}</p>
                      <p className="mt-1 text-xs text-slate-500">{item.source_name}{item.target_label ? ` -> ${item.target_label}` : ""}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Badge tone={statusTone(item.readiness_status)}>{prettyStatus(item.readiness_status)}</Badge>
                      <Badge tone="default">Score {item.readiness_score}</Badge>
                      <Badge tone="default">{prettyStatus(item.recommended_action)}</Badge>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-600">
                    <Badge tone="success">Pass {item.benchmark_evidence.pass_count}</Badge>
                    <Badge tone="warning">Review {item.benchmark_evidence.review_count}</Badge>
                    <Badge tone={item.benchmark_evidence.fail_count ? "danger" : "default"}>Fail {item.benchmark_evidence.fail_count}</Badge>
                    <Badge tone="default">Pending {item.benchmark_evidence.pending_count}</Badge>
                    <Badge tone="default">Owner {item.proposed_owner_name ?? "Unassigned"}</Badge>
                    <Badge tone="default">Status {prettyStatus(item.proposed_certification_status)}</Badge>
                  </div>
                  {item.blockers.length ? (
                    <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-3">
                      <p className="text-xs uppercase tracking-wide text-rose-700">Blockers</p>
                      <ul className="mt-2 space-y-1 text-sm text-rose-900">
                        {item.blockers.map((blocker) => (
                          <li key={blocker}>{blocker}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  <div className="mt-3 grid gap-4 md:grid-cols-2">
                    <div>
                      <p className="text-xs uppercase tracking-wide text-slate-500">Review guidance</p>
                      <ul className="mt-2 space-y-1 text-sm text-slate-700">
                        {item.review_notes.map((note) => (
                          <li key={note}>{note}</li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-wide text-slate-500">Suggested synonyms</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {item.suggested_synonyms.map((synonym) => (
                          <Badge key={synonym} tone="default">{synonym}</Badge>
                        ))}
                      </div>
                      {item.certification_note ? <p className="mt-3 text-sm text-slate-600">{item.certification_note}</p> : null}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {promotionResult ? (
        <Card>
          <CardHeader>
            <CardTitle>Bulk KPI Promotion</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
              <Badge tone="success">Promoted {promotionResult.promoted_count}</Badge>
              <span>
                New semantic model version: <Link href="/semantic" className="font-medium text-brand-600">{promotionResult.semantic_model.name} v{promotionResult.semantic_model.version}</Link>
              </span>
            </div>
            <div className="space-y-3">
              {promotionResult.results.map((item) => (
                <div key={item.source_name} className="rounded-lg border border-slate-200 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-medium text-slate-800">{item.source_name}</p>
                    <Badge tone={statusTone(item.status)}>{prettyStatus(item.status)}</Badge>
                  </div>
                  <p className="mt-1 text-sm text-slate-600">{item.target_label ?? item.target_name ?? "No governed target"}</p>
                  <p className="mt-1 text-xs text-slate-500">Owner {item.owner_name ?? "Unassigned"} | Status {prettyStatus(item.certification_status)}</p>
                  <p className="mt-1 text-xs text-slate-500">{item.rationale}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {analysis ? (
        <Card>
          <CardHeader>
            <CardTitle>Migration Analysis</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
              <span>Recommended pack:</span>
              <Badge tone="success">{analysis.recommended_launch_pack_title ?? "No pack"}</Badge>
              <Badge tone="default">Matched KPIs {analysis.coverage.matched_kpis}/{analysis.coverage.total_kpis}</Badge>
              <Badge tone={analysis.coverage.unmatched_assets ? "warning" : "success"}>Unmatched assets {analysis.coverage.unmatched_assets}</Badge>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">Dashboard mapping</p>
                <div className="mt-3 space-y-3">
                  {analysis.dashboard_matches.length ? analysis.dashboard_matches.map((item) => (
                    <div key={item.source_name} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                      <p className="text-sm font-medium text-slate-800">{item.source_name}</p>
                      <p className="mt-1 text-xs text-slate-500">{item.recommended_dashboard_name}</p>
                      <p className="mt-2 text-sm text-slate-700">{item.suggested_goal}</p>
                    </div>
                  )) : <p className="text-sm text-slate-500">No dashboard titles provided.</p>}
                </div>
              </div>
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">Report mapping</p>
                <div className="mt-3 space-y-3">
                  {analysis.report_matches.length ? analysis.report_matches.map((item) => (
                    <div key={item.source_name} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                      <p className="text-sm font-medium text-slate-800">{item.source_name}</p>
                      <p className="mt-1 text-xs text-slate-500">{item.recommended_launch_pack_title}</p>
                      <p className="mt-2 text-sm text-slate-700">{item.rationale}</p>
                    </div>
                  )) : <p className="text-sm text-slate-500">No report titles provided.</p>}
                </div>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">KPI matches</p>
                <div className="mt-3 space-y-2">
                  {analysis.kpi_matches.map((match) => (
                    <div key={match.source_name} className="rounded-lg border border-slate-200 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-medium text-slate-800">{match.source_name}</p>
                        <Badge tone={statusTone(match.status)}>{prettyStatus(match.status)}</Badge>
                      </div>
                      <p className="mt-1 text-sm text-slate-600">{match.target_label ?? "No governed match"}</p>
                      <p className="mt-1 text-xs text-slate-500">Score {match.score.toFixed(2)} | {match.rationale}</p>
                    </div>
                  ))}
                </div>
              </div>
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">Dimension matches</p>
                <div className="mt-3 space-y-2">
                  {analysis.dimension_matches.length ? analysis.dimension_matches.map((match) => (
                    <div key={match.source_name} className="rounded-lg border border-slate-200 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-medium text-slate-800">{match.source_name}</p>
                        <Badge tone={statusTone(match.status)}>{prettyStatus(match.status)}</Badge>
                      </div>
                      <p className="mt-1 text-sm text-slate-600">{match.target_label ?? "No governed match"}</p>
                      <p className="mt-1 text-xs text-slate-500">Score {match.score.toFixed(2)} | {match.rationale}</p>
                    </div>
                  )) : <p className="text-sm text-slate-500">No dimension names provided.</p>}
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs uppercase tracking-wide text-slate-500">Automated trust comparison</p>
                <div className="flex flex-wrap gap-2 text-xs">
                  <Badge tone="success">Pass {analysis.automated_trust_comparison.summary.pass_count}</Badge>
                  <Badge tone="warning">Review {analysis.automated_trust_comparison.summary.review_count}</Badge>
                  <Badge tone="danger">Fail {analysis.automated_trust_comparison.summary.fail_count}</Badge>
                  <Badge tone="default">Pending {analysis.automated_trust_comparison.summary.pending_count}</Badge>
                </div>
              </div>
              {analysis.automated_trust_comparison.rows.length ? (
                <div className="mt-3 space-y-3">
                  {analysis.automated_trust_comparison.rows.map((row) => (
                    <div key={`${row.label}:${row.source_name}:${row.dimension_name ?? "topline"}`} className="rounded-lg border border-slate-200 bg-white p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-medium text-slate-800">{row.label}</p>
                        <Badge tone={statusTone(row.status)}>{prettyStatus(row.status)}</Badge>
                      </div>
                      <p className="mt-1 text-sm text-slate-600">
                        {row.target_label ?? "No governed target"}
                        {row.dimension_name ? ` by ${row.dimension_name}` : ""}
                        {row.dimension_value !== undefined && row.dimension_value !== null ? ` = ${row.dimension_value}` : ""}
                      </p>
                      <p className="mt-2 text-sm text-slate-700">Expected {formatNumber(row.expected_value)} | Governed {formatNumber(row.governed_value)}</p>
                      <p className="mt-1 text-xs text-slate-500">Variance {formatNumber(row.variance)} | {formatPercent(row.variance_pct)}</p>
                      <p className="mt-1 text-xs text-slate-500">{row.rationale}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-3 text-sm text-slate-500">Provide benchmark export rows to compare incumbent values to governed KPI outputs automatically.</p>
              )}
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500">Trust validation plan</p>
              <ul className="mt-3 space-y-2 text-sm text-slate-700">
                {analysis.trust_validation_checks.map((check) => (
                  <li key={check}>{check}</li>
                ))}
              </ul>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {bootstrapResult ? (
        <Card>
          <CardHeader>
            <CardTitle>Bootstrapped Migration Pack</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
              <span>Dashboard: <Link href={`/dashboards/${bootstrapResult.provisioned_pack.dashboard_id}`} className="font-medium text-brand-600">{bootstrapResult.provisioned_pack.dashboard_name}</Link></span>
              <span>Widgets: {bootstrapResult.provisioned_pack.widgets_added}</span>
              <Badge tone="default">{bootstrapResult.provisioned_pack.report_pack.report_type.replace(/_/g, " ")}</Badge>
              {bootstrapResult.provisioned_pack.report_schedule_name ? <span>Schedule: {bootstrapResult.provisioned_pack.report_schedule_name}</span> : null}
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500">Executive summary</p>
              <p className="mt-2 text-sm text-slate-700">{bootstrapResult.provisioned_pack.report_pack.executive_summary}</p>
              <div className="mt-3 pt-3 border-t border-slate-200">
                <FeedbackButton artifactType="dashboard_report" artifactId={bootstrapResult.provisioned_pack.dashboard_id} />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">Operating views</p>
                <ul className="mt-3 space-y-2 text-sm text-slate-700">
                  {bootstrapResult.provisioned_pack.report_pack.operating_views.map((view) => (
                    <li key={view}>{view}</li>
                  ))}
                </ul>
              </div>
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">Suggested next actions</p>
                <ul className="mt-3 space-y-2 text-sm text-slate-700">
                  {bootstrapResult.provisioned_pack.report_pack.next_actions.map((action) => (
                    <li key={action}>{action}</li>
                  ))}
                </ul>
              </div>
            </div>
            {bootstrapResult.provisioned_pack.report_pack.exception_report ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                <p className="text-xs uppercase tracking-wide text-amber-700">Exception report</p>
                <p className="mt-2 text-sm font-medium text-amber-900">{bootstrapResult.provisioned_pack.report_pack.exception_report.title}</p>
                <p className="mt-2 text-sm text-amber-900">{bootstrapResult.provisioned_pack.report_pack.exception_report.body}</p>
              </div>
            ) : null}
            <div className="rounded-xl border border-slate-200 p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500">Suggested alert watchlist</p>
              <ul className="mt-3 space-y-2 text-sm text-slate-700">
                {bootstrapResult.provisioned_pack.suggested_alerts.map((alert) => (
                  <li key={alert.metric_id}>{alert.metric_label}: {alert.reason}</li>
                ))}
              </ul>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {!analysis && !importedBundle && !semanticModelsQuery.isLoading ? (
        <EmptyState>
          <EmptyStateTitle>No migration analysis yet</EmptyStateTitle>
          <EmptyStateBody>Import an incumbent workbook or analyze a bundle to get KPI mappings, trust checks, benchmark variance results, and a governed migration-pack recommendation.</EmptyStateBody>
        </EmptyState>
      ) : null}
    </section>
  );
}







