"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { Button, Card, CardContent, CardHeader, CardTitle, Input } from "@/components/ui";

import { apiRequest } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

import type { AuthPayload } from "@platform/types";

export default function SignupPage() {
  const router = useRouter();
  const setSession = useAuthStore((state) => state.setSession);

  const [form, setForm] = useState({
    email: "",
    full_name: "",
    password: "",
    organization_name: "",
    workspace_name: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const payload = await apiRequest<AuthPayload>(
        "/api/v1/auth/signup",
        {
          method: "POST",
          body: JSON.stringify(form),
        },
        { withAuth: false, workspaceScoped: false },
      );

      setSession({
        accessToken: payload.access_token,
        refreshToken: payload.refresh_token,
        email: payload.email,
        userId: payload.user_id,
        workspaces: payload.workspaces,
      });
      router.push("/dashboards");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to sign up");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-lg items-center">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Create account</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid grid-cols-1 gap-3 md:grid-cols-2" onSubmit={onSubmit}>
            <div className="md:col-span-2">
              <label className="mb-1 block text-sm text-slate-600">Email</label>
              <Input value={form.email} onChange={(e) => setForm((v) => ({ ...v, email: e.target.value }))} />
            </div>
            <div className="md:col-span-2">
              <label className="mb-1 block text-sm text-slate-600">Full name</label>
              <Input value={form.full_name} onChange={(e) => setForm((v) => ({ ...v, full_name: e.target.value }))} />
            </div>
            <div className="md:col-span-2">
              <label className="mb-1 block text-sm text-slate-600">Password</label>
              <Input type="password" value={form.password} onChange={(e) => setForm((v) => ({ ...v, password: e.target.value }))} />
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-600">Organization</label>
              <Input value={form.organization_name} onChange={(e) => setForm((v) => ({ ...v, organization_name: e.target.value }))} />
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-600">Workspace</label>
              <Input value={form.workspace_name} onChange={(e) => setForm((v) => ({ ...v, workspace_name: e.target.value }))} />
            </div>
            {error ? <p className="md:col-span-2 text-sm text-red-600">{error}</p> : null}
            <div className="md:col-span-2">
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Creating account..." : "Create account"}
              </Button>
            </div>
            <p className="md:col-span-2 text-sm text-slate-500">
              Already have an account? <Link href="/signin" className="text-brand-600">Sign in</Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

