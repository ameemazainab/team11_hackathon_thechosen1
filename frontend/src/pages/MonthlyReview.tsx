import { Link } from "react-router-dom";
import { useState } from "react";
import { api, type ReviewResp } from "../api";
import { money, monthLabel, stamp } from "../format";
import { useSession } from "../session";
import { Badge, Card, ErrorBox, Page, Spinner, errText, useApi, useToast } from "../ui";

export default function MonthlyReview() {
  const { me } = useSession();
  const toast = useToast();
  const { data, error, loading, reload } = useApi(() => api.get<ReviewResp>("/review"));
  const [sel, setSel] = useState<Set<string>>(new Set());
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (loading || !data) return <Spinner />;
  const todo = data.mine.filter((r) => !r.attested);
  const toggle = (id: string) => { const n = new Set(sel); if (n.has(id)) n.delete(id); else n.add(id); setSel(n); };
  const attest = async (ids: string[]) => {
    try { const r = await api.post<{ attested: number }>("/review/attest", { row_ids: ids }); toast("success", `${r.attested} row${r.attested === 1 ? "" : "s"} marked as reviewed.`); setSel(new Set()); reload(); }
    catch (e) { toast("danger", errText(e)); }
  };
  return (
    <Page title="Monthly review" subtitle={`Each month, owners confirm the rows that bring in revenue over the next 3 months (${data.window.map(monthLabel).join(", ")}). Due ${data.due}.`}>
      <div className="row g-3">
        <div className="col-xl-7">
          <Card title={me.capabilities.can_edit_any ? "Your rows to review" : "Rows"} actions={todo.length ? <div className="d-flex gap-2"><button className="btn btn-sm btn-outline-primary" disabled={!sel.size} onClick={() => attest([...sel])}>Mark {sel.size || ""} selected as reviewed</button><button className="btn btn-sm btn-primary" onClick={() => attest(todo.map((r) => r.id))}>Everything is right: review all {todo.length}</button></div> : null}>
            {data.mine.length === 0 ? <p className="text-muted mb-0">You do not own any rows with revenue in the next 3 months.</p> : (
              <div className="table-responsive"><table className="table table-sm align-middle">
                <thead><tr><th scope="col"><span className="visually-hidden">Select</span></th><th scope="col">Project</th>{data.window.map((m) => <th key={m} scope="col" className="num">{monthLabel(m)}</th>)}<th scope="col">Last changed</th><th scope="col">Status</th></tr></thead>
                <tbody>{data.mine.map((r) => (
                  <tr key={r.id}><td><input type="checkbox" className="form-check-input" aria-label={`Select ${r.customer} ${r.project}`} disabled={r.attested} checked={sel.has(r.id)} onChange={() => toggle(r.id)} /></td>
                    <td><Link to={`/forecast?q=${r.id}`}>{r.customer}</Link><div className="small text-muted">{r.project}</div></td>
                    {data.window.map((m) => <td key={m} className="num">{money(r.window[m])}</td>)}
                    <td className="small">{r.last_updated}</td>
                    <td>{r.attested ? <Badge tone="success">Reviewed {stamp(r.attested_at).slice(0, 10)}</Badge> : <Badge tone="warning">To review</Badge>}</td></tr>))}</tbody>
              </table></div>
            )}
            <p className="form-text mb-0">Not right? Fix the numbers in the <Link to="/forecast">Forecast grid</Link> first (add a reason), then come back and confirm.</p>
          </Card>
        </div>
        <div className="col-xl-5">
          <Card title="Review status by owner">
            <div className="d-flex justify-content-between small mb-1"><span>Overall</span><span>{data.overall.attested} of {data.overall.rows} rows ({data.overall.pct}%)</span></div>
            <div className="progress mb-3" role="progressbar" aria-label="Overall review" aria-valuenow={data.overall.pct} aria-valuemin={0} aria-valuemax={100}><div className="progress-bar bg-success" style={{ width: data.overall.pct + "%" }} /></div>
            <table className="table table-sm"><thead><tr><th scope="col">Owner</th><th scope="col" className="num">Reviewed</th><th scope="col" className="num">In window</th><th scope="col">Note</th></tr></thead>
              <tbody>{data.status.map((s) => (<tr key={s.owner}><td>{s.owner_name || "No owner"}</td><td className="num">{s.attested} / {s.total}</td><td className="num">{money(s.amount)}</td><td className="small">{s.stale ? <span className="text-danger">Oldest update {s.oldest}</span> : s.attested === s.total ? <Badge tone="success">Done</Badge> : ""}</td></tr>))}</tbody></table>
          </Card>
        </div>
      </div>
    </Page>
  );
}
