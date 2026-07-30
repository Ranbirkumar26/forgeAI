export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type RunStatus =
  | "queued"
  | "running"
  | "awaiting_approval"
  | "completed"
  | "failed"
  | "rejected";

export interface RunEvent {
  id: string;
  sequence: number;
  level: string;
  agent: string | null;
  event_type: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface AgentStep {
  id: string;
  agent: string;
  status: string;
  summary: string;
  token_input: number;
  token_output: number;
}

export interface ApprovalRequest {
  id: string;
  action_type: string;
  status: string;
  prompt: string;
  risk_level: string;
  payload: Record<string, unknown>;
}

export interface Artifact {
  id: string;
  kind: string;
  title: string;
  path: string | null;
  content: string | null;
  payload: Record<string, unknown>;
}

export interface VerifiedPatch {
  id: string;
  base_sha: string | null;
  diff: string;
  files_changed: string[];
  lines_added: number;
  lines_removed: number;
  applies_cleanly: boolean;
  applied_at: string | null;
  apply_output: string | null;
  checks: Array<Record<string, unknown>>;
  attempts: number;
  context_files_read: Array<Record<string, unknown>>;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  sandbox_image: string;
  provenance: Record<string, unknown>;
}

export interface LLMCall {
  id: string;
  model: string;
  messages_hash: string;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  cost_usd: number;
  created_at: string;
}

export interface TaskRun {
  id: string;
  task: string;
  repo_path: string | null;
  status: RunStatus;
  model_profile: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  events: RunEvent[];
  steps: AgentStep[];
  approvals: ApprovalRequest[];
  artifacts: Artifact[];
  verified_patches: VerifiedPatch[];
  llm_calls: LLMCall[];
}

export interface SearchItem {
  file_path: string;
  content: string;
  score: number;
  language: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json() as Promise<T>;
}

export function createRun(task: string, repoPath?: string, modelProfile = "balanced") {
  return request<TaskRun>("/api/runs", {
    method: "POST",
    body: JSON.stringify({
      task,
      repo_path: repoPath?.trim() || null,
      model_profile: modelProfile
    })
  });
}

export function getRun(runId: string) {
  return request<TaskRun>(`/api/runs/${runId}`);
}

export function approveRun(
  runId: string,
  approvalId: string,
  decision: "approved" | "rejected",
  reason?: string
) {
  return request<TaskRun>(`/api/runs/${runId}/approvals/${approvalId}`, {
    method: "POST",
    body: JSON.stringify({ decision, actor: "dashboard", reason })
  });
}

export function indexRepo(path: string) {
  return request<{ indexed_chunks: number; path: string }>("/api/repos/index", {
    method: "POST",
    body: JSON.stringify({ path })
  });
}

export function searchRepo(query: string) {
  return request<SearchItem[]>(`/api/search?q=${encodeURIComponent(query)}&limit=6`);
}
