"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { Button, Card, CardContent, CardHeader, CardTitle, Input } from "@/components/ui";

import { apiRequest } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

import type { AuthPayload } from "@platform/types";

export default function SigninPage() {
  const router = useRouter();
  const setSession = useAuthStore((state) => state.setSession);

  const [email, setEmail] = useState("owner@dataviz.com");
  const [password, setPassword] = useState("Password123!");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const payload = await apiRequest<AuthPayload>(
        "/api/v1/auth/login",
        {
          method: "POST",
          body: JSON.stringify({ email, password }),
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
      setError(err instanceof Error ? err.message : "Failed to sign in");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md items-center">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Sign in</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-3" onSubmit={onSubmit}>
            <div>
              <label className="mb-1 block text-sm text-slate-600">Email</label>
              <Input value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-600">Password</label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            {error ? <p className="text-sm text-red-600">{error}</p> : null}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Signing in..." : "Sign in"}
            </Button>
            <p className="text-sm text-slate-500">
              No account? <Link href="/signup" className="text-brand-600">Create one</Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}


