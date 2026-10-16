import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type AskResp, type ChecksResp, type Finding } from "../api";
import { money, stamp } from "../format";
import { useSession } from "../session";
import { Badge, Card, ErrorBox, Modal, Page, SeverityBadge, Spinner, errText, useApi, useToast } from "../ui";

const RULES: Record<string, string> = {
  DUPLICATE: "Possible duplicate", STALE: "Not updated lately", MISSING_FIELDS: "Missing details", DRAFT_OVERDUE: "Closed Won not confirmed", RUN_RATE: "Big change vs recent months",
  NO_REASON: "Change with no reason", HOLIDAY: "No holiday dip", FY_END: "Stops at year end", CLOSE_DATE_PAST: "Past close date", MISSING_PHASING: "Deal cannot be phased",
  RENEWAL_OVERLAP: "Renewal may double count", LOOKALIKE: "Look-alike deals", LOST_DEAL_SPIKE: "Increase based on lost deal", AMOUNT_MISMATCH: "Deal amount vs schedule",
};
const EXAMPLES = ["Why did December drop?", "What changed since the last snapshot?", "Who has not updated their rows?", "What is going on with Kestrel?"];

export default function QualityChecks() {
  const { me } = useSession();
  const toast = useToast();
  const [status, setStatus] = useState("open");
  const [rule, setRule] = useState("");
  const [mine, setMine] = useState(false);
  const { data, error, loading, reload } = useApi(() => api.get<ChecksResp>("/checks", { status, rule, mine }), [status, rule, mine]);
  const [busy, setBusy] = useState(false);
  const [resolve, setResolve] = useState<{ f: Finding; kind: "accepted" | "dismissed" } | null>(null);

  const run = async () => { setBusy(true); try { await api.post("/checks/run"); toast("success", "Quality checks finished."); reload(); } catch (e) { toast("danger", errText(e)); } finally { setBusy(false); } };
  return (
    <Page title="Quality checks" subtitle="Automatic checks look for double entries, stale rows, odd changes and HubSpot mismatches. They never change your numbers: a person accepts or dismisses each one, with a reason."
      actions={<button className="btn btn-primary btn-sm" disabled={busy} onClick={run}>{busy ? "Checking..." : "Run quality checks now"}</button>}>
      <Ask enabled={me.ai_enabled} />
      {error && <ErrorBox error={error} onRetry={reload} />}
      {data && (
        <div className="d-flex flex-wrap gap-2 align-items-center mb-3">
          <Badge tone="danger">{data.summary.by_severity.high} high</Badge><Badge tone="warning">{data.summary.by_severity.medium} medium</Badge><Badge tone="secondary">{data.summary.by_severity.low} low</Badge>
          <span className="text-muted small ms-2">Last run {stamp(data.last_run) || "not yet"}. Runs automatically every night.</span>
        </div>
      )}
      <div className="card shadow-sm mb-3"><div className="card-body py-2 d-flex flex-wrap gap-3 align-items-end">
        <div><label className="form-label small mb-0" htmlFor="c-status">Show</label><select id="c-status" className="form-select form-select-sm" value={status} onChange={(e) => setStatus(e.target.value)}><option value="open">Waiting for a decision</option><option value="accepted">Accepted</option><option value="dismissed">Dismissed</option><option value="">Everything</option></select></div>
        <div><label className="form-label small mb-0" htmlFor="c-rule">Type</label><select id="c-rule" className="form-select form-select-sm" value={rule} onChange={(e) => setRule(e.target.value)}><option value="">All types</option>{Object.entries(data?.summary.by_rule ?? {}).map(([k, n]) => <option key={k} value={k}>{RULES[k] ?? k} ({n})</option>)}</select></div>
        <div className="form-check"><input className="form-check-input" type="checkbox" id="c-mine" checked={mine} onChange={(e) => setMine(e.target.checked)} /><label className="form-check-label" htmlFor="c-mine">Only mine</label></div>
      </div></div>
      {loading && !data && <Spinner />}
      {data?.findings.length === 0 && <div className="alert alert-success">Nothing here. </div>}
      {data?.findings.map((f) => (
        <article key={f.id} className={`card shadow-sm mb-2 finding sev-${f.severity} ${f.status !== "open" ? "done" : ""}`}>
          <div className="card-body">
            <div className="d-flex flex-wrap justify-content-between gap-2">
              <div><SeverityBadge s={f.severity} /> <Badge tone="light">{RULES[f.rule] ?? f.rule}</Badge> {f.status !== "open" && <Badge tone={f.status === "accepted" ? "success" : "dark"}>{f.status === "accepted" ? "Accepted" : "Dismissed"}</Badge>}
                <h2 className="h6 mt-2 mb-1">{f.title}</h2></div>
              <div className="text-end small text-muted">Owner: <strong>{f.owner_name}</strong><br />Impact about {money(f.impact)}</div>
            </div>
            <ul className="mb-2">{f.evidence.map((e, i) => <li key={i}>{e}</li>)}</ul>
            <div className="small mb-2"><strong>Suggested fix:</strong> {f.fix}</div>
            {f.rows.length > 0 && <div className="small mb-2">Projects: {f.rows.map((r) => <Link key={r.id} className="me-2" to={`/forecast?q=${r.id}`}>{r.customer} ({r.id})</Link>)}</div>}
            {f.resolution && <div className="small text-muted mb-2">{f.status === "accepted" ? "Accepted" : "Dismissed"} by {f.resolution.by_name} on {stamp(f.resolution.at)}: "{f.resolution.reason}"</div>}
            <div className="d-flex gap-2">
              {f.status === "open" && f.can_resolve && <><button className="btn btn-sm btn-outline-success" onClick={() => setResolve({ f, kind: "accepted" })}>Accept: this is right, I will fix it</button><button className="btn btn-sm btn-outline-secondary" onClick={() => setResolve({ f, kind: "dismissed" })}>Dismiss: not a problem</button></>}
              {f.status === "open" && !f.can_resolve && <span className="small text-muted">Only {f.owner_name} or Sales leadership can accept or dismiss this.</span>}
              {f.status !== "open" && f.can_resolve && <button className="btn btn-sm btn-link" onClick={async () => { try { await api.post(`/checks/${f.id}/resolve`, { status: "open" }); reload(); } catch (e) { toast("danger", errText(e)); } }}>Reopen</button>}
            </div>
          </div>
        </article>
      ))}
      {resolve && <ResolveModal {...resolve} onClose={() => setResolve(null)} onDone={() => { setResolve(null); reload(); }} />}
    </Page>
  );
}

function ResolveModal({ f, kind, onClose, onDone }: { f: Finding; kind: "accepted" | "dismissed"; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [reason, setReason] = useState("");
  const go = async () => {
    try { await api.post(`/checks/${f.id}/resolve`, { status: kind, reason }); toast("success", kind === "accepted" ? "Accepted" : "Dismissed"); onDone(); }
    catch (e) { toast("danger", errText(e)); }
  };
  return (
    <Modal title={kind === "accepted" ? "Accept this check" : "Dismiss this check"} onClose={onClose} footer={<><button className="btn btn-outline-secondary" onClick={onClose}>Cancel</button><button className="btn btn-primary" disabled={!reason.trim()} onClick={go}>{kind === "accepted" ? "Accept" : "Dismiss"}</button></>}>
      <p><strong>{f.title}</strong></p>
      <p className="text-muted">{kind === "accepted" ? "Accepting means the check is right and the owner will correct the data. Nothing changes automatically." : "Dismissing means this is expected. It will not come back unless the facts change."}</p>
      <label className="form-label fw-semibold" htmlFor="res-reason">Reason (required)</label>
      <textarea id="res-reason" className="form-control" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
    </Modal>
  );
}

function Ask({ enabled }: { enabled: boolean }) {
  const [q, setQ] = useState("");
  const [ans, setAns] = useState<AskResp | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const go = async (text: string) => {
    if (!text.trim()) return;
    setBusy(true); setErr(null);
    try { setAns(await api.post<AskResp>("/ask", { question: text })); } catch (e) { setErr(errText(e)); } finally { setBusy(false); }
  };
  return (
    <Card title="Ask about the forecast">
      <form className="d-flex gap-2 mb-2" onSubmit={(e) => { e.preventDefault(); go(q); }}>
        <input className="form-control" aria-label="Your question" placeholder="For example: Why did December drop?" value={q} onChange={(e) => setQ(e.target.value)} maxLength={500} />
        <button className="btn btn-primary" disabled={busy}>{busy ? "Thinking..." : "Ask"}</button>
      </form>
      <div className="d-flex flex-wrap gap-2 mb-2">{EXAMPLES.map((x) => <button key={x} className="btn btn-sm btn-outline-secondary" onClick={() => { setQ(x); go(x); }}>{x}</button>)}</div>
      {err && <ErrorBox error={err} />}
      {ans && (
        <div className="border rounded p-3 bg-light" aria-live="polite">
          <h3 className="h6">{ans.title} <Badge tone={ans.used_ai ? "info" : "secondary"}>{ans.used_ai ? "Written with AI help" : "Standard answer"}</Badge></h3>
          {ans.notice && <div className="alert alert-warning py-1">{ans.notice}</div>}
          {ans.answer.map((p, i) => <p key={i} className="mb-1">{p}</p>)}
          {ans.cites.length > 0 && <details className="mt-2"><summary>Based on {ans.cites.length} project{ans.cites.length === 1 ? "" : "s"} and history entries</summary>
            <ul className="small mt-1 mb-0">{ans.cites.map((c, i) => <li key={i}><Link to={`/forecast?q=${c.row_id}`}>{c.label} ({c.row_id})</Link>{c.entry_id && <> - change {c.entry_id}: {c.entry}</>}</li>)}</ul></details>}
          <div className="form-text">{enabled ? "Only a short summary of the facts above is sent to Claude, never the whole forecast." : "Answers are built from the forecast data and the audit history."}</div>
        </div>
      )}
    </Card>
  );
}
