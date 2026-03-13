"use client";

import { FormEvent, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, EmptyState, EmptyStateBody, EmptyStateTitle, Input, Skeleton } from "@/components/ui";

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

type ConnectorType = "file_upload" | "postgresql" | "mysql" | "google_sheets" | "salesforce";

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
  { value: "file_upload", label: "File Upload", description: "Upload CSV, TSV, JSON, Excel, Parquet, ODS, XML, or text files for governed ingestion." },
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
  if (value === "csv" || value === "file_upload") return "File Upload";
  return connectorOptions.find((option) => option.value === value)?.label ?? value;
}

function toneForStatus(status: string): "default" | "success" | "warning" | "danger" {
  if (status === "success" || status === "ready") return "success";
  if (status === "running") return "warning";
  if (status === "failed") return "danger";
  return "default";
}

export default function ConnectionsPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("Revenue Source");
  const [connectorType, setConnectorType] = useState<ConnectorType>("file_upload");
  const [forms, setForms] = useState<ConnectorForms>(initialForms);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [preview, setPreview] = useState<SchemaPreview | null>(null);
  const [activeLogConnectionId, setActiveLogConnectionId] = useState<string | null>(null);

  const connectionsQuery = useQuery({
    queryKey: ["connections"],
    queryFn: () => apiRequest<Connection[]>("/api/v1/connections"),
  });

  const syncRunsQuery = useQuery({
    queryKey: ["sync-runs", activeLogConnectionId],
    enabled: Boolean(activeLogConnectionId),
    queryFn: () => apiRequest<SyncRun[]>(`/api/v1/connections/${activeLogConnectionId}/sync-runs`),
  });

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
    if (connectorType === "file_upload") {
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

  const refreshConnections = async () => {
    await queryClient.invalidateQueries({ queryKey: ["connections"] });
    if (activeLogConnectionId) {
      await queryClient.invalidateQueries({ queryKey: ["sync-runs", activeLogConnectionId] });
    }
  };

  const createConnection = useMutation({
    mutationFn: async () => {
      let config = buildConfig();
      if (connectorType === "file_upload") {
        if (!uploadedFile) {
          throw new Error("Please upload a supported file first.");
        }
        const body = new FormData();
        body.append("file", uploadedFile);
        const upload = await apiRequest<{ file_path: string; file_name: string; file_format: string }>(
          "/api/v1/connections/files/upload",
          { method: "POST", body },
          { withAuth: true, workspaceScoped: true },
        );
        config = { file_path: upload.file_path, file_format: upload.file_format };
      }

      return apiRequest("/api/v1/connections", {
        method: "POST",
        body: JSON.stringify({ name, connector_type: connectorType, config }),
      });
    },
    onSuccess: async () => {
      setPageError(null);
      setPreview(null);
      await refreshConnections();
    },
    onError: (error) => setPageError(error instanceof Error ? error.message : "Failed to create connection"),
  });

  const discoverConnection = useMutation({
    mutationFn: (connectionId: string) => apiRequest<SchemaPreview>(`/api/v1/connections/${connectionId}/discover`, { method: "POST" }),
    onSuccess: (data) => {
      setPageError(null);
      setPreview(data);
    },
    onError: (error) => setPageError(error instanceof Error ? error.message : "Failed to discover schema"),
  });

  const syncConnection = useMutation({
    mutationFn: (connectionId: string) => apiRequest(`/api/v1/connections/${connectionId}/sync`, { method: "POST" }),
    onSuccess: async (_, connectionId) => {
      setPageError(null);
      setActiveLogConnectionId(connectionId);
      await refreshConnections();
    },
    onError: (error) => setPageError(error instanceof Error ? error.message : "Failed to sync connection"),
  });

  const scheduleWeekly = useMutation({
    mutationFn: (connectionId: string) =>
      apiRequest(`/api/v1/connections/${connectionId}/sync-jobs`, {
        method: "POST",
        body: JSON.stringify({ schedule_type: "weekly", schedule_time: "09:00", weekday: 1 }),
      }),
    onSuccess: async () => {
      setPageError(null);
      await refreshConnections();
    },
    onError: (error) => setPageError(error instanceof Error ? error.message : "Failed to update schedule"),
  });

  function renderConnectorForm() {
    if (connectorType === "file_upload") {
      return (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/80 p-4">
          <p className="mb-3 text-sm font-medium text-slate-700">Local file source</p>
          <input type="file" accept=".csv,.tsv,.txt,.json,.jsonl,.ndjson,.xlsx,.xls,.ods,.parquet,.xml" onChange={(event) => setUploadedFile(event.target.files?.[0] ?? null)} />
          <p className="mt-2 text-xs text-slate-500">Upload common analyst file formats directly. Supported: CSV, TSV, TXT, JSON, JSONL, Excel, ODS, Parquet, and XML.</p>
        </div>
      );
    }

    if (connectorType === "postgresql") {
      return (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="md:col-span-2">
            <label className="mb-1 block text-sm text-slate-600">Connection URI</label>
            <Input value={forms.postgresql.uri} onChange={(event) => setConnectorField("postgresql", "uri", event.target.value)} />
          </div>
        </div>
      );
    }

    if (connectorType === "mysql") {
      return (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="md:col-span-2">
            <label className="mb-1 block text-sm text-slate-600">Connection URI</label>
            <Input value={forms.mysql.uri} onChange={(event) => setConnectorField("mysql", "uri", event.target.value)} />
          </div>
        </div>
      );
    }

    if (connectorType === "google_sheets") {
      return (
        <div className="grid grid-cols-1 gap-3">
          <div>
            <label className="mb-1 block text-sm text-slate-600">Published CSV export URL</label>
            <Input value={forms.google_sheets.csv_export_url} onChange={(event) => setConnectorField("google_sheets", "csv_export_url", event.target.value)} />
          </div>
        </div>
      );
    }

    return (
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm text-slate-600">Username</label>
          <Input value={forms.salesforce.username} onChange={(event) => setConnectorField("salesforce", "username", event.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-sm text-slate-600">Password</label>
          <Input type="password" value={forms.salesforce.password} onChange={(event) => setConnectorField("salesforce", "password", event.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-sm text-slate-600">Security token</label>
          <Input type="password" value={forms.salesforce.security_token} onChange={(event) => setConnectorField("salesforce", "security_token", event.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-sm text-slate-600">Domain</label>
          <select className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" value={forms.salesforce.domain} onChange={(event) => setConnectorField("salesforce", "domain", event.target.value)}>
            <option value="login">Production</option>
            <option value="test">Sandbox</option>
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="mb-1 block text-sm text-slate-600">Object name</label>
          <Input value={forms.salesforce.object_name} onChange={(event) => setConnectorField("salesforce", "object_name", event.target.value)} placeholder="Opportunity" />
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
          <form
            className="space-y-4"
            onSubmit={(event: FormEvent) => {
              event.preventDefault();
              createConnection.mutate();
            }}
          >
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div>
                <label className="mb-1 block text-sm text-slate-600">Connection name</label>
                <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Revenue Source" />
              </div>
              <div>
                <label className="mb-1 block text-sm text-slate-600">Connector</label>
                <select className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" value={connectorType} onChange={(event) => setConnectorType(event.target.value as ConnectorType)}>
                  {connectorOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-end">
                <Button type="submit" className="w-full" disabled={createConnection.isPending}>
                  {createConnection.isPending ? "Creating..." : "Create connection"}
                </Button>
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white/70 p-4">
              <p className="text-sm font-medium text-slate-900">{activeOption.label}</p>
              <p className="mt-1 text-sm text-slate-500">{activeOption.description}</p>
              <div className="mt-4">{renderConnectorForm()}</div>
            </div>
          </form>
          {pageError ? <p className="mt-3 text-sm text-red-600">{pageError}</p> : null}
          {connectionsQuery.error ? <p className="mt-3 text-sm text-red-600">{connectionsQuery.error instanceof Error ? connectionsQuery.error.message : "Failed to load connections"}</p> : null}
        </CardContent>
      </Card>

      {connectionsQuery.isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      ) : null}

      <div className="space-y-3">
        {(connectionsQuery.data ?? []).map((connection) => (
          <Card key={connection.id}>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <CardTitle>{connection.name}</CardTitle>
                <Badge tone={toneForStatus(connection.status)}>{connection.status}</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="mb-3 flex flex-wrap gap-4 text-xs text-slate-500">
                <span>Type: {connectorLabel(connection.connector_type)}</span>
                <span>Frequency: {connection.sync_frequency}</span>
                <span>Last sync: {connection.last_synced_at ?? "Never"}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" disabled={discoverConnection.isPending} onClick={() => discoverConnection.mutate(connection.id)}>
                  Discover schema
                </Button>
                <Button variant="secondary" disabled={syncConnection.isPending} onClick={() => syncConnection.mutate(connection.id)}>
                  Manual sync
                </Button>
                <Button variant="ghost" disabled={scheduleWeekly.isPending} onClick={() => scheduleWeekly.mutate(connection.id)}>
                  Set weekly sync
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setActiveLogConnectionId(connection.id);
                    void queryClient.invalidateQueries({ queryKey: ["sync-runs", connection.id] });
                  }}
                >
                  View sync logs
                </Button>
              </div>

              {activeLogConnectionId === connection.id && syncRunsQuery.data?.length ? (
                <div className="mt-3 space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs">
                  {syncRunsQuery.data.map((run) => (
                    <div key={run.id} className="rounded-lg border border-slate-200 bg-white p-3">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-medium">
                          {run.status.toUpperCase()} - {run.records_synced} records
                        </p>
                        <Badge tone={toneForStatus(run.status)}>{run.status}</Badge>
                      </div>
                      <p className="mt-1 text-slate-500">Started: {new Date(run.started_at).toLocaleString()}</p>
                      <p className="text-slate-500">{run.message ?? "No errors"}</p>
                    </div>
                  ))}
                </div>
              ) : null}
            </CardContent>
          </Card>
        ))}
      </div>

      {!connectionsQuery.isLoading && !connectionsQuery.data?.length ? (
        <EmptyState>
          <EmptyStateTitle>No connections yet</EmptyStateTitle>
          <EmptyStateBody>Add a connector to start schema discovery, sync, and semantic modeling.</EmptyStateBody>
        </EmptyState>
      ) : null}

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
                  <Badge tone="default">{dataset.fields.length} fields</Badge>
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


