"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { Button, Card, CardContent, CardHeader, CardTitle, Input } from "@platform/ui";

import { apiRequest } from "@/lib/api";

type Field = {
  name: string;
  data_type: string;
};

type Dataset = {
  id: string;
  name: string;
  fields: Field[];
};

type SemanticModel = {
  id: string;
  name: string;
  model_key: string;
  version: number;
  created_at: string;
};

export default function SemanticPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [models, setModels] = useState<SemanticModel[]>([]);
  const [baseDatasetId, setBaseDatasetId] = useState("");
  const [modelName, setModelName] = useState("Revenue Model");
  const [modelKey, setModelKey] = useState("revenue_model");
  const [metricName, setMetricName] = useState("revenue");
  const [metricFormula, setMetricFormula] = useState("SUM(revenue)");
  const [dimensionName, setDimensionName] = useState("region");
  const [dimensionField, setDimensionField] = useState("region");
  const [error, setError] = useState<string | null>(null);
  const [validation, setValidation] = useState<string[] | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [datasetData, modelData] = await Promise.all([
          apiRequest<Dataset[]>("/api/v1/semantic/datasets"),
          apiRequest<SemanticModel[]>("/api/v1/semantic/models"),
        ]);
        setDatasets(datasetData);
        setModels(modelData);
        if (datasetData[0] && !baseDatasetId) {
          setBaseDatasetId(datasetData[0].id);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load semantic resources");
      }
    }
    void load();
  }, []);

  const selectedDataset = useMemo(() => datasets.find((dataset) => dataset.id === baseDatasetId), [datasets, baseDatasetId]);

  async function validateModel() {
    setError(null);
    setValidation(null);
    try {
      const response = await apiRequest<{ valid: boolean; errors: string[] }>("/api/v1/semantic/models/validate", {
        method: "POST",
        body: JSON.stringify({
          name: modelName,
          model_key: modelKey,
          description: "",
          base_dataset_id: baseDatasetId,
          joins: [],
          metrics: [{ name: metricName, label: metricName, formula: metricFormula, aggregation: "sum", visibility: "public" }],
          dimensions: [{ name: dimensionName, label: dimensionName, field_ref: dimensionField, data_type: "string", visibility: "public" }],
          calculated_fields: [],
        }),
      });
      setValidation(response.errors);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed");
    }
  }

  async function createModel(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await apiRequest("/api/v1/semantic/models", {
        method: "POST",
        body: JSON.stringify({
          name: modelName,
          model_key: modelKey,
          description: "Revenue semantic model",
          base_dataset_id: baseDatasetId,
          joins: [],
          metrics: [{ name: metricName, label: metricName, formula: metricFormula, aggregation: "sum", visibility: "public" }],
          dimensions: [{ name: dimensionName, label: dimensionName, field_ref: dimensionField, data_type: "string", visibility: "public" }],
          calculated_fields: [],
        }),
      });
      const modelData = await apiRequest<SemanticModel[]>("/api/v1/semantic/models");
      setModels(modelData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create model");
    }
  }

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Semantic Model Editor</h2>
        <p className="text-sm text-slate-500">Define governed dimensions and metrics before any NL analytics query.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Create semantic model</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-3" onSubmit={createModel}>
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

            <div className="grid gap-3 md:grid-cols-2">
              <Input value={metricName} onChange={(e) => setMetricName(e.target.value)} placeholder="Metric name" />
              <Input value={metricFormula} onChange={(e) => setMetricFormula(e.target.value)} placeholder="Metric formula" />
              <Input value={dimensionName} onChange={(e) => setDimensionName(e.target.value)} placeholder="Dimension name" />
              <Input value={dimensionField} onChange={(e) => setDimensionField(e.target.value)} placeholder="Field reference" />
            </div>

            <div className="flex gap-2">
              <Button type="button" variant="secondary" onClick={validateModel}>
                Validate
              </Button>
              <Button type="submit">Save semantic model</Button>
            </div>
          </form>

          {selectedDataset ? (
            <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
              <p className="mb-1 font-medium">Available fields in {selectedDataset.name}</p>
              <p className="text-slate-600">{selectedDataset.fields.map((field) => field.name).join(", ")}</p>
            </div>
          ) : null}

          {validation ? (
            <div className="mt-3 text-sm">
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

          {error ? <p className="mt-2 text-sm text-red-600">{error}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Model version history</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            {models.map((model) => (
              <div key={model.id} className="rounded-md border border-slate-200 p-3">
                <p className="font-medium">
                  {model.name} v{model.version}
                </p>
                <p className="text-xs text-slate-500">Key: {model.model_key}</p>
              </div>
            ))}
            {!models.length ? <p className="text-slate-500">No semantic models created yet.</p> : null}
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
