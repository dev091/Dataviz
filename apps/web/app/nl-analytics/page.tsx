"use client";

import { FormEvent, useEffect, useState } from "react";

import { Button, Card, CardContent, CardHeader, CardTitle, Input } from "@platform/ui";

import { ChartRenderer } from "@/components/chart-renderer";
import { apiRequest } from "@/lib/api";
import { useNLStore } from "@/store/nl-store";

type SemanticModel = {
  id: string;
  name: string;
  version: number;
};

type NLResponse = {
  ai_query_session_id: string;
  plan: Record<string, unknown>;
  agent_trace: Array<Record<string, unknown>>;
  sql: string;
  rows: Array<Record<string, unknown>>;
  chart: Record<string, unknown>;
  summary: string;
  insights: Array<{ title?: string; body?: string }>;
  follow_up_questions: string[];
};

export default function NLAnalyticsPage() {
  const [models, setModels] = useState<SemanticModel[]>([]);
  const [modelId, setModelId] = useState("");
  const [question, setQuestion] = useState("show monthly revenue by region");
  const [result, setResult] = useState<NLResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const setLastResult = useNLStore((state) => state.setLastResult);

  useEffect(() => {
    async function load() {
      try {
        const data = await apiRequest<SemanticModel[]>("/api/v1/semantic/models");
        setModels(data);
        if (data[0]) {
          setModelId(data[0].id);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load semantic models");
      }
    }
    void load();
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await apiRequest<NLResponse>("/api/v1/nl/query", {
        method: "POST",
        body: JSON.stringify({ semantic_model_id: modelId, question }),
      });
      setResult(data);
      setLastResult({
        aiQuerySessionId: data.ai_query_session_id,
        summary: data.summary,
        chart: data.chart,
        rows: data.rows,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run query");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Natural Language Analytics</h2>
        <p className="text-sm text-slate-500">Query through governed semantic metrics and dimensions, with safe multi-agent planning.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Ask a question</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-3" onSubmit={onSubmit}>
            <select
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
            >
              <option value="">Select semantic model</option>
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name} (v{model.version})
                </option>
              ))}
            </select>
            <Input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="show monthly revenue by region" />
            <Button type="submit" disabled={loading}>
              {loading ? "Running..." : "Run query"}
            </Button>
          </form>
          {error ? <p className="mt-2 text-sm text-red-600">{error}</p> : null}
        </CardContent>
      </Card>

      {result ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Chart</CardTitle>
            </CardHeader>
            <CardContent>
              <ChartRenderer chart={result.chart} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Executive Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-slate-700">{result.summary}</p>
              <div className="rounded-md bg-slate-50 p-3">
                <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Safe SQL</p>
                <pre className="overflow-auto text-xs text-slate-700">{result.sql}</pre>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Insights and next questions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <p className="mb-2 text-sm font-medium">Insights</p>
                  <ul className="space-y-2 text-sm text-slate-700">
                    {result.insights.map((insight, idx) => (
                      <li key={`${insight.title}-${idx}`} className="rounded-md border border-slate-200 p-2">
                        <p className="font-medium">{insight.title ?? "Insight"}</p>
                        <p className="text-xs text-slate-600">{insight.body}</p>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="mb-2 text-sm font-medium">Suggested follow-ups</p>
                  <ul className="space-y-2 text-sm text-slate-700">
                    {result.follow_up_questions.map((questionItem) => (
                      <li key={questionItem} className="rounded-md border border-slate-200 p-2">
                        {questionItem}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Agent Execution Trace</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {result.agent_trace.map((step, index) => (
                  <div key={`${step.agent}-${index}`} className="rounded-md border border-slate-200 p-3 text-xs">
                    <p className="font-medium">
                      {String(step.agent)} - {String(step.status)}
                    </p>
                    <p className="text-slate-500">Started: {String(step.started_at ?? "")}</p>
                    <p className="text-slate-500">Finished: {String(step.finished_at ?? "")}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </>
      ) : null}
    </section>
  );
}
