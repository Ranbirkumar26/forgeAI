"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Activity,
  AlertTriangle,
  Box,
  Check,
  ClipboardCheck,
  Copy,
  Database,
  FileDiff,
  GitBranch,
  Moon,
  Play,
  Search,
  ShieldCheck,
  Sun,
  Terminal,
  X
} from "lucide-react";
import {
  API_BASE,
  approveRun,
  createRun,
  getRun,
  indexRepo,
  searchRepo,
  type AgentStep,
  type Artifact,
  type ApprovalRequest,
  type RunEvent,
  type RunStatus,
  type SearchItem,
  type TaskRun,
  type VerifiedPatch
} from "../lib/api";

type Theme = "light" | "dark";
type Decision = "approved" | "rejected";

const defaultTask =
  "Add server-side validation to the demo API and return a verified patch with tests.";

const agentPlan = [
  {
    key: "planner",
    label: "Planner",
    icon: GitBranch,
    copy: "Scopes work, risk, and evidence."
  },
  {
    key: "engineer",
    label: "Engineer",
    icon: Terminal,
    copy: "Reads repo context and drafts patch."
  },
  {
    key: "reviewer",
    label: "Reviewer",
    icon: ShieldCheck,
    copy: "Checks policy, tests, and apply safety."
  },
  {
    key: "documenter",
    label: "Documenter",
    icon: ClipboardCheck,
    copy: "Writes changelog and handoff notes."
  }
] as const;

function formatTime(value?: string | null) {
  if (!value) {
    return "Pending";
  }
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  }).format(new Date(value));
}

function formatStatus(status?: RunStatus | string) {
  if (!status) {
    return "Idle";
  }
  return status.replaceAll("_", " ");
}

function statusClass(status?: string) {
  return (status ?? "idle").replaceAll(" ", "_").replaceAll("/", "_").toLowerCase();
}

function mergeEvents(current: RunEvent[], next: RunEvent) {
  if (current.some((event) => event.id === next.id)) {
    return current;
  }
  return [...current, next].slice(-120);
}

function latestPatch(run: TaskRun | null): VerifiedPatch | null {
  if (!run?.verified_patches.length) {
    return null;
  }
  return run.verified_patches[run.verified_patches.length - 1] ?? null;
}

function activeApproval(run: TaskRun | null): ApprovalRequest | null {
  return run?.approvals.find((approval) => approval.status === "pending") ?? null;
}

function valueText(value: unknown) {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (value == null) {
    return "";
  }
  return JSON.stringify(value);
}

function diffClass(line: string) {
  if (line.startsWith("+") && !line.startsWith("+++")) {
    return "diff-add";
  }
  if (line.startsWith("-") && !line.startsWith("---")) {
    return "diff-remove";
  }
  if (line.startsWith("@@") || line.startsWith("diff --git")) {
    return "diff-meta";
  }
  return "";
}

function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark">F</span>
      <div>
        <p className="eyebrow">ForgeAI</p>
        <h1>Verified software agent</h1>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status?: RunStatus | string }) {
  return (
    <span className={`status-pill status-${statusClass(status)}`}>
      <span aria-hidden="true" />
      {formatStatus(status)}
    </span>
  );
}

function IconButton({
  label,
  onClick,
  children
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button className="icon-button" onClick={onClick} title={label} aria-label={label}>
      {children}
    </button>
  );
}

function RunComposer({
  task,
  repoPath,
  busy,
  onTaskChange,
  onRepoPathChange,
  onRun,
  onIndex
}: {
  task: string;
  repoPath: string;
  busy: boolean;
  onTaskChange: (value: string) => void;
  onRepoPathChange: (value: string) => void;
  onRun: () => void;
  onIndex: () => void;
}) {
  return (
    <section className="panel command-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">New run</p>
          <h2>Task command</h2>
        </div>
        <Play size={18} aria-hidden="true" />
      </div>

      <label className="field">
        <span>Task</span>
        <textarea
          value={task}
          onChange={(event) => onTaskChange(event.target.value)}
          rows={5}
          spellCheck={false}
        />
      </label>

      <label className="field">
        <span>Repository path</span>
        <input
          value={repoPath}
          onChange={(event) => onRepoPathChange(event.target.value)}
          placeholder="/absolute/path/to/repo"
          spellCheck={false}
        />
      </label>

      <div className="button-row">
        <button className="button primary" onClick={onRun} disabled={busy || !task.trim()}>
          <Play size={16} aria-hidden="true" />
          Start run
        </button>
        <button className="button secondary" onClick={onIndex} disabled={busy || !repoPath.trim()}>
          <Database size={16} aria-hidden="true" />
          Index repo
        </button>
      </div>
    </section>
  );
}

function ApprovalPanel({
  approval,
  busy,
  onDecision
}: {
  approval: ApprovalRequest | null;
  busy: boolean;
  onDecision: (decision: Decision, reason?: string) => void;
}) {
  const [reason, setReason] = useState("");

  useEffect(() => {
    setReason("");
  }, [approval?.id]);

  if (!approval) {
    return (
      <section className="panel approval-panel muted-panel">
        <div className="empty-state">
          <ShieldCheck size={22} aria-hidden="true" />
          <div>
            <h2>No approval pending</h2>
            <p>Mutating actions wait here before any patch apply or deploy action runs.</p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="panel approval-panel attention">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Approval gate</p>
          <h2>{approval.action_type}</h2>
        </div>
        <StatusPill status={approval.risk_level} />
      </div>
      <p className="approval-copy">{approval.prompt}</p>
      <label className="field">
        <span>Decision note</span>
        <textarea
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          rows={3}
          placeholder="Optional audit note"
        />
      </label>
      <div className="button-row">
        <button className="button primary" onClick={() => onDecision("approved", reason)} disabled={busy}>
          <Check size={16} aria-hidden="true" />
          Approve
        </button>
        <button className="button danger" onClick={() => onDecision("rejected", reason)} disabled={busy}>
          <X size={16} aria-hidden="true" />
          Reject
        </button>
      </div>
    </section>
  );
}

function SearchPanel({
  query,
  results,
  busy,
  onQueryChange,
  onSearch
}: {
  query: string;
  results: SearchItem[];
  busy: boolean;
  onQueryChange: (value: string) => void;
  onSearch: () => void;
}) {
  return (
    <section className="panel search-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Repo RAG</p>
          <h2>Semantic search</h2>
        </div>
        <Search size={18} aria-hidden="true" />
      </div>
      <div className="search-row">
        <input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              onSearch();
            }
          }}
          placeholder="Search indexed code"
          spellCheck={false}
        />
        <button className="button secondary icon-only" onClick={onSearch} disabled={busy || !query.trim()} aria-label="Search">
          <Search size={16} aria-hidden="true" />
        </button>
      </div>
      <div className="search-results">
        {results.length === 0 ? (
          <p className="quiet">Index a repo, then query symbols, routes, or bug context.</p>
        ) : (
          results.map((item) => (
            <article className="search-result" key={`${item.file_path}-${item.score}`}>
              <div className="result-meta">
                <strong>{item.file_path}</strong>
                <span>{item.language || "text"}</span>
              </div>
              <p>{item.content}</p>
              <span className="score">{item.score.toFixed(3)}</span>
            </article>
          ))
        )}
      </div>
    </section>
  );
}

function MetricStrip({ run, patch }: { run: TaskRun | null; patch: VerifiedPatch | null }) {
  const tokens = (run?.llm_calls ?? []).reduce(
    (total, call) => total + call.tokens_in + call.tokens_out,
    patch ? patch.tokens_in + patch.tokens_out : 0
  );
  const cost = (run?.llm_calls ?? []).reduce(
    (total, call) => total + call.cost_usd,
    patch?.cost_usd ?? 0
  );

  return (
    <section className="metric-strip" aria-label="Run metrics">
      <div className="metric">
        <span>Status</span>
        <strong>{formatStatus(run?.status)}</strong>
      </div>
      <div className="metric">
        <span>Patch</span>
        <strong>{patch ? `${patch.files_changed.length} files` : "None"}</strong>
      </div>
      <div className="metric">
        <span>Checks</span>
        <strong>{patch ? patch.checks.length : 0}</strong>
      </div>
      <div className="metric">
        <span>Tokens</span>
        <strong>{tokens.toLocaleString()}</strong>
      </div>
      <div className="metric">
        <span>Cost</span>
        <strong>${cost.toFixed(4)}</strong>
      </div>
    </section>
  );
}

function AgentGraph({ steps, runStatus }: { steps: AgentStep[]; runStatus?: RunStatus }) {
  return (
    <section className="panel graph-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Execution graph</p>
          <h2>Agent trace</h2>
        </div>
        <Activity size={18} aria-hidden="true" />
      </div>

      <div className="agent-grid">
        {agentPlan.map((agent, index) => {
          const Icon = agent.icon;
          const step = steps.find((item) => item.agent.toLowerCase().includes(agent.key));
          const state = step?.status ?? (runStatus === "queued" && index === 0 ? "queued" : "idle");

          return (
            <article className={`agent-node agent-${statusClass(state)}`} key={agent.key}>
              <div className="node-topline">
                <span className="node-icon">
                  <Icon size={17} aria-hidden="true" />
                </span>
                <StatusPill status={state} />
              </div>
              <h3>{agent.label}</h3>
              <p>{step?.summary || agent.copy}</p>
              <div className="node-tokens">
                <span>{(step?.token_input ?? 0).toLocaleString()} in</span>
                <span>{(step?.token_output ?? 0).toLocaleString()} out</span>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function PatchPanel({ patch, onCopy }: { patch: VerifiedPatch | null; onCopy: () => void }) {
  if (!patch) {
    return (
      <section className="panel patch-panel muted-panel">
        <div className="empty-state">
          <FileDiff size={22} aria-hidden="true" />
          <div>
            <h2>No verified patch yet</h2>
            <p>Planner and engineer output appears here once ForgeAI can prove the patch applies.</p>
          </div>
        </div>
      </section>
    );
  }

  const lines = patch.diff.split("\n");

  return (
    <section className="panel patch-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Verified patch</p>
          <h2>{patch.files_changed.length} files changed</h2>
        </div>
        <button className="button secondary compact" onClick={onCopy}>
          <Copy size={16} aria-hidden="true" />
          Copy diff
        </button>
      </div>

      <div className="patch-summary">
        <span>+{patch.lines_added}</span>
        <span>-{patch.lines_removed}</span>
        <span>{patch.applies_cleanly ? "Applies cleanly" : "Apply check failed"}</span>
        <span>{patch.sandbox_image}</span>
      </div>

      <pre className="diff-view" aria-label="Patch diff">
        {lines.map((line, index) => (
          <span className={diffClass(line)} key={`${index}-${line.slice(0, 24)}`}>
            {line || " "}
          </span>
        ))}
      </pre>
    </section>
  );
}

function ChecksPanel({ patch }: { patch: VerifiedPatch | null }) {
  return (
    <section className="panel checks-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Evidence</p>
          <h2>Verification checks</h2>
        </div>
        <Check size={18} aria-hidden="true" />
      </div>

      {!patch?.checks.length ? (
        <p className="quiet padded">No checks reported yet.</p>
      ) : (
        <div className="check-list">
          {patch.checks.map((check, index) => (
            <article className="check-item" key={`${index}-${valueText(check.name)}`}>
              <div>
                <strong>{valueText(check.name) || `Check ${index + 1}`}</strong>
                <p>{valueText(check.output) || valueText(check.summary) || "Completed"}</p>
              </div>
              <StatusPill status={valueText(check.status) || "unknown"} />
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function TimelinePanel({ events }: { events: RunEvent[] }) {
  return (
    <section className="panel timeline-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Run events</p>
          <h2>Timeline</h2>
        </div>
        <Terminal size={18} aria-hidden="true" />
      </div>

      <div className="timeline">
        {events.length === 0 ? (
          <p className="quiet">Start a run to stream planner, engineer, reviewer, and documenter events.</p>
        ) : (
          events
            .slice()
            .reverse()
            .map((event) => (
              <article className="event-row" key={event.id}>
                <div className={`event-level level-${statusClass(event.level)}`} aria-hidden="true" />
                <div>
                  <div className="event-meta">
                    <strong>{event.agent || "system"}</strong>
                    <span>{event.event_type}</span>
                    <span>{formatTime(event.created_at)}</span>
                  </div>
                  <p>{event.message}</p>
                </div>
              </article>
            ))
        )}
      </div>
    </section>
  );
}

function ArtifactPanel({ artifacts }: { artifacts: Artifact[] }) {
  return (
    <section className="panel artifact-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Artifacts</p>
          <h2>Run output</h2>
        </div>
        <Box size={18} aria-hidden="true" />
      </div>

      {artifacts.length === 0 ? (
        <p className="quiet padded">Docs, changelog drafts, screenshots, and reports land here.</p>
      ) : (
        <div className="artifact-list">
          {artifacts.map((artifact) => (
            <article className="artifact-item" key={artifact.id}>
              <div className="result-meta">
                <strong>{artifact.title}</strong>
                <span>{artifact.kind}</span>
              </div>
              {artifact.path ? <code>{artifact.path}</code> : null}
              {artifact.content ? <p>{artifact.content}</p> : null}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export function ForgeDashboard() {
  const [theme, setTheme] = useState<Theme>("light");
  const [task, setTask] = useState(defaultTask);
  const [repoPath, setRepoPath] = useState("");
  const [run, setRun] = useState<TaskRun | null>(null);
  const [streamEvents, setStreamEvents] = useState<RunEvent[]>([]);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchItem[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const patch = latestPatch(run);
  const approval = activeApproval(run);
  const events = useMemo(() => {
    const all = [...(run?.events ?? []), ...streamEvents];
    const byId = new Map(all.map((event) => [event.id, event]));
    return [...byId.values()].sort((left, right) => left.sequence - right.sequence);
  }, [run?.events, streamEvents]);

  useEffect(() => {
    const dark = document.documentElement.classList.contains("dark");
    setTheme(dark ? "dark" : "light");
  }, []);

  useEffect(() => {
    if (!run?.id) {
      return;
    }

    let cancelled = false;
    const refresh = async () => {
      try {
        const next = await getRun(run.id);
        if (!cancelled) {
          setRun(next);
        }
      } catch (error) {
        if (!cancelled) {
          setNotice(error instanceof Error ? error.message : "Run refresh failed");
        }
      }
    };

    const source = new EventSource(`${API_BASE}/api/runs/${run.id}/events`);
    source.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as RunEvent;
        setStreamEvents((current) => mergeEvents(current, event));
        void refresh();
      } catch {
        setNotice("Event stream returned malformed data");
      }
    };
    source.onerror = () => {
      source.close();
    };

    const interval = window.setInterval(() => {
      void refresh();
    }, 2500);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
      source.close();
    };
  }, [run?.id]);

  const setDocumentTheme = (next: Theme) => {
    setTheme(next);
    document.documentElement.classList.toggle("dark", next === "dark");
    window.localStorage.setItem("forgeai-theme", next);
  };

  const startRun = async () => {
    setBusy(true);
    setNotice(null);
    try {
      const created = await createRun(task, repoPath, "balanced");
      setRun(created);
      setStreamEvents(created.events ?? []);
      setNotice(`Run ${created.id} started`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Run creation failed");
    } finally {
      setBusy(false);
    }
  };

  const submitApproval = async (decision: Decision, reason?: string) => {
    if (!run || !approval) {
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      const next = await approveRun(run.id, approval.id, decision, reason);
      setRun(next);
      setNotice(`Approval ${decision}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Approval failed");
    } finally {
      setBusy(false);
    }
  };

  const submitIndex = async () => {
    if (!repoPath.trim()) {
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      const result = await indexRepo(repoPath);
      setNotice(`Indexed ${result.indexed_chunks} chunks from ${result.path}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Indexing failed");
    } finally {
      setBusy(false);
    }
  };

  const submitSearch = async () => {
    if (!query.trim()) {
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      setSearchResults(await searchRepo(query));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Search failed");
    } finally {
      setBusy(false);
    }
  };

  const copyPatch = async () => {
    if (!patch) {
      return;
    }
    await navigator.clipboard.writeText(patch.diff);
    setNotice("Patch diff copied");
  };

  return (
    <main className="dashboard-shell">
      <aside className="sidebar">
        <div className="sidebar-top">
          <Brand />
          <IconButton
            label={theme === "dark" ? "Use light theme" : "Use dark theme"}
            onClick={() => setDocumentTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
          </IconButton>
        </div>

        <RunComposer
          task={task}
          repoPath={repoPath}
          busy={busy}
          onTaskChange={setTask}
          onRepoPathChange={setRepoPath}
          onRun={startRun}
          onIndex={submitIndex}
        />

        <ApprovalPanel approval={approval} busy={busy} onDecision={submitApproval} />
        <SearchPanel
          query={query}
          results={searchResults}
          busy={busy}
          onQueryChange={setQuery}
          onSearch={submitSearch}
        />
      </aside>

      <section className="workspace">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Control plane</p>
            <h2>{run?.task || "Start a verified engineering run"}</h2>
          </div>
          <div className="header-actions">
            {notice ? (
              <div className="notice" role="status">
                <AlertTriangle size={15} aria-hidden="true" />
                {notice}
              </div>
            ) : null}
            <StatusPill status={run?.status} />
          </div>
        </header>

        <MetricStrip run={run} patch={patch} />

        <div className="content-grid">
          <div className="main-column">
            <AgentGraph steps={run?.steps ?? []} runStatus={run?.status} />
            <PatchPanel patch={patch} onCopy={copyPatch} />
          </div>
          <div className="side-column">
            <ChecksPanel patch={patch} />
            <TimelinePanel events={events} />
            <ArtifactPanel artifacts={run?.artifacts ?? []} />
          </div>
        </div>
      </section>
    </main>
  );
}
