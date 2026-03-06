import { create } from "zustand";

export type LastNLResult = {
  aiQuerySessionId: string;
  summary: string;
  chart: Record<string, unknown>;
  rows: Array<Record<string, unknown>>;
};

type NLState = {
  lastResult: LastNLResult | null;
  setLastResult: (result: LastNLResult) => void;
};

export const useNLStore = create<NLState>((set) => ({
  lastResult: null,
  setLastResult: (result) => set({ lastResult: result }),
}));
