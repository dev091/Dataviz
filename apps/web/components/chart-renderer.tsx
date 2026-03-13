"use client";

import ReactECharts from "echarts-for-react";
import * as echarts from "echarts";

import { buildChartOption } from "@platform/visuals";

type ChartPair = [string | number, string | number];

type ChartSeries = {
  name: string;
  data: Array<ChartPair | number[]>;
};

function seriesFromChart(chart: Record<string, unknown>): ChartSeries[] {
  return Array.isArray(chart.series) ? (chart.series as ChartSeries[]) : [];
}

export function ChartRenderer({ chart }: { chart: Record<string, unknown> }) {
  const type = String(chart.type ?? "table");

  const onEvents = {
    click: (params: unknown) => {
      console.log("Chart clicked:", params);
    },
  };

  if (type === "kpi") {
    return (
      <div className="relative overflow-hidden rounded-xl border border-slate-200/60 bg-white p-6 shadow-sm transition-all hover:shadow-md">
        <p className="text-sm font-medium uppercase tracking-wider text-slate-500">{String(chart.metric ?? "Metric")}</p>
        <div className="mt-3 flex items-baseline gap-2">
          <p className="text-3xl font-bold tracking-tight text-slate-900">{String(chart.value ?? "-")}</p>
          {chart.delta !== undefined ? (
            <span
              className={`rounded-full px-2 py-0.5 text-sm font-semibold ${String(chart.delta).startsWith("-") ? "bg-red-50 text-red-600" : "bg-emerald-50 text-emerald-600"}`}
            >
              {String(chart.delta).startsWith("-") ? "" : "+"}
              {String(chart.delta)}
            </span>
          ) : null}
        </div>
      </div>
    );
  }

  if (type === "kpi_sparkline") {
    const sparkData = Array.isArray(chart.trend) ? chart.trend : [];
    const isPositive = !String(chart.delta).startsWith("-");
    const color = isPositive ? "#10b981" : "#ef4444";

    return (
      <div className="relative flex h-[160px] flex-col justify-between overflow-hidden rounded-xl border border-slate-200/60 bg-white p-6 shadow-sm transition-all hover:shadow-md">
        <div className="relative z-10">
          <p className="text-sm font-medium uppercase tracking-wider text-slate-500">{String(chart.metric ?? "Metric")}</p>
          <div className="mt-2 flex items-baseline gap-2">
            <p className="text-3xl font-bold tracking-tight text-slate-900">{String(chart.value ?? "-")}</p>
            {chart.delta !== undefined ? (
              <span
                className={`rounded-full px-2 py-0.5 text-sm font-semibold ${isPositive ? "bg-emerald-50 text-emerald-600" : "bg-red-50 text-red-600"}`}
              >
                {isPositive ? "+" : ""}
                {String(chart.delta)}
              </span>
            ) : null}
          </div>
        </div>
        <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-16 opacity-40">
          <ReactECharts
            style={{ height: "100%", width: "100%" }}
            option={{
              grid: { left: -10, right: -10, top: 0, bottom: -10 },
              xAxis: { type: "category", show: false, boundaryGap: false },
              yAxis: { type: "value", show: false, min: "dataMin" },
              tooltip: { show: false },
              series: [
                {
                  type: "line",
                  data: sparkData.map((item) => (Array.isArray(item) ? item[1] : 0)),
                  smooth: 0.4,
                  symbol: "none",
                  lineStyle: { width: 2, color },
                  areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                      { offset: 0, color },
                      { offset: 1, color: "rgba(255,255,255,0)" },
                    ]),
                  },
                },
              ],
            }}
          />
        </div>
      </div>
    );
  }

  if (type === "progress_list") {
    const series = seriesFromChart(chart);
    const listData = (series[0]?.data ?? []).map((pair) => ({
      name: String(Array.isArray(pair) ? pair[0] : ""),
      value: Number(Array.isArray(pair) ? pair[1] : 0),
      delta: Array.isArray(pair) && pair[2] !== undefined ? String(pair[2]) : undefined,
    }));
    const maxValue = Math.max(...listData.map((item) => item.value), 1);

    return (
      <div className="flex h-full flex-col gap-4 overflow-y-auto py-2 pr-2">
        {listData.map((item, index) => (
          <div key={`${item.name}-${index}`} className="group flex flex-col gap-1.5">
            <div className="flex items-end justify-between text-sm">
              <span className="truncate pr-4 font-medium text-slate-700">{item.name}</span>
              <div className="flex shrink-0 items-center gap-3">
                <span className="font-semibold text-slate-900">{item.value.toLocaleString()}</span>
                {item.delta ? (
                  <span className={`w-16 text-right text-xs font-semibold ${item.delta.startsWith("-") ? "text-red-500" : "text-emerald-500"}`}>
                    {item.delta.startsWith("-") ? "" : "+"}
                    {item.delta}
                  </span>
                ) : null}
              </div>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-blue-500 transition-all duration-1000 ease-out group-hover:bg-blue-600"
                style={{ width: `${Math.max(2, (item.value / maxValue) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (type === "table") {
    const columns = (chart.columns as string[]) ?? [];
    const rows = (chart.rows as Array<Record<string, unknown>>) ?? [];
    return (
      <div className="h-full w-full overflow-auto">
        <table className="min-w-full border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-white/95 backdrop-blur">
            <tr>
              {columns.map((column) => (
                <th key={column} className="border-b-2 border-slate-200 px-4 py-3 text-left font-semibold text-slate-800">
                  {String(column).replace(/_/g, " ").toUpperCase()}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={`row-${rowIndex}`} className="group transition-colors hover:bg-slate-50/80">
                {columns.map((column) => {
                  const isNumeric = typeof row[column] === "number";
                  return (
                    <td
                      key={`${rowIndex}-${column}`}
                      className={`border-b border-slate-100 px-4 py-3 text-slate-700 ${isNumeric ? "font-mono font-medium" : ""}`}
                    >
                      {String(row[column] ?? "-")}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length ? (
          <div className="mt-2 flex items-center justify-center rounded border border-dashed border-slate-200 bg-slate-50/50 p-8 text-sm text-slate-500">
            No table rows configured.
          </div>
        ) : null}
      </div>
    );
  }

  const option = buildChartOption(chart);
  if (option) {
    return <ReactECharts style={{ height: "100%", width: "100%", minHeight: 180 }} option={option} onEvents={onEvents} />;
  }

  return (
    <div className="flex h-full min-h-[180px] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 text-center text-sm text-slate-500">
      Unsupported chart payload. Use the custom ECharts option editor for advanced visuals.
    </div>
  );
}
