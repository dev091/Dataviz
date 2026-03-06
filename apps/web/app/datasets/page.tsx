"use client";

import { useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@platform/ui";

import { apiRequest } from "@/lib/api";

type DatasetField = {
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
  fields: DatasetField[];
};

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await apiRequest<Dataset[]>("/api/v1/semantic/datasets");
        setDatasets(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load datasets");
      }
    }
    void load();
  }, []);

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Dataset Catalog</h2>
        <p className="text-sm text-slate-500">Governed datasets discovered through connectors and sync runs.</p>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      <div className="space-y-3">
        {datasets.map((dataset) => (
          <Card key={dataset.id}>
            <CardHeader>
              <CardTitle>{dataset.name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex flex-wrap gap-4 text-xs text-slate-500">
                <span>Source: {dataset.source_table}</span>
                <span>Rows: {dataset.row_count}</span>
                <span>Warehouse table: {dataset.physical_table}</span>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                      <th className="px-2 py-2">Field</th>
                      <th className="px-2 py-2">Type</th>
                      <th className="px-2 py-2">Dimension</th>
                      <th className="px-2 py-2">Metric</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dataset.fields.map((field) => (
                      <tr key={field.id} className="border-b border-slate-100">
                        <td className="px-2 py-2">{field.name}</td>
                        <td className="px-2 py-2">{field.data_type}</td>
                        <td className="px-2 py-2">{field.is_dimension ? "Yes" : "No"}</td>
                        <td className="px-2 py-2">{field.is_metric ? "Yes" : "No"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {datasets.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No datasets yet</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-slate-600">Connect a data source and run sync to populate the catalog.</p>
          </CardContent>
        </Card>
      ) : null}
    </section>
  );
}
