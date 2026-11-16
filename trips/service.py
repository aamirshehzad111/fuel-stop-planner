"""The trip-planning use case: from two typed places to a route and its fuel stops."""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Protocol

from core.exceptions import FuelPricesNotLoadedError, NoStationAlongRouteError, SameLocationError
from core.geo import BoundingBox, Coordinates, haversine_miles
from locations.resolvers import ResolvedLocation
from planning.plan import FuelPlan, FuelPlanner
from planning.station import Station
from planning.vehicle import Vehicle
from routing.route import Route, RouteProvider

# Two resolved places closer than this are the same place.
_SAME_PLACE_MILES = 0.1


class LocationResolver(Protocol):
    def resolve(self, query: str) -> ResolvedLocation: ...


class StationSource(Protocol):
    def has_stations(self) -> bool: ...

    def find_within(self, box: BoundingBox) -> list[Station]: ...

    def find_nearest(self, point: Coordinates) -> Station | None: ...


@dataclass(frozen=True, slots=True)
class TripPlan:
    start: ResolvedLocation
    finish: ResolvedLocation
    route: Route
    fuel: FuelPlan
    vehicle: Vehicle
    timings_ms: dict[str, float] = field(default_factory=dict)


class TripPlanner:
    """Resolves the two places, makes one routing call and plans the fuel stops."""

    def __init__(
        self,
        resolver: LocationResolver,
        router: RouteProvider,
        stations: StationSource,
        fuel_planner: FuelPlanner,
        vehicle: Vehicle,
    ) -> None:
        self._resolver = resolver
        self._router = router
        self._stations = stations
        self._fuel_planner = fuel_planner
        self._vehicle = vehicle

    def plan(self, start: str, finish: str) -> TripPlan:
        if not self._stations.has_stations():
            raise FuelPricesNotLoadedError()
        timings: dict[str, float] = {}
        with _timed(timings, "resolve"):
            origin = self._resolver.resolve(start)
            destination = self._resolver.resolve(finish)
        if haversine_miles(origin.coordinates, destination.coordinates) < _SAME_PLACE_MILES:
            raise SameLocationError()

        with _timed(timings, "route"):
            route = self._router.route(origin.coordinates, destination.coordinates)

        with _timed(timings, "stations"):
            stations = self._stations.find_within(self._area_around(route))

        with _timed(timings, "plan"):
            fuel = self._plan_fuel(route, stations, origin.coordinates)

        return TripPlan(origin, destination, route, fuel, self._vehicle, timings)

    def _plan_fuel(self, route: Route, stations: list[Station], start: Coordinates) -> FuelPlan:
        try:
            return self._fuel_planner.plan(route, stations)
        except NoStationAlongRouteError:
            # A trip within range can still be priced: one fill-up before setting off,
            # at the nearest listed station.
            nearest = self._stations.find_nearest(start)
            if route.distance_miles > self._vehicle.range_miles or nearest is None:
                raise
            return self._fuel_planner.plan_single_fill_up(
                route, nearest, haversine_miles(start, nearest.coordinates)
            )

    def _area_around(self, route: Route) -> BoundingBox:
        """The route's bounding box, grown by the distance at which stations still count."""
        south, west = route.path.min(axis=0)
        north, east = route.path.max(axis=0)
        box = BoundingBox(float(south), float(west), float(north), float(east))
        return box.expanded(self._fuel_planner.max_offset_miles)


@contextmanager
def _timed(timings: dict[str, float], name: str) -> Iterator[None]:
    started = time.perf_counter()
    try:
        yield
    finally:
        timings[name] = (time.perf_counter() - started) * 1000
