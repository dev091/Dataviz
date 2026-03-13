"use client";

import { useEffect, useState } from "react";
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
  Skeleton,
} from "@/components/ui";

import { apiRequest } from "@/lib/api";
import { FeedbackButton } from "@/components/feedback-button";

type DatasetField = {
  id: string;
  name: string;
  data_type: string;
  is_dimension: boolean;
  is_metric: boolean;
};

type FieldProfile = {
  name: string;
  data_type: string;
  null_count: number;
  null_ratio: number;
  distinct_count: number;
  unique_ratio: number;
  sample_values: string[];
  warnings: string[];
};

type QualityProfile = {
  overall_score: number;
  status: string;
  duplicate_rows: number;
  duplicate_ratio: number;
  completeness_score: number;
  duplicate_score: number;
  cleaning_score: number;
  cleaning: {
    rows_before?: number;
    rows_after?: number;
    rows_dropped?: number;
    renamed_columns?: Record<string, string>;
    unnamed_columns_removed?: string[];
  };
  warnings: string[];
  field_profiles: FieldProfile[];
};

type Dataset = {
  id: string;
  name: string;
  source_table: string;
  physical_table: string;
  row_count: number;
  quality_status: string;
  quality_profile: QualityProfile;
  fields: DatasetField[];
};

type PrepFeedbackSummary = {
  approved: number;
  rejected: number;
};

type PrepPlanStep = {
  step_id: string;
  title: string;
  step_type: string;
  target_fields: string[];
  explanation: string;
  reversible: boolean;
  revert_strategy: string;
  sql_preview?: string | null;
  confidence: number;
  feedback: PrepFeedbackSummary;
  applied: boolean;
  applied_at?: string | null;
};

type PrepJoinSuggestion = {
  target_dataset_id: string;
  target_dataset_name: string;
  left_field: string;
  right_field: string;
  score: number;
  rationale: string;
};

type PrepUnionSuggestion = {
  target_dataset_id: string;
  target_dataset_name: string;
  shared_fields: string[];
  score: number;
  rationale: string;
};

type PrepCalculatedFieldSuggestion = {
  name: string;
  expression: string;
  data_type: string;
  rationale: string;
};

type PrepTransformationLineageItem = {
  source: string;
  description: string;
  affected_fields: string[];
  status?: string | null;
  recorded_at?: string | null;
};

type DataPrepPlan = {
  dataset_id: string;
  dataset_name: string;
  dataset_quality_status: string;
  generated_at: string;
  cleaning_steps: PrepPlanStep[];
  join_suggestions: PrepJoinSuggestion[];
  union_suggestions: PrepUnionSuggestion[];
  calculated_field_suggestions: PrepCalculatedFieldSuggestion[];
  transformation_lineage: PrepTransformationLineageItem[];
  notes: string[];
};

type FeedbackPayload = {
  datasetId: string;
  stepId: string;
  decision: "approve" | "reject";
};

type PrepActionPayload = {
  datasetId: string;
  stepId: string;
  action: "apply" | "rollback";
};

function toneForQuality(status: string): "default" | "success" | "warning" | "danger" {
  if (status === "excellent" || status === "good") return "success";
  if (status === "warning") return "warning";
  if (status === "critical") return "danger";
  return "default";
}

function toneForConfidence(score: number): "default" | "success" | "warning" | "danger" {
  if (score >= 0.85) return "success";
  if (score >= 0.65) return "warning";
  if (score < 0.45) return "danger";
  return "default";
}

export default function DatasetsPage() {
  const queryClient = useQueryClient();
  const [activeDatasetId, setActiveDatasetId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const datasetsQuery = useQuery({
    queryKey: ["datasets"],
    queryFn: () => apiRequest<Dataset[]>("/api/v1/semantic/datasets"),
  });

  useEffect(() => {
    if (!activeDatasetId && datasetsQuery.data?.[0]?.id) {
      setActiveDatasetId(datasetsQuery.data[0].id);
    }
  }, [activeDatasetId, datasetsQuery.data]);

  const prepPlanQuery = useQuery({
    queryKey: ["dataset-prep-plan", activeDatasetId],
    queryFn: () => apiRequest<DataPrepPlan>(`/api/v1/semantic/datasets/${activeDatasetId}/prep-plan`),
    enabled: Boolean(activeDatasetId),
  });

  const feedbackMutation = useMutation({
    mutationFn: ({ datasetId, stepId, decision }: FeedbackPayload) =>
      apiRequest<{ note: string }>(`/api/v1/semantic/datasets/${datasetId}/prep-feedback`, {
        method: "POST",
        body: JSON.stringify({ step_id: stepId, decision }),
      }),
    onSuccess: async (payload, variables) => {
      setError(null);
      setNotice(payload.note);
      await queryClient.invalidateQueries({ queryKey: ["dataset-prep-plan", variables.datasetId] });
    },
    onError: (mutationError) => {
      setNotice(null);
      setError(mutationError instanceof Error ? mutationError.message : "Failed to capture feedback");
    },
  });

  const prepActionMutation = useMutation({
    mutationFn: ({ datasetId, stepId, action }: PrepActionPayload) =>
      apiRequest<{ note: string }>(`/api/v1/semantic/datasets/${datasetId}/prep-actions`, {
        method: "POST",
        body: JSON.stringify({ step_id: stepId, action }),
      }),
    onSuccess: async (payload, variables) => {
      setError(null);
      setNotice(payload.note);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["dataset-prep-plan", variables.datasetId] }),
        queryClient.invalidateQueries({ queryKey: ["datasets"] }),
      ]);
    },
    onError: (mutationError) => {
      setNotice(null);
      setError(mutationError instanceof Error ? mutationError.message : "Failed to update prep step state");
    },
  });

  const activePlan = prepPlanQuery.data;

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">Dataset Catalog</h2>
        <p className="text-sm text-slate-500">
          Governed datasets discovered through connectors and sync runs, now scored for quality, cleaning impact, field reliability,
          and AI-guided prep actions.
        </p>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {notice ? <p className="text-sm text-emerald-700">{notice}</p> : null}
      {datasetsQuery.error ? (
        <p className="text-sm text-red-600">{datasetsQuery.error instanceof Error ? datasetsQuery.error.message : "Failed to load datasets"}</p>
      ) : null}

      {datasetsQuery.isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      ) : null}

      <div className="space-y-3">
        {(datasetsQuery.data ?? []).map((dataset) => {
          const quality = dataset.quality_profile;
          const isActive = dataset.id === activeDatasetId;
          return (
            <Card key={dataset.id}>
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <CardTitle>{dataset.name}</CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge tone={toneForQuality(dataset.quality_status)}>{dataset.quality_status}</Badge>
                    <Badge tone="default">Score {quality?.overall_score ?? "-"}</Badge>
                    <Badge tone="default">{dataset.fields.length} fields</Badge>
                    <Button type="button" variant={isActive ? "secondary" : "default"} size="sm" onClick={() => setActiveDatasetId(dataset.id)}>
                      {isActive ? "Viewing Autopilot Plan" : "Open Autopilot Plan"}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-4 text-xs text-slate-500">
                  <span>Source: {dataset.source_table}</span>
                  <span>Rows: {dataset.row_count}</span>
                  <span>Warehouse table: {dataset.physical_table}</span>
                  <span>Duplicates: {quality?.duplicate_rows ?? 0}</span>
                  <span>Completeness: {quality?.completeness_score ?? 0}</span>
                </div>

                {quality ? (
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                      <p className="text-xs uppercase tracking-wide text-slate-500">Overall Score</p>
                      <p className="mt-1 text-2xl font-semibold text-slate-900">{quality.overall_score}</p>
                      <p className="text-xs text-slate-500">Status: {quality.status}</p>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                      <p className="text-xs uppercase tracking-wide text-slate-500">Cleaning Impact</p>
                      <p className="mt-1 text-2xl font-semibold text-slate-900">{quality.cleaning_score}</p>
                      <p className="text-xs text-slate-500">Dropped rows: {quality.cleaning?.rows_dropped ?? 0}</p>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                      <p className="text-xs uppercase tracking-wide text-slate-500">Duplicate Score</p>
                      <p className="mt-1 text-2xl font-semibold text-slate-900">{quality.duplicate_score}</p>
                      <p className="text-xs text-slate-500">Duplicate ratio: {(quality.duplicate_ratio * 100).toFixed(1)}%</p>
                    </div>
                  </div>
                ) : null}

                {quality?.warnings?.length ? (
                  <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-3 text-sm text-amber-900">
                    <p className="font-medium">Quality warnings</p>
                    <ul className="mt-2 space-y-1">
                      {quality.warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                <div className="overflow-x-auto rounded-xl border border-slate-200">
                  <table className="min-w-full text-sm">
                    <thead className="bg-slate-50">
                      <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                        <th className="px-3 py-3">Field</th>
                        <th className="px-3 py-3">Type</th>
                        <th className="px-3 py-3">Dimension</th>
                        <th className="px-3 py-3">Metric</th>
                        <th className="px-3 py-3">Null %</th>
                        <th className="px-3 py-3">Distinct</th>
                        <th className="px-3 py-3">Samples</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dataset.fields.map((field) => {
                        const fieldProfile = quality?.field_profiles?.find((item) => item.name === field.name);
                        return (
                          <tr key={field.id} className="border-t border-slate-100 align-top">
                            <td className="px-3 py-3 font-medium text-slate-900">
                              {field.name}
                              {fieldProfile?.warnings?.length ? <p className="mt-1 text-xs text-amber-700">{fieldProfile.warnings.join(" ")}</p> : null}
                            </td>
                            <td className="px-3 py-3 text-slate-600">{field.data_type}</td>
                            <td className="px-3 py-3">{field.is_dimension ? <Badge tone="success">yes</Badge> : <Badge>no</Badge>}</td>
                            <td className="px-3 py-3">{field.is_metric ? <Badge tone="success">yes</Badge> : <Badge>no</Badge>}</td>
                            <td className="px-3 py-3 text-slate-600">{fieldProfile ? `${(fieldProfile.null_ratio * 100).toFixed(1)}%` : "-"}</td>
                            <td className="px-3 py-3 text-slate-600">{fieldProfile?.distinct_count ?? "-"}</td>
                            <td className="px-3 py-3 text-slate-600">{fieldProfile?.sample_values?.join(", ") || "-"}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {activeDatasetId ? (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle>AI Data Prep Autopilot</CardTitle>
                <p className="text-sm text-slate-500">
                  Review reversible cleaning plans, join and union suggestions, calculated fields, and transformation lineage for the selected dataset.
                </p>
              </div>
              {activePlan ? (
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <Badge tone={toneForQuality(activePlan.dataset_quality_status)}>{activePlan.dataset_quality_status}</Badge>
                  <span>Generated {new Date(activePlan.generated_at).toLocaleString()}</span>
                </div>
              ) : null}
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            {activePlan ? (
              <div className="mb-2">
                <FeedbackButton artifactType="data_prep" artifactId={activePlan.dataset_id} />
              </div>
            ) : null}
            {prepPlanQuery.isLoading ? <Skeleton className="h-64" /> : null}
            {prepPlanQuery.error ? (
              <p className="text-sm text-red-600">{prepPlanQuery.error instanceof Error ? prepPlanQuery.error.message : "Failed to load prep plan"}</p>
            ) : null}

            {activePlan ? (
              <>
                <div className="grid gap-3 md:grid-cols-4">
                  <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                    <p className="text-xs uppercase tracking-wide text-slate-500">Cleaning Steps</p>
                    <p className="mt-1 text-2xl font-semibold text-slate-900">{activePlan.cleaning_steps.length}</p>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                    <p className="text-xs uppercase tracking-wide text-slate-500">Join Suggestions</p>
                    <p className="mt-1 text-2xl font-semibold text-slate-900">{activePlan.join_suggestions.length}</p>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                    <p className="text-xs uppercase tracking-wide text-slate-500">Union Suggestions</p>
                    <p className="mt-1 text-2xl font-semibold text-slate-900">{activePlan.union_suggestions.length}</p>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                    <p className="text-xs uppercase tracking-wide text-slate-500">Calculated Fields</p>
                    <p className="mt-1 text-2xl font-semibold text-slate-900">{activePlan.calculated_field_suggestions.length}</p>
                  </div>
                </div>

                <div className="space-y-3">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900">Recommended cleaning plan</h3>
                    <p className="text-xs text-slate-500">These actions stay reversible and record approval feedback for future recommendations.</p>
                  </div>
                  {activePlan.cleaning_steps.length ? (
                    <div className="space-y-3">
                      {activePlan.cleaning_steps.map((step) => {
                        const isSubmitting = feedbackMutation.isPending && feedbackMutation.variables?.stepId === step.step_id;
                        const isApplying = prepActionMutation.isPending && prepActionMutation.variables?.stepId === step.step_id;
                        return (
                          <div key={step.step_id} className="rounded-xl border border-slate-200 bg-white p-4">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div>
                                <p className="font-medium text-slate-900">{step.title}</p>
                                <p className="text-xs uppercase tracking-wide text-slate-500">{step.step_type.replace(/_/g, " ")}</p>
                              </div>
                              <div className="flex items-center gap-2">
                                {step.applied ? <Badge tone="success">Applied</Badge> : null}
                                <Badge tone={toneForConfidence(step.confidence)}>Confidence {(step.confidence * 100).toFixed(0)}%</Badge>
                                <Badge tone="default">Approved {step.feedback.approved}</Badge>
                                <Badge tone="default">Rejected {step.feedback.rejected}</Badge>
                              </div>
                            </div>
                            <p className="mt-3 text-sm text-slate-600">{step.explanation}</p>
                            {step.target_fields.length ? (
                              <p className="mt-2 text-xs text-slate-500">Fields: {step.target_fields.join(", ")}</p>
                            ) : null}
                            {step.applied_at ? <p className="mt-2 text-xs text-emerald-700">Applied {new Date(step.applied_at).toLocaleString()}</p> : null}
                            <div className="mt-3 grid gap-3 md:grid-cols-2">
                              <div className="rounded-lg border border-slate-200 bg-slate-50/80 p-3 text-sm text-slate-600">
                                <p className="font-medium text-slate-900">Revert strategy</p>
                                <p className="mt-1">{step.revert_strategy}</p>
                              </div>
                              <div className="rounded-lg border border-slate-200 bg-slate-50/80 p-3 text-sm text-slate-600">
                                <p className="font-medium text-slate-900">SQL preview</p>
                                <p className="mt-1 font-mono text-xs text-slate-700">{step.sql_preview ?? "Semantic-only annotation. No SQL rewrite required."}</p>
                              </div>
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2">
                              <Button
                                type="button"
                                size="sm"
                                disabled={isApplying}
                                onClick={() => prepActionMutation.mutate({ datasetId: activePlan.dataset_id, stepId: step.step_id, action: step.applied ? "rollback" : "apply" })}
                              >
                                {isApplying ? "Saving..." : step.applied ? "Roll back step" : "Apply step"}
                              </Button>
                              <Button
                                type="button"
                                variant="secondary"
                                size="sm"
                                disabled={isSubmitting}
                                onClick={() => feedbackMutation.mutate({ datasetId: activePlan.dataset_id, stepId: step.step_id, decision: "approve" })}
                              >
                                {isSubmitting ? "Saving..." : "Approve step"}
                              </Button>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                disabled={isSubmitting}
                                onClick={() => feedbackMutation.mutate({ datasetId: activePlan.dataset_id, stepId: step.step_id, decision: "reject" })}
                              >
                                Reject step
                              </Button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <EmptyState>
                      <EmptyStateTitle>No cleaning actions suggested</EmptyStateTitle>
                      <EmptyStateBody>The current sample does not require urgent reversible cleaning actions.</EmptyStateBody>
                    </EmptyState>
                  )}
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="space-y-3">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900">Join suggestions</h3>
                      <p className="text-xs text-slate-500">High-confidence join candidates based on field names, types, and sampled value overlap.</p>
                    </div>
                    {activePlan.join_suggestions.length ? (
                      activePlan.join_suggestions.map((suggestion) => (
                        <div key={`${suggestion.target_dataset_id}:${suggestion.left_field}:${suggestion.right_field}`} className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                          <div className="flex items-center justify-between gap-2">
                            <p className="font-medium text-slate-900">{suggestion.target_dataset_name}</p>
                            <Badge tone={toneForConfidence(suggestion.score)}>Confidence {(suggestion.score * 100).toFixed(0)}%</Badge>
                          </div>
                          <p className="mt-2 text-sm text-slate-600">{suggestion.left_field}{" -> "}{suggestion.right_field}</p>
                          <p className="mt-1 text-sm text-slate-500">{suggestion.rationale}</p>
                        </div>
                      ))
                    ) : (
                      <p className="rounded-xl border border-slate-200 bg-slate-50/80 p-3 text-sm text-slate-500">No high-confidence join suggestion passed the current threshold.</p>
                    )}
                  </div>

                  <div className="space-y-3">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900">Union suggestions</h3>
                      <p className="text-xs text-slate-500">Similar-shape datasets that can likely be stacked into a governed reporting table.</p>
                    </div>
                    {activePlan.union_suggestions.length ? (
                      activePlan.union_suggestions.map((suggestion) => (
                        <div key={`${suggestion.target_dataset_id}:${suggestion.score}`} className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                          <div className="flex items-center justify-between gap-2">
                            <p className="font-medium text-slate-900">{suggestion.target_dataset_name}</p>
                            <Badge tone={toneForConfidence(suggestion.score)}>Confidence {(suggestion.score * 100).toFixed(0)}%</Badge>
                          </div>
                          <p className="mt-2 text-sm text-slate-600">Shared fields: {suggestion.shared_fields.join(", ")}</p>
                          <p className="mt-1 text-sm text-slate-500">{suggestion.rationale}</p>
                        </div>
                      ))
                    ) : (
                      <p className="rounded-xl border border-slate-200 bg-slate-50/80 p-3 text-sm text-slate-500">No union-compatible sibling dataset passed the current threshold.</p>
                    )}
                  </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="space-y-3">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900">Calculated field suggestions</h3>
                      <p className="text-xs text-slate-500">Promote recurring executive logic into governed reusable fields.</p>
                    </div>
                    {activePlan.calculated_field_suggestions.length ? (
                      activePlan.calculated_field_suggestions.map((suggestion) => (
                        <div key={suggestion.name} className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                          <div className="flex items-center justify-between gap-2">
                            <p className="font-medium text-slate-900">{suggestion.name}</p>
                            <Badge tone="default">{suggestion.data_type}</Badge>
                          </div>
                          <p className="mt-2 font-mono text-xs text-slate-700">{suggestion.expression}</p>
                          <p className="mt-2 text-sm text-slate-500">{suggestion.rationale}</p>
                        </div>
                      ))
                    ) : (
                      <p className="rounded-xl border border-slate-200 bg-slate-50/80 p-3 text-sm text-slate-500">No high-confidence calculated field suggestions were inferred.</p>
                    )}
                  </div>

                  <div className="space-y-3">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900">Transformation lineage</h3>
                      <p className="text-xs text-slate-500">Current lineage reflects ingestion-time cleanups plus governed autopilot apply or rollback actions.</p>
                    </div>
                    {activePlan.transformation_lineage.length ? (
                      activePlan.transformation_lineage.map((item, index) => (
                        <div key={`${item.source}:${index}`} className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                          <div className="flex items-center justify-between gap-2">
                            <p className="font-medium text-slate-900">{item.source.replace(/_/g, " ")}</p>
                            <Badge tone="default">{item.affected_fields.length} fields</Badge>
                          </div>
                          <p className="mt-2 text-sm text-slate-500">{item.description}</p>
                          {item.affected_fields.length ? <p className="mt-2 text-xs text-slate-500">Affected: {item.affected_fields.join(", ")}</p> : null}
                        </div>
                      ))
                    ) : (
                      <p className="rounded-xl border border-slate-200 bg-slate-50/80 p-3 text-sm text-slate-500">No ingestion lineage has been captured for this dataset yet.</p>
                    )}
                  </div>
                </div>

                {activePlan.notes.length ? (
                  <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3 text-sm text-slate-600">
                    <p className="font-medium text-slate-900">Autopilot notes</p>
                    <ul className="mt-2 space-y-1">
                      {activePlan.notes.map((note) => (
                        <li key={note}>{note}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {!datasetsQuery.isLoading && !datasetsQuery.data?.length ? (
        <EmptyState>
          <EmptyStateTitle>No datasets yet</EmptyStateTitle>
          <EmptyStateBody>Connect a data source and run sync to populate the governed catalog.</EmptyStateBody>
        </EmptyState>
      ) : null}
    </section>
  );
}