"use client";

import { useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@platform/ui";

import { apiRequest } from "@/lib/api";

type AuditLog = {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  user_id?: string;
  created_at: string;
  metadata: Record<string, unknown>;
};

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await apiRequest<AuditLog[]>("/api/v1/admin/audit-logs");
        setLogs(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load audit logs");
      }
    }
    void load();
  }, []);

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Audit Log</h2>
        <p className="text-sm text-slate-500">Track critical actions across connectors, semantic changes, AI queries, and alerts.</p>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle>Recent events</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {logs.map((log) => (
              <div key={log.id} className="rounded-md border border-slate-200 p-3">
                <p className="text-sm font-medium">{log.action}</p>
                <p className="text-xs text-slate-500">
                  {log.entity_type} ({log.entity_id}) by {log.user_id ?? "system"}
                </p>
                <p className="mt-1 text-xs text-slate-600">{new Date(log.created_at).toLocaleString()}</p>
              </div>
            ))}
            {!logs.length ? <p className="text-sm text-slate-500">No audit events yet.</p> : null}
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
