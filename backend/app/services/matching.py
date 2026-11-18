"""
Cross-camera association: decide which tracks from different evidence are the same real-world object.

Pure Python/NumPy (no database or web imports) so it can be unit-tested on its own.

link score = appearance similarity  x  travel plausibility  x  small time-proximity prior

* appearance      : cosine similarity of the appearance descriptors (see embedder.py)
* plausibility    : can an object get from camera A to camera B in the time between the sightings?
                    (distance / time gap compared with a maximum speed for persons/vehicles)
* hard constraints: different classes never match; two tracks in the same evidence that overlap in time
                    are different objects; the same object cannot be in two distant places at once.

Tracks are then grouped with constrained average-linkage clustering.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

import numpy as np

from .geo import has_coords, haversine_m

FORBIDDEN = float("-inf")


@dataclass
class TrackInfo:
    id: int
    evidence_id: int
    source_id: int
    cls: str
    group: str
    start: datetime
    end: datetime
    lat: Optional[float]
    lng: Optional[float]
    emb: Optional[np.ndarray]


@dataclass
class MatchConfig:
    threshold: float = 0.75
    person_max_speed: float = 7.0       # m/s
    vehicle_max_speed: float = 35.0     # m/s
    same_place_m: float = 30.0


def _gap_seconds(a: TrackInfo, b: TrackInfo) -> float:
    """Seconds between the two sightings (0 when they overlap in time)."""
    if a.end <= b.start:
        return (b.start - a.end).total_seconds()
    if b.end <= a.start:
        return (a.start - b.end).total_seconds()
    return 0.0


def link_score(a: TrackInfo, b: TrackInfo, cfg: MatchConfig) -> float:
    """Return a score in [0, 1], or FORBIDDEN (-inf) if the two tracks cannot be the same object."""
    if a.cls != b.cls or a.emb is None or b.emb is None or a.emb.shape != b.emb.shape:
        return FORBIDDEN

    gap = _gap_seconds(a, b)
    if a.evidence_id == b.evidence_id and gap == 0.0:
        return FORBIDDEN                                  # two simultaneous tracks in one camera = two objects

    plaus = 1.0
    if has_coords(a.lat, a.lng) and has_coords(b.lat, b.lng):
        d = haversine_m(a.lat, a.lng, b.lat, b.lng)
        if d > cfg.same_place_m:
            if gap <= 0.0:
                return FORBIDDEN                          # same time, different places
            vmax = cfg.person_max_speed if a.group == "PERSON" else cfg.vehicle_max_speed
            v = d / gap
            if v >= 2 * vmax:
                return FORBIDDEN                          # physically impossible journey
            if v > vmax:
                plaus = max(0.0, 2.0 - v / vmax)          # tapering penalty between 1x and 2x max speed

    appearance = float(np.clip(np.dot(a.emb, b.emb), 0.0, 1.0))
    time_prior = 0.9 + 0.1 * float(np.exp(-gap / 900.0))
    return appearance * plaus * time_prior


def score_matrix(tracks: List[TrackInfo], cfg: MatchConfig) -> np.ndarray:
    n = len(tracks)
    s = np.full((n, n), FORBIDDEN)
    for i in range(n):
        for j in range(i + 1, n):
            s[i, j] = s[j, i] = link_score(tracks[i], tracks[j], cfg)
    return s


def cluster(tracks: List[TrackInfo], cfg: MatchConfig) -> Tuple[List[List[int]], np.ndarray]:
    """Constrained average-linkage clustering. Returns (clusters as index lists, pairwise score matrix)."""
    n = len(tracks)
    s = score_matrix(tracks, cfg)
    if n == 0:
        return [], s
    d = s.copy()
    np.fill_diagonal(d, FORBIDDEN)
    size = np.ones(n)
    members = {i: [i] for i in range(n)}

    while True:
        flat = int(np.argmax(d))
        a, b = divmod(flat, n)
        if d[a, b] < cfg.threshold:                       # also stops when everything left is forbidden (-inf)
            break
        for c in range(n):
            if c in (a, b):
                continue
            if d[a, c] == FORBIDDEN or d[b, c] == FORBIDDEN:
                d[a, c] = d[c, a] = FORBIDDEN             # one forbidden pair blocks the whole merge
            else:
                d[a, c] = d[c, a] = (size[a] * d[a, c] + size[b] * d[b, c]) / (size[a] + size[b])
        d[b, :] = FORBIDDEN
        d[:, b] = FORBIDDEN
        d[a, a] = FORBIDDEN
        size[a] += size[b]
        members[a].extend(members.pop(b))

    return [sorted(m) for m in members.values()], s


def cluster_confidence(indices: List[int], s: np.ndarray) -> Optional[float]:
    """Mean pairwise score inside a cluster (None for a single track)."""
    if len(indices) < 2:
        return None
    vals = [s[i, j] for k, i in enumerate(indices) for j in indices[k + 1:] if s[i, j] != FORBIDDEN]
    return float(np.mean(vals)) if vals else None


def member_confidence(i: int, indices: List[int], s: np.ndarray) -> Optional[float]:
    vals = [s[i, j] for j in indices if j != i and s[i, j] != FORBIDDEN]
    return float(np.mean(vals)) if vals else None
