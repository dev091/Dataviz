"use client";

import { useQuery } from "@tanstack/react-query";
import { Badge, Card, CardContent, CardHeader, CardTitle, EmptyState, EmptyStateBody, EmptyStateTitle, Skeleton } from "@/components/ui";

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

function toneForAction(action: string): "default" | "success" | "warning" | "danger" {
  if (action.includes("delivered") || action.includes("create") || action.includes("execute")) return "success";
  if (action.includes("failed") || action.includes("delete")) return "danger";
  return "default";
}

export default function AuditPage() {
  const logsQuery = useQuery({
    queryKey: ["audit-logs"],
    queryFn: () => apiRequest<AuditLog[]>("/api/v1/admin/audit-logs"),
  });

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">Audit Log</h2>
        <p className="text-sm text-slate-500">Track critical actions across connectors, semantic changes, AI queries, scheduling, and governance events.</p>
      </div>

      {logsQuery.error ? <p className="text-sm text-red-600">{logsQuery.error instanceof Error ? logsQuery.error.message : "Failed to load audit logs"}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle>Recent events</CardTitle>
        </CardHeader>
        <CardContent>
          {logsQuery.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-20" />
              <Skeleton className="h-20" />
              <Skeleton className="h-20" />
            </div>
          ) : null}

          <div className="space-y-2">
            {(logsQuery.data ?? []).map((log) => (
              <div key={log.id} className="rounded-xl border border-slate-200 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium">{log.action}</p>
                  <Badge tone={toneForAction(log.action)}>{log.entity_type}</Badge>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {log.entity_id} by {log.user_id ?? "system"}
                </p>
                <p className="mt-2 text-xs text-slate-600">{new Date(log.created_at).toLocaleString()}</p>
              </div>
            ))}
            {!logsQuery.isLoading && !logsQuery.data?.length ? (
              <EmptyState>
                <EmptyStateTitle>No audit events yet</EmptyStateTitle>
                <EmptyStateBody>Critical workspace actions will appear here as the team connects data and builds analytics assets.</EmptyStateBody>
              </EmptyState>
            ) : null}
          </div>
        </CardContent>
      </Card>
    </section>
  );
}

