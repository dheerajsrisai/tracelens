"""Run with:  python -m pytest tests -q   (or just: python tests/test_matching.py)"""
import os, sys
from datetime import datetime, timedelta

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("MEDIA_DIR", "/tmp/tl_test_media")

from app.services import embedder
from app.services.matching import FORBIDDEN, MatchConfig, TrackInfo, cluster, link_score

RNG = np.random.default_rng(7)


def person(upper, lower, bright=1.0, tint=(0, 0, 0), noise=12, w=60, h=130):
    img = np.full((h, w, 3), 110, np.uint8)
    img[:] = (RNG.integers(90, 150, 3))                       # random background
    img[int(h * .02):int(h * .15), 20:40] = (150, 170, 210)    # head
    img[int(h * .15):int(h * .50), 8:52] = upper               # shirt
    img[int(h * .50):int(h * .90), 12:48] = lower              # trousers
    img = img.astype(np.float32) * bright + np.array(tint, np.float32)
    img += RNG.normal(0, noise, img.shape)
    img = np.clip(img, 0, 255).astype(np.uint8)
    return cv2.GaussianBlur(img, (3, 3), 0)


def emb(img, group="PERSON"):
    return embedder.histogram_embedding(img, group)


def test_same_vs_different_person():
    people = {
        "red/blue":    ((40, 40, 200), (180, 90, 30)),
        "green/black": ((60, 170, 60), (25, 25, 25)),
        "white/blue":  ((235, 235, 235), (180, 90, 30)),
        "red/black":   ((40, 40, 200), (25, 25, 25)),
        "yellow/gray": ((40, 210, 230), (120, 120, 120)),
        "navy/navy":   ((120, 50, 30), (110, 45, 30)),
    }
    same, diff = [], []
    names = list(people)
    for n in names:
        a = emb(person(*people[n]))
        b = emb(person(*people[n], bright=0.75, tint=(8, -4, 6)))        # other camera: darker, colour cast
        c = emb(person(*people[n], bright=1.25, tint=(-6, 4, 0), noise=20))
        same += [float(a @ b), float(a @ c), float(b @ c)]
    for i, n in enumerate(names):
        for m in names[i + 1:]:
            diff.append(float(emb(person(*people[n])) @ emb(person(*people[m], bright=0.8))))
    print(f"same-person similarity : min {min(same):.3f}  mean {np.mean(same):.3f}")
    print(f"different people       : max {max(diff):.3f}  mean {np.mean(diff):.3f}")
    assert np.mean(same) > 0.85 and min(same) > 0.70      # same person, different camera conditions
    assert max(diff) < 0.75                               # different clothing colours stay below the threshold


def _t(i, ev, src, emb_, start_s, dur_s, lat, lng, cls="PERSON", group="PERSON"):
    base = datetime(2026, 5, 1, 10, 0, 0)
    return TrackInfo(i, ev, src, cls, group, base + timedelta(seconds=start_s), base + timedelta(seconds=start_s + dur_s), lat, lng, emb_)


def test_clustering_with_time_and_place():
    cfg = MatchConfig()
    A = person((40, 40, 200), (180, 90, 30)); B = person((60, 170, 60), (25, 25, 25))
    ea1, ea2, ea3 = emb(A), emb(person((40, 40, 200), (180, 90, 30), bright=.8)), emb(person((40, 40, 200), (180, 90, 30), bright=1.2))
    eb1, eb2 = emb(B), emb(person((60, 170, 60), (25, 25, 25), bright=.85))
    # cameras ~ 250 m apart along a road
    cam1, cam2, cam3 = (16.5000, 80.6400), (16.5022, 80.6400), (16.5044, 80.6400)
    tracks = [
        _t(0, 1, 1, ea1, 0, 10, *cam1),        # A at cam1
        _t(1, 1, 1, eb1, 3, 8, *cam1),         # B at cam1 (overlaps A in the same video -> different people)
        _t(2, 2, 2, ea2, 150, 10, *cam2),      # A at cam2, 2.5 min later (walkable)
        _t(3, 2, 2, eb2, 160, 10, *cam2),      # B at cam2
        _t(4, 3, 3, ea3, 330, 10, *cam3),      # A at cam3
    ]
    clusters, s = cluster(tracks, cfg)
    groups = sorted(sorted(c) for c in clusters)
    print("clusters:", groups)
    assert [0, 2, 4] in groups and [1, 3] in groups
    assert s[0, 1] == FORBIDDEN                                         # overlapping tracks in one camera


def test_impossible_travel_is_blocked():
    cfg = MatchConfig()
    e = emb(person((40, 40, 200), (180, 90, 30)))
    far = _t(1, 2, 2, e, 20, 5, 16.5100, 80.6400)                       # ~1.2 km away, 20 s later
    near = _t(0, 1, 1, e, 0, 5, 16.5000, 80.6400)
    assert link_score(near, far, cfg) == FORBIDDEN                      # a person cannot cover 1.2 km in 15 s
    # a vehicle can
    v1 = _t(0, 1, 1, e, 0, 5, 16.5000, 80.6400, "CAR", "VEHICLE")
    v2 = _t(1, 2, 2, e, 120, 5, 16.5100, 80.6400, "CAR", "VEHICLE")
    assert link_score(v1, v2, cfg) > 0.75


def test_classes_never_match():
    cfg = MatchConfig()
    e = emb(person((40, 40, 200), (180, 90, 30)))
    assert link_score(_t(0, 1, 1, e, 0, 5, None, None), _t(1, 2, 2, e, 60, 5, None, None, "CAR", "VEHICLE"), cfg) == FORBIDDEN


if __name__ == "__main__":
    test_same_vs_different_person()
    test_clustering_with_time_and_place()
    test_impossible_travel_is_blocked()
    test_classes_never_match()
    print("ALL OK")
