export type ChartScalar = string | number;
export type ChartPair = [ChartScalar, number];
export type ScatterPoint = [number, number, number?, string?];
export type HeatmapPoint = [ChartScalar, ChartScalar, number];
export type BoxplotPoint = [number, number, number, number, number];

export type ChartSeries = {
  name: string;
  data: Array<ChartPair | ScatterPoint | HeatmapPoint | BoxplotPoint | Record<string, unknown>>;
};

export type HierarchyNode = {
  name: string;
  value?: number;
  children?: HierarchyNode[];
};

export type SankeyNode = {
  name: string;
};

export type SankeyLink = {
  source: string;
  target: string;
  value: number;
};

export type DashboardChart = Record<string, unknown> & {
  type?: string;
  option?: Record<string, unknown>;
  series?: ChartSeries[];
  x_metric?: string;
  y_metric?: string;
  metric?: string;
  value?: number | string;
  formatter?: string;
  x_categories?: string[];
  y_categories?: string[];
  nodes?: HierarchyNode[] | SankeyNode[];
  links?: SankeyLink[];
  categories?: string[];
};

export const SUPPORTED_CHART_TYPES = [
  { id: "bar", label: "Bar", inputMode: "paired", description: "Rank or compare categorical values." },
  { id: "horizontal_bar", label: "Horizontal Bar", inputMode: "paired", description: "Compare long labels or Top N lists." },
  { id: "stacked_bar", label: "Stacked Bar", inputMode: "paired", description: "Show composition across categories." },
  { id: "line", label: "Line", inputMode: "paired", description: "Track change over time or ordered categories." },
  { id: "area", label: "Area", inputMode: "paired", description: "Highlight magnitude over time." },
  { id: "stacked_area", label: "Stacked Area", inputMode: "paired", description: "Show contribution of stacked trends." },
  { id: "pie", label: "Pie", inputMode: "paired", description: "Simple proportional share view." },
  { id: "donut", label: "Donut", inputMode: "paired", description: "Share view with central whitespace for KPI framing." },
  { id: "funnel", label: "Funnel", inputMode: "paired", description: "Stage conversion or pipeline drop-off." },
  { id: "waterfall", label: "Waterfall", inputMode: "paired", description: "Variance bridge and contribution analysis." },
  { id: "radar", label: "Radar", inputMode: "paired", description: "Multi-axis profile comparisons." },
  { id: "scatter", label: "Scatter", inputMode: "xy", description: "Relationship between two measures." },
  { id: "bubble", label: "Bubble", inputMode: "xy_size", description: "Scatter with size-coded magnitude." },
  { id: "heatmap", label: "Heatmap", inputMode: "matrix", description: "Dense matrix comparison across two dimensions." },
  { id: "treemap", label: "Treemap", inputMode: "hierarchy", description: "Hierarchy and proportional composition." },
  { id: "sunburst", label: "Sunburst", inputMode: "hierarchy", description: "Radial hierarchy exploration." },
  { id: "sankey", label: "Sankey", inputMode: "flow", description: "Flow between stages, channels, or entities." },
  { id: "boxplot", label: "Box Plot", inputMode: "statistical", description: "Distribution with quartiles and outliers." },
  { id: "gauge", label: "Gauge", inputMode: "value", description: "Target or attainment style metric view." },
] as const;

export type SupportedChartTypeId = (typeof SUPPORTED_CHART_TYPES)[number]["id"];
export type ChartInputMode = (typeof SUPPORTED_CHART_TYPES)[number]["inputMode"];

const BRAND_COLORS = ["#2563eb", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#0ea5e9", "#14b8a6", "#f97316"];

function asSeries(chart: DashboardChart): ChartSeries[] {
  return Array.isArray(chart.series) ? (chart.series as ChartSeries[]) : [];
}

function numericValue(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function categoryValue(value: unknown): string {
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

function gradient(color: string, alphaTop = "66", alphaBottom = "08"): Record<string, unknown> {
  return {
    type: "linear",
    x: 0,
    y: 0,
    x2: 0,
    y2: 1,
    colorStops: [
      { offset: 0, color: `${color}${alphaTop}` },
      { offset: 1, color: `${color}${alphaBottom}` },
    ],
  };
}

function baseTooltip(trigger: "axis" | "item" = "axis"): Record<string, unknown> {
  return {
    trigger,
    backgroundColor: "rgba(255,255,255,0.96)",
    borderColor: "#e2e8f0",
    borderWidth: 1,
    padding: [12, 16],
    textStyle: { color: "#334155" },
    extraCssText: "box-shadow: 0 10px 25px -15px rgba(15,23,42,.35); border-radius: 12px;",
  };
}

function categoricalAxisOption(chart: DashboardChart, type: SupportedChartTypeId | "combo_line_bar"): Record<string, unknown> {
  const series = asSeries(chart);
  const categories = Array.isArray(chart.categories)
    ? (chart.categories as string[])
    : (series[0]?.data ?? []).map((pair) => categoryValue(Array.isArray(pair) ? pair[0] : ""));

  const horizontal = type === "horizontal_bar";
  const stacked = type === "stacked_bar" || type === "stacked_area";
  const combo = type === "combo_line_bar";
  const area = type === "area" || type === "stacked_area";

  return {
    color: BRAND_COLORS,
    legend: { top: 0, icon: "circle", textStyle: { color: "#64748b", fontWeight: 500 } },
    grid: { left: 48, right: combo ? 56 : 24, top: 48, bottom: 40, containLabel: true },
    tooltip: baseTooltip("axis"),
    xAxis: horizontal
      ? { type: "value", splitLine: { lineStyle: { type: "dashed", color: "#e2e8f0" } }, axisLabel: { color: "#64748b" } }
      : { type: "category", data: categories, axisLine: { lineStyle: { color: "#cbd5e1" } }, axisLabel: { color: "#64748b", margin: 12 } },
    yAxis: horizontal
      ? { type: "category", data: categories, axisLine: { lineStyle: { color: "#cbd5e1" } }, axisLabel: { color: "#475569", fontWeight: 500 } }
      : [
          { type: "value", splitLine: { lineStyle: { type: "dashed", color: "#e2e8f0" } }, axisLabel: { color: "#64748b" } },
          ...(combo ? [{ type: "value", splitLine: { show: false }, axisLabel: { color: "#64748b" }, position: "right" }] : []),
        ],
    series: series.map((item, index) => {
      const palette = BRAND_COLORS[index % BRAND_COLORS.length];
      const lineMode = type === "line" || area || (combo && index === 1);
      return {
        name: item.name,
        type: lineMode ? "line" : "bar",
        yAxisIndex: combo && index === 1 ? 1 : 0,
        data: item.data.map((pair) => numericValue(Array.isArray(pair) ? pair[1] : 0)),
        stack: stacked ? "total" : undefined,
        smooth: lineMode ? 0.35 : undefined,
        showSymbol: lineMode ? false : undefined,
        symbolSize: lineMode ? 8 : undefined,
        barMaxWidth: 44,
        itemStyle: lineMode
          ? { color: palette }
          : { color: palette, borderRadius: horizontal ? [0, 6, 6, 0] : [6, 6, 0, 0] },
        lineStyle: lineMode ? { width: 3, color: palette } : undefined,
        areaStyle: area ? { color: gradient(palette) } : undefined,
      };
    }),
  };
}

function pieOption(chart: DashboardChart, donut = false): Record<string, unknown> {
  const series = asSeries(chart);
  const points = (series[0]?.data ?? []).map((pair) => ({
    name: categoryValue(Array.isArray(pair) ? pair[0] : ""),
    value: numericValue(Array.isArray(pair) ? pair[1] : 0),
  }));
  return {
    color: BRAND_COLORS,
    tooltip: baseTooltip("item"),
    legend: { bottom: 0, icon: "circle", textStyle: { color: "#64748b" } },
    series: [
      {
        type: "pie",
        radius: donut ? ["48%", "72%"] : "72%",
        center: ["50%", "45%"],
        data: points,
        label: { color: "#475569" },
        itemStyle: { borderColor: "#fff", borderWidth: 2, borderRadius: donut ? 6 : 0 },
        emphasis: { itemStyle: { shadowBlur: 16, shadowColor: "rgba(15,23,42,0.18)" } },
      },
    ],
  };
}

function scatterOption(chart: DashboardChart, bubble = false): Record<string, unknown> {
  const series = asSeries(chart);
  return {
    color: BRAND_COLORS,
    grid: { left: 48, right: 24, top: 36, bottom: 40, containLabel: true },
    tooltip: {
      ...baseTooltip("item"),
      formatter: (params: { value: ScatterPoint }) => {
        const [x, y, size, label] = params.value;
        const sizeLine = bubble && size !== undefined ? `<br/><span style="color:#64748b">Size:</span> ${size}` : "";
        return `<div style="font-weight:600;margin-bottom:4px">${label ?? "Point"}</div><div><span style="color:#64748b">${String(chart.x_metric ?? "X")}:</span> ${x}<br/><span style="color:#64748b">${String(chart.y_metric ?? "Y")}:</span> ${y}${sizeLine}</div>`;
      },
    },
    xAxis: { type: "value", name: String(chart.x_metric ?? "X"), splitLine: { lineStyle: { type: "dashed", color: "#e2e8f0" } }, axisLabel: { color: "#64748b" } },
    yAxis: { type: "value", name: String(chart.y_metric ?? "Y"), splitLine: { lineStyle: { type: "dashed", color: "#e2e8f0" } }, axisLabel: { color: "#64748b" } },
    series: series.map((item, index) => ({
      name: item.name,
      type: "scatter",
      data: item.data,
      symbolSize: bubble
        ? (value: ScatterPoint) => {
            const size = numericValue(value[2] ?? 12);
            return Math.max(10, Math.min(42, size));
          }
        : 14,
      itemStyle: { color: BRAND_COLORS[index % BRAND_COLORS.length], opacity: bubble ? 0.8 : 0.9 },
    })),
  };
}

function funnelOption(chart: DashboardChart): Record<string, unknown> {
  const series = asSeries(chart);
  const data = (series[0]?.data ?? []).map((pair) => ({
    name: categoryValue(Array.isArray(pair) ? pair[0] : ""),
    value: numericValue(Array.isArray(pair) ? pair[1] : 0),
  }));
  return {
    color: BRAND_COLORS,
    tooltip: baseTooltip("item"),
    series: [
      {
        type: "funnel",
        top: 16,
        bottom: 16,
        left: "10%",
        width: "80%",
        minSize: "20%",
        maxSize: "100%",
        sort: "descending",
        gap: 4,
        label: { color: "#334155", formatter: "{b}\n{c}" },
        itemStyle: { borderRadius: 8, borderColor: "#fff", borderWidth: 2 },
        data,
      },
    ],
  };
}

function radarOption(chart: DashboardChart): Record<string, unknown> {
  const series = asSeries(chart);
  const maxValue = Math.max(...series.flatMap((item) => item.data.map((pair) => numericValue(Array.isArray(pair) ? pair[1] : 0))), 100);
  const indicators = (series[0]?.data ?? []).map((pair) => ({ name: categoryValue(Array.isArray(pair) ? pair[0] : ""), max: Math.ceil(maxValue * 1.15) }));
  return {
    color: BRAND_COLORS,
    legend: { bottom: 0, icon: "circle", textStyle: { color: "#64748b" } },
    tooltip: baseTooltip("item"),
    radar: {
      indicator: indicators,
      radius: "62%",
      splitArea: { areaStyle: { color: ["rgba(148,163,184,0.06)", "rgba(148,163,184,0.02)"] } },
      axisName: { color: "#475569" },
    },
    series: [
      {
        type: "radar",
        data: series.map((item, index) => ({
          name: item.name,
          value: item.data.map((pair) => numericValue(Array.isArray(pair) ? pair[1] : 0)),
          lineStyle: { color: BRAND_COLORS[index % BRAND_COLORS.length], width: 2 },
          areaStyle: { color: gradient(BRAND_COLORS[index % BRAND_COLORS.length], "33", "08") },
        })),
      },
    ],
  };
}

function heatmapOption(chart: DashboardChart): Record<string, unknown> {
  const xCategories = Array.isArray(chart.x_categories) ? (chart.x_categories as string[]) : [];
  const yCategories = Array.isArray(chart.y_categories) ? (chart.y_categories as string[]) : [];
  const series = asSeries(chart);
  const rawData = (series[0]?.data ?? []) as HeatmapPoint[];
  const data = rawData.map((point) => [xCategories.indexOf(String(point[0])), yCategories.indexOf(String(point[1])), numericValue(point[2])]);
  const maxValue = Math.max(...rawData.map((point) => numericValue(point[2])), 0);
  return {
    grid: { left: 72, right: 24, top: 24, bottom: 54 },
    tooltip: baseTooltip("item"),
    xAxis: { type: "category", data: xCategories, splitArea: { show: true }, axisLabel: { color: "#64748b" } },
    yAxis: { type: "category", data: yCategories, splitArea: { show: true }, axisLabel: { color: "#64748b" } },
    visualMap: {
      min: 0,
      max: maxValue || 100,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      inRange: { color: ["#e0f2fe", "#60a5fa", "#1d4ed8"] },
      textStyle: { color: "#64748b" },
    },
    series: [{ type: "heatmap", data, label: { show: true, color: "#0f172a" }, emphasis: { itemStyle: { shadowBlur: 12 } } }],
  };
}

function hierarchyOption(chart: DashboardChart, type: "treemap" | "sunburst"): Record<string, unknown> {
  const nodes = Array.isArray(chart.nodes) ? (chart.nodes as HierarchyNode[]) : [];
  return {
    color: BRAND_COLORS,
    tooltip: baseTooltip("item"),
    series: [
      {
        type,
        radius: type === "sunburst" ? ["18%", "82%"] : undefined,
        data: nodes,
        nodeClick: false,
        roam: type === "treemap" ? false : undefined,
        label: { color: "#0f172a" },
        itemStyle: { borderColor: "#fff", borderWidth: 2, borderRadius: type === "treemap" ? 6 : 0 },
      },
    ],
  };
}

function waterfallOption(chart: DashboardChart): Record<string, unknown> {
  const series = asSeries(chart);
  const points = (series[0]?.data ?? []) as ChartPair[];
  const categories = points.map((pair) => categoryValue(pair[0]));
  const values = points.map((pair) => numericValue(pair[1]));
  const assist: number[] = [];
  const positive: number[] = [];
  const negative: number[] = [];
  let runningTotal = 0;

  values.forEach((value) => {
    const start = runningTotal;
    runningTotal += value;
    assist.push(value >= 0 ? start : runningTotal);
    positive.push(value >= 0 ? value : 0);
    negative.push(value < 0 ? Math.abs(value) : 0);
  });

  return {
    color: ["rgba(148,163,184,0.18)", "#10b981", "#ef4444"],
    legend: { top: 0, data: ["Increase", "Decrease"], textStyle: { color: "#64748b" } },
    grid: { left: 48, right: 24, top: 48, bottom: 40, containLabel: true },
    tooltip: baseTooltip("axis"),
    xAxis: { type: "category", data: categories, axisLabel: { color: "#64748b" } },
    yAxis: { type: "value", splitLine: { lineStyle: { type: "dashed", color: "#e2e8f0" } }, axisLabel: { color: "#64748b" } },
    series: [
      { type: "bar", stack: "total", data: assist, itemStyle: { color: "transparent" }, emphasis: { itemStyle: { color: "transparent" } }, silent: true },
      { name: "Increase", type: "bar", stack: "total", data: positive, itemStyle: { color: "#10b981", borderRadius: [6, 6, 0, 0] } },
      { name: "Decrease", type: "bar", stack: "total", data: negative, itemStyle: { color: "#ef4444", borderRadius: [6, 6, 0, 0] } },
    ],
  };
}

function sankeyOption(chart: DashboardChart): Record<string, unknown> {
  const nodes = Array.isArray(chart.nodes) ? (chart.nodes as SankeyNode[]) : [];
  const links = Array.isArray(chart.links) ? (chart.links as SankeyLink[]) : [];
  return {
    color: BRAND_COLORS,
    tooltip: baseTooltip("item"),
    series: [
      {
        type: "sankey",
        data: nodes,
        links,
        lineStyle: { color: "gradient", curveness: 0.5, opacity: 0.35 },
        nodeWidth: 18,
        nodeGap: 18,
        label: { color: "#334155", fontWeight: 500 },
        emphasis: { focus: "adjacency" },
      },
    ],
  };
}

function boxplotOption(chart: DashboardChart): Record<string, unknown> {
  const categories = Array.isArray(chart.categories) ? (chart.categories as string[]) : [];
  const series = asSeries(chart);
  const data = (series[0]?.data ?? []) as BoxplotPoint[];
  return {
    color: ["#2563eb"],
    grid: { left: 48, right: 24, top: 36, bottom: 40, containLabel: true },
    tooltip: baseTooltip("item"),
    xAxis: { type: "category", data: categories, axisLabel: { color: "#64748b" } },
    yAxis: { type: "value", splitLine: { lineStyle: { type: "dashed", color: "#e2e8f0" } }, axisLabel: { color: "#64748b" } },
    series: [{ type: "boxplot", data, itemStyle: { borderColor: "#2563eb", color: "rgba(37,99,235,0.18)" } }],
  };
}

function gaugeOption(chart: DashboardChart): Record<string, unknown> {
  return {
    series: [
      {
        type: "gauge",
        progress: { show: true, width: 18 },
        axisLine: { lineStyle: { width: 18 } },
        pointer: { show: true, itemStyle: { color: "#0f172a" } },
        title: { offsetCenter: [0, "70%"], color: "#475569", fontSize: 13 },
        detail: { valueAnimation: true, formatter: String(chart.formatter ?? "{value}"), color: "#0f172a", fontSize: 24 },
        data: [{ value: numericValue(chart.value), name: String(chart.metric ?? "Metric") }],
      },
    ],
  };
}

export function buildChartOption(chart: DashboardChart): Record<string, unknown> | null {
  if (chart.option && typeof chart.option === "object") {
    return chart.option as Record<string, unknown>;
  }

  const type = String(chart.type ?? "table") as SupportedChartTypeId | "combo_line_bar" | "table" | "kpi" | "kpi_sparkline" | "progress_list" | "custom";
  if (["kpi", "kpi_sparkline", "progress_list", "table", "custom"].includes(type)) {
    return null;
  }

  if (["bar", "horizontal_bar", "stacked_bar", "line", "area", "stacked_area", "combo_line_bar"].includes(type)) {
    return categoricalAxisOption(chart, type as SupportedChartTypeId);
  }
  if (type === "pie") {
    return pieOption(chart, false);
  }
  if (type === "donut") {
    return pieOption(chart, true);
  }
  if (type === "scatter") {
    return scatterOption(chart, false);
  }
  if (type === "bubble") {
    return scatterOption(chart, true);
  }
  if (type === "funnel") {
    return funnelOption(chart);
  }
  if (type === "radar") {
    return radarOption(chart);
  }
  if (type === "heatmap") {
    return heatmapOption(chart);
  }
  if (type === "treemap" || type === "sunburst") {
    return hierarchyOption(chart, type);
  }
  if (type === "waterfall") {
    return waterfallOption(chart);
  }
  if (type === "sankey") {
    return sankeyOption(chart);
  }
  if (type === "boxplot") {
    return boxplotOption(chart);
  }
  if (type === "gauge") {
    return gaugeOption(chart);
  }
  return null;
}

export function getChartInputBlueprint(type: SupportedChartTypeId): { inputMode: ChartInputMode; note: string; labelsPlaceholder?: string; valuesPlaceholder?: string; rowsPlaceholder?: string } {
  const selected = SUPPORTED_CHART_TYPES.find((item) => item.id === type);
  const note = selected?.description ?? "Advanced chart configuration.";
  switch (type) {
    case "scatter":
      return { inputMode: "xy", note, rowsPlaceholder: "21,44,North\n35,52,South\n28,41,West" };
    case "bubble":
      return { inputMode: "xy_size", note, rowsPlaceholder: "21,44,18,North\n35,52,26,South\n28,41,14,West" };
    case "heatmap":
      return { inputMode: "matrix", note, rowsPlaceholder: "West,Jan,54\nWest,Feb,62\nEast,Jan,41" };
    case "treemap":
    case "sunburst":
      return { inputMode: "hierarchy", note, rowsPlaceholder: "North,59800,\nSouth,30600,\nWest,37100," };
    case "sankey":
      return { inputMode: "flow", note, rowsPlaceholder: "Lead,Qualified,120\nQualified,Proposal,80\nProposal,Won,35" };
    case "boxplot":
      return { inputMode: "statistical", note, rowsPlaceholder: "North,10,18,24,31,40\nSouth,8,14,19,26,35" };
    case "gauge":
      return { inputMode: "value", note };
    default:
      return {
        inputMode: "paired",
        note,
        labelsPlaceholder: "North,South,West",
        valuesPlaceholder: "59800,30600,37100",
      };
  }
}

