"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { PropsWithChildren, useEffect, useMemo } from "react";

import { Button } from "@platform/ui";

import { useAuthStore } from "@/store/auth-store";

const navItems = [
  { href: "/workspaces", label: "Workspaces" },
  { href: "/dashboards", label: "Dashboards" },
  { href: "/datasets", label: "Datasets" },
  { href: "/connections", label: "Connections" },
  { href: "/semantic", label: "Semantic" },
  { href: "/nl-analytics", label: "NL Analytics" },
  { href: "/alerts", label: "Alerts" },
  { href: "/admin", label: "Admin" },
  { href: "/audit", label: "Audit" },
];

export function AppShell({ children }: PropsWithChildren) {
  const pathname = usePathname();
  const router = useRouter();
  const { accessToken, workspaces, currentWorkspaceId, selectWorkspace, clear, email } = useAuthStore();

  const isAuthScreen = useMemo(() => pathname.startsWith("/signin") || pathname.startsWith("/signup"), [pathname]);

  useEffect(() => {
    if (!accessToken && !isAuthScreen) {
      router.push("/signin");
    }
  }, [accessToken, isAuthScreen, router]);

  if (isAuthScreen) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen px-4 py-5 md:px-8">
      <div className="mx-auto grid max-w-[1400px] grid-cols-1 gap-4 md:grid-cols-[240px,1fr]">
        <aside className="panel h-fit p-4">
          <div className="mb-5">
            <h1 className="text-base font-semibold">Autonomy Analytics</h1>
            <p className="text-xs text-slate-500">AI-native BI platform</p>
          </div>

          <nav className="space-y-1">
            {navItems.map((item) => {
              const active = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`block rounded-md px-3 py-2 text-sm ${active ? "bg-brand-100 text-brand-900" : "text-slate-600 hover:bg-slate-100"}`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </aside>

        <main className="space-y-4">
          <header className="panel flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Workspace</p>
              <select
                className="mt-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
                value={currentWorkspaceId ?? ""}
                onChange={(e) => selectWorkspace(e.target.value)}
              >
                {workspaces.map((workspace) => (
                  <option key={workspace.workspace_id} value={workspace.workspace_id}>
                    {workspace.organization_name} / {workspace.workspace_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-3">
              <p className="text-sm text-slate-600">{email}</p>
              <Button
                variant="secondary"
                onClick={() => {
                  clear();
                  router.push("/signin");
                }}
              >
                Sign out
              </Button>
            </div>
          </header>

          {children}
        </main>
      </div>
    </div>
  );
}
