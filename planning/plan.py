import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import numpy as np

from core.exceptions import NoFuelPlanError, NoStationAlongRouteError
from core.geo import EARTH_RADIUS_MILES
from planning.corridor import RouteCorridor
from planning.optimizer import FuelStopOptimizer, StopOption
from planning.station import Station
from planning.vehicle import Vehicle
from routing.route import Route

_CENTS = Decimal("0.01")
_HUNDREDTHS_OF_A_GALLON = Decimal("0.01")
# Beyond this, a note explains where the departure fill-up's price comes from.
_FAR_FIRST_STATION_MILES = 25
# Gallons are rounded to hundredths, so "just enough" fuel can be off by this much distance.
_ROUNDING_MILES = 0.15
# A first purchase below this share of a tank gets a note saying why it's so small.
_SMALL_DEPARTURE_SHARE_OF_TANK = 0.25
# Half of Earth's circumference: no point is farther from a route than this.
_ANY_DISTANCE_MILES = math.pi * EARTH_RADIUS_MILES


@dataclass(frozen=True, slots=True)
class FuelStop:
    """A purchase. The departure stop is the fill-up before setting off, priced at
    the first station on the route (usually in the start town)."""

    sequence: int
    station: Station
    route_mile: float
    offset_miles: float  # straight-line distance from the route to the station's town
    gallons: Decimal
    cost: Decimal
    departure: bool = False

    @property
    def price_per_gallon(self) -> Decimal:
        return self.station.price_per_gallon


@dataclass(frozen=True, slots=True)
class FuelPlan:
    stops: tuple[FuelStop, ...]
    total_gallons: Decimal
    total_cost: Decimal
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _Located:
    station: Station
    route_mile: float
    offset_miles: float


class FuelPlanner:
    """Plans the fuel stops for a route from the stations near it."""

    def __init__(
        self, vehicle: Vehicle, optimizer: FuelStopOptimizer, max_offset_miles: float
    ) -> None:
        self._vehicle = vehicle
        self._optimizer = optimizer
        self._max_offset_miles = max_offset_miles

    @property
    def max_offset_miles(self) -> float:
        return self._max_offset_miles

    def plan(self, route: Route, stations: Sequence[Station]) -> FuelPlan:
        """Plan the purchases; raises NoFuelPlanError if part of the route is out of range."""
        along = self._stations_along(route, stations)
        if not along:
            raise NoStationAlongRouteError(0, route.distance_miles, self._vehicle.range_miles)
        # The vehicle sets off with an empty tank, so it first buys fuel at the start,
        # at the price of the first station on the route.
        first = along[0]
        options = [_Located(first.station, 0.0, first.offset_miles), *along]
        purchases = self._optimizer.optimize(
            [StopOption(option.route_mile, option.station.price_per_gallon) for option in options],
            route.distance_miles,
        )

        stops: list[FuelStop] = []
        for purchase in purchases:
            option = options[purchase.option_index]
            gallons = Decimal(purchase.gallons).quantize(_HUNDREDTHS_OF_A_GALLON, ROUND_HALF_UP)
            if gallons == 0:
                continue
            cost = _cost(gallons, option.station.price_per_gallon)
            stops.append(
                FuelStop(
                    sequence=len(stops) + 1,
                    station=option.station,
                    route_mile=option.route_mile,
                    offset_miles=option.offset_miles,
                    gallons=gallons,
                    cost=cost,
                    departure=purchase.option_index == 0,
                )
            )

        notes = []
        if first.route_mile > _FAR_FIRST_STATION_MILES:
            station = first.station
            notes.append(
                f"No station from the price list is within {_FAR_FIRST_STATION_MILES} miles of "
                f"the start, so the fuel bought before setting off is priced at {station.name} "
                f"in {station.city}, {station.state} (mile {first.route_mile:.0f}), the first "
                "listed station on the route."
            )
        elif note := self._small_departure_note(stops):
            notes.append(note)
        return FuelPlan(
            stops=tuple(stops),
            total_gallons=sum((stop.gallons for stop in stops), Decimal(0)),
            total_cost=sum((stop.cost for stop in stops), Decimal(0)),
            notes=tuple(notes),
        )

    def plan_single_fill_up(
        self, route: Route, station: Station, distance_from_start_miles: float
    ) -> FuelPlan:
        """One fill-up before setting off, priced at a station that isn't on the route.

        For a trip within range that passes no listed station.
        """
        if route.distance_miles > self._vehicle.range_miles:
            raise NoFuelPlanError(0, route.distance_miles, self._vehicle.range_miles)
        gallons = Decimal(route.distance_miles / self._vehicle.miles_per_gallon).quantize(
            _HUNDREDTHS_OF_A_GALLON, ROUND_HALF_UP
        )
        stop = FuelStop(
            sequence=1,
            station=station,
            route_mile=0.0,
            offset_miles=self._distance_from_route(route, station),
            gallons=gallons,
            cost=_cost(gallons, station.price_per_gallon),
            departure=True,
        )
        note = (
            f"No station from the price list is within {self._max_offset_miles:g} miles of this "
            f"route, so the fuel is priced at {station.name} in {station.city}, {station.state}, "
            f"the nearest listed station to the start ({distance_from_start_miles:.0f} miles away)."
        )
        return FuelPlan(stops=(stop,), total_gallons=gallons, total_cost=stop.cost, notes=(note,))

    def _small_departure_note(self, stops: list[FuelStop]) -> str | None:
        """Explain a small first purchase, at a station in the start town, that only buys
        enough to reach a cheaper station further on."""
        if len(stops) < 2 or not stops[0].departure:
            return None
        departure, following = stops[0], stops[1]
        if float(departure.gallons) >= _SMALL_DEPARTURE_SHARE_OF_TANK * self._vehicle.tank_gallons:
            return None
        reach_miles = float(departure.gallons) * self._vehicle.miles_per_gallon
        just_enough = abs(reach_miles - following.route_mile) <= _ROUNDING_MILES
        saving = departure.price_per_gallon - following.price_per_gallon
        if not just_enough or saving <= 0:
            return None
        here, there = departure.station, following.station
        return (
            f"Only {departure.gallons} gallons are bought at {here.name} in {here.city}, "
            f"{here.state}, at the start: just enough to reach {there.name} in {there.city}, "
            f"{there.state} (mile {following.route_mile:.0f}), where fuel is ${saving:.2f} a "
            "gallon cheaper."
        )

    @staticmethod
    def _distance_from_route(route: Route, station: Station) -> float:
        point = np.array([[station.coordinates.lat, station.coordinates.lng]])
        located = RouteCorridor(route.path, route.distance_miles).locate(
            point, max_offset_miles=_ANY_DISTANCE_MILES
        )
        return float(located.offsets_miles[0])

    def _stations_along(self, route: Route, stations: Sequence[Station]) -> list[_Located]:
        """Stations near the route in route order, keeping the cheapest at each position.

        Stations are placed at their town's center, so all stations in a town share
        a position and only the cheapest of them can be worth stopping at.
        """
        points = np.array(
            [[station.coordinates.lat, station.coordinates.lng] for station in stations],
            dtype=np.float64,
        ).reshape(-1, 2)
        located = RouteCorridor(route.path, route.distance_miles).locate(
            points, self._max_offset_miles
        )
        cheapest: dict[float, _Located] = {}
        for index, mile, offset in zip(
            located.indices, located.route_miles, located.offsets_miles, strict=True
        ):
            option = _Located(stations[index], float(mile), float(offset))
            position = round(option.route_mile, 2)
            current = cheapest.get(position)
            if current is None or _preference(option) < _preference(current):
                cheapest[position] = option
        return sorted(cheapest.values(), key=lambda option: option.route_mile)


def _cost(gallons: Decimal, price_per_gallon: Decimal) -> Decimal:
    return (gallons * price_per_gallon).quantize(_CENTS, ROUND_HALF_UP)


def _preference(option: _Located) -> tuple[Decimal, float, int]:
    return option.station.price_per_gallon, option.offset_miles, option.station.id
