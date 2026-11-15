"""Geographic primitives shared across the project."""

from __future__ import annotations

import itertools
import json
import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path

EARTH_RADIUS_MILES = 3958.7613
METERS_PER_MILE = 1609.344

US_BOUNDARY_PATH = Path(__file__).resolve().parent.parent / "data" / "us_boundary.geojson"

# The boundary is a 1:50m outline, so coastlines can be off by a mile or two.
# Points this close to it count as inside (this also admits points just across
# a land border, which can still be routed).
US_BOUNDARY_TOLERANCE_MILES = 5.0
_MILES_PER_DEGREE_LAT = 69.172

type Ring = tuple[tuple[float, float], ...]  # (lng, lat) pairs, closed


@dataclass(frozen=True, slots=True)
class Coordinates:
    """A WGS84 point."""

    lat: float
    lng: float

    def __post_init__(self) -> None:
        if not -90 <= self.lat <= 90:
            raise ValueError(f"latitude must be between -90 and 90, got {self.lat}")
        if not -180 <= self.lng <= 180:
            raise ValueError(f"longitude must be between -180 and 180, got {self.lng}")


def haversine_miles(a: Coordinates, b: Coordinates) -> float:
    """Great-circle distance between two points, in miles."""
    lat1, lng1, lat2, lng2 = map(math.radians, (a.lat, a.lng, b.lat, b.lng))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(h))


@dataclass(frozen=True, slots=True)
class _Polygon:
    outer: Ring
    holes: tuple[Ring, ...]
    min_lng: float
    min_lat: float
    max_lng: float
    max_lat: float

    def contains(self, lng: float, lat: float) -> bool:
        if not self._bbox_contains(lng, lat, margin_degrees=0):
            return False
        return _ring_contains(self.outer, lng, lat) and not any(
            _ring_contains(hole, lng, lat) for hole in self.holes
        )

    def is_near(self, lng: float, lat: float, miles: float) -> bool:
        margin = miles / (_MILES_PER_DEGREE_LAT * max(math.cos(math.radians(lat)), 0.01))
        if not self._bbox_contains(lng, lat, margin_degrees=margin):
            return False
        return any(
            _distance_to_ring_miles(ring, lng, lat) <= miles for ring in (self.outer, *self.holes)
        )

    def _bbox_contains(self, lng: float, lat: float, margin_degrees: float) -> bool:
        return (
            self.min_lng - margin_degrees <= lng <= self.max_lng + margin_degrees
            and self.min_lat - margin_degrees <= lat <= self.max_lat + margin_degrees
        )


def _ring_contains(ring: Ring, x: float, y: float) -> bool:
    """Even-odd ray casting."""
    inside = False
    x1, y1 = ring[-1]
    for x2, y2 in ring:
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
        x1, y1 = x2, y2
    return inside


def _distance_to_ring_miles(ring: Ring, lng: float, lat: float) -> float:
    """Shortest distance from a point to a ring's edges (equirectangular, fine at this scale)."""
    scale = math.cos(math.radians(lat))
    best = math.inf
    for (x1, y1), (x2, y2) in itertools.pairwise(ring):
        ax, ay = (x1 - lng) * scale, y1 - lat
        dx, dy = (x2 - x1) * scale, y2 - y1
        length_sq = dx * dx + dy * dy
        t = 0.0 if length_sq == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / length_sq))
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best * _MILES_PER_DEGREE_LAT


@cache
def _us_polygons() -> tuple[_Polygon, ...]:
    geometry = json.loads(US_BOUNDARY_PATH.read_text())
    polygons = []
    for rings in geometry["coordinates"]:
        outer, *holes = (tuple((float(x), float(y)) for x, y in ring) for ring in rings)
        polygons.append(
            _Polygon(
                outer=outer,
                holes=tuple(holes),
                min_lng=min(x for x, _ in outer),
                min_lat=min(y for _, y in outer),
                max_lng=max(x for x, _ in outer),
                max_lat=max(y for _, y in outer),
            )
        )
    return tuple(polygons)


def is_in_united_states(point: Coordinates) -> bool:
    """True when the point lies within the 50 states or DC (territories excluded)."""
    polygons = _us_polygons()
    return any(polygon.contains(point.lng, point.lat) for polygon in polygons) or any(
        polygon.is_near(point.lng, point.lat, US_BOUNDARY_TOLERANCE_MILES) for polygon in polygons
    )
