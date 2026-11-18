"""Builds the investigation timeline (events, entity paths, narrative) from tracks. No web/DB imports."""
import csv
import io
from datetime import timedelta
from typing import Dict, List, Optional

from .geo import has_coords, haversine_m, path_length_m

PALETTE = ["#d62839", "#0e7c86", "#e07a1f", "#5b3cc4", "#2a9d3f", "#c2185b", "#1565c0", "#8d6e00",
           "#00897b", "#6d4c41", "#ad1457", "#455a64"]
CLS_WORD = {"PERSON": "person", "CAR": "car", "BUS": "bus", "TRUCK": "truck", "BICYCLE": "bicycle", "MOTORCYCLE": "motorcycle"}


def fmt_duration(sec: float) -> str:
    sec = int(round(sec))
    if sec < 60:
        return f"{sec} s"
    m, s = divmod(sec, 60)
    if m < 60:
        return f"{m} min {s:02d} s"
    h, m = divmod(m, 60)
    return f"{h} h {m:02d} min"


def fmt_distance(m: float) -> str:
    return f"{m / 1000:.1f} km" if m >= 1000 else f"{int(round(m))} m"


def effective_location(ev):
    if has_coords(ev.lat, ev.lng):
        return ev.lat, ev.lng
    return ev.source.lat, ev.source.lng


def sighting_of(t) -> dict:
    ev = t.evidence
    lat, lng = effective_location(ev)
    start = ev.recorded_at + timedelta(seconds=t.start_offset)
    end = ev.recorded_at + timedelta(seconds=t.end_offset)
    return {
        "track_id": t.id, "evidence_id": ev.id, "evidence_name": ev.filename, "media_type": ev.media_type,
        "source_id": ev.source.id, "source_name": ev.source.name, "source_type": ev.source.type,
        "lat": lat, "lng": lng, "start": start, "end": end, "offset_s": t.start_offset,
        "cls": t.cls, "conf": round(t.conf or 0, 3), "score": None if t.link_score is None else round(t.link_score, 3),
        "has_thumb": bool(t.has_thumb),
    }


def summarize(label: str, cls: str, sightings: List[dict]) -> dict:
    """Distance, duration, speed and a plain-English narrative for one entity."""
    first, last = sightings[0], sightings[-1]
    duration = max(0.0, (last["end"] - first["start"]).total_seconds())
    dist = path_length_m([(s["lat"], s["lng"]) for s in sightings])
    speed = (dist / duration * 3.6) if duration > 0 and dist > 0 else None
    places = []
    for s in sightings:
        if s["source_name"] not in places:
            places.append(s["source_name"])
    word = CLS_WORD.get(cls, cls.lower())
    if len(sightings) == 1:
        text = f"{label} ({word}) was detected once, at {first['source_name']} at {first['start']:%H:%M:%S}."
    else:
        text = (f"{label} ({word}) was seen {len(sightings)} times at {len(places)} location{'s' if len(places) != 1 else ''} "
                f"over {fmt_duration(duration)}")
        if dist > 0:
            text += f", covering about {fmt_distance(dist)}"
            if speed:
                text += f" (average {speed:.1f} km/h)"
        text += (f". First seen at {first['source_name']} at {first['start']:%H:%M:%S}, "
                 f"last seen at {last['source_name']} at {last['end']:%H:%M:%S}.")
    return {"duration_s": duration, "distance_m": dist, "avg_speed_kmh": speed, "places": places, "summary": text}


def build(case, entities, tracks) -> dict:
    """entities: Entity rows; tracks: Track rows (with .evidence.source loaded)."""
    by_entity: Dict[int, List[dict]] = {}
    for t in tracks:
        if t.entity_id is None:
            continue
        by_entity.setdefault(t.entity_id, []).append(sighting_of(t))

    out_entities, events = [], []
    ordered = sorted((e for e in entities if e.id in by_entity), key=lambda e: min(s["start"] for s in by_entity[e.id]))
    for idx, e in enumerate(ordered):
        sightings = sorted(by_entity[e.id], key=lambda s: (s["start"], s["track_id"]))
        info = summarize(e.label, e.cls, sightings)
        color = PALETTE[idx % len(PALETTE)]
        word = CLS_WORD.get(e.cls, e.cls.lower())
        distinct_sources = len({s["source_id"] for s in sightings})
        out_entities.append({
            "id": e.id, "label": e.label, "group": e.group, "cls": e.cls, "locked": e.locked,
            "confidence": None if e.confidence is None else round(e.confidence, 3),
            "color": color, "n_sources": distinct_sources, "sightings": sightings, **info,
        })
        prev = None
        for s in sightings:
            if prev is None:
                text = f"{e.label} ({word}) first detected at {s['source_name']}"
            else:
                gap = (s["start"] - prev["end"]).total_seconds()
                bits = []
                if has_coords(prev["lat"], prev["lng"]) and has_coords(s["lat"], s["lng"]) and prev["source_id"] != s["source_id"]:
                    bits.append(f"{fmt_distance(haversine_m(prev['lat'], prev['lng'], s['lat'], s['lng']))} from {prev['source_name']}")
                if gap > 0:
                    bits.append(f"after {fmt_duration(gap)}")
                text = f"{e.label} ({word}) reappears at {s['source_name']}" + (f" ({', '.join(bits)})" if bits else "")
            common = {"entity_id": e.id, "label": e.label, "color": color, "track_id": s["track_id"], "source_id": s["source_id"],
                      "source_name": s["source_name"], "source_type": s["source_type"], "lat": s["lat"], "lng": s["lng"],
                      "evidence_id": s["evidence_id"], "evidence_name": s["evidence_name"], "media_type": s["media_type"],
                      "offset_s": s["offset_s"], "has_thumb": s["has_thumb"], "score": s["score"]}
            events.append({**common, "time": s["start"], "kind": "first_seen", "text": text})
            if (s["end"] - s["start"]).total_seconds() >= 1:
                events.append({**common, "time": s["end"], "kind": "last_seen",
                               "text": f"{e.label} last seen at {s['source_name']}"})
            prev = s

    events.sort(key=lambda ev: (ev["time"], 0 if ev["kind"] == "first_seen" else 1))
    all_times = [s["start"] for e in out_entities for s in e["sightings"]] + [s["end"] for e in out_entities for s in e["sightings"]]
    return {
        "range": {"start": min(all_times) if all_times else None, "end": max(all_times) if all_times else None},
        "entities": out_entities,
        "events": events,
    }


def to_csv(timeline: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["time", "entity", "event", "description", "camera", "camera_type", "lat", "lng", "evidence_file", "video_offset_s", "link_confidence"])
    for ev in timeline["events"]:
        w.writerow([ev["time"].isoformat(sep=" ", timespec="seconds"), ev["label"], ev["kind"], ev["text"], ev["source_name"],
                    ev["source_type"], ev["lat"], ev["lng"], ev["evidence_name"], round(ev["offset_s"], 1), ev["score"]])
    return buf.getvalue()
