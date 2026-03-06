"use client";

import { FormEvent, useMemo, useState } from "react";

import { Button, Card, CardContent, CardHeader, CardTitle, Input } from "@platform/ui";

import { apiRequest } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

export default function WorkspacesPage() {
  const { workspaces, currentWorkspaceId, selectWorkspace } = useAuthStore();
  const [name, setName] = useState("Regional Ops");
  const [key, setKey] = useState("regional_ops");
  const [error, setError] = useState<string | null>(null);

  const organizationId = useMemo(() => workspaces[0]?.organization_id ?? "", [workspaces]);

  async function createWorkspace(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await apiRequest("/api/v1/workspaces", {
        method: "POST",
        body: JSON.stringify({ organization_id: organizationId, name, key }),
      });
      window.location.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create workspace");
    }
  }

  return (
    <section className="space-y-4">
      <h2 className="text-xl font-semibold">Workspace Selection</h2>
      <div className="grid gap-3 md:grid-cols-2">
        {workspaces.map((workspace) => (
          <button
            key={workspace.workspace_id}
            type="button"
            onClick={() => selectWorkspace(workspace.workspace_id)}
            className={`panel p-4 text-left transition ${workspace.workspace_id === currentWorkspaceId ? "ring-2 ring-brand-500" : "hover:border-slate-300"}`}
          >
            <p className="text-sm text-slate-500">{workspace.organization_name}</p>
            <p className="text-base font-semibold">{workspace.workspace_name}</p>
            <p className="text-xs text-slate-500">Role: {workspace.role}</p>
          </button>
        ))}
      </div>

      {organizationId ? (
        <Card>
          <CardHeader>
            <CardTitle>Create workspace</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="grid grid-cols-1 gap-3 md:grid-cols-3" onSubmit={createWorkspace}>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Workspace name" />
              <Input value={key} onChange={(e) => setKey(e.target.value)} placeholder="workspace_key" />
              <Button type="submit">Create</Button>
            </form>
            {error ? <p className="mt-2 text-sm text-red-600">{error}</p> : null}
          </CardContent>
        </Card>
      ) : null}

      {workspaces.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No workspaces</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-slate-600">Create an account first to provision your first organization and workspace.</p>
          </CardContent>
        </Card>
      ) : null}
    </section>
  );
}
