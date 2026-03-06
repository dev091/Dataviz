"use client";

import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Responsive, WidthProvider } from "react-grid-layout";

import { Button, Card, CardContent, CardHeader, CardTitle, Input } from "@platform/ui";

import { apiRequest } from "@/lib/api";
import { useNLStore } from "@/store/nl-store";

const ResponsiveGridLayout = WidthProvider(Responsive);

type Widget = {
  id: string;
  title: string;
  widget_type: string;
  config: Record<string, unknown>;
  position: { x: number; y: number; w: number; h: number };
};

type DashboardDetails = {
  id: string;
  name: string;
  description?: string;
  widgets: Widget[];
};

export default function DashboardBuilderPage() {
  const params = useParams<{ id: string }>();
  const dashboardId = params.id;
  const [dashboard, setDashboard] = useState<DashboardDetails | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [segmentFilter, setSegmentFilter] = useState("");
  const lastResult = useNLStore((state) => state.lastResult);

  async function load() {
    try {
      const data = await apiRequest<DashboardDetails>(`/api/v1/dashboards/${dashboardId}`);
      setDashboard(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    }
  }

  useEffect(() => {
    if (!dashboardId) {
      return;
    }
    void load();
    // load depends on the current dynamic dashboard route.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dashboardId]);

  async function saveLastAIResult() {
    if (!lastResult) {
      setError("Run NL analytics first to save an AI widget.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await apiRequest(`/api/v1/dashboards/${dashboardId}/widgets/from-ai`, {
        method: "POST",
        body: JSON.stringify({
          ai_query_session_id: lastResult.aiQuerySessionId,
          title: "AI Insight Widget",
          position: { x: 0, y: 0, w: 6, h: 4 },
        }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save AI widget");
    } finally {
      setLoading(false);
    }
  }

  const layouts = useMemo(() => {
    const list = dashboard?.widgets ?? [];
    return {
      lg: list.map((widget) => ({ i: widget.id, ...widget.position })),
      md: list.map((widget) => ({ i: widget.id, ...widget.position })),
      sm: list.map((widget) => ({ i: widget.id, ...widget.position })),
    };
  }, [dashboard]);

  if (!dashboard) {
    return <p className="text-sm text-slate-600">Loading dashboard...</p>;
  }

  return (
    <section className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold">{dashboard.name}</h2>
          <p className="text-sm text-slate-500">Drag-and-drop report layout builder.</p>
        </div>
        <Button onClick={saveLastAIResult} disabled={loading}>
          {loading ? "Saving..." : "Add last AI result"}
        </Button>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle>Global Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-3">
            <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            <Input value={segmentFilter} onChange={(e) => setSegmentFilter(e.target.value)} placeholder="Region/Product filter" />
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Active filter context: {dateFrom || "Any start"} to {dateTo || "Any end"}; segment: {segmentFilter || "All"}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Report View Mode</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveGridLayout
            className="layout"
            layouts={layouts}
            breakpoints={{ lg: 1200, md: 996, sm: 768 }}
            cols={{ lg: 12, md: 10, sm: 6 }}
            rowHeight={42}
            isDraggable
            isResizable
          >
            {dashboard.widgets.map((widget) => (
              <div key={widget.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-sm font-semibold">{widget.title}</p>
                <p className="mt-1 text-xs text-slate-500">Type: {widget.widget_type}</p>
                <p className="mt-2 line-clamp-6 text-xs text-slate-600">{String(widget.config.summary ?? "Widget saved")}</p>
              </div>
            ))}
          </ResponsiveGridLayout>
        </CardContent>
      </Card>
    </section>
  );
}
