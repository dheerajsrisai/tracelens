// Timestamps are "naive" local times (what an investigator reads off a camera clock), so no time-zone maths.
export const parseT = (s) => (s ? new Date(String(s).replace(/(\.\d{3})\d+/, "$1")) : null);
const pad = (n) => String(n).padStart(2, "0");
const asDate = (v) => (typeof v === "string" ? parseT(v) : v);
export const fmtTime = (v) => { const d = asDate(v); return d ? `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}` : ""; };
export const fmtDate = (v) => { const d = asDate(v); return d ? d.toLocaleDateString([], { dateStyle: "medium" }) : ""; };
export const fmtDateTime = (v) => (v ? `${fmtDate(v)} ${fmtTime(v)}` : "");
export const toInput = (v) => {
  const d = asDate(v);
  return d ? `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${fmtTime(d)}` : "";
};
export const fmtDur = (sec) => {
  sec = Math.round(sec || 0);
  if (sec < 60) return `${sec} s`;
  const m = Math.floor(sec / 60), s = sec % 60;
  if (m < 60) return `${m} min ${String(s).padStart(2, "0")} s`;
  return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`;
};
export const fmtSize = (b) => (b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);
export const fmtDist = (m) => (m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`);

export const SOURCE_TYPES = [["CCTV", "CCTV camera"], ["TRAFFIC", "Traffic camera"], ["BUS", "Bus camera"], ["CITIZEN", "Citizen upload"], ["OTHER", "Other"]];
export const typeLabel = (k) => (SOURCE_TYPES.find((t) => t[0] === k) || [k, k])[1];

/** Where was an entity at time t (ms)? Interpolates between sightings. Sightings need t0/t1 (ms), lat, lng. */
export function positionAt(sightings, t) {
  const pts = sightings.filter((s) => s.lat != null && s.lng != null);
  if (!pts.length || t < pts[0].t0) return null;
  for (let i = 0; i < pts.length; i++) {
    const s = pts[i];
    if (t <= s.t1) return { lat: s.lat, lng: s.lng, moving: false };
    const n = pts[i + 1];
    if (n && t < n.t0) {
      const f = (t - s.t1) / Math.max(1, n.t0 - s.t1);
      return { lat: s.lat + (n.lat - s.lat) * f, lng: s.lng + (n.lng - s.lng) * f, moving: true };
    }
  }
  const last = pts[pts.length - 1];
  return { lat: last.lat, lng: last.lng, moving: false };
}

/** Parse API timeline: add numeric times used by the map slider. */
export function prepareTimeline(d) {
  d.entities.forEach((e) => e.sightings.forEach((s) => { s.t0 = parseT(s.start).getTime(); s.t1 = parseT(s.end).getTime(); }));
  d.events.forEach((ev) => { ev.ts = parseT(ev.time).getTime(); });
  d.startMs = d.range.start ? parseT(d.range.start).getTime() : null;
  d.endMs = d.range.end ? parseT(d.range.end).getTime() : null;
  return d;
}
