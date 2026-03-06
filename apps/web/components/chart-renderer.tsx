"use client";

import ReactECharts from "echarts-for-react";

export function ChartRenderer({ chart }: { chart: Record<string, unknown> }) {
  const type = String(chart.type ?? "table");

  if (type === "kpi") {
    return (
      <div className="rounded-lg bg-slate-50 p-5">
        <p className="text-xs uppercase text-slate-500">{String(chart.metric ?? "Metric")}</p>
        <p className="mt-2 text-2xl font-semibold">{String(chart.value ?? "-")}</p>
      </div>
    );
  }

  if (type === "line" || type === "bar") {
    const series = (chart.series as Array<{ data: [string | number, string | number][]; name: string }>) ?? [];
    const firstSeries = series[0] ?? { data: [] };
    const xAxis = firstSeries.data.map((pair) => pair[0]);
    const yAxis = firstSeries.data.map((pair) => pair[1]);

    return (
      <ReactECharts
        style={{ height: 360 }}
        option={{
          grid: { left: 40, right: 20, top: 20, bottom: 40 },
          xAxis: { type: "category", data: xAxis },
          yAxis: { type: "value" },
          series: [{ type, data: yAxis, smooth: type === "line" }],
          tooltip: { trigger: "axis" },
        }}
      />
    );
  }

  const columns = (chart.columns as string[]) ?? [];
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border-collapse text-sm">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col} className="border-b border-slate-200 px-3 py-2 text-left text-slate-600">
                {col}
              </th>
            ))}
          </tr>
        </thead>
      </table>
      <p className="p-4 text-sm text-slate-500">Table output is available in rows payload.</p>
    </div>
  );
}
