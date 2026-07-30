"use client";

import { Check, Copy, Database, Play, RefreshCw, Search, X } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  API_BASE,
  ApprovalRequest,
  Artifact,
  RunEvent,
  SearchItem,
  TaskRun,
  VerifiedPatch,
  approveRun,
  createRun,
  getRun,
  indexRepo,
  searchRepo
} from "@/lib/api";

const pipeline = ["planner", "engineer", "reviewer", "documenter"];

const demoTask = "Prepare a safe README improvement with verified patch evidence.";

export function ForgeDashboard() {
  const [task, setTask] = useState(demoTask);
  const [repoPath, setRepoPath] = useState(process.env.NEXT_PUBLIC_DEMO_REPO_PATH ?? "");
  const [run, setRun] = useState<TaskRun | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [query, setQuery] = useState("approval verified patch");
  const [searchResults, setSearchResults] = useState<SearchItem[]>([]);
  const [isBusy, setIsBusy] = useState(false);
  const [notice, setNotice] = useState("Idle");

  const pendingApproval = run?.approvals.find((approval) => approval.status === "pending") ?? null;
  const latestPatch = run?.verified_patches.at(-1) ?? null;
  const completedAgents = new Set(run?.steps.map((step) => step.agent) ?? []);
  const latestEvent = events.at(-1)?.message ?? notice;

  const tokenTotal = useMemo(() => {
    const stepTokens = (run?.steps ?? []).reduce(
      (total, step) => total + step.token_input + step.token_output,
      0
    );
    const callTokens = (run?.llm_calls ?? []).reduce(
      (total, call) => total + call.tokens_in + call.tokens_out,
      0
    );
    return Math.max(stepTokens, callTokens);
  }, [run]);

  useEffect(() => {
    if (!run?.id) return;
    const interval = window.setInterval(async () => {
      try {
        const fresh = await getRun(run.id);
        setRun(fresh);
        setEvents(fresh.events);
      } catch (error) {
        setNotice(error instanceof Error ? error.message : "Refresh failed");
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
      setNotice("Run queued");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Run failed");
    } finally {
      setIsBusy(false);
    }
  }

  async function onIndexRepo() {
    if (!repoPath.trim()) {
      setNotice("Repository path required");
      return;
    }
    setIsBusy(true);
    try {
      const result = await indexRepo(repoPath);
      setNotice(`Indexed ${result.indexed_chunks} chunks`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Index failed");
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
      setNotice(`Search returned ${results.length} matches`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Search failed");
    } finally {
      setIsBusy(false);
    }
  }

  async function resolveApproval(
    approval: ApprovalRequest,
    decision: "approved" | "rejected",
    reason?: string
  ) {
    if (!run) return;
    setIsBusy(true);
    try {
      const updated = await approveRun(run.id, approval.id, decision, reason);
      setRun(updated);
      setEvents(updated.events);
      setNotice(`Approval ${decision}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Approval failed");
    } finally {
      setIsBusy(false);
    }
  }

  async function copyText(value: string) {
    await navigator.clipboard?.writeText(value);
    setNotice("Copied");
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">ForgeAI</p>
          <h1>Verified patch control plane</h1>
        </div>
        <StatusBadge status={run?.status ?? "idle"} />
      </header>

      <section className="workspace">
        <aside className="left-rail">
          <form className="panel composer" onSubmit={onCreateRun}>
            <PanelTitle title="Run" />
            <label>
              <span>Task</span>
              <textarea value={task} onChange={(event) => setTask(event.target.value)} />
            </label>
            <label>
              <span>Repository path</span>
              <input
                value={repoPath}
                onChange={(event) => setRepoPath(event.target.value)}
                placeholder="/absolute/path/to/repository"
              />
            </label>
            <div className="button-row">
              <button type="submit" disabled={isBusy}>
                <Play size={16} />
                Start
              </button>
              <button type="button" onClick={onIndexRepo} disabled={isBusy}>
                <Database size={16} />
                Index
              </button>
            </div>
          </form>

          <ApprovalPanel
            approval={pendingApproval}
            busy={isBusy}
            patch={latestPatch}
            onResolve={resolveApproval}
          />

          <form className="panel search-panel" onSubmit={onSearch}>
            <PanelTitle title="Vector Search" />
            <input value={query} onChange={(event) => setQuery(event.target.value)} />
            <button type="submit" disabled={isBusy}>
              <Search size={16} />
              Search
            </button>
            <div className="search-results">
              {searchResults.map((item) => (
                <article key={`${item.file_path}-${item.score}`} className="result-item">
                  <strong>{item.file_path}</strong>
                  <span>
                    {item.language} / {item.score.toFixed(3)}
                  </span>
                  <p>{item.content.slice(0, 180)}</p>
                </article>
              ))}
            </div>
          </form>
        </aside>

        <section className="main-grid">
          <section className="panel run-panel">
            <PanelTitle title="Run Trace" />
            <div className="run-summary">
              <Copyable label="Run ID" value={run?.id ?? "none"} onCopy={copyText} />
              <Copyable label="Base SHA" value={latestPatch?.base_sha ?? "none"} onCopy={copyText} />
              <Metric label="Files" value={String(latestPatch?.files_changed.length ?? 0)} />
              <Metric label="Tokens" value={String(tokenTotal)} />
              <Metric label="Events" value={String(events.length)} />
              <Metric label="Artifacts" value={String(run?.artifacts.length ?? 0)} />
            </div>
            <p className="latest">{latestEvent}</p>
            <div className="agent-lane">
              {pipeline.map((agent) => (
                <div key={agent} className="agent-step" data-complete={completedAgents.has(agent)}>
                  <StatusDot active={completedAgents.has(agent)} />
                  <span>{agent}</span>
                </div>
              ))}
            </div>
          </section>

          <PatchPanel patch={latestPatch} />
          <TimelinePanel events={events} />
          <ArtifactsPanel artifacts={run?.artifacts ?? []} />
        </section>
      </section>
    </main>
  );
}

function PanelTitle({ title }: { title: string }) {
  return (
    <div className="panel-title">
      <span>{title}</span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <div className="status-badge" data-status={status}>
      <StatusDot active={status === "running" || status === "completed"} />
      <span>{status.replace("_", " ")}</span>
    </div>
  );
}

function StatusDot({ active }: { active: boolean }) {
  return <span className="status-dot" data-active={active} />;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Copyable({
  label,
  value,
  onCopy
}: {
  label: string;
  value: string;
  onCopy: (value: string) => void;
}) {
  return (
    <div className="copyable">
      <span>{label}</span>
      <button type="button" onClick={() => onCopy(value)} aria-label={`Copy ${label}`}>
        <Copy size={14} />
      </button>
      <code>{value}</code>
    </div>
  );
}

function ApprovalPanel({
  approval,
  busy,
  patch,
  onResolve
}: {
  approval: ApprovalRequest | null;
  busy: boolean;
  patch: VerifiedPatch | null;
  onResolve: (approval: ApprovalRequest, decision: "approved" | "rejected", reason?: string) => void;
}) {
  const [reason, setReason] = useState("");

  if (!approval) {
    return (
      <section className="panel approval-panel">
        <PanelTitle title="Approval" />
        <p className="empty">No pending approval</p>
      </section>
    );
  }

  return (
    <section className="panel approval-panel" data-active="true">
      <PanelTitle title="Approval" />
      <p>{approval.prompt}</p>
      <div className="evidence-grid">
        <Metric label="Risk" value={approval.risk_level} />
        <Metric label="Action" value={approval.action_type} />
        <Metric label="Added" value={String(patch?.lines_added ?? 0)} />
        <Metric label="Removed" value={String(patch?.lines_removed ?? 0)} />
      </div>
      <CheckList checks={patch?.checks ?? []} />
      <label>
        <span>Rejection reason</span>
        <textarea value={reason} onChange={(event) => setReason(event.target.value)} />
      </label>
      <div className="button-row split">
        <button
          type="button"
          onClick={() => onResolve(approval, "rejected", reason)}
          disabled={busy || !reason.trim()}
        >
          <X size={16} />
          Reject
        </button>
        <button type="button" onClick={() => onResolve(approval, "approved")} disabled={busy}>
          <Check size={16} />
          Approve and apply
        </button>
      </div>
    </section>
  );
}

function PatchPanel({ patch }: { patch: VerifiedPatch | null }) {
  return (
    <section className="panel patch-panel">
      <PanelTitle title="VerifiedPatch" />
      {patch ? (
        <>
          <div className="patch-stats">
            <Metric label="Clean apply" value={patch.applies_cleanly ? "yes" : "no"} />
            <Metric label="Applied" value={patch.applied_at ? "yes" : "no"} />
            <Metric label="Attempts" value={String(patch.attempts)} />
            <Metric label="Cost" value={`$${patch.cost_usd.toFixed(4)}`} />
          </div>
          <CheckList checks={patch.checks} />
          <pre className="diff">{patch.diff}</pre>
        </>
      ) : (
        <p className="empty">No patch yet</p>
      )}
    </section>
  );
}

function CheckList({ checks }: { checks: Array<Record<string, unknown>> }) {
  if (!checks.length) return null;
  return (
    <div className="check-list">
      {checks.map((check, index) => (
        <article key={`${String(check.name)}-${index}`} className="check-row">
          <StatusDot active={Number(check.exit_code) === 0} />
          <strong>{String(check.name ?? "check")}</strong>
          <code>{String(check.command ?? "")}</code>
          <p>{String(check.output_tail ?? "")}</p>
        </article>
      ))}
    </div>
  );
}

function TimelinePanel({ events }: { events: RunEvent[] }) {
  return (
    <section className="panel timeline-panel">
      <PanelTitle title="Events" />
      <div className="timeline">
        {events.length === 0 ? (
          <p className="empty">No events yet</p>
        ) : (
          events
            .slice()
            .reverse()
            .map((event) => <TimelineItem key={event.id} event={event} />)
        )}
      </div>
    </section>
  );
}

function TimelineItem({ event }: { event: RunEvent }) {
  return (
    <article className="timeline-item" data-level={event.level}>
      <div>
        <strong>{event.agent ?? "system"}</strong>
        <span>
          #{event.sequence} {event.event_type}
        </span>
      </div>
      <p>{event.message}</p>
    </article>
  );
}

function ArtifactsPanel({ artifacts }: { artifacts: Artifact[] }) {
  return (
    <section className="panel artifacts-panel">
      <PanelTitle title="Artifacts" />
      <div className="artifact-list">
        {artifacts.length === 0 ? (
          <p className="empty">No artifacts yet</p>
        ) : (
          artifacts.map((artifact) => (
            <article key={artifact.id} className="artifact-item">
              <div>
                <strong>{artifact.title}</strong>
                <span>{artifact.kind}</span>
              </div>
              {artifact.content ? <pre>{artifact.content.slice(0, 720)}</pre> : null}
              {artifact.path ? <code>{artifact.path}</code> : null}
            </article>
          ))
        )}
      </div>
    </section>
  );
}
