import { useEffect, useState } from "react";
import api from "../api";
import { fmtDateTime, fmtDist, fmtDur, fmtTime, prepareTimeline, typeLabel } from "../util";

const REFS = [
  "Bochinski, E., Senst, T., & Sikora, T. (2017). High-Speed Tracking-by-Detection Without Using Image Information. IEEE AVSS.",
  "Ge, Z., Liu, S., Wang, F., Li, Z., & Sun, J. (2021). YOLOX: Exceeding YOLO Series in 2021. arXiv:2107.08430.",
  "Wojke, N., Bewley, A., & Paulus, D. (2017). Simple Online and Realtime Tracking with a Deep Association Metric. IEEE ICIP.",
  "Zhang, Y., et al. (2022). ByteTrack: Multi-Object Tracking by Associating Every Detection Box. ECCV.",
];

/** Printable investigation report: use the browser's Print > Save as PDF. */
export default function ReportTab({ caseId, caseInfo }) {
  const [tl, setTl] = useState(null);
  const [ev, setEv] = useState([]);
  useEffect(() => {
    api.get(`/cases/${caseId}/timeline`).then((r) => setTl(prepareTimeline(r.data)));
    api.get(`/cases/${caseId}/evidence`).then((r) => setEv(r.data));
  }, [caseId]);
  if (!tl) return <p className="muted">Loading…</p>;

  return (
    <article className="report">
      <div className="row between noprint">
        <p className="muted">Use Print and choose "Save as PDF" to export this report.</p>
        <button className="btn" onClick={() => window.print()}>Print / Save as PDF</button>
      </div>
      <h2>Investigation timeline report</h2>
      <p><strong>{caseInfo.title}</strong><br />Generated {fmtDateTime(new Date())}{caseInfo.incident_time && <> · incident time {fmtDateTime(caseInfo.incident_time)}</>}</p>
      {caseInfo.description && <p>{caseInfo.description}</p>}

      <h3>1. Summary of findings</h3>
      {tl.entities.length === 0 ? <p>No people or vehicles were detected.</p> : (
        <ul>{tl.entities.filter((e) => e.n_sources > 1).concat(tl.entities.filter((e) => e.n_sources <= 1)).map((e) => <li key={e.id}>{e.summary}</li>)}</ul>
      )}

      <h3>2. Chronological timeline</h3>
      <table className="table">
        <thead><tr><th>Time</th><th>Subject</th><th>Event</th><th>Camera</th><th>Match</th></tr></thead>
        <tbody>
          {tl.events.map((e, i) => (
            <tr key={i}><td className="mono">{fmtTime(e.time)}</td><td>{e.label}</td><td>{e.text}</td><td>{e.source_name} ({typeLabel(e.source_type)})</td><td>{e.score != null ? `${Math.round(e.score * 100)}%` : "–"}</td></tr>
          ))}
        </tbody>
      </table>

      <h3>3. Movement paths</h3>
      <table className="table">
        <thead><tr><th>Subject</th><th>Cameras (in order)</th><th>Distance</th><th>Duration</th></tr></thead>
        <tbody>
          {tl.entities.filter((e) => e.n_sources > 1).map((e) => (
            <tr key={e.id}><td>{e.label}</td><td>{e.places.join(" → ")}</td><td>{e.distance_m > 0 ? fmtDist(e.distance_m) : "–"}</td><td>{fmtDur(e.duration_s)}</td></tr>
          ))}
        </tbody>
      </table>

      <h3>4. Evidence register (chain of custody)</h3>
      <table className="table">
        <thead><tr><th>File</th><th>Camera</th><th>Recorded</th><th>Uploaded</th><th>SHA-256</th></tr></thead>
        <tbody>
          {ev.map((e) => (
            <tr key={e.id}><td>{e.filename}</td><td>{e.source.name}</td><td className="mono">{fmtDateTime(e.recorded_at)}</td><td className="mono">{fmtDateTime(e.uploaded_at)}</td><td className="mono small-hash">{e.sha256}</td></tr>
          ))}
        </tbody>
      </table>

      <h3>5. Method and limitations</h3>
      <p>People and vehicles are detected with YOLO11 and followed within each video with ByteTrack. Each tracked object is described by a colour-appearance signature and linked across cameras when the signatures are similar and the time and distance between sightings are physically plausible (maximum walking/driving speed). Persons are never identified by face.</p>
      <p>Automatic links are investigative leads, not proof. Similar clothing or vehicle colours can be confused, camera clocks may be off, and low-quality footage reduces accuracy. Investigators should confirm every link against the original footage; edited links are marked in the system.</p>

      <h3>References</h3>
      <ol className="refs">{REFS.map((r) => <li key={r}>{r}</li>)}</ol>
    </article>
  );
}
