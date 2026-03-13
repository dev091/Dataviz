"use client";

import { FormEvent, useEffect, useState } from "react";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, EmptyState, EmptyStateBody, EmptyStateTitle, Skeleton, Textarea } from "@/components/ui";

import { ChartRenderer } from "@/components/chart-renderer";
import { FeedbackButton } from "@/components/feedback-button";
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
  related_queries: Array<{ id: string; question: string; summary: string; similarity: number; created_at: string }>;
};

export default function NLAnalyticsPage() {
  const [modelId, setModelId] = useState("");
  const [question, setQuestion] = useState("show monthly revenue by region");
  const [pageError, setPageError] = useState<string | null>(null);
  const setLastResult = useNLStore((state) => state.setLastResult);

  const modelsQuery = useQuery({
    queryKey: ["semantic-models"],
    queryFn: () => apiRequest<SemanticModel[]>("/api/v1/semantic/models"),
  });

  useEffect(() => {
    if (!modelId && modelsQuery.data?.[0]) {
      setModelId(modelsQuery.data[0].id);
    }
  }, [modelId, modelsQuery.data]);

  const queryMutation = useMutation({
    mutationFn: () =>
      apiRequest<NLResponse>("/api/v1/nl/query", {
        method: "POST",
        body: JSON.stringify({ semantic_model_id: modelId, question }),
      }),
    onSuccess: (data) => {
      setPageError(null);
      setLastResult({
        aiQuerySessionId: data.ai_query_session_id,
        summary: data.summary,
        chart: data.chart,
        rows: data.rows,
      });
    },
    onError: (error) => setPageError(error instanceof Error ? error.message : "Failed to run query"),
  });

  const result = queryMutation.data;

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">Natural Language Analytics</h2>
        <p className="text-sm text-slate-500">Query governed metrics through the multi-agent planner, with safe SQL generation and related-analysis recall.</p>
      </div>

      {pageError ? <p className="text-sm text-red-600">{pageError}</p> : null}
      {modelsQuery.error ? <p className="text-sm text-red-600">{modelsQuery.error instanceof Error ? modelsQuery.error.message : "Failed to load semantic models"}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle>Ask a question</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-3"
            onSubmit={(event: FormEvent) => {
              event.preventDefault();
              queryMutation.mutate();
            }}
          >
            <select
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={modelId}
              onChange={(event) => setModelId(event.target.value)}
            >
              <option value="">Select semantic model</option>
              {(modelsQuery.data ?? []).map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name} (v{model.version})
                </option>
              ))}
            </select>
            <Textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="show monthly revenue by region" />
            <Button type="submit" disabled={queryMutation.isPending || !modelId}>
              {queryMutation.isPending ? "Running..." : "Run query"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {queryMutation.isPending ? (
        <div className="space-y-3">
          <Skeleton className="h-72" />
          <Skeleton className="h-40" />
          <Skeleton className="h-52" />
        </div>
      ) : null}

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
              <div className="rounded-xl bg-slate-50 p-3">
                <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Safe SQL</p>
                <pre className="overflow-auto text-xs text-slate-700">{result.sql}</pre>
              </div>
              <div className="pt-2 border-t border-slate-100">
                <FeedbackButton artifactType="ai_query_session" artifactId={result.ai_query_session_id} />
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
            <Card>
              <CardHeader>
                <CardTitle>Insights and next questions</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 md:grid-cols-2">
                  <div>
                    <p className="mb-2 text-sm font-medium">Insights</p>
                    <ul className="space-y-2 text-sm text-slate-700">
                      {result.insights.map((insight, index) => (
                        <li key={`${insight.title}-${index}`} className="rounded-xl border border-slate-200 p-3">
                          <p className="font-medium">{insight.title ?? "Insight"}</p>
                          <p className="mt-1 text-xs text-slate-600">{insight.body}</p>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="mb-2 text-sm font-medium">Suggested follow-ups</p>
                    <ul className="space-y-2 text-sm text-slate-700">
                      {result.follow_up_questions.map((questionItem) => (
                        <li key={questionItem} className="rounded-xl border border-slate-200 p-3">
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
                <CardTitle>Related prior analyses</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {result.related_queries.map((related) => (
                  <div key={related.id} className="rounded-xl border border-slate-200 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium">{related.question}</p>
                      <Badge tone="default">{Math.round(related.similarity * 100)}% match</Badge>
                    </div>
                    <p className="mt-2 text-xs text-slate-600">{related.summary}</p>
                  </div>
                ))}
                {!result.related_queries.length ? (
                  <EmptyState className="p-6 text-left">
                    <EmptyStateTitle>No similar prior analysis yet</EmptyStateTitle>
                    <EmptyStateBody>As the team runs more NL questions, the platform will reuse the closest historical context.</EmptyStateBody>
                  </EmptyState>
                ) : null}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Agent Execution Trace</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {result.agent_trace.map((step, index) => (
                  <div key={`${step.agent}-${index}`} className="rounded-xl border border-slate-200 p-3 text-xs">
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

      {!queryMutation.isPending && !result ? (
        <EmptyState>
          <EmptyStateTitle>Ready for governed questions</EmptyStateTitle>
          <EmptyStateBody>Pick a semantic model, ask a business question, and the platform will return a safe query plan, chart, summary, and follow-ups.</EmptyStateBody>
        </EmptyState>
      ) : null}
    </section>
  );
}

