import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import CameraForm from "../components/CameraForm";
import { typeLabel } from "../util";

export default function Cameras() {
  const [cams, setCams] = useState(null);
  const [edit, setEdit] = useState(undefined);      // undefined = new, object = editing
  const [error, setError] = useState("");
  const load = () => api.get("/cameras").then((r) => setCams(r.data));
  useEffect(() => { load(); }, []);

  const remove = async (c) => {
    if (!window.confirm(`Delete "${c.name}"?`)) return;
    try { await api.delete(`/cameras/${c.id}`); load(); } catch (err) { setError(errMsg(err)); }
  };

  return (
    <>
      <h1>Cameras and sources</h1>
      <p className="muted">Register each camera once, with its location, and reuse it across cases. Bus cameras and citizen photos can override the location per upload.</p>
      {error && <div className="alert error">{error}</div>}
      <div className="two-col">
        <div>
          {!cams ? <p className="muted">Loading…</p> : cams.length === 0 ? <div className="empty">No cameras yet.</div> : (
            <table className="table">
              <thead><tr><th>Name</th><th>Type</th><th>Location</th><th></th></tr></thead>
              <tbody>
                {cams.map((c) => (
                  <tr key={c.id}>
                    <td><strong>{c.name}</strong><div className="muted">{c.evidence_count} evidence</div></td>
                    <td>{typeLabel(c.type)}</td>
                    <td className="mono">{c.lat != null ? `${c.lat.toFixed(4)}, ${c.lng.toFixed(4)}` : <span className="muted">not set</span>}</td>
                    <td className="actions">
                      <button className="link" onClick={() => setEdit(c)}>Edit</button>
                      <button className="link danger" onClick={() => remove(c)}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <CameraForm key={edit?.id ?? "new"} camera={edit} others={cams || []}
                    onSaved={() => { setEdit(undefined); load(); }} onCancel={edit ? () => setEdit(undefined) : null} />
      </div>
    </>
  );
}
