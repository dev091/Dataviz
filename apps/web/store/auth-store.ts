import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { WorkspaceAccess } from "@platform/types";

type AuthState = {
  accessToken: string | null;
  refreshToken: string | null;
  email: string | null;
  userId: string | null;
  workspaces: WorkspaceAccess[];
  currentWorkspaceId: string | null;
  hasHydrated: boolean;
  setSession: (payload: {
    accessToken: string;
    refreshToken: string;
    email: string;
    userId: string;
    workspaces: WorkspaceAccess[];
  }) => void;
  selectWorkspace: (workspaceId: string) => void;
  markHydrated: () => void;
  clear: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      email: null,
      userId: null,
      workspaces: [],
      currentWorkspaceId: null,
      hasHydrated: false,
      setSession: ({ accessToken, refreshToken, email, userId, workspaces }) =>
        set({
          accessToken,
          refreshToken,
          email,
          userId,
          workspaces,
          currentWorkspaceId: workspaces[0]?.workspace_id ?? null,
        }),
      selectWorkspace: (workspaceId) => set({ currentWorkspaceId: workspaceId }),
      markHydrated: () => set({ hasHydrated: true }),
      clear: () =>
        set({
          accessToken: null,
          refreshToken: null,
          email: null,
          userId: null,
          workspaces: [],
          currentWorkspaceId: null,
        }),
    }),
    {
      name: "auth-store-v1",
      onRehydrateStorage: () => (state) => {
        state?.markHydrated();
      },
    },
  ),
);
