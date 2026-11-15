from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import numpy as np

from core.exceptions import NoFuelPlanError
from planning.corridor import RouteCorridor
from planning.optimizer import FuelStopOptimizer, StopOption
from planning.station import Station
from planning.vehicle import Vehicle
from routing.route import Route

_CENTS = Decimal("0.01")
_HUNDREDTHS_OF_A_GALLON = Decimal("0.01")
# Beyond this, a note explains where the departure fill-up's price comes from.
_FAR_FIRST_STATION_MILES = 25


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

    def plan(self, route: Route, stations: Sequence[Station]) -> FuelPlan:
        """Plan the purchases; raises NoFuelPlanError if part of the route is out of range."""
        along = self._stations_along(route, stations)
        if not along:
            raise NoFuelPlanError(0, route.distance_miles, self._vehicle.range_miles)
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
            cost = (gallons * option.station.price_per_gallon).quantize(_CENTS, ROUND_HALF_UP)
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
        return FuelPlan(
            stops=tuple(stops),
            total_gallons=sum((stop.gallons for stop in stops), Decimal(0)),
            total_cost=sum((stop.cost for stop in stops), Decimal(0)),
            notes=tuple(notes),
        )

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


def _preference(option: _Located) -> tuple[Decimal, float, int]:
    return option.station.price_per_gallon, option.offset_miles, option.station.id
