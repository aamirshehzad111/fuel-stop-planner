"""Operations on paths: (N, 2) arrays of [latitude, longitude] rows."""

import numpy as np
import numpy.typing as npt

from core.geo import EARTH_RADIUS_MILES

type Path = npt.NDArray[np.float64]


def segment_miles(path: Path) -> npt.NDArray[np.float64]:
    """Great-circle length of each segment (haversine)."""
    lat, lng = np.radians(path[:, 0]), np.radians(path[:, 1])
    h = (
        np.sin(np.diff(lat) / 2) ** 2
        + np.cos(lat[:-1]) * np.cos(lat[1:]) * np.sin(np.diff(lng) / 2) ** 2
    )
    return np.asarray(2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(np.clip(h, 0, 1))))


def cumulative_miles(path: Path) -> npt.NDArray[np.float64]:
    """Distance along the path at each point, starting at 0."""
    return np.concatenate(([0.0], np.cumsum(segment_miles(path))))


def densify(path: Path, max_step_miles: float) -> Path:
    """Insert evenly spaced points so no segment is longer than `max_step_miles`."""
    pieces = np.maximum(np.ceil(segment_miles(path) / max_step_miles).astype(int), 1)
    if (pieces == 1).all():
        return path
    starts = np.repeat(path[:-1], pieces, axis=0)
    deltas = np.repeat(np.diff(path, axis=0) / pieces[:, None], pieces, axis=0)
    steps = np.concatenate([np.arange(count) for count in pieces])[:, None]
    return np.vstack((starts + deltas * steps, path[-1:]))


def simplify(path: Path, tolerance_degrees: float) -> Path:
    """Ramer-Douglas-Peucker: drop points closer than the tolerance to the simplified line."""
    keep = np.zeros(len(path), dtype=bool)
    keep[[0, -1]] = True
    stack = [(0, len(path) - 1)]
    while stack:
        first, last = stack.pop()
        if last - first < 2:
            continue
        start, end = path[first], path[last]
        between = path[first + 1 : last]
        direction = end - start
        length = np.hypot(*direction)
        if length == 0:
            distances = np.hypot(*(between - start).T)
        else:
            offsets = between - start
            distances = np.abs(direction[0] * offsets[:, 1] - direction[1] * offsets[:, 0]) / length
        farthest = int(np.argmax(distances))
        if distances[farthest] > tolerance_degrees:
            index = first + 1 + farthest
            keep[index] = True
            stack.extend(((first, index), (index, last)))
    return path[keep]
