import { Link } from "react-router-dom";
import { useRef, useState } from "react";
import { api, ApiError, type AccuracyResp, type Snapshot } from "../api";
import { money, monthLabel, monthLong, pct, stamp } from "../format";
import { useSession } from "../session";
import { Badge, Card, ErrorBox, Modal, Page, Spinner, Tabs, download, errText, useApi, useToast } from "../ui";

interface ActualsResult { loaded: number; months: string[]; rejects: { line: number; reason: string }[]; unmatched: { line: number; customer: string; project: string }[] }

export default function Snapshots() {
  const { me, meta, reloadMeta } = useSession();
  const toast = useToast();
  const [tab, setTab] = useState<"snaps" | "acc" | "close">("snaps");
  const snaps = useApi(() => api.get<Snapshot[]>("/snapshots"));
  const [label, setLabel] = useState("");
  const [view, setView] = useState<string | null>(null);

  const take = async () => {
    try { await api.post("/snapshots", { label }); toast("success", "Snapshot saved. It cannot be changed."); setLabel(""); snaps.reload(); }
    catch (e) { toast("danger", errText(e)); }
  };
  return (
    <Page title="Snapshots & export" subtitle="A snapshot freezes the forecast at a point in time. It is taken automatically on the first business day of each month, and Finance can take one any time. Snapshots can never be edited.">
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "snaps", label: "Snapshots and export" }, { id: "acc", label: "Actuals and accuracy" }, { id: "close", label: "Close months" }]} />
      {tab === "snaps" && (
        <>
          <Card title="Export what you see in the Forecast grid">
            <p className="mb-2">Open the <Link to="/forecast">Forecast grid</Link>, set your filters, then choose Export Excel or Export CSV. The file includes the export time and the filters used, and its totals match the screen. Or export everything:</p>
            <div className="btn-group btn-group-sm"><button className="btn btn-outline-primary" onClick={() => download(api.url("/export/forecast", { format: "xlsx" }))}>Everything as Excel</button><button className="btn btn-outline-primary" onClick={() => download(api.url("/export/forecast", { format: "csv" }))}>Everything as CSV</button></div>
          </Card>
          {me.capabilities.can_snapshot && (
            <Card title="Take a snapshot now"><form className="d-flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); take(); }}>
              <input className="form-control" style={{ maxWidth: 420 }} aria-label="Snapshot name" placeholder="Name, for example: Before the board call" value={label} onChange={(e) => setLabel(e.target.value)} /><button className="btn btn-primary">Take snapshot</button></form></Card>
          )}
          {snaps.error && <ErrorBox error={snaps.error} onRetry={snaps.reload} />}
          {snaps.loading && !snaps.data && <Spinner />}
          {snaps.data && (
            <div className="card shadow-sm"><div className="table-responsive"><table className="table table-sm align-middle mb-0">
              <thead><tr><th scope="col">Snapshot</th><th scope="col">Taken</th><th scope="col" className="num">Projects</th><th scope="col" className="num">Committed, {monthLabel(meta.window[0])}</th><th scope="col" className="num">Committed, {monthLabel(meta.window[2])}</th><th scope="col" /></tr></thead>
              <tbody>{snaps.data.map((s) => (
                <tr key={s.id}><td><strong>{s.label}</strong> {s.auto && <Badge tone="secondary">automatic</Badge>}<div className="small text-muted">{s.date}</div></td><td className="small">{stamp(s.created)} by {s.taken_by}</td><td className="num">{s.rows}</td>
                  <td className="num">{money(s.committed[meta.window[0]])}</td><td className="num">{money(s.committed[meta.window[2]])}</td>
                  <td className="text-nowrap"><button className="btn btn-link btn-sm" onClick={() => setView(s.id)}>View</button><button className="btn btn-link btn-sm" onClick={() => download(api.url(`/snapshots/${s.id}/export`, { format: "xlsx" }))}>Excel</button><button className="btn btn-link btn-sm" onClick={() => download(api.url(`/snapshots/${s.id}/export`, { format: "csv" }))}>CSV</button></td></tr>))}</tbody>
            </table></div></div>
          )}
        </>
      )}
      {tab === "acc" && <Accuracy />}
      {tab === "close" && <CloseMonths onChanged={() => { reloadMeta(); }} />}
      {view && <SnapshotView id={view} onClose={() => setView(null)} />}
    </Page>
  );
}

function SnapshotView({ id, onClose }: { id: string; onClose: () => void }) {
  const { data, error } = useApi(() => api.get<Snapshot>(`/snapshots/${id}`), [id]);
  return (
    <Modal title={data ? `${data.label} (${data.date})` : "Snapshot"} onClose={onClose} size="xl">
      {error && <ErrorBox error={error} />}{!data && !error && <Spinner />}
      {data && (
        <div className="table-responsive" style={{ maxHeight: "60vh" }}><table className="table table-sm">
          <thead className="sticky-top bg-white"><tr><th scope="col">Project</th>{data.months.map((m) => <th key={m} scope="col" className="num">{monthLabel(m)}</th>)}</tr></thead>
          <tbody>{data.table?.map((r) => <tr key={r.id}><td className="text-nowrap">{r.customer} <span className="text-muted">{r.project}</span></td>{data.months.map((m) => <td key={m} className="num">{r.values[m] !== undefined ? money(r.values[m]).slice(1) : ""}</td>)}</tr>)}</tbody>
          <tfoot><tr className="fw-bold"><th scope="row">Total committed</th>{data.months.map((m) => <td key={m} className="num">{money(data.committed[m])}</td>)}</tr></tfoot>
        </table></div>
      )}
    </Modal>
  );
}

function Accuracy() {
  const { me } = useSession();
  const toast = useToast();
  const acc = useApi(() => api.get<AccuracyResp>("/insights/accuracy"));
  const [result, setResult] = useState<ActualsResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);
  const upload = async (f: File | undefined) => {
    if (!f) return;
    setErr(null);
    try { const r = await api.upload<ActualsResult>("/actuals/upload", f); setResult(r); toast("success", `Loaded ${r.loaded} lines for ${r.months.map(monthLabel).join(", ")}.`); acc.reload(); }
    catch (e) { setErr(e instanceof ApiError ? e.message : errText(e)); setResult(e instanceof ApiError && Array.isArray(e.detail.rejects) ? { loaded: 0, months: [], rejects: e.detail.rejects as ActualsResult["rejects"], unmatched: [] } : null); }
    finally { if (file.current) file.current.value = ""; }
  };
  return (
    <>
      {me.capabilities.can_snapshot && (
        <Card title="Load monthly actuals">
          <p>Upload a .csv or .xlsx with the headings <strong>Customer, Project, Amount, Month</strong> (month like 2026-09 or Sep 2026). A new file replaces earlier figures for the same months. <a href={api.url("/actuals/template")}>Download a template</a>.</p>
          <input ref={file} type="file" accept=".csv,.xlsx,.xlsm" className="form-control" style={{ maxWidth: 420 }} aria-label="Actuals file" onChange={(e) => upload(e.target.files?.[0])} />
          {err && <div className="alert alert-danger mt-2" role="alert">{err}</div>}
          {result && (result.rejects.length > 0 || result.unmatched.length > 0) && (
            <div className="alert alert-warning mt-2"><strong>Check these lines.</strong>
              {result.rejects.length > 0 && <><div>Not loaded:</div><ul className="mb-1">{result.rejects.map((r) => <li key={r.line}>Line {r.line}: {r.reason}</li>)}</ul></>}
              {result.unmatched.length > 0 && <><div>Loaded, but no matching project (still counted in the company total):</div><ul className="mb-0">{result.unmatched.map((r) => <li key={r.line}>Line {r.line}: {r.customer} / {r.project}</li>)}</ul></>}</div>
          )}
        </Card>
      )}
      <Card title="Forecast accuracy: how close was the forecast, 1, 2 and 3 months ahead?">
        {acc.error && <ErrorBox error={acc.error} onRetry={acc.reload} />}
        {acc.loading && !acc.data && <Spinner />}
        {acc.data && acc.data.months.length === 0 && <p className="text-muted mb-0">No actuals have been loaded yet. Once Finance loads a month, this table compares it with the snapshots taken 1, 2 and 3 months before.</p>}
        {acc.data && acc.data.months.length > 0 && (
          <>
            <div className="table-responsive"><table className="table table-sm align-middle">
              <thead><tr><th scope="col">Month</th><th scope="col" className="num">Actual</th>{[3, 2, 1].map((k) => <th key={k} scope="col" className="num">Forecast {k} month{k > 1 ? "s" : ""} ahead</th>)}</tr></thead>
              <tbody>{acc.data.months.map((m) => (
                <tr key={m.month}><th scope="row">{monthLong(m.month)}</th><td className="num">{money(m.actual)}</td>
                  {[3, 2, 1].map((k) => { const l = m.lookaheads.find((x) => x.k === k)!; return (
                    <td key={k} className="num">{l.snapshot_id ? <>{money(l.has_weighted ? l.total : l.committed)}<div className={(l.has_weighted ? l.total_flag : l.committed_flag) ? "text-danger fw-bold" : "text-success"}>{pct(l.has_weighted ? l.total_variance_pct : l.committed_variance_pct)} {(l.has_weighted ? l.total_flag : l.committed_flag) ? "outside 5%" : "within 5%"}</div><div className="small text-muted">snapshot {l.snapshot_date}</div></> : <span className="text-muted small">no snapshot</span>}</td>); })}</tr>))}</tbody>
            </table></div>
            <p className="form-text mb-0">{acc.data.note} Forecast = committed plus weighted pipeline when the snapshot recorded pipeline, otherwise committed only.</p>
          </>
        )}
      </Card>
    </>
  );
}

function CloseMonths({ onChanged }: { onChanged: () => void }) {
  const { me, meta } = useSession();
  const toast = useToast();
  const log = useApi(() => api.get<{ closed_through: string; log: { at: string; by: string; from: string; to: string; reason: string }[] }>("/months/close-log"));
  const [to, setTo] = useState("");
  const [reason, setReason] = useState("");
  const go = async () => {
    try { await api.post("/months/close", { closed_through: to, reason }); toast("success", `Closed through ${monthLong(to)}.`); setReason(""); setTo(""); log.reload(); onChanged(); }
    catch (e) { toast("danger", errText(e)); }
  };
  return (
    <>
      <Card title="Closed months are locked">
        <p>Closed through <strong>{monthLong(meta.closed_through)}</strong>. Nobody can edit a closed month. {me.capabilities.can_close_months ? "As Finance you can close the next month, or reopen a month to fix something." : "Only Finance can close or reopen months."}</p>
        {me.capabilities.can_close_months && (
          <div className="row g-2 align-items-end">
            <div className="col-md-3"><label className="form-label small mb-0" htmlFor="cl-to">Closed through</label><select id="cl-to" className="form-select form-select-sm" value={to} onChange={(e) => setTo(e.target.value)}><option value="">Choose a month</option>{meta.months.filter((m) => m !== meta.closed_through).map((m) => <option key={m} value={m}>{monthLong(m)}{m < meta.closed_through ? " (reopens later months)" : ""}</option>)}</select></div>
            <div className="col-md-5"><label className="form-label small mb-0" htmlFor="cl-reason">Reason (required)</label><input id="cl-reason" className="form-control form-control-sm" value={reason} onChange={(e) => setReason(e.target.value)} /></div>
            <div className="col-auto"><button className="btn btn-primary btn-sm" disabled={!to || !reason.trim()} onClick={go}>Apply</button></div>
          </div>
        )}
      </Card>
      <Card title="Close and reopen log">
        {log.data?.log.length ? <table className="table table-sm mb-0"><thead><tr><th scope="col">When</th><th scope="col">Who</th><th scope="col">Change</th><th scope="col">Reason</th></tr></thead><tbody>{log.data.log.map((l, i) => <tr key={i}><td>{stamp(l.at)}</td><td>{l.by}</td><td>{monthLabel(l.from)} to {monthLabel(l.to)}</td><td>{l.reason}</td></tr>)}</tbody></table> : <p className="text-muted mb-0">No months have been closed or reopened in the app yet.</p>}
      </Card>
    </>
  );
}
