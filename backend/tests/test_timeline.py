import os, sys
from datetime import datetime
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services import timeline


def test_build_timeline():
    base = datetime(2026, 5, 1, 10, 0, 0)
    gate = NS(id=1, name="Main Gate CCTV", type="CCTV", lat=16.5000, lng=80.6400)
    junction = NS(id=2, name="Junction traffic cam", type="TRAFFIC", lat=16.5022, lng=80.6400)
    bus = NS(id=3, name="Bus 21 front cam", type="BUS", lat=16.5044, lng=80.6400)
    ev1 = NS(id=1, filename="gate.mp4", media_type="video", recorded_at=base, lat=None, lng=None, source=gate)
    ev2 = NS(id=2, filename="junction.mp4", media_type="video", recorded_at=base.replace(minute=2), lat=None, lng=None, source=junction)
    ev3 = NS(id=3, filename="bus.jpg", media_type="image", recorded_at=base.replace(minute=5, second=30), lat=16.5050, lng=80.6401, source=bus)
    mk = lambda i, ev, a, b, ent: NS(id=i, evidence=ev, entity_id=ent, start_offset=a, end_offset=b, cls="PERSON", conf=.9, link_score=.88, has_thumb=True)
    tracks = [mk(1, ev1, 5, 20, 1), mk(2, ev2, 30, 45, 1), mk(3, ev3, 0, 0, 1), mk(4, ev1, 8, 12, 2)]
    ents = [NS(id=1, label="P-01", group="PERSON", cls="PERSON", locked=False, confidence=.88),
            NS(id=2, label="P-02", group="PERSON", cls="PERSON", locked=False, confidence=None)]
    tl = timeline.build(None, ents, tracks)
    p1 = tl["entities"][0]
    print(p1["summary"])
    assert p1["label"] == "P-01" and p1["n_sources"] == 3 and len(p1["sightings"]) == 3
    assert 400 < p1["distance_m"] < 800
    times = [e["time"] for e in tl["events"]]
    assert times == sorted(times)
    assert "reappears" in tl["events"][2]["text"] or any("reappears" in e["text"] for e in tl["events"])
    assert tl["entities"][1]["n_sources"] == 1
    csv_text = timeline.to_csv(tl)
    assert csv_text.splitlines()[0].startswith("time,entity") and "Bus 21" in csv_text
    assert timeline.fmt_duration(252) == "4 min 12 s" and timeline.fmt_distance(1300) == "1.3 km"


if __name__ == "__main__":
    test_build_timeline(); print("ALL OK")
