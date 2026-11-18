import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { errMsg } from "../api";
import { fmtDateTime } from "../util";

export default function Cases() {
  const nav = useNavigate();
  const [cases, setCases] = useState(null);
  const [f, setF] = useState({ title: "", description: "", incident_time: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const load = () => api.get("/cases").then((r) => setCases(r.data));
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const c = (await api.post("/cases", { title: f.title, description: f.description, incident_time: f.incident_time || null })).data;
      nav(`/cases/${c.id}/evidence`);
    } catch (err) { setError(errMsg(err)); }
  };
  const demo = async () => {
    setBusy(true);
    try { nav(`/cases/${(await api.post("/cases/demo")).data.id}`); } catch (err) { setError(errMsg(err)); setBusy(false); }
  };

  return (
    <>
      <div className="row between">
        <h1>Cases</h1>
        <button className="btn ghost" onClick={demo} disabled={busy}>{busy ? "Building demo…" : "Load demo case"}</button>
      </div>
      {error && <div className="alert error">{error}</div>}

      <div className="two-col">
        <div>
          {!cases ? <p className="muted">Loading…</p> : cases.length === 0 ? (
            <div className="empty">No cases yet. Create one, or load the demo case to see the full workflow with synthetic footage.</div>
          ) : (
            <ul className="caselist">
              {cases.map((c) => (
                <li key={c.id}>
                  <Link to={`/cases/${c.id}`}><strong>{c.title}</strong></Link>
                  <span className="muted">{c.evidence_count} evidence · {c.entity_count} tracked subjects · opened {fmtDateTime(c.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <form className="card form" onSubmit={create}>
          <h2>New case</h2>
          <label>Title<input value={f.title} onChange={set("title")} required maxLength={200} placeholder="e.g. Robbery near the central market" /></label>
          <label>Description<textarea rows={3} value={f.description} onChange={set("description")} /></label>
          <label>Approximate incident time (optional)<input type="datetime-local" step="1" value={f.incident_time} onChange={set("incident_time")} /></label>
          <button className="btn">Create case</button>
        </form>
      </div>
    </>
  );
}
