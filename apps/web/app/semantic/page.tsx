"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Input } from "@/components/ui";

import { apiRequest } from "@/lib/api";

type Field = {
  id: string;
  name: string;
  data_type: string;
  is_dimension: boolean;
  is_metric: boolean;
};

type Dataset = {
  id: string;
  name: string;
  source_table: string;
  physical_table: string;
  row_count: number;
  fields: Field[];
};

type SemanticModel = {
  id: string;
  name: string;
  model_key: string;
  version: number;
  created_at: string;
};

type GovernanceInput = {
  owner_name?: string | null;
  owner_email?: string | null;
  certification_status: "draft" | "review" | "certified" | "deprecated";
  certification_note?: string | null;
  trusted_for_nl: boolean;
};

type JoinInput = {
  left_dataset_id: string;
  right_dataset_id: string;
  left_field: string;
  right_field: string;
  join_type: "left" | "inner" | "right" | "full";
  left_alias?: string;
  right_alias?: string;
};

type MetricInput = {
  name: string;
  label: string;
  formula: string;
  aggregation: string;
  value_format?: string;
  visibility: string;
  description?: string | null;
  synonyms: string[];
  owner_name?: string | null;
  certification_status: GovernanceInput["certification_status"];
};

type DimensionInput = {
  name: string;
  label: string;
  field_ref: string;
  data_type: string;
  time_grain?: string;
  visibility: string;
  description?: string | null;
  synonyms: string[];
  hierarchy: string[];
  owner_name?: string | null;
  certification_status: GovernanceInput["certification_status"];
};

type CalculatedFieldInput = {
  name: string;
  expression: string;
  data_type: string;
};

type ValidateResponse = {
  valid: boolean;
  errors: string[];
};

type DraftSemanticModel = {
  name: string;
  model_key: string;
  description?: string | null;
  base_dataset_id: string;
  joins: JoinInput[];
  metrics: MetricInput[];
  dimensions: DimensionInput[];
  calculated_fields: CalculatedFieldInput[];
  governance: GovernanceInput;
  inference_notes: string[];
};

type TrustActivityItem = {
  activity_type: string;
  title: string;
  detail?: string | null;
  created_at: string;
};

type TrustLineageSummary = {
  base_dataset_name: string;
  base_quality_status: string;
  joins_configured: number;
  datasets_in_scope: string[];
  metrics_governed: number;
  dimensions_governed: number;
};

type TrustPanel = {
  model_id: string;
  model_name: string;
  model_key: string;
  version: number;
  governance: GovernanceInput;
  lineage_summary: TrustLineageSummary;
  recent_activity: TrustActivityItem[];
  open_gaps: string[];
};

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "") || "dataset";
}

function parseListInput(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item, index, array) => array.findIndex((candidate) => candidate.toLowerCase() === item.toLowerCase()) === index);
}

function formatListInput(value: string[] | undefined): string {
  return (value ?? []).join(", ");
}

function emptyMetric(): MetricInput {
  return {
    name: "revenue",
    label: "Revenue",
    formula: "SUM(revenue)",
    aggregation: "sum",
    value_format: "currency",
    visibility: "public",
    description: "Primary revenue KPI used in executive reporting.",
    synonyms: ["Revenue", "Sales"],
    owner_name: "",
    certification_status: "draft",
  };
}

function emptyDimension(defaultField?: Field): DimensionInput {
  const lowerDataType = defaultField?.data_type.toLowerCase() ?? "string";
  const isTime = lowerDataType.includes("date") || lowerDataType.includes("time");
  return {
    name: defaultField?.name ?? "region",
    label: defaultField?.name ? defaultField.name.replace(/_/g, " ") : "Region",
    field_ref: defaultField?.name ?? "region",
    data_type: defaultField?.data_type ?? "string",
    time_grain: isTime ? "month" : undefined,
    visibility: "public",
    description: defaultField?.name ? `Governed dimension mapped from ${defaultField.name}.` : "Governed business dimension.",
    synonyms: defaultField?.name ? [defaultField.name.replace(/_/g, " ")] : ["Region"],
    hierarchy: isTime ? ["year", "quarter", "month"] : [],
    owner_name: "",
    certification_status: "draft",
  };
}

function emptyCalculatedField(): CalculatedFieldInput {
  return {
    name: "gross_margin",
    expression: "revenue - cost",
    data_type: "number",
  };
}

function emptyGovernance(): GovernanceInput {
  return {
    owner_name: "",
    owner_email: "",
    certification_status: "draft",
    certification_note: "",
    trusted_for_nl: true,
  };
}

function toneForCertification(status: string): "default" | "success" | "warning" | "danger" {
  if (status === "certified") return "success";
  if (status === "review") return "warning";
  if (status === "deprecated") return "danger";
  return "default";
}

export default function SemanticPage() {
  const queryClient = useQueryClient();
  const [baseDatasetId, setBaseDatasetId] = useState("");
  const [selectedTrustModelId, setSelectedTrustModelId] = useState("");
  const [modelName, setModelName] = useState("Revenue Model");
  const [modelKey, setModelKey] = useState("revenue_model");
  const [description, setDescription] = useState("Governed revenue model for executive reporting.");
  const [governance, setGovernance] = useState<GovernanceInput>(emptyGovernance());
  const [joins, setJoins] = useState<JoinInput[]>([]);
  const [metrics, setMetrics] = useState<MetricInput[]>([emptyMetric()]);
  const [dimensions, setDimensions] = useState<DimensionInput[]>([emptyDimension()]);
  const [calculatedFields, setCalculatedFields] = useState<CalculatedFieldInput[]>([]);
  const [validation, setValidation] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [draftNotes, setDraftNotes] = useState<string[]>([]);

  const datasetsQuery = useQuery({
    queryKey: ["semantic", "datasets"],
    queryFn: () => apiRequest<Dataset[]>("/api/v1/semantic/datasets"),
  });
  const modelsQuery = useQuery({
    queryKey: ["semantic", "models"],
    queryFn: () => apiRequest<SemanticModel[]>("/api/v1/semantic/models"),
  });
  const trustPanelQuery = useQuery({
    queryKey: ["semantic", "trust-panel", selectedTrustModelId],
    queryFn: () => apiRequest<TrustPanel>(`/api/v1/semantic/models/${selectedTrustModelId}/trust-panel`),
    enabled: Boolean(selectedTrustModelId),
  });

  const datasets = datasetsQuery.data ?? [];
  const models = modelsQuery.data ?? [];

  useEffect(() => {
    if (!baseDatasetId && datasets[0]) {
      setBaseDatasetId(datasets[0].id);
      const firstField = datasets[0].fields.find((field) => field.is_dimension) ?? datasets[0].fields[0];
      setDimensions([emptyDimension(firstField)]);
    }
  }, [datasets, baseDatasetId]);

  useEffect(() => {
    if (!selectedTrustModelId && models[0]) {
      setSelectedTrustModelId(models[0].id);
    }
  }, [models, selectedTrustModelId]);

  const datasetById = useMemo(() => Object.fromEntries(datasets.map((dataset) => [dataset.id, dataset])), [datasets]);
  const selectedDataset = datasetById[baseDatasetId];

  const fieldReferenceOptions = useMemo(() => {
    const options: Array<{ value: string; label: string }> = [];
    if (selectedDataset) {
      for (const field of selectedDataset.fields) {
        options.push({ value: field.name, label: `${selectedDataset.name}.${field.name}` });
      }
    }

    for (const join of joins) {
      const dataset = datasetById[join.right_dataset_id];
      const alias = (join.right_alias || slugify(dataset?.name ?? "joined")).trim();
      if (!dataset || !alias) {
        continue;
      }
      for (const field of dataset.fields) {
        options.push({ value: `${alias}.${field.name}`, label: `${alias}.${field.name}` });
      }
    }

    return options;
  }, [datasetById, joins, selectedDataset]);

  function buildPayload() {
    return {
      name: modelName,
      model_key: modelKey,
      description,
      base_dataset_id: baseDatasetId,
      joins,
      metrics,
      dimensions,
      calculated_fields: calculatedFields,
      governance,
    };
  }

  const validateMutation = useMutation({
    mutationFn: (payload: ReturnType<typeof buildPayload>) =>
      apiRequest<ValidateResponse>("/api/v1/semantic/models/validate", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: (result) => {
      setValidation(result.errors);
      setDraftNotes([]);
      setNotice(result.errors.length ? null : "Semantic model payload is valid.");
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Validation failed");
    },
  });

  const createMutation = useMutation({
    mutationFn: (payload: ReturnType<typeof buildPayload>) =>
      apiRequest<SemanticModel>("/api/v1/semantic/models", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: async (result) => {
      setNotice("Semantic model saved.");
      setValidation(null);
      setSelectedTrustModelId(result.id);
      await queryClient.invalidateQueries({ queryKey: ["semantic", "models"] });
      await queryClient.invalidateQueries({ queryKey: ["semantic", "trust-panel", result.id] });
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Failed to create model");
    },
  });

  const draftMutation = useMutation({
    mutationFn: (datasetId: string) =>
      apiRequest<DraftSemanticModel>("/api/v1/semantic/models/draft", {
        method: "POST",
        body: JSON.stringify({ dataset_id: datasetId }),
      }),
    onSuccess: (draft) => {
      setModelName(draft.name);
      setModelKey(draft.model_key);
      setDescription(draft.description ?? "");
      setJoins(draft.joins);
      setMetrics(draft.metrics);
      setDimensions(draft.dimensions);
      setCalculatedFields(draft.calculated_fields);
      setGovernance(draft.governance ?? emptyGovernance());
      setDraftNotes(draft.inference_notes);
      setValidation(null);
      setError(null);
      setNotice("AI-ready semantic draft generated from the selected dataset.");
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Failed to generate semantic draft");
    },
  });

  function updateJoin(index: number, patch: Partial<JoinInput>) {
    setJoins((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)));
  }

  function updateMetric(index: number, patch: Partial<MetricInput>) {
    setMetrics((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)));
  }

  function updateDimension(index: number, patch: Partial<DimensionInput>) {
    setDimensions((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)));
  }

  function updateCalculatedField(index: number, patch: Partial<CalculatedFieldInput>) {
    setCalculatedFields((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)));
  }

  function addJoin() {
    const rightDataset = datasets.find((dataset) => dataset.id !== baseDatasetId);
    setJoins((current) => [
      ...current,
      {
        left_dataset_id: baseDatasetId,
        right_dataset_id: rightDataset?.id ?? "",
        left_field: selectedDataset?.fields[0]?.name ?? "",
        right_field: rightDataset?.fields[0]?.name ?? "",
        join_type: "left",
        left_alias: "base",
        right_alias: slugify(rightDataset?.name ?? "joined"),
      },
    ]);
  }

  function removeJoin(index: number) {
    setJoins((current) => current.filter((_, itemIndex) => itemIndex !== index));
  }

  function addMetric() {
    setMetrics((current) => [...current, emptyMetric()]);
  }

  function removeMetric(index: number) {
    setMetrics((current) => current.filter((_, itemIndex) => itemIndex !== index));
  }

  function addDimension() {
    const field = selectedDataset?.fields.find((item) => item.is_dimension) ?? selectedDataset?.fields[0];
    setDimensions((current) => [...current, emptyDimension(field)]);
  }

  function removeDimension(index: number) {
    setDimensions((current) => current.filter((_, itemIndex) => itemIndex !== index));
  }

  function addCalculatedField() {
    setCalculatedFields((current) => [...current, emptyCalculatedField()]);
  }

  function removeCalculatedField(index: number) {
    setCalculatedFields((current) => current.filter((_, itemIndex) => itemIndex !== index));
  }

  async function handleValidate() {
    setError(null);
    setNotice(null);
    setValidation(null);
    setDraftNotes([]);
    await validateMutation.mutateAsync(buildPayload());
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setValidation(null);
    await createMutation.mutateAsync(buildPayload());
  }

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">Semantic Model Editor</h2>
        <p className="text-sm text-slate-500">Define joins, metrics, dimensions, and calculated fields before any governed analytics query runs.</p>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {notice ? <p className="text-sm text-emerald-700">{notice}</p> : null}
      {draftNotes.length ? (
        <ul className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-3 text-sm text-emerald-900">
          {draftNotes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Create semantic model</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-5" onSubmit={handleSubmit}>
            <div className="grid gap-3 md:grid-cols-3">
              <Input value={modelName} onChange={(e) => setModelName(e.target.value)} placeholder="Model name" />
              <Input value={modelKey} onChange={(e) => setModelKey(e.target.value)} placeholder="Model key" />
              <select
                className="rounded-md border border-slate-300 px-3 py-2 text-sm"
                value={baseDatasetId}
                onChange={(e) => setBaseDatasetId(e.target.value)}
              >
                <option value="">Select base dataset</option>
                {datasets.map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    {dataset.name}
                  </option>
                ))}
              </select>
            </div>

            <textarea
              className="min-h-24 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the governed model and intended business use."
            />

            <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
              <div className="mb-3">
                <p className="text-sm font-semibold text-slate-900">Governance and trust</p>
                <p className="text-xs text-slate-500">Assign ownership, certification state, and whether this model is trusted for natural-language analytics.</p>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <Input value={governance.owner_name ?? ""} onChange={(e) => setGovernance((current) => ({ ...current, owner_name: e.target.value }))} placeholder="Owner name" />
                <Input value={governance.owner_email ?? ""} onChange={(e) => setGovernance((current) => ({ ...current, owner_email: e.target.value }))} placeholder="Owner email" />
                <select
                  className="rounded-md border border-slate-300 px-3 py-2 text-sm"
                  value={governance.certification_status}
                  onChange={(e) => setGovernance((current) => ({ ...current, certification_status: e.target.value as GovernanceInput["certification_status"] }))}
                >
                  <option value="draft">Draft</option>
                  <option value="review">In review</option>
                  <option value="certified">Certified</option>
                  <option value="deprecated">Deprecated</option>
                </select>
                <select
                  className="rounded-md border border-slate-300 px-3 py-2 text-sm"
                  value={governance.trusted_for_nl ? "true" : "false"}
                  onChange={(e) => setGovernance((current) => ({ ...current, trusted_for_nl: e.target.value === "true" }))}
                >
                  <option value="true">Trusted for NL</option>
                  <option value="false">Do not trust for NL yet</option>
                </select>
              </div>
              <textarea
                className="mt-3 min-h-24 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                value={governance.certification_note ?? ""}
                onChange={(e) => setGovernance((current) => ({ ...current, certification_note: e.target.value }))}
                placeholder="Certification note, validation evidence, or rollout constraints."
              />
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-900">Join graph</p>
                  <p className="text-xs text-slate-500">Model reusable dataset joins with explicit aliases.</p>
                </div>
                <Button type="button" variant="secondary" onClick={addJoin} disabled={!datasets.length || datasets.length < 2}>
                  Add join
                </Button>
              </div>
              <div className="space-y-3">
                {joins.map((join, index) => {
                  const leftFields = datasetById[join.left_dataset_id]?.fields ?? [];
                  const rightFields = datasetById[join.right_dataset_id]?.fields ?? [];
                  return (
                    <div key={`join-${index}`} className="grid gap-3 rounded-lg border border-slate-200 bg-white p-3 md:grid-cols-4">
                      <select
                        className="rounded-md border border-slate-300 px-3 py-2 text-sm"
                        value={join.left_dataset_id}
                        onChange={(e) => updateJoin(index, { left_dataset_id: e.target.value, left_field: datasetById[e.target.value]?.fields[0]?.name ?? "" })}
                      >
                        {datasets.map((dataset) => (
                          <option key={dataset.id} value={dataset.id}>
                            {dataset.name}
                          </option>
                        ))}
                      </select>
                      <select
                        className="rounded-md border border-slate-300 px-3 py-2 text-sm"
                        value={join.left_field}
                        onChange={(e) => updateJoin(index, { left_field: e.target.value })}
                      >
                        {leftFields.map((field) => (
                          <option key={field.id} value={field.name}>
                            {field.name}
                          </option>
                        ))}
                      </select>
                      <select
                        className="rounded-md border border-slate-300 px-3 py-2 text-sm"
                        value={join.join_type}
                        onChange={(e) => updateJoin(index, { join_type: e.target.value as JoinInput["join_type"] })}
                      >
                        <option value="left">Left join</option>
                        <option value="inner">Inner join</option>
                        <option value="right">Right join</option>
                        <option value="full">Full join</option>
                      </select>
                      <Button type="button" variant="ghost" onClick={() => removeJoin(index)}>
                        Remove
                      </Button>

                      <select
                        className="rounded-md border border-slate-300 px-3 py-2 text-sm"
                        value={join.right_dataset_id}
                        onChange={(e) => updateJoin(index, { right_dataset_id: e.target.value, right_field: datasetById[e.target.value]?.fields[0]?.name ?? "", right_alias: slugify(datasetById[e.target.value]?.name ?? "joined") })}
                      >
                        {datasets.filter((dataset) => dataset.id !== join.left_dataset_id).map((dataset) => (
                          <option key={dataset.id} value={dataset.id}>
                            {dataset.name}
                          </option>
                        ))}
                      </select>
                      <select
                        className="rounded-md border border-slate-300 px-3 py-2 text-sm"
                        value={join.right_field}
                        onChange={(e) => updateJoin(index, { right_field: e.target.value })}
                      >
                        {rightFields.map((field) => (
                          <option key={field.id} value={field.name}>
                            {field.name}
                          </option>
                        ))}
                      </select>
                      <Input value={join.left_alias ?? "base"} onChange={(e) => updateJoin(index, { left_alias: e.target.value })} placeholder="Left alias" />
                      <Input value={join.right_alias ?? "joined"} onChange={(e) => updateJoin(index, { right_alias: e.target.value })} placeholder="Right alias" />
                    </div>
                  );
                })}
                {!joins.length ? <p className="text-sm text-slate-500">No joins configured. The model will query only the base dataset.</p> : null}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-900">Metrics</p>
                  <p className="text-xs text-slate-500">Define governed formulas, business language coverage, and certification state.</p>
                </div>
                <Button type="button" variant="secondary" onClick={addMetric}>Add metric</Button>
              </div>
              <div className="space-y-3">
                {metrics.map((metric, index) => (
                  <div key={`metric-${index}`} className="space-y-3 rounded-lg border border-slate-200 bg-white p-3">
                    <div className="grid gap-3 md:grid-cols-3">
                      <Input value={metric.name} onChange={(e) => updateMetric(index, { name: e.target.value })} placeholder="Metric key" />
                      <Input value={metric.label} onChange={(e) => updateMetric(index, { label: e.target.value })} placeholder="Display label" />
                      <Input value={metric.formula} onChange={(e) => updateMetric(index, { formula: e.target.value })} placeholder="SUM(revenue)" />
                      <select className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={metric.aggregation} onChange={(e) => updateMetric(index, { aggregation: e.target.value })}>
                        <option value="sum">Sum</option>
                        <option value="avg">Average</option>
                        <option value="count">Count</option>
                        <option value="min">Min</option>
                        <option value="max">Max</option>
                      </select>
                      <Input value={metric.value_format ?? ""} onChange={(e) => updateMetric(index, { value_format: e.target.value })} placeholder="currency, percent, integer" />
                      <div className="flex gap-2">
                        <select className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm" value={metric.visibility} onChange={(e) => updateMetric(index, { visibility: e.target.value })}>
                          <option value="public">Public</option>
                          <option value="private">Private</option>
                        </select>
                        <Button type="button" variant="ghost" onClick={() => removeMetric(index)} disabled={metrics.length === 1}>
                          Remove
                        </Button>
                      </div>
                    </div>
                    <textarea
                      className="min-h-24 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                      value={metric.description ?? ""}
                      onChange={(e) => updateMetric(index, { description: e.target.value })}
                      placeholder="Business definition and when leadership should trust this KPI."
                    />
                    <div className="grid gap-3 md:grid-cols-3">
                      <Input value={formatListInput(metric.synonyms)} onChange={(e) => updateMetric(index, { synonyms: parseListInput(e.target.value) })} placeholder="Synonyms: revenue, sales, bookings" />
                      <Input value={metric.owner_name ?? ""} onChange={(e) => updateMetric(index, { owner_name: e.target.value })} placeholder="Metric owner" />
                      <select className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={metric.certification_status} onChange={(e) => updateMetric(index, { certification_status: e.target.value as MetricInput["certification_status"] })}>
                        <option value="draft">Draft</option>
                        <option value="review">In review</option>
                        <option value="certified">Certified</option>
                        <option value="deprecated">Deprecated</option>
                      </select>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-900">Dimensions</p>
                  <p className="text-xs text-slate-500">Select field references, time grain, hierarchy, and language grounding.</p>
                </div>
                <Button type="button" variant="secondary" onClick={addDimension}>Add dimension</Button>
              </div>
              <div className="space-y-3">
                {dimensions.map((dimension, index) => (
                  <div key={`dimension-${index}`} className="space-y-3 rounded-lg border border-slate-200 bg-white p-3">
                    <div className="grid gap-3 md:grid-cols-3">
                      <Input value={dimension.name} onChange={(e) => updateDimension(index, { name: e.target.value })} placeholder="Dimension key" />
                      <Input value={dimension.label} onChange={(e) => updateDimension(index, { label: e.target.value })} placeholder="Display label" />
                      <select className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={dimension.field_ref} onChange={(e) => updateDimension(index, { field_ref: e.target.value })}>
                        {fieldReferenceOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                      <select className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={dimension.data_type} onChange={(e) => updateDimension(index, { data_type: e.target.value })}>
                        <option value="string">String</option>
                        <option value="number">Number</option>
                        <option value="integer">Integer</option>
                        <option value="date">Date</option>
                        <option value="datetime">Datetime</option>
                        <option value="boolean">Boolean</option>
                      </select>
                      <select className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={dimension.time_grain ?? ""} onChange={(e) => updateDimension(index, { time_grain: e.target.value || undefined })}>
                        <option value="">No grain</option>
                        <option value="day">Day</option>
                        <option value="week">Week</option>
                        <option value="month">Month</option>
                        <option value="quarter">Quarter</option>
                        <option value="year">Year</option>
                      </select>
                      <div className="flex gap-2">
                        <select className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm" value={dimension.visibility} onChange={(e) => updateDimension(index, { visibility: e.target.value })}>
                          <option value="public">Public</option>
                          <option value="private">Private</option>
                        </select>
                        <Button type="button" variant="ghost" onClick={() => removeDimension(index)} disabled={dimensions.length === 1}>
                          Remove
                        </Button>
                      </div>
                    </div>
                    <textarea
                      className="min-h-24 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                      value={dimension.description ?? ""}
                      onChange={(e) => updateDimension(index, { description: e.target.value })}
                      placeholder="Business definition for this dimension and how it should be used in reports."
                    />
                    <div className="grid gap-3 md:grid-cols-2">
                      <Input value={formatListInput(dimension.synonyms)} onChange={(e) => updateDimension(index, { synonyms: parseListInput(e.target.value) })} placeholder="Synonyms: region, territory, market" />
                      <Input value={formatListInput(dimension.hierarchy)} onChange={(e) => updateDimension(index, { hierarchy: parseListInput(e.target.value) })} placeholder="Hierarchy: year, quarter, month" />
                      <Input value={dimension.owner_name ?? ""} onChange={(e) => updateDimension(index, { owner_name: e.target.value })} placeholder="Dimension owner" />
                      <select className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={dimension.certification_status} onChange={(e) => updateDimension(index, { certification_status: e.target.value as DimensionInput["certification_status"] })}>
                        <option value="draft">Draft</option>
                        <option value="review">In review</option>
                        <option value="certified">Certified</option>
                        <option value="deprecated">Deprecated</option>
                      </select>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-900">Calculated fields</p>
                  <p className="text-xs text-slate-500">Add reusable transformations for downstream metric formulas.</p>
                </div>
                <Button type="button" variant="secondary" onClick={addCalculatedField}>Add calculated field</Button>
              </div>
              <div className="space-y-3">
                {calculatedFields.map((field, index) => (
                  <div key={`calc-${index}`} className="grid gap-3 rounded-lg border border-slate-200 bg-white p-3 md:grid-cols-3">
                    <Input value={field.name} onChange={(e) => updateCalculatedField(index, { name: e.target.value })} placeholder="gross_margin" />
                    <Input value={field.expression} onChange={(e) => updateCalculatedField(index, { expression: e.target.value })} placeholder="revenue - cost" />
                    <div className="flex gap-2">
                      <select className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm" value={field.data_type} onChange={(e) => updateCalculatedField(index, { data_type: e.target.value })}>
                        <option value="number">Number</option>
                        <option value="integer">Integer</option>
                        <option value="string">String</option>
                        <option value="boolean">Boolean</option>
                      </select>
                      <Button type="button" variant="ghost" onClick={() => removeCalculatedField(index)}>
                        Remove
                      </Button>
                    </div>
                  </div>
                ))}
                {!calculatedFields.length ? <p className="text-sm text-slate-500">No calculated fields yet.</p> : null}
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="secondary" onClick={() => draftMutation.mutate(baseDatasetId)} disabled={draftMutation.isPending || !baseDatasetId}>
                {draftMutation.isPending ? "Generating draft..." : "Generate draft from dataset"}
              </Button>
              <Button type="button" variant="secondary" onClick={handleValidate} disabled={validateMutation.isPending || !baseDatasetId}>
                {validateMutation.isPending ? "Validating..." : "Validate model"}
              </Button>
              <Button type="submit" disabled={createMutation.isPending || !baseDatasetId}>
                {createMutation.isPending ? "Saving..." : "Save semantic model"}
              </Button>
            </div>
          </form>

          {validation ? (
            <div className="mt-4 text-sm">
              {validation.length ? (
                <ul className="list-disc space-y-1 pl-4 text-red-600">
                  {validation.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-emerald-600">Semantic model payload is valid.</p>
              )}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-[1.4fr,1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Dataset field references</CardTitle>
          </CardHeader>
          <CardContent>
            {datasetsQuery.isLoading ? <p className="text-sm text-slate-500">Loading datasets...</p> : null}
            <div className="space-y-3 text-sm">
              {datasets.map((dataset) => (
                <div key={dataset.id} className="rounded-md border border-slate-200 p-3">
                  <p className="font-medium">{dataset.name}</p>
                  <p className="text-xs text-slate-500">{dataset.row_count} rows</p>
                  <p className="mt-2 text-slate-600">{dataset.fields.map((field) => field.name).join(", ")}</p>
                </div>
              ))}
              {!datasets.length ? <p className="text-slate-500">No synced datasets yet.</p> : null}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Model version history</CardTitle>
            </CardHeader>
            <CardContent>
              {modelsQuery.isLoading ? <p className="text-sm text-slate-500">Loading models...</p> : null}
              <div className="space-y-2 text-sm">
                {models.map((model) => (
                  <button
                    key={model.id}
                    type="button"
                    className={`w-full rounded-md border p-3 text-left ${selectedTrustModelId === model.id ? "border-slate-900 bg-slate-50" : "border-slate-200"}`}
                    onClick={() => setSelectedTrustModelId(model.id)}
                  >
                    <p className="font-medium">
                      {model.name} v{model.version}
                    </p>
                    <p className="text-xs text-slate-500">Key: {model.model_key}</p>
                    <p className="text-xs text-slate-500">Created: {new Date(model.created_at).toLocaleString()}</p>
                  </button>
                ))}
                {!models.length ? <p className="text-slate-500">No semantic models created yet.</p> : null}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Trust Panel</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              {trustPanelQuery.isLoading ? <p className="text-slate-500">Loading trust panel...</p> : null}
              {trustPanelQuery.error ? <p className="text-red-600">{trustPanelQuery.error instanceof Error ? trustPanelQuery.error.message : "Failed to load trust panel"}</p> : null}
              {trustPanelQuery.data ? (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={toneForCertification(trustPanelQuery.data.governance.certification_status)}>{trustPanelQuery.data.governance.certification_status}</Badge>
                    <Badge tone={trustPanelQuery.data.governance.trusted_for_nl ? "success" : "warning"}>
                      {trustPanelQuery.data.governance.trusted_for_nl ? "Trusted for NL" : "Hold NL trust"}
                    </Badge>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                    <p className="font-medium text-slate-900">Owner</p>
                    <p className="mt-1 text-slate-600">{trustPanelQuery.data.governance.owner_name || "Unassigned"}</p>
                    <p className="text-xs text-slate-500">{trustPanelQuery.data.governance.owner_email || "No owner email recorded"}</p>
                    {trustPanelQuery.data.governance.certification_note ? <p className="mt-2 text-xs text-slate-500">{trustPanelQuery.data.governance.certification_note}</p> : null}
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                    <p className="font-medium text-slate-900">Lineage summary</p>
                    <p className="mt-1 text-slate-600">Base dataset: {trustPanelQuery.data.lineage_summary.base_dataset_name}</p>
                    <p className="text-xs text-slate-500">Base quality: {trustPanelQuery.data.lineage_summary.base_quality_status}</p>
                    <p className="text-xs text-slate-500">Joins configured: {trustPanelQuery.data.lineage_summary.joins_configured}</p>
                    <p className="text-xs text-slate-500">Metrics governed: {trustPanelQuery.data.lineage_summary.metrics_governed}</p>
                    <p className="text-xs text-slate-500">Dimensions governed: {trustPanelQuery.data.lineage_summary.dimensions_governed}</p>
                    <p className="mt-2 text-xs text-slate-500">Datasets in scope: {trustPanelQuery.data.lineage_summary.datasets_in_scope.join(", ")}</p>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                    <p className="font-medium text-slate-900">Recent activity</p>
                    <div className="mt-2 space-y-2">
                      {trustPanelQuery.data.recent_activity.map((activity, index) => (
                        <div key={`${activity.activity_type}-${index}`}>
                          <p className="text-slate-700">{activity.title}</p>
                          <p className="text-xs text-slate-500">{activity.activity_type} | {new Date(activity.created_at).toLocaleString()}</p>
                          {activity.detail ? <p className="text-xs text-slate-500">{activity.detail}</p> : null}
                        </div>
                      ))}
                      {!trustPanelQuery.data.recent_activity.length ? <p className="text-slate-500">No trust activity recorded yet.</p> : null}
                    </div>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                    <p className="font-medium text-slate-900">Open gaps</p>
                    {trustPanelQuery.data.open_gaps.length ? (
                      <ul className="mt-2 space-y-1 text-slate-600">
                        {trustPanelQuery.data.open_gaps.map((gap) => (
                          <li key={gap}>{gap}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-emerald-700">No immediate trust gaps detected for the current governance settings.</p>
                    )}
                  </div>
                </>
              ) : null}
              {!trustPanelQuery.isLoading && !trustPanelQuery.data && !models.length ? <p className="text-slate-500">Create a semantic model to populate the trust panel.</p> : null}
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}
