"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { Button, Card, CardContent, CardHeader, CardTitle, Input } from "@platform/ui";

import { apiRequest } from "@/lib/api";

type Dashboard = {
  id: string;
  name: string;
  description?: string;
};

export default function DashboardsPage() {
  const [dashboards, setDashboards] = useState<Dashboard[]>([]);
  const [name, setName] = useState("Executive Overview");
  const [description, setDescription] = useState("Core executive KPIs and insights");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const data = await apiRequest<Dashboard[]>("/api/v1/dashboards");
      setDashboards(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboards");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function createDashboard(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await apiRequest<Dashboard>("/api/v1/dashboards", {
        method: "POST",
        body: JSON.stringify({
          name,
          description,
          layout: { cols: 12, rowHeight: 32 },
        }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create dashboard");
    }
  }

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Dashboards</h2>
        <p className="text-sm text-slate-500">Build, save, and schedule governed dashboard views.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Create dashboard</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid grid-cols-1 gap-3 md:grid-cols-3" onSubmit={createDashboard}>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Dashboard name" />
            <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description" />
            <Button type="submit">Create</Button>
          </form>
          {error ? <p className="mt-2 text-sm text-red-600">{error}</p> : null}
        </CardContent>
      </Card>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {dashboards.map((dashboard) => (
          <Card key={dashboard.id}>
            <CardHeader>
              <CardTitle>{dashboard.name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-slate-600">{dashboard.description || "No description"}</p>
              <Link href={`/dashboards/${dashboard.id}`} className="text-sm font-medium text-brand-600">
                Open builder
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
