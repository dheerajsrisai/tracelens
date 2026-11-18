import { useEffect, useRef } from "react";
import L from "leaflet";
import { fmtTime, positionAt } from "../util";
import { makeMap } from "./MapPicker";

/** Movement paths of every visible entity, numbered sightings, and the position at the slider time. */
export default function TimelineMap({ entities, t, selectedId, focus, onOpenEvidence }) {
  const el = useRef(null);
  const map = useRef(null);
  const layer = useRef(null);
  const fitted = useRef(false);
  const open = useRef(onOpenEvidence);
  open.current = onOpenEvidence;

  useEffect(() => {
    map.current = makeMap(el.current);
    layer.current = L.layerGroup().addTo(map.current);
    return () => { map.current.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    const g = layer.current;
    if (!g) return;
    g.clearLayers();
    const all = [];
    entities.forEach((e) => {
      const pts = e.sightings.filter((s) => s.lat != null && s.lng != null);
      const dim = selectedId && selectedId !== e.id;
      const opacity = dim ? 0.25 : 1;
      pts.forEach((s) => all.push([s.lat, s.lng]));
      if (pts.length > 1) {
        L.polyline(pts.map((s) => [s.lat, s.lng]), { color: e.color, weight: 3, opacity: 0.35 * (dim ? 0.5 : 1), dashArray: "6 8" }).addTo(g);
        const done = pts.filter((s) => s.t0 <= t).map((s) => [s.lat, s.lng]);
        const here = positionAt(e.sightings, t);
        if (here) done.push([here.lat, here.lng]);
        if (done.length > 1) L.polyline(done, { color: e.color, weight: 5, opacity }).addTo(g);
      }
      pts.forEach((s, i) => {
        const seen = s.t0 <= t;
        const icon = L.divIcon({
          className: "pin-wrap",
          html: `<span class="pin${seen ? "" : " future"}" style="background:${e.color};opacity:${dim ? 0.35 : seen ? 1 : 0.45}">${i + 1}</span>`,
          iconSize: [24, 24], iconAnchor: [12, 12],
        });
        const m = L.marker([s.lat, s.lng], { icon }).addTo(g);
        const box = document.createElement("div");                       // DOM nodes: names can never inject HTML
        const h = document.createElement("strong");
        h.textContent = `${e.label} · ${s.source_name}`;
        const when = document.createElement("div");
        when.textContent = `${fmtTime(new Date(s.t0))}${s.t1 > s.t0 ? ` – ${fmtTime(new Date(s.t1))}` : ""}`;
        const b = document.createElement("button");
        b.className = "btn small";
        b.textContent = "Open evidence";
        b.onclick = () => open.current?.({ id: s.evidence_id, name: s.evidence_name, media_type: s.media_type, offset: s.offset_s });
        box.append(h, when, b);
        m.bindPopup(box);
      });
      const here = positionAt(e.sightings, t);
      if (here) {
        L.circleMarker([here.lat, here.lng], { radius: 11, color: "#ffffff", weight: 3, fillColor: e.color, fillOpacity: 1, opacity })
          .bindTooltip(e.label, { permanent: true, direction: "top", offset: [0, -10], className: "ent-tip" }).addTo(g);
      }
    });
    if (!fitted.current && all.length) {
      map.current.fitBounds(all, { padding: [50, 50], maxZoom: 17 });
      fitted.current = true;
    }
  }, [entities, t, selectedId]);

  useEffect(() => {
    if (focus && map.current) map.current.flyTo([focus.lat, focus.lng], Math.max(map.current.getZoom(), 16), { duration: 0.6 });
  }, [focus]);

  return <div ref={el} className="map tall" role="img" aria-label="Map of the reconstructed movement paths" />;
}
