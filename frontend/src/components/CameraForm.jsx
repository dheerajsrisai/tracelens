import { useState } from "react";
import api, { errMsg } from "../api";
import { SOURCE_TYPES } from "../util";
import MapPicker from "./MapPicker";

export default function CameraForm({ camera, others = [], onSaved, onCancel }) {
  const [f, setF] = useState({ name: camera?.name || "", type: camera?.type || "CCTV", lat: camera?.lat ?? null, lng: camera?.lng ?? null, notes: camera?.notes || "" });
  const [error, setError] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const body = { ...f, lat: f.lat === "" ? null : f.lat, lng: f.lng === "" ? null : f.lng };
      const r = camera ? await api.put(`/cameras/${camera.id}`, body) : await api.post("/cameras", body);
      onSaved(r.data);
    } catch (err) { setError(errMsg(err)); }
  };

  return (
    <form className="card form" onSubmit={submit}>
      <h2>{camera ? "Edit camera" : "Add camera / source"}</h2>
      {error && <div className="alert error">{error}</div>}
      <label>Name<input value={f.name} onChange={set("name")} required placeholder="e.g. Market gate CCTV" /></label>
      <label>Type
        <select value={f.type} onChange={set("type")}>{SOURCE_TYPES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
      </label>
      <div>
        <span className="field-title">Location (needed to draw paths and check travel times)</span>
        <MapPicker value={f.lat != null ? { lat: f.lat, lng: f.lng } : null} onChange={(lat, lng) => setF((p) => ({ ...p, lat, lng }))} others={others} height={240} />
      </div>
      <label>Notes<input value={f.notes} onChange={set("notes")} placeholder="Direction it faces, owner, clock accuracy…" /></label>
      <div className="row">
        <button className="btn">Save</button>
        {onCancel && <button type="button" className="btn ghost" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  );
}
