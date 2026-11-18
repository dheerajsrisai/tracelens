import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import api, { errMsg } from "../api";
import EvidenceViewer from "../components/EvidenceViewer";
import TimelineMap from "../components/TimelineMap";
import { fmtDate, fmtDist, fmtDur, fmtTime, prepareTimeline, typeLabel } from "../util";

export default function TimelineTab({ caseId }) {
  const [tl, setTl] = useState(null);
  const [error, setError] = useState("");
  const [onlyLinked, setOnlyLinked] = useState(null);
  const [hidden, setHidden] = useState({});
  const [sel, setSel] = useState(null);
  const [t, setT] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [focus, setFocus] = useState(null);
  const [viewer, setViewer] = useState(null);
  const [rename, setRename] = useState("");

  const load = useCallback(async () => {
    try {
      const d = prepareTimeline((await api.get(`/cases/${caseId}/timeline`)).data);
      setTl(d);
      setT((prev) => (prev == null || d.endMs == null ? d.endMs : Math.min(Math.max(prev, d.startMs), d.endMs)));
    } catch (e) { setError(errMsg(e)); }
  }, [caseId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {                                  // keep refreshing while evidence is still being analysed
    if (!tl || tl.stats.pending === 0) return undefined;
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, [tl, load]);

  useEffect(() => {
    if (!playing || !tl) return undefined;
    const step = Math.max(1000, (tl.endMs - tl.startMs) / 250);
    const id = setInterval(() => setT((p) => { const n = p + step; if (n >= tl.endMs) { setPlaying(false); return tl.endMs; } return n; }), 100);
    return () => clearInterval(id);
  }, [playing, tl]);

  const showLinked = onlyLinked ?? (tl ? tl.stats.linked > 0 : false);
  const entities = useMemo(() => (tl ? tl.entities.filter((e) => !hidden[e.id] && (!showLinked || e.n_sources > 1 || e.id === sel)) : []), [tl, hidden, showLinked, sel]);
  const events = useMemo(() => {
    const ids = new Set(entities.map((e) => e.id));
    return tl ? tl.events.filter((ev) => ids.has(ev.entity_id)) : [];
  }, [tl, entities]);
  const selected = tl?.entities.find((e) => e.id === sel);

  const act = async (fn) => { setError(""); try { await fn(); await load(); } catch (e) { setError(errMsg(e)); } };

  if (error && !tl) return <div className="alert error">{error}</div>;
  if (!tl) return <p className="muted">Loading…</p>;
  if (tl.stats.evidence === 0)
    return <div className="empty">No evidence yet. <Link to={`/cases/${caseId}/evidence`}>Upload videos or images</Link> to start building the timeline.</div>;

  const clickEvent = (ev) => {
    setSel(ev.entity_id);
    setT(ev.ts);
    if (ev.lat != null) setFocus({ lat: ev.lat, lng: ev.lng, k: Date.now() });
  };
  const noLoc = tl.entities.reduce((n, e) => n + e.sightings.filter((s) => s.lat == null).length, 0);
  const others = selected ? tl.entities.filter((e) => e.group === selected.group && e.id !== selected.id) : [];

  return (
    <>
      <div className="stats">
        <span><b>{tl.stats.evidence}</b> evidence{tl.stats.pending > 0 && <em className="pend"> ({tl.stats.pending} analysing…)</em>}{tl.stats.failed > 0 && <em className="fail"> ({tl.stats.failed} failed)</em>}</span>
        <span><b>{tl.stats.entities}</b> tracked subjects</span>
        <span><b>{tl.stats.linked}</b> seen on 2+ cameras</span>
        <span><b>{tl.stats.events}</b> events</span>
        <span className="spacer" />
        <label className="check"><input type="checkbox" checked={showLinked} onChange={(e) => setOnlyLinked(e.target.checked)} /> Only subjects seen on 2+ cameras</label>
        <button className="btn ghost small" onClick={() => act(() => api.post(`/cases/${caseId}/rebuild`))} title="Re-run the automatic cross-camera linking (your manual edits are kept)">Re-link</button>
        <a className="btn ghost small" href={`/api/cases/${caseId}/export.csv`}>Export CSV</a>
      </div>
      {error && <div className="alert error">{error}</div>}
      {noLoc > 0 && <div className="alert info">{noLoc} sighting{noLoc > 1 ? "s" : ""} have no camera location and are missing from the map. Set locations under <Link to="/cameras">Cameras</Link>.</div>}

      <div className="chips">
        {tl.entities.filter((e) => !showLinked || e.n_sources > 1 || e.id === sel).map((e) => (
          <span key={e.id} className={`chip ${sel === e.id ? "on" : ""} ${hidden[e.id] ? "off" : ""}`} style={{ "--c": e.color }}>
            <button className="chip-main" onClick={() => setSel(sel === e.id ? null : e.id)} aria-pressed={sel === e.id}>
              <i /> {e.label} <small>{e.n_sources} cam{e.n_sources > 1 ? "s" : ""}</small>
            </button>
            <button className="chip-eye" onClick={() => setHidden({ ...hidden, [e.id]: !hidden[e.id] })} title={hidden[e.id] ? "Show on map" : "Hide from map"}>{hidden[e.id] ? "show" : "hide"}</button>
          </span>
        ))}
      </div>

      <div className="workspace">
        <section className="events" aria-label="Chronological events">
          <h2>Timeline</h2>
          {events.length === 0 ? <div className="empty">Nothing to show with these filters.</div> : (
            <ol className="rail">
              {events.map((ev, i) => {
                const newDay = i === 0 || fmtDate(events[i - 1].time) !== fmtDate(ev.time);
                return (
                  <li key={`${ev.track_id}-${ev.kind}-${i}`} style={{ "--c": ev.color }} className={`${sel === ev.entity_id ? "sel" : ""} ${ev.kind}`}>
                    {newDay && <div className="day">{fmtDate(ev.time)}</div>}
                    <button className="ev" onClick={() => clickEvent(ev)}>
                      <span className="time mono">{fmtTime(ev.time)}</span>
                      <span className="dot" />
                      <span className="body">
                        <span>{ev.text}</span>
                        <span className="muted">{typeLabel(ev.source_type)}{ev.score != null && ` · match ${Math.round(ev.score * 100)}%`}</span>
                      </span>
                      {ev.has_thumb && ev.kind === "first_seen" && <img className="th" src={`/api/tracks/${ev.track_id}/thumb`} alt="" />}
                    </button>
                  </li>
                );
              })}
            </ol>
          )}
        </section>

        <section className="mapcol" aria-label="Map">
          <TimelineMap entities={entities} t={t ?? 0} selectedId={sel} focus={focus} onOpenEvidence={setViewer} />
          {tl.startMs !== tl.endMs && (
            <div className="replay">
              <button className="btn small" onClick={() => { if (t >= tl.endMs) setT(tl.startMs); setPlaying(!playing); }}>{playing ? "Pause" : "Replay"}</button>
              <input type="range" min={tl.startMs} max={tl.endMs} step={1000} value={t ?? tl.endMs} onChange={(e) => { setPlaying(false); setT(+e.target.value); }} aria-label="Replay time" />
              <span className="mono">{fmtTime(new Date(t ?? tl.endMs))}</span>
            </div>
          )}
          <p className="muted">Solid line = path travelled so far, dashed = remaining. Numbers show the order of sightings.</p>
        </section>
      </div>

      {selected && (
        <section className="card entity" style={{ "--c": selected.color }}>
          <div className="row between">
            <h2><i className="swatch" /> {selected.label}</h2>
            <button className="btn ghost small" onClick={() => setSel(null)}>Close</button>
          </div>
          <p>{selected.summary}</p>
          <p className="muted">
            {selected.distance_m > 0 && <>Path length {fmtDist(selected.distance_m)} · </>}
            {selected.duration_s > 0 && <>duration {fmtDur(selected.duration_s)} · </>}
            {selected.confidence != null ? <>link confidence {Math.round(selected.confidence * 100)}%</> : <>single sighting</>}
            {selected.locked && <> · edited by an investigator</>}
          </p>
          <div className="row">
            <input value={rename} onChange={(e) => setRename(e.target.value)} placeholder="Rename (e.g. Suspect 1)" aria-label="New name" />
            <button className="btn small" disabled={!rename.trim()} onClick={() => act(async () => { await api.put(`/entities/${selected.id}`, { label: rename }); setRename(""); })}>Rename</button>
            {others.length > 0 && (
              <select value="" aria-label="Merge with another subject" onChange={(e) => e.target.value && window.confirm("Merge these two subjects into one?") && act(() => api.post("/entities/merge", { target_id: selected.id, source_ids: [+e.target.value] }))}>
                <option value="">Merge with…</option>
                {others.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
              </select>
            )}
          </div>
          <div className="sightings">
            {selected.sightings.map((s, i) => (
              <div className="sight" key={s.track_id}>
                {s.has_thumb ? <img src={`/api/tracks/${s.track_id}/thumb`} alt="" /> : <span className="noimg" />}
                <div>
                  <strong>#{i + 1} {s.source_name}</strong>
                  <div className="muted mono">{fmtTime(new Date(s.t0))}{s.t1 > s.t0 ? ` – ${fmtTime(new Date(s.t1))}` : ""}{s.score != null && ` · match ${Math.round(s.score * 100)}%`}</div>
                  <div className="row small">
                    <button className="link" onClick={() => setViewer({ id: s.evidence_id, name: s.evidence_name, media_type: s.media_type, offset: s.offset_s })}>Open evidence</button>
                    {selected.sightings.length > 1 && <button className="link danger" onClick={() => window.confirm("Mark this sighting as a different subject?") && act(() => api.post(`/tracks/${s.track_id}/detach`))}>Not the same</button>}
                    {others.length > 0 && (
                      <select className="mini" value="" aria-label="Move sighting to" onChange={(e) => e.target.value && act(() => api.post(`/tracks/${s.track_id}/assign`, { entity_id: +e.target.value }))}>
                        <option value="">Move to…</option>
                        {others.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
                      </select>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
      <p className="muted disclaimer">Automatic matching compares clothing/vehicle colour, timing and travel distance. Treat links as investigative leads and verify them against the footage before relying on them.</p>
      {viewer && <EvidenceViewer item={viewer} onClose={() => setViewer(null)} />}
    </>
  );
}
