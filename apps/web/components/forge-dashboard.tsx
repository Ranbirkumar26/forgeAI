"use client";

import {
  Activity,
  Boxes,
  Check,
  Clock3,
  Code2,
  Database,
  Eye,
  FileText,
  GitPullRequest,
  Lock,
  Play,
  Radar,
  RefreshCw,
  Rocket,
  Search,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  X
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  API_BASE,
  ApprovalRequest,
  Artifact,
  RunEvent,
  SearchItem,
  TaskRun,
  approveRun,
  createRun,
  getRun,
  indexRepo,
  searchRepo
} from "@/lib/api";

const agents = [
  { id: "planner", label: "Planner", icon: Radar },
  { id: "repo-rag", label: "Repo RAG", icon: Database },
  { id: "coder", label: "Coder", icon: Code2 },
  { id: "testing", label: "Testing", icon: TerminalSquare },
  { id: "vision", label: "Vision", icon: Eye },
  { id: "security", label: "Security", icon: ShieldCheck },
  { id: "review", label: "Review", icon: GitPullRequest },
  { id: "docs", label: "Docs", icon: FileText },
  { id: "deployment", label: "Deploy", icon: Rocket },
  { id: "memory", label: "Memory", icon: Boxes }
];

const demoTask =
  "Inspect this repository, prepare a small product-quality improvement, test it, visually review it, and generate release notes.";

export function ForgeDashboard() {
  const [task, setTask] = useState(demoTask);
  const [repoPath, setRepoPath] = useState(process.env.NEXT_PUBLIC_DEMO_REPO_PATH ?? "");
  const [run, setRun] = useState<TaskRun | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [query, setQuery] = useState("approval gated coder agent");
  const [searchResults, setSearchResults] = useState<SearchItem[]>([]);
  const [isBusy, setIsBusy] = useState(false);
  const [notice, setNotice] = useState("Ready for a local autonomous engineering run.");

  const pendingApproval = run?.approvals.find((approval) => approval.status === "pending") ?? null;
  const completedAgents = new Set(run?.steps.map((step) => step.agent) ?? []);
  const latestEvent = events.at(-1)?.message ?? notice;

  const tokenTotal = useMemo(() => {
    return (run?.steps ?? []).reduce((total, step) => total + step.token_input + step.token_output, 0);
  }, [run]);

  useEffect(() => {
    if (!run?.id) return;
    const interval = window.setInterval(async () => {
      try {
        const fresh = await getRun(run.id);
        setRun(fresh);
        setEvents(fresh.events);
      } catch (error) {
        setNotice(error instanceof Error ? error.message : "Unable to refresh run.");
      }
    }, 1800);
    const source = new EventSource(`${API_BASE}/api/runs/${run.id}/events`);
    source.addEventListener("run_event", (event) => {
      const parsed = JSON.parse((event as MessageEvent).data) as RunEvent;
      setEvents((current) => {
        if (current.some((item) => item.id === parsed.id)) return current;
        return [...current, parsed].sort((a, b) => a.sequence - b.sequence);
      });
    });
    source.addEventListener("run_done", () => source.close());
    source.onerror = () => source.close();
    return () => {
      window.clearInterval(interval);
      source.close();
    };
  }, [run?.id]);

  async function onCreateRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsBusy(true);
    try {
      const created = await createRun(task, repoPath);
      setRun(created);
      setEvents(created.events);
      setNotice("Run submitted. Agents are waking up.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Run failed to start.");
    } finally {
      setIsBusy(false);
    }
  }

  async function onIndexRepo() {
    if (!repoPath.trim()) {
      setNotice("Add a local repository path before indexing.");
      return;
    }
    setIsBusy(true);
    try {
      const result = await indexRepo(repoPath);
      setNotice(`Indexed ${result.indexed_chunks} chunks from ${result.path}.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Repository indexing failed.");
    } finally {
      setIsBusy(false);
    }
  }

  async function onSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsBusy(true);
    try {
      const results = await searchRepo(query);
      setSearchResults(results);
      setNotice(`Found ${results.length} semantic matches.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Search failed.");
    } finally {
      setIsBusy(false);
    }
  }

  async function resolveApproval(approval: ApprovalRequest, decision: "approved" | "rejected") {
    if (!run) return;
    setIsBusy(true);
    try {
      const updated = await approveRun(run.id, approval.id, decision);
      setRun(updated);
      setEvents(updated.events);
      setNotice(`Approval ${decision}.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Approval failed.");
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">ForgeAI Control Plane</p>
          <h1>Autonomous software engineering, with a human hand on the launch key.</h1>
        </div>
        <div className="status-pill" data-status={run?.status ?? "idle"}>
          <Activity size={16} />
          <span>{run?.status?.replace("_", " ") ?? "idle"}</span>
        </div>
      </header>

      <section className="metrics-band">
        <Metric label="Agents" value={`${completedAgents.size}/${agents.length}`} detail="completed" />
        <Metric label="Approvals" value={String(run?.approvals.length ?? 0)} detail="requested" />
        <Metric label="Artifacts" value={String(run?.artifacts.length ?? 0)} detail="generated" />
        <Metric label="Tokens" value={String(tokenTotal)} detail="tracked" />
      </section>

      <section className="workspace">
        <div className="left-rail">
          <form className="panel composer" onSubmit={onCreateRun}>
            <div className="panel-title">
              <Sparkles size={18} />
              <span>New Task</span>
            </div>
            <textarea value={task} onChange={(event) => setTask(event.target.value)} />
            <input
              value={repoPath}
              onChange={(event) => setRepoPath(event.target.value)}
              placeholder="/absolute/path/to/repository"
            />
            <div className="button-row">
              <button type="submit" disabled={isBusy}>
                <Play size={16} />
                Start Run
              </button>
              <button type="button" className="secondary" onClick={onIndexRepo} disabled={isBusy}>
                <Database size={16} />
                Index Repo
              </button>
            </div>
          </form>

          <ApprovalPanel approval={pendingApproval} busy={isBusy} onResolve={resolveApproval} />

          <form className="panel search-panel" onSubmit={onSearch}>
            <div className="panel-title">
              <Search size={18} />
              <span>Vector Search</span>
            </div>
            <input value={query} onChange={(event) => setQuery(event.target.value)} />
            <button type="submit" disabled={isBusy}>
              <Search size={16} />
              Search
            </button>
            <div className="search-results">
              {searchResults.map((item) => (
                <article key={`${item.file_path}-${item.score}`} className="result-item">
                  <strong>{item.file_path}</strong>
                  <span>{item.language} · {item.score.toFixed(3)}</span>
                  <p>{item.content.slice(0, 180)}</p>
                </article>
              ))}
            </div>
          </form>
        </div>

        <div className="main-grid">
          <section className="panel graph-panel">
            <div className="panel-title">
              <Radar size={18} />
              <span>Live Agent Graph</span>
            </div>
            <div className="agent-grid">
              {agents.map((agent) => {
                const Icon = agent.icon;
                const isComplete = completedAgents.has(agent.id);
                const isWaiting = pendingApproval && agent.id === "coder";
                return (
                  <div
                    key={agent.id}
                    className="agent-node"
                    data-complete={isComplete}
                    data-waiting={Boolean(isWaiting)}
                  >
                    <Icon size={19} />
                    <span>{agent.label}</span>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="panel timeline-panel">
            <div className="panel-title">
              <Clock3 size={18} />
              <span>Timeline</span>
            </div>
            <p className="latest">{latestEvent}</p>
            <div className="timeline">
              {events.length === 0 ? (
                <p className="empty">Start a run to watch the agent trace stream in.</p>
              ) : (
                events
                  .slice()
                  .reverse()
                  .map((event) => <TimelineItem key={event.id} event={event} />)
              )}
            </div>
          </section>

          <ArtifactsPanel artifacts={run?.artifacts ?? []} />
        </div>
      </section>
    </main>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function ApprovalPanel({
  approval,
  busy,
  onResolve
}: {
  approval: ApprovalRequest | null;
  busy: boolean;
  onResolve: (approval: ApprovalRequest, decision: "approved" | "rejected") => void;
}) {
  return (
    <section className="panel approval-panel" data-active={Boolean(approval)}>
      <div className="panel-title">
        <Lock size={18} />
        <span>Approval Gate</span>
      </div>
      {approval ? (
        <>
          <p>{approval.prompt}</p>
          <div className="risk-line">
            <span>Action</span>
            <strong>{approval.action_type}</strong>
            <span>Risk</span>
            <strong>{approval.risk_level}</strong>
          </div>
          <div className="button-row">
            <button type="button" onClick={() => onResolve(approval, "approved")} disabled={busy}>
              <Check size={16} />
              Approve
            </button>
            <button
              type="button"
              className="danger"
              onClick={() => onResolve(approval, "rejected")}
              disabled={busy}
            >
              <X size={16} />
              Reject
            </button>
          </div>
        </>
      ) : (
        <p className="empty">No pending approvals. Mutating actions will stop here before execution.</p>
      )}
    </section>
  );
}

function TimelineItem({ event }: { event: RunEvent }) {
  return (
    <article className="timeline-item" data-level={event.level}>
      <div>
        <strong>{event.agent ?? "system"}</strong>
        <span>{event.event_type}</span>
      </div>
      <p>{event.message}</p>
    </article>
  );
}

function ArtifactsPanel({ artifacts }: { artifacts: Artifact[] }) {
  return (
    <section className="panel artifacts-panel">
      <div className="panel-title">
        <FileText size={18} />
        <span>Artifacts</span>
      </div>
      <div className="artifact-list">
        {artifacts.length === 0 ? (
          <p className="empty">Plans, patches, visual diffs, reviews, and docs will appear here.</p>
        ) : (
          artifacts.map((artifact) => (
            <article key={artifact.id} className="artifact-item">
              <div>
                <strong>{artifact.title}</strong>
                <span>{artifact.kind}</span>
              </div>
              {artifact.content ? <pre>{artifact.content.slice(0, 520)}</pre> : null}
              {artifact.path ? <code>{artifact.path}</code> : null}
            </article>
          ))
        )}
      </div>
    </section>
  );
}

