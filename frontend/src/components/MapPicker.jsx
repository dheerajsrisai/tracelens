import { useEffect, useRef } from "react";
import L from "leaflet";

const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

export const makeMap = (el, center = [20.59, 78.96], zoom = 5) => {
  const map = L.map(el).setView(center, zoom);
  L.tileLayer(TILES, { maxZoom: 19, attribution: ATTR, referrerPolicy: "origin" }).addTo(map);
  setTimeout(() => map.invalidateSize(), 250);
  return map;
};

/** Click the map (or drag the pin) to choose a location. `others` are existing cameras shown as small dots. */
export default function MapPicker({ value, onChange, others = [], height = 280 }) {
  const el = useRef(null);
  const map = useRef(null);
  const pin = useRef(null);
  const dots = useRef(null);
  const cb = useRef(onChange);
  cb.current = onChange;

  useEffect(() => {
    map.current = makeMap(el.current);
    dots.current = L.layerGroup().addTo(map.current);
    map.current.on("click", (e) => cb.current(+e.latlng.lat.toFixed(6), +e.latlng.lng.toFixed(6)));
    return () => { map.current.remove(); map.current = null; pin.current = null; };
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    if (value?.lat == null || value?.lng == null) {
      if (pin.current) { pin.current.remove(); pin.current = null; }
      return;
    }
    const ll = [value.lat, value.lng];
    if (!pin.current) {
      pin.current = L.marker(ll, { draggable: true }).addTo(m);
      pin.current.on("dragend", () => { const p = pin.current.getLatLng(); cb.current(+p.lat.toFixed(6), +p.lng.toFixed(6)); });
      m.setView(ll, Math.max(m.getZoom(), 15));
    } else {
      pin.current.setLatLng(ll);
    }
  }, [value?.lat, value?.lng]);

  useEffect(() => {
    const g = dots.current;
    if (!g) return;
    g.clearLayers();
    others.filter((c) => c.lat != null && c.lng != null).forEach((c) => {
      L.circleMarker([c.lat, c.lng], { radius: 6, color: "#fff", weight: 2, fillColor: "#0b8aa0", fillOpacity: 1 })
        .bindTooltip(c.name).addTo(g);
    });
    if (others.length && !pin.current && value?.lat == null) {
      const pts = others.filter((c) => c.lat != null).map((c) => [c.lat, c.lng]);
      if (pts.length) map.current.fitBounds(pts, { padding: [40, 40], maxZoom: 16 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [others]);

  const here = () => navigator.geolocation?.getCurrentPosition(
    (p) => { cb.current(+p.coords.latitude.toFixed(6), +p.coords.longitude.toFixed(6)); map.current?.setView([p.coords.latitude, p.coords.longitude], 16); },
    () => alert("Could not get your location. Click the map instead."), { enableHighAccuracy: true, timeout: 10000 });

  return (
    <div>
      <div ref={el} className="map" style={{ height }} role="application" aria-label="Map: click to choose a location" />
      <div className="row small">
        <button type="button" className="btn ghost small" onClick={here}>Use my current location</button>
        <span className="muted">{value?.lat != null ? `${(+value.lat).toFixed(5)}, ${(+value.lng).toFixed(5)}` : "Click the map to place the pin"}</span>
      </div>
    </div>
  );
}
