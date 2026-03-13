"use client";

import ReactECharts from "echarts-for-react";
import * as echarts from 'echarts/core';

type ChartPair = [string | number, string | number];
type ScatterPoint = [number, number, string?];

type ChartSeries = {
  name: string;
  data: Array<ChartPair | ScatterPoint>;
};

function seriesFromChart(chart: Record<string, unknown>): ChartSeries[] {
  return Array.isArray(chart.series) ? (chart.series as ChartSeries[]) : [];
}

export function ChartRenderer({ chart }: { chart: Record<string, unknown> }) {
  const type = String(chart.type ?? "table");
  
  const onEvents = {
    click: (params: any) => {
      console.log('Chart clicked:', params);
      // In a real Tableau-like setup, this would dispatch a global cross-filter context
    }
  };

  if (chart.option && typeof chart.option === "object") {
    return <ReactECharts style={{ height: '100%', width: '100%', minHeight: 180 }} option={chart.option as Record<string, unknown>} onEvents={onEvents} />;
  }

  if (type === "kpi") {
    return (
      <div className="relative overflow-hidden rounded-xl bg-white border border-slate-200/60 p-6 shadow-sm transition-all hover:shadow-md">
        <p className="text-sm font-medium uppercase tracking-wider text-slate-500">{String(chart.metric ?? "Metric")}</p>
        <div className="mt-3 flex items-baseline gap-2">
           <p className="text-3xl font-bold tracking-tight text-slate-900">{String(chart.value ?? "-")}</p>
           {chart.delta !== undefined ? (
             <span className={`text-sm font-semibold px-2 py-0.5 rounded-full ${String(chart.delta).startsWith('-') ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-600'}`}>
               {String(chart.delta).startsWith('-') ? '' : '+'}{String(chart.delta)}
             </span>
           ) : null}
        </div>
      </div>
    );
  }

  if (type === "kpi_sparkline") {
    const sparkData = Array.isArray(chart.trend) ? chart.trend : [];
    const isPositive = !String(chart.delta).startsWith('-');
    const color = isPositive ? '#10b981' : '#ef4444';
    
    return (
      <div className="relative overflow-hidden rounded-xl bg-white border border-slate-200/60 p-6 shadow-sm transition-all hover:shadow-md flex flex-col justify-between h-[160px]">
        <div className="z-10 relative">
          <p className="text-sm font-medium uppercase tracking-wider text-slate-500">{String(chart.metric ?? "Metric")}</p>
          <div className="mt-2 flex items-baseline gap-2">
            <p className="text-3xl font-bold tracking-tight text-slate-900">{String(chart.value ?? "-")}</p>
            {chart.delta !== undefined ? (
               <span className={`text-sm font-semibold px-2 py-0.5 rounded-full ${isPositive ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-600'}`}>
                 {isPositive ? '+' : ''}{String(chart.delta)}
               </span>
            ) : null}
          </div>
        </div>
        <div className="absolute bottom-0 left-0 right-0 h-16 opacity-40 pointer-events-none">
          <ReactECharts
            style={{ height: '100%', width: '100%' }}
            option={{
              grid: { left: -10, right: -10, top: 0, bottom: -10 },
              xAxis: { type: 'category', show: false, boundaryGap: false },
              yAxis: { type: 'value', show: false, min: 'dataMin' },
              tooltip: { show: false },
              series: [{
                type: 'line',
                data: sparkData.map((d: any) => d[1]),
                smooth: 0.4,
                symbol: 'none',
                lineStyle: { width: 2, color },
                areaStyle: {
                  color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: color },
                    { offset: 1, color: 'rgba(255,255,255,0)' }
                  ])
                }
              }]
            }}
          />
        </div>
      </div>
    );
  }

  if (type === "gauge") {
    return (
      <ReactECharts
        style={{ height: '100%', width: '100%', minHeight: 180 }}
        option={{
          series: [
            {
              type: "gauge",
              progress: { show: true, width: 18 },
              axisLine: { lineStyle: { width: 18 } },
              detail: { valueAnimation: true, formatter: chart.formatter ?? "{value}" },
              data: [{ value: Number(chart.value ?? 0), name: String(chart.metric ?? "Metric") }],
            },
          ],
        }}
      />
    );
  }

  const series = seriesFromChart(chart);

  if (["line", "area", "bar", "horizontal_bar", "stacked_bar", "combo_line_bar"].includes(type)) {
    const categories = (series[0]?.data ?? []).map((pair) => pair[0]);
    const horizontal = type === "horizontal_bar";
    const stacked = type === "stacked_bar";
    const isCombo = type === "combo_line_bar";

    const premiumColors = ['#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#0ea5e9'];

    return (
      <ReactECharts
        style={{ height: '100%', width: "100%", minHeight: 180 }}
        onEvents={onEvents}
        option={{
          color: premiumColors,
          grid: { left: 48, right: isCombo ? 48 : 24, top: 48, bottom: 40, containLabel: true },
          legend: { top: 0, icon: 'circle', textStyle: { color: '#64748b', fontWeight: 500 } },
          tooltip: {
            trigger: "axis",
            axisPointer: { type: 'cross', crossStyle: { color: '#94a3b8' } },
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#e2e8f0',
            borderWidth: 1,
            padding: [12, 16],
            textStyle: { color: '#334155' },
            extraCssText: 'box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1); border-radius: 8px;'
          },
          xAxis: horizontal ? { type: "value", splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } } } : { type: "category", data: categories, axisLine: { lineStyle: { color: '#cbd5e1' } }, axisLabel: { color: '#64748b', margin: 12 } },
          yAxis: horizontal ? { type: "category", data: categories, axisLine: { lineStyle: { color: '#cbd5e1' } }, axisLabel: { color: '#475569', fontWeight: 500 } } : [
            { type: "value", splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } }, axisLabel: { color: '#64748b' } },
            ...(isCombo ? [{ type: "value", splitLine: { show: false }, axisLabel: { color: '#64748b' }, position: 'right' }] : [])
          ],
          series: series.map((item, idx) => {
            const seriesType = type === "area" || (isCombo && idx === 1) ? "line" : (type === "line" ? "line" : "bar");
            
            return {
              name: item.name,
              type: seriesType,
              yAxisIndex: isCombo && idx === 1 ? 1 : 0,
              data: item.data.map((pair) => pair[1]),
              smooth: seriesType === "line" ? 0.4 : undefined,
              showSymbol: seriesType === "line" ? false : undefined,
              symbolSize: 8,
              barMaxWidth: 48,
              itemStyle: seriesType === "bar" ? { borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] } : undefined,
              areaStyle: type === "area" ? {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: `${premiumColors[idx % premiumColors.length]}66` },
                  { offset: 1, color: `${premiumColors[idx % premiumColors.length]}00` }
                ])
              } : undefined,
              stack: stacked ? "total" : undefined,
            };
          }),
        }}
      />
    );
  }

  if (["pie", "donut"].includes(type)) {
    const points = (series[0]?.data ?? []).map((pair) => ({ name: String(pair[0]), value: Number(pair[1]) }));
    const premiumColors = ['#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#0ea5e9'];
    return (
      <ReactECharts
        style={{ height: '100%', width: '100%', minHeight: 180 }}
        onEvents={onEvents}
        option={{
          tooltip: { trigger: "item", backgroundColor: 'rgba(255, 255, 255, 0.95)', borderColor: '#e2e8f0', borderWidth: 1, padding: [12, 16], textStyle: { color: '#334155' }, extraCssText: 'box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); border-radius: 8px;' },
          legend: { bottom: 0, icon: 'circle', textStyle: { color: '#64748b' } },
          color: premiumColors,
          series: [
            {
              type: "pie",
              radius: type === "donut" ? ["45%", "72%"] : "70%",
              data: points,
              itemStyle: { borderRadius: type === "donut" ? 4 : 0, borderColor: '#fff', borderWidth: 2 },
              emphasis: { itemStyle: { shadowBlur: 12, shadowOffsetX: 0 } },
            },
          ],
        }}
      />
    );
  }

  if (type === "scatter") {
    const premiumColors = ['#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#0ea5e9'];
    return (
      <ReactECharts
        style={{ height: '100%', width: '100%', minHeight: 180 }}
        option={{
          color: premiumColors,
          grid: { left: 48, right: 20, top: 36, bottom: 40, containLabel: true },
          tooltip: {
            backgroundColor: 'rgba(255, 255, 255, 0.95)', borderColor: '#e2e8f0', borderWidth: 1, padding: [12, 16], textStyle: { color: '#334155' }, extraCssText: 'box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); border-radius: 8px;',
            formatter: (params: { value: ScatterPoint }) => {
              const [x, y, label] = params.value;
              return `<div class="font-semibold text-slate-800 mb-1">${label ?? "Point"}</div><div class="text-sm text-slate-600"><span class="font-medium text-slate-500">${String(chart.x_metric ?? "X")}:</span> ${x}<br/><span class="font-medium text-slate-500">${String(chart.y_metric ?? "Y")}:</span> ${y}</div>`;
            },
          },
          xAxis: { type: "value", name: String(chart.x_metric ?? "X"), splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } }, axisLine: { lineStyle: { color: '#cbd5e1' } }, axisLabel: { color: '#64748b' } },
          yAxis: { type: "value", name: String(chart.y_metric ?? "Y"), splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } }, axisLabel: { color: '#64748b' } },
          series: series.map((item) => ({
            name: item.name,
            type: "scatter",
            symbolSize: 14,
            data: item.data,
          })),
        }}
      />
    );
  }

  if (type === "funnel") {
    const points = (series[0]?.data ?? []).map((pair) => ({ name: String(pair[0]), value: Number(pair[1]) }));
    return (
      <ReactECharts
        style={{ height: '100%', width: '100%', minHeight: 180 }}
        onEvents={onEvents}
        option={{
          tooltip: { trigger: "item", backgroundColor: 'rgba(255, 255, 255, 0.95)', borderColor: '#e2e8f0', borderWidth: 1, padding: [12, 16], textStyle: { color: '#334155' }, extraCssText: 'box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); border-radius: 8px;' },
          color: ['#1e40af', '#2563eb', '#3b82f6', '#60a5fa', '#93c5fd'],
          series: [{ 
            type: "funnel", 
            left: "10%", 
            width: "80%", 
            data: points,
            label: { formatter: '{b}\n{c}', fontSize: 13 },
            itemStyle: { borderOpacity: 0 }
          }],
        }}
      />
    );
  }

  if (type === "radar") {
    const premiumColors = ['#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#0ea5e9'];
    const maxVal = Math.max(...series.flatMap(s => s.data.map(p => Number(p[1])))) * 1.1;
    const indicators = (series[0]?.data ?? []).map((pair) => ({ name: String(pair[0]), max: maxVal || 100 }));
    
    return (
      <ReactECharts
        style={{ height: '100%', width: '100%', minHeight: 180 }}
        onEvents={onEvents}
        option={{
          color: premiumColors,
          tooltip: { trigger: 'item', backgroundColor: 'rgba(255, 255, 255, 0.95)', borderColor: '#e2e8f0', borderWidth: 1, padding: [12, 16], textStyle: { color: '#334155' }, extraCssText: 'box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); border-radius: 8px;' },
          legend: { bottom: 0, icon: 'circle', textStyle: { color: '#64748b' } },
          radar: {
            indicator: indicators,
            splitArea: { areaStyle: { color: ['rgba(250,250,250,0.3)', 'rgba(200,200,200,0.1)'] } }
          },
          series: [{
            type: 'radar',
            data: series.map(s => ({
              value: s.data.map(p => Number(p[1])),
              name: s.name,
              areaStyle: { opacity: 0.2 }
            }))
          }]
        }}
      />
    );
  }

  if (type === "progress_list") {
    const listData = (series[0]?.data ?? []).map((pair) => ({
      name: String(pair[0]),
      value: Number(pair[1]),
      delta: pair[2] ? String(pair[2]) : undefined
    }));
    const maxValue = Math.max(...listData.map(d => d.value));

    return (
      <div className="flex h-full flex-col gap-4 overflow-y-auto py-2 pr-2">
        {listData.map((item, idx) => (
          <div key={idx} className="flex flex-col gap-1.5 group">
            <div className="flex items-end justify-between text-sm">
              <span className="font-medium text-slate-700 truncate pr-4">{item.name}</span>
              <div className="flex items-center gap-3 shrink-0">
                <span className="font-semibold text-slate-900">{item.value.toLocaleString()}</span>
                {item.delta ? (
                  <span className={`text-xs font-semibold w-16 text-right ${item.delta.startsWith('-') ? 'text-red-500' : 'text-emerald-500'}`}>
                    {item.delta.startsWith('-') ? '' : '+'}{item.delta}
                  </span>
                ) : null}
              </div>
            </div>
            <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
              <div 
                className="h-full bg-blue-500 rounded-full transition-all duration-1000 ease-out group-hover:bg-blue-600"
                style={{ width: `${Math.max(2, (item.value / maxValue) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    );
  }

  const columns = (chart.columns as string[]) ?? [];
  const rows = (chart.rows as Array<Record<string, unknown>>) ?? [];

  return (
    <div className="h-full w-full overflow-auto">
      <table className="min-w-full border-collapse text-sm">
        <thead className="sticky top-0 bg-white/95 backdrop-blur z-10">
          <tr>
            {columns.map((col) => (
              <th key={col} className="border-b-2 border-slate-200 px-4 py-3 text-left font-semibold text-slate-800">
                {String(col).replace(/_/g, ' ').toUpperCase()}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`row-${index}`} className="group hover:bg-slate-50/80 transition-colors">
              {columns.map((col) => {
                const isNumeric = typeof row[col] === 'number';
                return (
                  <td key={`${index}-${col}`} className={`border-b border-slate-100 px-4 py-3 text-slate-700 ${isNumeric ? 'font-medium font-mono' : ''}`}>
                    {String(row[col] ?? "-")}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length ? <div className="flex items-center justify-center p-8 text-sm text-slate-500 bg-slate-50/50 rounded border border-dashed border-slate-200 mt-2">No table rows configured.</div> : null}
    </div>
  );
}
