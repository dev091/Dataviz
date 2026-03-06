import { useAuthStore } from "@/store/auth-store";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  opts: { withAuth?: boolean; workspaceScoped?: boolean } = { withAuth: true, workspaceScoped: true },
): Promise<T> {
  const state = useAuthStore.getState();
  const headers = new Headers(init.headers);
  const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;
  if (!isFormData) {
    headers.set("Content-Type", headers.get("Content-Type") ?? "application/json");
  }

  if (opts.withAuth && state.accessToken) {
    headers.set("Authorization", `Bearer ${state.accessToken}`);
  }
  if (opts.workspaceScoped !== false && state.currentWorkspaceId) {
    headers.set("X-Workspace-Id", state.currentWorkspaceId);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `API request failed with status ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export { API_BASE };
