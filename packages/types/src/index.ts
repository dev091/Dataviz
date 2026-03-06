export type WorkspaceAccess = {
  workspace_id: string;
  workspace_name: string;
  organization_id: string;
  organization_name: string;
  role: "Owner" | "Admin" | "Analyst" | "Viewer";
};

export type AuthPayload = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user_id: string;
  email: string;
  workspaces: WorkspaceAccess[];
};

export type NLQueryResult = {
  ai_query_session_id: string;
  plan: Record<string, unknown>;
  agent_trace: Array<Record<string, unknown>>;
  sql: string;
  rows: Array<Record<string, unknown>>;
  chart: Record<string, unknown>;
  summary: string;
  insights: Array<Record<string, unknown>>;
  follow_up_questions: string[];
  created_at: string;
};
