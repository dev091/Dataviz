"use client";

import { FormEvent, useEffect, useState } from "react";

import { Button, Card, CardContent, CardHeader, CardTitle, Input } from "@platform/ui";

import { apiRequest } from "@/lib/api";

type Dashboard = { id: string; name: string };
type SemanticModel = { id: string; name: string };
type MetricOption = { id: string; name: string };

type Rule = {
  id: string;
  name: string;
  condition: string;
  threshold: number;
  enabled: boolean;
};

type ReportSchedule = {
  id: string;
  name: string;
  schedule_type: string;
  email_to: string[];
};

type AlertEvent = {
  id: string;
  rule_name: string;
  status: string;
  value: number;
  message: string;
  triggered_at: string;
};

export default function AlertsPage() {
  const [dashboards, setDashboards] = useState<Dashboard[]>([]);
  const [models, setModels] = useState<SemanticModel[]>([]);
  const [modelMetrics, setModelMetrics] = useState<MetricOption[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [schedules, setSchedules] = useState<ReportSchedule[]>([]);
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [dashboardId, setDashboardId] = useState("");
  const [scheduleName, setScheduleName] = useState("Weekly Executive Digest");

  const [ruleName, setRuleName] = useState("Revenue drop alert");
  const [semanticModelId, setSemanticModelId] = useState("");
  const [metricId, setMetricId] = useState("");
  const [threshold, setThreshold] = useState("10000");

  async function load() {
    try {
      const [dashboardData, modelData, scheduleData, ruleData, eventData] = await Promise.all([
        apiRequest<Dashboard[]>("/api/v1/dashboards"),
        apiRequest<SemanticModel[]>("/api/v1/semantic/models"),
        apiRequest<ReportSchedule[]>("/api/v1/alerts/report-schedules"),
        apiRequest<Rule[]>("/api/v1/alerts/rules"),
        apiRequest<AlertEvent[]>("/api/v1/alerts/events"),
      ]);

      setDashboards(dashboardData);
      setModels(modelData);
      setSchedules(scheduleData);
      setRules(ruleData);
      setEvents(eventData);

      if (!dashboardId && dashboardData[0]) {
        setDashboardId(dashboardData[0].id);
      }
      if (!semanticModelId && modelData[0]) {
        setSemanticModelId(modelData[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load alerts page");
    }
  }

  async function loadMetrics(modelId: string) {
    if (!modelId) return;
    try {
      const metrics = await apiRequest<MetricOption[]>(`/api/v1/semantic/models/${modelId}/metrics`);
      setModelMetrics(metrics);
      if (metrics[0]) {
        setMetricId(metrics[0].id);
      }
    } catch {
      setModelMetrics([]);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    void loadMetrics(semanticModelId);
  }, [semanticModelId]);

  async function createSchedule(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await apiRequest("/api/v1/alerts/report-schedules", {
        method: "POST",
        body: JSON.stringify({
          dashboard_id: dashboardId,
          name: scheduleName,
          email_to: ["ops@dataviz.com"],
          schedule_type: "weekly",
          daily_time: "09:00",
          weekday: 1,
          enabled: true,
        }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create report schedule");
    }
  }

  async function createRule(event: FormEvent) {
    event.preventDefault();
    setError(null);

    try {
      if (!metricId) {
        throw new Error("Select a semantic metric before creating an alert.");
      }
      await apiRequest("/api/v1/alerts/rules", {
        method: "POST",
        body: JSON.stringify({
          semantic_model_id: semanticModelId,
          metric_id: metricId,
          name: ruleName,
          condition: "<",
          threshold: Number(threshold),
          schedule_type: "daily",
          enabled: true,
        }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create alert rule");
    }
  }

  async function evaluate(ruleId: string) {
    try {
      await apiRequest(`/api/v1/alerts/rules/${ruleId}/evaluate`, { method: "POST" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to evaluate alert rule");
    }
  }

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Alerts and Scheduling</h2>
        <p className="text-sm text-slate-500">Create report schedules and metric threshold alerts with delivery logs.</p>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Schedule dashboard email</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-3" onSubmit={createSchedule}>
              <select
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                value={dashboardId}
                onChange={(e) => setDashboardId(e.target.value)}
              >
                {dashboards.map((dashboard) => (
                  <option key={dashboard.id} value={dashboard.id}>
                    {dashboard.name}
                  </option>
                ))}
              </select>
              <Input value={scheduleName} onChange={(e) => setScheduleName(e.target.value)} />
              <Button type="submit">Create schedule</Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Create threshold alert</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-3" onSubmit={createRule}>
              <select
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                value={semanticModelId}
                onChange={(e) => setSemanticModelId(e.target.value)}
              >
                {models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name}
                  </option>
                ))}
              </select>
              <select
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                value={metricId}
                onChange={(e) => setMetricId(e.target.value)}
              >
                {modelMetrics.map((metric) => (
                  <option key={metric.id} value={metric.id}>
                    {metric.name}
                  </option>
                ))}
              </select>
              <Input value={ruleName} onChange={(e) => setRuleName(e.target.value)} />
              <Input value={threshold} onChange={(e) => setThreshold(e.target.value)} />
              <Button type="submit">Create alert rule</Button>
            </form>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Report schedules</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {schedules.map((schedule) => (
              <div key={schedule.id} className="rounded-md border border-slate-200 p-3">
                <p className="font-medium">{schedule.name}</p>
                <p className="text-xs text-slate-500">
                  {schedule.schedule_type} to {schedule.email_to.join(", ")}
                </p>
              </div>
            ))}
            {!schedules.length ? <p className="text-slate-500">No schedules yet.</p> : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Alert rules</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {rules.map((rule) => (
              <div key={rule.id} className="rounded-md border border-slate-200 p-3">
                <p className="font-medium">{rule.name}</p>
                <p className="text-xs text-slate-500">
                  Trigger when value {rule.condition} {rule.threshold}
                </p>
                <Button className="mt-2" variant="secondary" onClick={() => evaluate(rule.id)}>
                  Evaluate now
                </Button>
              </div>
            ))}
            {!rules.length ? <p className="text-slate-500">No alert rules yet.</p> : null}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Alert events</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {events.map((event) => (
            <div key={event.id} className="rounded-md border border-slate-200 p-3">
              <p className="font-medium">{event.rule_name} - {event.status}</p>
              <p className="text-xs text-slate-500">Value: {event.value}</p>
              <p className="text-xs text-slate-500">{new Date(event.triggered_at).toLocaleString()}</p>
              <p className="text-xs text-slate-600">{event.message}</p>
            </div>
          ))}
          {!events.length ? <p className="text-slate-500">No alert events yet.</p> : null}
        </CardContent>
      </Card>
    </section>
  );
}

