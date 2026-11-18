import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errMsg } from "../api";
import CameraForm from "../components/CameraForm";
import EvidenceViewer from "../components/EvidenceViewer";
import MapPicker from "../components/MapPicker";
import { fmtDateTime, fmtDur, fmtSize, toInput, typeLabel } from "../util";

const nowInput = () => toInput(new Date());

function Status({ e }) {
  if (e.status === "DONE") return <span className="badge ok">Analysed</span>;
  if (e.status === "FAILED") return <span className="badge bad" title={e.error}>Failed</span>;
  return (
    <span className="badge wait">
      {e.status === "PENDING" ? "Queued" : `Analysing ${e.progress}%`}
      <span className="bar"><span style={{ width: `${e.progress}%` }} /></span>
    </span>
  );
}

function EditForm({ ev, cameras, onSaved, onCancel }) {
  const [f, setF] = useState({ recorded_at: toInput(ev.recorded_at), source_id: ev.source.id, lat: ev.lat, lng: ev.lng, notes: ev.notes || "" });
  const [override, setOverride] = useState(ev.lat != null);
  const [error, setError] = useState("");
  const save = async (e) => {
    e.preventDefault();
    try {
      await api.put(`/evidence/${ev.id}`, { recorded_at: f.recorded_at, source_id: +f.source_id, lat: override ? f.lat : null, lng: override ? f.lng : null, notes: f.notes });
      onSaved();
    } catch (err) { setError(errMsg(err)); }
  };
  return (
    <form className="card form" onSubmit={save}>
      <h3>Edit {ev.filename}</h3>
      <p className="muted">Correcting the start time or location moves every detection from this file on the timeline.</p>
      {error && <div className="alert error">{error}</div>}
      <label>Recording start time<input type="datetime-local" step="1" value={f.recorded_at} onChange={(e) => setF({ ...f, recorded_at: e.target.value })} required /></label>
      <label>Camera<select value={f.source_id} onChange={(e) => setF({ ...f, source_id: e.target.value })}>{cameras.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <label className="check"><input type="checkbox" checked={override} onChange={(e) => setOverride(e.target.checked)} /> Use a different location for this file</label>
      {override && <MapPicker value={f.lat != null ? { lat: f.lat, lng: f.lng } : null} onChange={(lat, lng) => setF((p) => ({ ...p, lat, lng }))} height={220} />}
      <label>Notes<input value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></label>
      <div className="row"><button className="btn">Save</button><button type="button" className="btn ghost" onClick={onCancel}>Cancel</button></div>
    </form>
  );
}

export default function EvidenceTab({ caseId }) {
  const [items, setItems] = useState(null);
  const [cameras, setCameras] = useState([]);
  const [file, setFile] = useState(null);
  const [f, setF] = useState({ source_id: "", recorded_at: nowInput(), notes: "" });
  const [override, setOverride] = useState(false);
  const [loc, setLoc] = useState({ lat: null, lng: null });
  const [addCam, setAddCam] = useState(false);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState("");
  const [viewer, setViewer] = useState(null);
  const [editing, setEditing] = useState(null);

  const load = useCallback(() => api.get(`/cases/${caseId}/evidence`).then((r) => setItems(r.data)), [caseId]);
  const loadCams = () => api.get("/cameras").then((r) => setCameras(r.data));
  useEffect(() => { load(); loadCams(); }, [load]);
  useEffect(() => {
    if (!items || !items.some((e) => e.status === "PENDING" || e.status === "PROCESSING")) return undefined;
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, [items, load]);

  const upload = async (e) => {
    e.preventDefault();
    setError("");
    if (!file) return setError("Choose a video or image file.");
    if (!f.source_id) return setError("Choose the camera this file came from (or add one).");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("source_id", f.source_id);
    if (f.recorded_at) fd.append("recorded_at", f.recorded_at);
    if (override && loc.lat != null) { fd.append("lat", loc.lat); fd.append("lng", loc.lng); }
    if (f.notes) fd.append("notes", f.notes);
    setProgress(0);
    try {
      await api.post(`/cases/${caseId}/evidence`, fd, { onUploadProgress: (p) => setProgress(p.total ? Math.round((100 * p.loaded) / p.total) : 0) });
      setFile(null);
      setF({ ...f, notes: "" });
      e.target.reset?.();
      load();
    } catch (err) { setError(errMsg(err)); }
    finally { setProgress(null); }
  };

  const remove = async (ev) => {
    if (!window.confirm(`Delete ${ev.filename} and its detections?`)) return;
    try { await api.delete(`/evidence/${ev.id}`); load(); } catch (err) { setError(errMsg(err)); }
  };

  return (
    <>
      <div className="two-col wide-left">
        <form className="card form" onSubmit={upload}>
          <h2>Add evidence</h2>
          {error && <div className="alert error">{error}</div>}
          <label>Video or image
            <input type="file" accept="video/*,image/*,.mkv" onChange={(e) => setFile(e.target.files[0] || null)} />
          </label>
          <label>Source camera
            <select value={f.source_id} onChange={(e) => setF({ ...f, source_id: e.target.value })} required>
              <option value="">Choose…</option>
              {cameras.map((c) => <option key={c.id} value={c.id}>{c.name} ({typeLabel(c.type)})</option>)}
            </select>
          </label>
          <button type="button" className="link" onClick={() => setAddCam(!addCam)}>{addCam ? "Hide camera form" : "+ Add a new camera / citizen location"}</button>
          {addCam && <CameraForm others={cameras} onSaved={(c) => { loadCams(); setF({ ...f, source_id: String(c.id) }); setAddCam(false); }} onCancel={() => setAddCam(false)} />}
          <label>Recording start time
            <input type="datetime-local" step="1" value={f.recorded_at} onChange={(e) => setF({ ...f, recorded_at: e.target.value })} />
          </label>
          <p className="muted">For a video, this is when the file starts (read it from the camera's on-screen clock). For a photo, leave it as is to use the time stored in the photo, if any.</p>
          <label className="check"><input type="checkbox" checked={override} onChange={(e) => setOverride(e.target.checked)} /> Use a specific location for this file (bus cameras, citizen photos)</label>
          {override && <MapPicker value={loc.lat != null ? loc : null} onChange={(lat, lng) => setLoc({ lat, lng })} others={cameras} height={220} />}
          <label>Notes (optional)<input value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></label>
          <button className="btn" disabled={progress !== null}>{progress !== null ? `Uploading ${progress}%` : "Upload and analyse"}</button>
          {progress !== null && <div className="progress"><div style={{ width: `${progress}%` }} /></div>}
        </form>

        <div>
          {editing && <EditForm ev={editing} cameras={cameras} onCancel={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
          <h2>Evidence ({items?.length ?? 0})</h2>
          {!items ? <p className="muted">Loading…</p> : items.length === 0 ? <div className="empty">No evidence uploaded yet.</div> : (
            <div className="scroll">
              <table className="table">
                <thead><tr><th></th><th>File</th><th>Camera</th><th>Recorded</th><th>Status</th><th>Found</th><th></th></tr></thead>
                <tbody>
                  {items.map((ev) => (
                    <tr key={ev.id}>
                      <td><button className="thumbbtn" onClick={() => setViewer({ id: ev.id, name: ev.filename, media_type: ev.media_type, offset: 0 })} aria-label={`Open ${ev.filename}`}>
                        <img className="evthumb" src={`/api/evidence/${ev.id}/preview`} alt="" onError={(e) => { e.currentTarget.style.visibility = "hidden"; }} /></button></td>
                      <td><strong className="clip">{ev.filename}</strong>
                        <div className="muted">{ev.media_type}{ev.duration_s > 0 && ` · ${fmtDur(ev.duration_s)}`} · {fmtSize(ev.size_bytes)}</div>
                        <div className="muted mono" title={`SHA-256 ${ev.sha256}`}>sha256 {ev.sha256.slice(0, 12)}…</div></td>
                      <td>{ev.source.name}<div className="muted">{typeLabel(ev.source.type)}{ev.lat != null && " · custom location"}</div></td>
                      <td className="mono">{fmtDateTime(ev.recorded_at)}</td>
                      <td><Status e={ev} />{ev.status === "FAILED" && <div className="muted err">{ev.error}</div>}</td>
                      <td>{ev.status === "DONE" ? ev.track_count : "–"}</td>
                      <td className="actions">
                        <button className="link" onClick={() => setEditing(ev)}>Edit</button>
                        <button className="link" onClick={() => api.post(`/evidence/${ev.id}/reprocess`).then(load)}>Re-analyse</button>
                        <a className="link" href={`/api/evidence/${ev.id}/file`} download={ev.filename}>Download</a>
                        <button className="link danger" onClick={() => remove(ev)}>Delete</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="muted">Analysis runs one file at a time and can take a few minutes for long videos on a CPU. <Link to={`/cases/${caseId}`}>Open the timeline</Link> to watch results appear.</p>
        </div>
      </div>
      {viewer && <EvidenceViewer item={viewer} onClose={() => setViewer(null)} />}
    </>
  );
}
