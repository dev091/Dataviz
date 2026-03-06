"use client";

import { FormEvent, useEffect, useState } from "react";

import { Button, Card, CardContent, CardHeader, CardTitle, Input } from "@platform/ui";

import { apiRequest } from "@/lib/api";

type Connection = {
  id: string;
  name: string;
  connector_type: string;
  status: string;
  sync_frequency: string;
  last_synced_at?: string;
};

type SyncRun = {
  id: string;
  status: string;
  started_at: string;
  finished_at?: string;
  records_synced: number;
  message?: string;
  logs: Record<string, unknown>;
};

type SchemaField = {
  name: string;
  data_type: string;
  nullable: boolean;
};

type SchemaDataset = {
  name: string;
  source_table: string;
  fields: SchemaField[];
};

type SchemaPreview = {
  datasets: SchemaDataset[];
};

type ConnectorType = "csv" | "postgresql" | "mysql" | "google_sheets" | "salesforce";

type ConnectorForms = {
  postgresql: { uri: string };
  mysql: { uri: string };
  google_sheets: { csv_export_url: string };
  salesforce: {
    username: string;
    password: string;
    security_token: string;
    domain: string;
    object_name: string;
  };
};

const connectorOptions: Array<{ value: ConnectorType; label: string; description: string }> = [
  { value: "csv", label: "CSV Upload", description: "Upload local files for quick governed ingestion." },
  { value: "postgresql", label: "PostgreSQL", description: "Connect a transactional or warehouse Postgres source." },
  { value: "mysql", label: "MySQL", description: "Sync operational MySQL tables into the workspace." },
  { value: "google_sheets", label: "Google Sheets", description: "Pull published Sheets via CSV export URL." },
  { value: "salesforce", label: "Salesforce", description: "Ingest CRM objects for pipeline and revenue analytics." },
];

const initialForms: ConnectorForms = {
  postgresql: { uri: "postgresql+psycopg://user:password@host:5432/database" },
  mysql: { uri: "mysql+pymysql://user:password@host:3306/database" },
  google_sheets: { csv_export_url: "https://docs.google.com/spreadsheets/d/.../export?format=csv" },
  salesforce: {
    username: "",
    password: "",
    security_token: "",
    domain: "login",
    object_name: "Opportunity",
  },
};

function connectorLabel(value: string): string {
  return connectorOptions.find((option) => option.value === value)?.label ?? value;
}

export default function ConnectionsPage() {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [syncRuns, setSyncRuns] = useState<Record<string, SyncRun[]>>({});
  const [name, setName] = useState("Revenue Source");
  const [connectorType, setConnectorType] = useState<ConnectorType>("csv");
  const [forms, setForms] = useState<ConnectorForms>(initialForms);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<SchemaPreview | null>(null);
  const [creating, setCreating] = useState(false);

  async function loadConnections() {
    try {
      const data = await apiRequest<Connection[]>("/api/v1/connections");
      setConnections(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load connections");
    }
  }

  useEffect(() => {
    void loadConnections();
  }, []);

  function setConnectorField<T extends keyof ConnectorForms>(type: T, field: keyof ConnectorForms[T], value: string) {
    setForms((current) => ({
      ...current,
      [type]: {
        ...current[type],
        [field]: value,
      },
    }));
  }

  function buildConfig(): Record<string, unknown> {
    if (connectorType === "csv") {
      return {};
    }
    if (connectorType === "postgresql") {
      return { uri: forms.postgresql.uri.trim() };
    }
    if (connectorType === "mysql") {
      return { uri: forms.mysql.uri.trim() };
    }
    if (connectorType === "google_sheets") {
      return { csv_export_url: forms.google_sheets.csv_export_url.trim() };
    }
    return {
      username: forms.salesforce.username.trim(),
      password: forms.salesforce.password,
      security_token: forms.salesforce.security_token.trim(),
      domain: forms.salesforce.domain.trim() || "login",
      object_name: forms.salesforce.object_name.trim() || "Opportunity",
    };
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setCreating(true);
    setError(null);

    try {
      let config = buildConfig();
      if (connectorType === "csv") {
        if (!csvFile) {
          throw new Error("Please upload a CSV file first.");
        }
        const body = new FormData();
        body.append("file", csvFile);
        const upload = await apiRequest<{ file_path: string }>(
          "/api/v1/connections/csv/upload",
          { method: "POST", body },
          { withAuth: true, workspaceScoped: true },
        );
        config = { file_path: upload.file_path };
      }

      await apiRequest("/api/v1/connections", {
        method: "POST",
        body: JSON.stringify({ name, connector_type: connectorType, config }),
      });
      setPreview(null);
      await loadConnections();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create connection");
    } finally {
      setCreating(false);
    }
  }

  async function discover(connectionId: string) {
    setError(null);
    try {
      const data = await apiRequest<SchemaPreview>(`/api/v1/connections/${connectionId}/discover`, {
        method: "POST",
      });
      setPreview(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to discover schema");
    }
  }

  async function sync(connectionId: string) {
    setError(null);
    try {
      await apiRequest(`/api/v1/connections/${connectionId}/sync`, { method: "POST" });
      await loadConnections();
      await loadSyncRuns(connectionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to sync connection");
    }
  }

  async function scheduleWeekly(connectionId: string) {
    setError(null);
    try {
      await apiRequest(`/api/v1/connections/${connectionId}/sync-jobs`, {
        method: "POST",
        body: JSON.stringify({ schedule_type: "weekly", schedule_time: "09:00", weekday: 1 }),
      });
      await loadConnections();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update schedule");
    }
  }

  async function loadSyncRuns(connectionId: string) {
    setError(null);
    try {
      const data = await apiRequest<SyncRun[]>(`/api/v1/connections/${connectionId}/sync-runs`);
      setSyncRuns((current) => ({ ...current, [connectionId]: data }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sync runs");
    }
  }

  function renderConnectorForm() {
    if (connectorType === "csv") {
      return (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/80 p-4">
          <p className="mb-3 text-sm font-medium text-slate-700">CSV source</p>
          <input type="file" accept=".csv" onChange={(e) => setCsvFile(e.target.files?.[0] ?? null)} />
          <p className="mt-2 text-xs text-slate-500">Upload a local CSV to create a workspace dataset immediately.</p>
        </div>
      );
    }

    if (connectorType === "postgresql") {
      return (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="md:col-span-2">
            <label className="mb-1 block text-sm text-slate-600">Connection URI</label>
            <Input value={forms.postgresql.uri} onChange={(e) => setConnectorField("postgresql", "uri", e.target.value)} />
          </div>
        </div>
      );
    }

    if (connectorType === "mysql") {
      return (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="md:col-span-2">
            <label className="mb-1 block text-sm text-slate-600">Connection URI</label>
            <Input value={forms.mysql.uri} onChange={(e) => setConnectorField("mysql", "uri", e.target.value)} />
          </div>
        </div>
      );
    }

    if (connectorType === "google_sheets") {
      return (
        <div className="grid grid-cols-1 gap-3">
          <div>
            <label className="mb-1 block text-sm text-slate-600">Published CSV export URL</label>
            <Input
              value={forms.google_sheets.csv_export_url}
              onChange={(e) => setConnectorField("google_sheets", "csv_export_url", e.target.value)}
            />
          </div>
        </div>
      );
    }

    return (
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm text-slate-600">Username</label>
          <Input value={forms.salesforce.username} onChange={(e) => setConnectorField("salesforce", "username", e.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-sm text-slate-600">Password</label>
          <Input type="password" value={forms.salesforce.password} onChange={(e) => setConnectorField("salesforce", "password", e.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-sm text-slate-600">Security token</label>
          <Input
            type="password"
            value={forms.salesforce.security_token}
            onChange={(e) => setConnectorField("salesforce", "security_token", e.target.value)}
          />
        </div>
        <div>
          <label className="mb-1 block text-sm text-slate-600">Domain</label>
          <select
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            value={forms.salesforce.domain}
            onChange={(e) => setConnectorField("salesforce", "domain", e.target.value)}
          >
            <option value="login">Production</option>
            <option value="test">Sandbox</option>
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="mb-1 block text-sm text-slate-600">Object name</label>
          <Input
            value={forms.salesforce.object_name}
            onChange={(e) => setConnectorField("salesforce", "object_name", e.target.value)}
            placeholder="Opportunity"
          />
        </div>
      </div>
    );
  }

  const activeOption = connectorOptions.find((option) => option.value === connectorType)!;

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">Data Connections</h2>
        <p className="text-sm text-slate-500">Configure governed source connections, inspect schema, and control sync cadence per workspace.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Add connection</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleCreate}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div>
                <label className="mb-1 block text-sm text-slate-600">Connection name</label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Revenue Source" />
              </div>
              <div>
                <label className="mb-1 block text-sm text-slate-600">Connector</label>
                <select
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                  value={connectorType}
                  onChange={(e) => setConnectorType(e.target.value as ConnectorType)}
                >
                  {connectorOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-end">
                <Button type="submit" className="w-full" disabled={creating}>
                  {creating ? "Creating..." : "Create connection"}
                </Button>
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white/70 p-4">
              <p className="text-sm font-medium text-slate-900">{activeOption.label}</p>
              <p className="mt-1 text-sm text-slate-500">{activeOption.description}</p>
              <div className="mt-4">{renderConnectorForm()}</div>
            </div>
          </form>
          {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}
        </CardContent>
      </Card>

      <div className="space-y-3">
        {connections.map((connection) => (
          <Card key={connection.id}>
            <CardHeader>
              <CardTitle>{connection.name}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="mb-3 flex flex-wrap gap-4 text-xs text-slate-500">
                <span>Type: {connectorLabel(connection.connector_type)}</span>
                <span>Status: {connection.status}</span>
                <span>Frequency: {connection.sync_frequency}</span>
                <span>Last sync: {connection.last_synced_at ?? "Never"}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={() => discover(connection.id)}>
                  Discover schema
                </Button>
                <Button variant="secondary" onClick={() => sync(connection.id)}>
                  Manual sync
                </Button>
                <Button variant="ghost" onClick={() => scheduleWeekly(connection.id)}>
                  Set weekly sync
                </Button>
                <Button variant="ghost" onClick={() => loadSyncRuns(connection.id)}>
                  View sync logs
                </Button>
              </div>

              {(syncRuns[connection.id] ?? []).length ? (
                <div className="mt-3 space-y-2 rounded-md border border-slate-200 bg-slate-50 p-3 text-xs">
                  {(syncRuns[connection.id] ?? []).map((run) => (
                    <div key={run.id} className="rounded border border-slate-200 bg-white p-2">
                      <p className="font-medium">
                        {run.status.toUpperCase()} - {run.records_synced} records
                      </p>
                      <p className="text-slate-500">Started: {new Date(run.started_at).toLocaleString()}</p>
                      <p className="text-slate-500">{run.message ?? "No errors"}</p>
                    </div>
                  ))}
                </div>
              ) : null}
            </CardContent>
          </Card>
        ))}
      </div>

      {preview ? (
        <Card>
          <CardHeader>
            <CardTitle>Schema preview</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {!preview.datasets.length ? <p className="text-sm text-slate-500">No datasets discovered.</p> : null}
            {preview.datasets.map((dataset) => (
              <div key={`${dataset.name}-${dataset.source_table}`} className="rounded-xl border border-slate-200 bg-slate-50/80 p-4">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{dataset.name}</p>
                    <p className="text-xs text-slate-500">Source table: {dataset.source_table}</p>
                  </div>
                  <span className="rounded-full bg-slate-200 px-2 py-1 text-[11px] font-medium text-slate-700">
                    {dataset.fields.length} fields
                  </span>
                </div>
                <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
                  {dataset.fields.map((field) => (
                    <div key={field.name} className="rounded-lg border border-slate-200 bg-white p-3 text-xs">
                      <p className="font-medium text-slate-900">{field.name}</p>
                      <p className="mt-1 text-slate-500">{field.data_type}</p>
                      <p className="mt-1 text-slate-400">{field.nullable ? "Nullable" : "Required"}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </section>
  );
}
