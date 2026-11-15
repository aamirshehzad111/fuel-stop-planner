from dataclasses import dataclass
from typing import Protocol

import numpy as np
import numpy.typing as npt

from core.geo import Coordinates

type Path = npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True, eq=False)
class Route:
    """A driving route. `path` is an (N, 2) array of [latitude, longitude] rows."""

    distance_miles: float
    duration_hours: float
    path: Path

    def __post_init__(self) -> None:
        if self.path.ndim != 2 or self.path.shape[0] < 2 or self.path.shape[1] != 2:
            raise ValueError(f"route path must have shape (N >= 2, 2), got {self.path.shape}")

    @property
    def start(self) -> tuple[float, float]:
        return float(self.path[0, 0]), float(self.path[0, 1])

    @property
    def end(self) -> tuple[float, float]:
        return float(self.path[-1, 0]), float(self.path[-1, 1])


class RouteProvider(Protocol):
    """Finds the driving route between two points."""

    def route(self, origin: Coordinates, destination: Coordinates) -> Route: ...
