from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy.spatial import cKDTree

from core.geo import EARTH_RADIUS_MILES
from planning.geometry import Path, cumulative_miles, densify

_STEP_MILES = 0.25


@dataclass(frozen=True, slots=True)
class LocatedPoints:
    """Points found near a route: their input indices, mileposts and distances from the route."""

    indices: npt.NDArray[np.intp]
    route_miles: npt.NDArray[np.float64]
    offsets_miles: npt.NDArray[np.float64]


class RouteCorridor:
    """Finds which points lie near a route and how far along it they are.

    The path is densified to a point every quarter mile and indexed in a k-d tree
    of unit vectors, so each lookup is a nearest-neighbour query. Mileposts are
    scaled so the route ends at `route_miles` (the routing service's road distance).
    """

    def __init__(self, path: Path, route_miles: float) -> None:
        dense = densify(path, _STEP_MILES)
        along = cumulative_miles(dense)
        scale = route_miles / along[-1] if along[-1] > 0 else 1.0
        self._mileposts = along * scale
        self._tree = cKDTree(_unit_vectors(dense))

    def locate(self, points: Path, max_offset_miles: float) -> LocatedPoints:
        if len(points) == 0:
            empty = np.empty(0)
            return LocatedPoints(empty.astype(np.intp), empty, empty)
        max_chord = 2 * np.sin(max_offset_miles / EARTH_RADIUS_MILES / 2)
        chords, nearest = self._tree.query(_unit_vectors(points), distance_upper_bound=max_chord)
        found = np.isfinite(chords)
        offsets = 2 * EARTH_RADIUS_MILES * np.arcsin(np.clip(chords[found] / 2, 0, 1))
        return LocatedPoints(
            indices=np.flatnonzero(found),
            route_miles=self._mileposts[nearest[found]],
            offsets_miles=offsets,
        )


def _unit_vectors(points: Path) -> npt.NDArray[np.float64]:
    lat, lng = np.radians(points[:, 0]), np.radians(points[:, 1])
    return np.column_stack((np.cos(lat) * np.cos(lng), np.cos(lat) * np.sin(lng), np.sin(lat)))
