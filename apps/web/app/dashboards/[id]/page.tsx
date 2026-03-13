"use client";

import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Layout, Responsive, WidthProvider } from "react-grid-layout";

import { Button, Card, CardContent, CardHeader, CardTitle, Input, Textarea } from "@/components/ui";

import { ChartRenderer } from "@/components/chart-renderer";
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

type WidgetPayload = {
  title: string;
  widget_type: string;
  config: Record<string, unknown>;
  position: { x: number; y: number; w: number; h: number };
};

type SemanticModelOption = {
  id: string;
  name: string;
  model_key: string;
};

type AutoComposeResponse = {
  dashboard_id: string;
  widgets_added: number;
  notes: string[];
};

type ReportPackSection = {
  title: string;
  body: string;
};

type ReportPack = {
  dashboard_id: string;
  dashboard_name: string;
  generated_at: string;
  audience: string;
  goal: string;
  executive_summary: string;
  sections: ReportPackSection[];
  next_actions: string[];
};

type ManualWidgetKind = "bar" | "line" | "area" | "donut" | "table" | "kpi" | "custom";

function parseCsvList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function widgetChart(widget: Widget): Record<string, unknown> {
  const embedded = widget.config.chart;
  if (embedded && typeof embedded === "object") {
    return embedded as Record<string, unknown>;
  }

  if (widget.widget_type === "table") {
    const rows = Array.isArray(widget.config.rows) ? (widget.config.rows as Array<Record<string, unknown>>) : [];
    const columns = Array.isArray(widget.config.columns)
      ? (widget.config.columns as string[])
      : rows[0]
        ? Object.keys(rows[0])
        : [];
    return { type: "table", columns, rows };
  }

  if (widget.widget_type === "kpi") {
    return {
      type: "kpi",
      metric: widget.config.metric,
      value: widget.config.value,
      delta: widget.config.delta,
    };
  }

  return { type: widget.widget_type };
}

export default function DashboardBuilderPage() {
  const params = useParams<{ id: string }>();
  const dashboardId = params?.id ?? "";
  const queryClient = useQueryClient();
  const lastResult = useNLStore((state) => state.lastResult);

  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [segmentFilter, setSegmentFilter] = useState("");
  const [widgetTitle, setWidgetTitle] = useState("Revenue Snapshot");
  const [widgetSummary, setWidgetSummary] = useState("Executive metric ready for dashboard review.");
  const [widgetKind, setWidgetKind] = useState<ManualWidgetKind>("bar");
  const [chartLabels, setChartLabels] = useState("North,South,West");
  const [chartValues, setChartValues] = useState("59800,30600,37100");
  const [tableColumns, setTableColumns] = useState("region,revenue,growth");
  const [tableRows, setTableRows] = useState("North,59800,12%\nSouth,30600,7%\nWest,37100,9%");
  const [kpiMetric, setKpiMetric] = useState("Revenue");
  const [kpiValue, setKpiValue] = useState("126500");
  const [kpiDelta, setKpiDelta] = useState("+9.4% vs prior period");
  const [customChartJson, setCustomChartJson] = useState('{"option":{"title":{"text":"Custom Widget"},"xAxis":{"type":"category","data":["A","B","C"]},"yAxis":{"type":"value"},"series":[{"type":"bar","data":[12,20,15]}]}}');
  const [autoComposeModelId, setAutoComposeModelId] = useState("");
  const [autoComposeGoal, setAutoComposeGoal] = useState("Executive overview with KPI, trend, mix, and detail widgets");
  const [reportAudience, setReportAudience] = useState("Executive leadership");
  const [reportGoal, setReportGoal] = useState("Board-ready summary with key changes, risks, and recommended actions");
  const [reportPack, setReportPack] = useState<ReportPack | null>(null);

  const dashboardQuery = useQuery({
    queryKey: ["dashboard", dashboardId],
    queryFn: () => apiRequest<DashboardDetails>(`/api/v1/dashboards/${dashboardId}`),
    enabled: Boolean(dashboardId),
  });

  const semanticModelsQuery = useQuery({
    queryKey: ["dashboard-builder", "semantic-models"],
    queryFn: () => apiRequest<SemanticModelOption[]>("/api/v1/semantic/models"),
  });

  const dashboard = dashboardQuery.data;
  const semanticModels = semanticModelsQuery.data ?? [];

  useEffect(() => {
    if (!autoComposeModelId && semanticModels[0]) {
      setAutoComposeModelId(semanticModels[0].id);
    }
  }, [autoComposeModelId, semanticModels]);

  const saveAIWidgetMutation = useMutation({
    mutationFn: () =>
      apiRequest(`/api/v1/dashboards/${dashboardId}/widgets/from-ai`, {
        method: "POST",
        body: JSON.stringify({
          ai_query_session_id: lastResult?.aiQuerySessionId,
          title: "AI Insight Widget",
          position: { x: 0, y: 0, w: 6, h: 4 },
        }),
      }),
    onSuccess: async () => {
      setNotice("AI result saved to dashboard.");
      await queryClient.invalidateQueries({ queryKey: ["dashboard", dashboardId] });
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Failed to save AI widget");
    },
  });

  const addWidgetMutation = useMutation({
    mutationFn: (payload: WidgetPayload) =>
      apiRequest(`/api/v1/dashboards/${dashboardId}/widgets`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: async () => {
      setNotice("Widget added to dashboard.");
      await queryClient.invalidateQueries({ queryKey: ["dashboard", dashboardId] });
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Failed to add widget");
    },
  });

  const autoComposeMutation = useMutation({
    mutationFn: () =>
      apiRequest<AutoComposeResponse>(`/api/v1/dashboards/${dashboardId}/auto-compose`, {
        method: "POST",
        body: JSON.stringify({
          semantic_model_id: autoComposeModelId,
          goal: autoComposeGoal,
          max_widgets: 6,
        }),
      }),
    onSuccess: async (payload) => {
      const summary = payload.notes.length ? ` ${payload.notes.join(" ")}` : "";
      setNotice(`Auto-composed ${payload.widgets_added} widgets.${summary}`);
      await queryClient.invalidateQueries({ queryKey: ["dashboard", dashboardId] });
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Failed to auto-compose dashboard");
    },
  });

  const deleteWidgetMutation = useMutation({
    mutationFn: (widgetId: string) =>
      apiRequest<void>(`/api/v1/dashboards/${dashboardId}/widgets/${widgetId}`, {
        method: "DELETE",
      }),
    onSuccess: async () => {
      setNotice("Widget removed.");
      await queryClient.invalidateQueries({ queryKey: ["dashboard", dashboardId] });
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Failed to delete widget");
    },
  });

  const reportPackMutation = useMutation({
    mutationFn: () =>
      apiRequest<ReportPack>(`/api/v1/dashboards/${dashboardId}/report-pack`, {
        method: "POST",
        body: JSON.stringify({
          audience: reportAudience,
          goal: reportGoal,
        }),
      }),
    onSuccess: (payload) => {
      setReportPack(payload);
      setNotice("AI report pack generated.");
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Failed to generate report pack");
    },
  });

  const layouts = useMemo(() => {
    const list = dashboard?.widgets ?? [];
    return {
      lg: list.map((widget) => ({ i: widget.id, ...widget.position })),
      md: list.map((widget) => ({ i: widget.id, ...widget.position })),
      sm: list.map((widget) => ({ i: widget.id, ...widget.position })),
    };
  }, [dashboard]);

  function buildManualWidgetPayload(): WidgetPayload {
    const y = (dashboard?.widgets.length ?? 0) * 4;

    if (["bar", "line", "area", "donut"].includes(widgetKind)) {
      const labels = parseCsvList(chartLabels);
      const numericValues = parseCsvList(chartValues).map((item) => Number(item));
      return {
        title: widgetTitle,
        widget_type: widgetKind,
        position: { x: 0, y, w: 6, h: 4 },
        config: {
          summary: widgetSummary,
          chart: {
            type: widgetKind,
            series: [
              {
                name: widgetTitle,
                data: labels.map((label, index) => [label, Number.isFinite(numericValues[index]) ? numericValues[index] : 0]),
              },
            ],
          },
        },
      };
    }

    if (widgetKind === "table") {
      const columns = parseCsvList(tableColumns);
      const rows = tableRows
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
          const values = line.split(",").map((item) => item.trim());
          return columns.reduce<Record<string, string>>((acc, column, index) => {
            acc[column] = values[index] ?? "";
            return acc;
          }, {});
        });

      return {
        title: widgetTitle,
        widget_type: "table",
        position: { x: 0, y, w: 8, h: 4 },
        config: {
          summary: widgetSummary,
          chart: {
            type: "table",
            columns,
            rows,
          },
        },
      };
    }

    if (widgetKind === "custom") {
      let parsed: unknown;
      try {
        parsed = JSON.parse(customChartJson);
      } catch {
        throw new Error("Custom chart JSON is invalid.");
      }
      const chart = parsed && typeof parsed === "object" && "option" in (parsed as Record<string, unknown>)
        ? (parsed as Record<string, unknown>)
        : { type: "custom", option: parsed as Record<string, unknown> };

      return {
        title: widgetTitle,
        widget_type: "custom",
        position: { x: 0, y, w: 8, h: 5 },
        config: {
          summary: widgetSummary,
          chart,
        },
      };
    }

    return {
      title: widgetTitle,
      widget_type: "kpi",
      position: { x: 0, y, w: 4, h: 3 },
      config: {
        summary: widgetSummary,
        chart: {
          type: "kpi",
          metric: kpiMetric,
          value: kpiValue,
          delta: kpiDelta,
        },
      },
    };
  }

  async function saveLastAIResult() {
    if (!lastResult) {
      setError("Run NL analytics first to save an AI widget.");
      return;
    }
    setError(null);
    setNotice(null);
    await saveAIWidgetMutation.mutateAsync();
  }

  async function addManualWidget() {
    setError(null);
    setNotice(null);
    try {
      await addWidgetMutation.mutateAsync(buildManualWidgetPayload());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add widget");
    }
  }

  async function persistLayout(currentLayout: Layout[]) {
    if (!dashboard) {
      return;
    }

    const changedWidgets = currentLayout
      .map((item) => {
        const widget = dashboard.widgets.find((entry) => entry.id === item.i);
        if (!widget) {
          return null;
        }
        const nextPosition = { x: item.x, y: item.y, w: item.w, h: item.h };
        const unchanged =
          widget.position.x === nextPosition.x &&
          widget.position.y === nextPosition.y &&
          widget.position.w === nextPosition.w &&
          widget.position.h === nextPosition.h;
        if (unchanged) {
          return null;
        }
        return { widget, nextPosition };
      })
      .filter((item): item is { widget: Widget; nextPosition: Widget["position"] } => Boolean(item));

    if (!changedWidgets.length) {
      return;
    }

    setError(null);
    setNotice(null);
    try {
      await Promise.all(
        changedWidgets.map(({ widget, nextPosition }) =>
          apiRequest(`/api/v1/dashboards/${dashboardId}/widgets/${widget.id}`, {
            method: "PUT",
            body: JSON.stringify({
              title: widget.title,
              widget_type: widget.widget_type,
              config: widget.config,
              position: nextPosition,
            }),
          }),
        ),
      );
      setNotice("Dashboard layout saved.");
      await queryClient.invalidateQueries({ queryKey: ["dashboard", dashboardId] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save layout");
    }
  }

  if (dashboardQuery.isLoading) {
    return <p className="text-sm text-slate-600">Loading dashboard...</p>;
  }

  if (!dashboard) {
    return <p className="text-sm text-red-600">Dashboard not found.</p>;
  }

  return (
    <section className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">{dashboard.name}</h2>
          <p className="text-sm text-slate-500">Drag widgets, auto-compose governed dashboards, save AI results, and author advanced ECharts widgets directly.</p>
        </div>
        <Button onClick={saveLastAIResult} disabled={saveAIWidgetMutation.isPending || !lastResult}>
          {saveAIWidgetMutation.isPending ? "Saving..." : "Add last AI result"}
        </Button>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {notice ? <p className="text-sm text-emerald-700">{notice}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle>Auto Dashboard Composer</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            <select className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={autoComposeModelId} onChange={(e) => setAutoComposeModelId(e.target.value)}>
              <option value="">Select semantic model</option>
              {semanticModels.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                </option>
              ))}
            </select>
            <Input 
              list="goal-presets"
              value={autoComposeGoal} 
              onChange={(e) => setAutoComposeGoal(e.target.value)} 
              placeholder="e.g., Sales Pipeline Analysis, HR Headcount" 
            />
            <datalist id="goal-presets">
              <option value="Executive overview, metrics and trend" />
              <option value="Sales Pipeline Analysis" />
              <option value="Marketing Campaign KPIs" />
              <option value="HR Headcount & Skills Radar" />
            </datalist>
            <Button onClick={() => autoComposeMutation.mutate()} disabled={autoComposeMutation.isPending || !autoComposeModelId}>
              {autoComposeMutation.isPending ? "Composing..." : "Auto-compose dashboard"}
            </Button>
          </div>
          <p className="text-xs text-slate-500">Auto-routes to department-specific layouts (Tableau/PowerBI level) based on the specified goal context (Sales, HR, Marketing, Exec).</p>
        </CardContent>
      </Card>

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
          <CardTitle>Manual Widget Studio</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            <Input value={widgetTitle} onChange={(e) => setWidgetTitle(e.target.value)} placeholder="Widget title" />
            <select className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={widgetKind} onChange={(e) => setWidgetKind(e.target.value as ManualWidgetKind)}>
              <option value="bar">Bar chart</option>
              <option value="line">Line chart</option>
              <option value="area">Area chart</option>
              <option value="donut">Donut chart</option>
              <option value="table">Table widget</option>
              <option value="kpi">KPI card</option>
              <option value="custom">Custom ECharts</option>
            </select>
            <Button onClick={addManualWidget} disabled={addWidgetMutation.isPending}>
              {addWidgetMutation.isPending ? "Adding..." : "Add widget"}
            </Button>
          </div>
          <Textarea
            className="min-h-20 w-full"
            value={widgetSummary}
            onChange={(e) => setWidgetSummary(e.target.value)}
            placeholder="Executive summary for this widget"
          />

          {(["bar", "line", "area", "donut"] as ManualWidgetKind[]).includes(widgetKind) ? (
            <div className="grid gap-3 md:grid-cols-2">
              <Textarea
                className="min-h-24"
                value={chartLabels}
                onChange={(e) => setChartLabels(e.target.value)}
                placeholder="North,South,West"
              />
              <Textarea
                className="min-h-24"
                value={chartValues}
                onChange={(e) => setChartValues(e.target.value)}
                placeholder="59800,30600,37100"
              />
            </div>
          ) : null}

          {widgetKind === "table" ? (
            <div className="grid gap-3 md:grid-cols-2">
              <Textarea
                className="min-h-24"
                value={tableColumns}
                onChange={(e) => setTableColumns(e.target.value)}
                placeholder="region,revenue,growth"
              />
              <Textarea
                className="min-h-24"
                value={tableRows}
                onChange={(e) => setTableRows(e.target.value)}
                placeholder="North,59800,12%"
              />
            </div>
          ) : null}

          {widgetKind === "kpi" ? (
            <div className="grid gap-3 md:grid-cols-3">
              <Input value={kpiMetric} onChange={(e) => setKpiMetric(e.target.value)} placeholder="Revenue" />
              <Input value={kpiValue} onChange={(e) => setKpiValue(e.target.value)} placeholder="126500" />
              <Input value={kpiDelta} onChange={(e) => setKpiDelta(e.target.value)} placeholder="+9.4% vs prior period" />
            </div>
          ) : null}

          {widgetKind === "custom" ? (
            <Textarea
              className="min-h-52 w-full font-mono text-xs"
              value={customChartJson}
              onChange={(e) => setCustomChartJson(e.target.value)}
              placeholder='{"option": {"series": [{"type": "bar", "data": [1,2,3]}]}}'
            />
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>AI Report Pack</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <Input value={reportAudience} onChange={(e) => setReportAudience(e.target.value)} placeholder="Executive leadership" />
            <Input value={reportGoal} onChange={(e) => setReportGoal(e.target.value)} placeholder="Board-ready summary, risk review, operating cadence..." />
          </div>
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-slate-500">Generates an executive narrative, section summaries, and suggested next actions from the current dashboard state.</p>
            <Button onClick={() => reportPackMutation.mutate()} disabled={reportPackMutation.isPending}>
              {reportPackMutation.isPending ? "Generating..." : "Generate AI report pack"}
            </Button>
          </div>

          {reportPack ? (
            <div className="space-y-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div className="space-y-1">
                <p className="text-sm font-semibold">{reportPack.dashboard_name}</p>
                <p className="text-xs text-slate-500">
                  Audience: {reportPack.audience} | Generated: {new Date(reportPack.generated_at).toLocaleString()}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Executive Summary</p>
                <p className="mt-2 text-sm text-slate-700">{reportPack.executive_summary}</p>
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                {reportPack.sections.map((section) => (
                  <div key={section.title} className="rounded-md border border-slate-200 bg-white p-3">
                    <p className="text-sm font-semibold">{section.title}</p>
                    <p className="mt-2 text-xs leading-6 text-slate-600">{section.body}</p>
                  </div>
                ))}
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Suggested Next Actions</p>
                <ul className="mt-2 space-y-2 text-sm text-slate-700">
                  {reportPack.next_actions.map((action) => (
                    <li key={action} className="rounded-md border border-slate-200 bg-white px-3 py-2">
                      {action}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : (
            <Textarea
              readOnly
              value="No report pack generated yet. Build the dashboard, then generate an executive-ready AI narrative pack."
              className="min-h-24 resize-none bg-slate-50"
            />
          )}
        </CardContent>
      </Card>

      <div className="-mx-4 -mb-8 mt-8 border-t border-slate-200 bg-slate-100/50 px-4 py-8 shadow-inner sm:-mx-8 sm:px-8">
        <div className="mb-6 flex items-center justify-between">
          <h3 className="text-xl font-bold tracking-tight text-slate-900">Executive Dashboard View</h3>
          <p className="text-sm font-medium text-slate-500">Live Grid Engine</p>
        </div>
        {!dashboard.widgets.length ? (
          <div className="flex min-h-[400px] items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50">
            <p className="text-sm text-slate-500">No widgets yet. Add a manual widget, auto-compose from a semantic model, or save an AI result.</p>
          </div>
        ) : null}
        <ResponsiveGridLayout
          className="layout -mx-2"
          layouts={layouts}
          breakpoints={{ lg: 1200, md: 996, sm: 768 }}
          cols={{ lg: 12, md: 10, sm: 6 }}
          rowHeight={60}
          draggableHandle=".drag-handle"
          isDraggable
          isResizable
          margin={[16, 16]}
          onDragStop={(layout) => {
            void persistLayout(layout);
          }}
          onResizeStop={(layout) => {
            void persistLayout(layout);
          }}
        >
          {dashboard.widgets.map((widget) => (
            <div key={widget.id} className="group relative flex h-full flex-col overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-sm transition-shadow hover:shadow-md">
              <div className="drag-handle flex cursor-move items-center justify-between border-b border-slate-100 bg-white px-4 py-3 hover:bg-slate-50">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-blue-500"></span>
                  <p className="text-sm font-bold text-slate-800">{widget.title}</p>
                </div>
                <Button 
                  variant="ghost" 
                  size="sm"
                  className="h-6 origin-right scale-0 px-2 text-xs text-slate-400 opacity-0 transition-all group-hover:scale-100 group-hover:opacity-100 hover:bg-red-50 hover:text-red-700"
                  onMouseDown={(e) => e.stopPropagation()}
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteWidgetMutation.mutate(widget.id);
                  }} 
                  disabled={deleteWidgetMutation.isPending}
                >
                  Remove
                </Button>
              </div>
              <div className="relative flex-1 p-2 overflow-hidden bg-transparent">
                <ChartRenderer chart={widgetChart(widget)} />
              </div>
            </div>
          ))}
        </ResponsiveGridLayout>
      </div>
    </section>
  );
}


