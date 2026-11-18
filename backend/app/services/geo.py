import math
from typing import Iterable, Optional, Tuple

Point = Tuple[Optional[float], Optional[float]]


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def has_coords(lat, lng) -> bool:
    return lat is not None and lng is not None


def path_length_m(points: Iterable[Point]) -> float:
    pts = [p for p in points if has_coords(*p)]
    return sum(haversine_m(a[0], a[1], b[0], b[1]) for a, b in zip(pts, pts[1:]))
