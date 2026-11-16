"""Choosing where to refuel along a route, and how much to buy.

The model
---------
The vehicle starts the trip (mile 0) with an empty tank at the first stop option,
which must be at mile 0, and buys every gallon it burns: exactly
`trip_miles / mpg` gallons in all. It may stop at any option, buying up to a full
tank.

The objective is the fuel bill plus a fixed `stop_penalty` per stop. The penalty
stands for the time a stop takes; it is never part of the reported cost. With a
penalty of 0 the plan is simply the cheapest.

The algorithm
-------------
In an optimal plan, at every stop the vehicle either fills the tank or buys just
enough to reach the next stop with an empty tank (if it bought more than that at a
station that isn't the cheapest within reach, moving the extra purchase to the
cheaper station would save money). So the fuel on arrival at a stop is either 0 or
`range - distance` from a previous stop where it filled up, and a dynamic program
over those few arrival states per station finds the exact optimum in
O(stations x stations-within-range) time.
"""

import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from math import inf

from core.exceptions import NoFuelPlanError
from planning.vehicle import Vehicle

# Breaks exact ties in favour of fewer stops without changing any real choice.
_TIE_BREAKER = 1e-7
_EPSILON = 1e-9


@dataclass(frozen=True, slots=True)
class StopOption:
    """A station the vehicle could stop at: its milepost and price."""

    mile: float
    price_per_gallon: Decimal


@dataclass(frozen=True, slots=True)
class Purchase:
    option_index: int
    gallons: float


# A state is the fuel on arrival at a station. It is identified by the previous stop
# where the vehicle filled up (the fuel left is range minus the distance from it),
# or by _EMPTY when the vehicle bought just enough to get here.
_EMPTY = -1


@dataclass(slots=True)
class _State:
    cost: float
    fuel_miles: float
    previous: tuple[int, int] | None  # (station, state key) of the previous stop
    bought_miles: float  # bought at the previous stop to get here


class FuelStopOptimizer:
    def __init__(self, vehicle: Vehicle, stop_penalty: Decimal = Decimal(0)) -> None:
        self._vehicle = vehicle
        self._stop_penalty = float(stop_penalty) + _TIE_BREAKER

    def optimize(self, options: Sequence[StopOption], trip_miles: float) -> list[Purchase]:
        """The purchases, in route order. Raises NoFuelPlanError if a stretch is out of range."""
        if not options:
            raise NoFuelPlanError(0, trip_miles, self._vehicle.range_miles)
        positions = [option.mile for option in options]
        if abs(positions[0]) > _EPSILON:
            raise ValueError("the first stop option must be at the start of the route (mile 0)")
        if any(later < earlier for earlier, later in itertools.pairwise(positions)):
            raise ValueError("stop options must be in route order")
        self._check_reachable(positions, trip_miles)

        tank = self._vehicle.range_miles
        per_mile = [
            float(option.price_per_gallon) / self._vehicle.miles_per_gallon for option in options
        ]
        states: list[dict[int, _State]] = [{} for _ in options]
        states[0][_EMPTY] = _State(cost=0.0, fuel_miles=0.0, previous=None, bought_miles=0.0)
        finish: _State | None = None

        for here, arrivals in enumerate(states):
            if not arrivals:
                continue
            price = per_mile[here]
            ahead = [
                (there, positions[there] - positions[here])
                for there in range(here + 1, len(options))
                if positions[there] - positions[here] <= tank
            ]

            # Option 1: fill the tank here, then drive to any station within range.
            fill_key, fill_state = min(
                arrivals.items(),
                key=lambda item: item[1].cost + (tank - item[1].fuel_miles) * price,
            )
            fill_bought = tank - fill_state.fuel_miles
            fill_cost = fill_state.cost + fill_bought * price + self._stop_penalty
            for there, distance in ahead:
                _relax(
                    states[there],
                    here,
                    _State(fill_cost, tank - distance, (here, fill_key), fill_bought),
                )

            # Option 2: buy just enough to reach the next stop (or the finish) empty.
            # For a given distance the best arrival state minimizes cost - fuel * price
            # among states with less fuel than the distance; sweep both in order.
            by_fuel = sorted(arrivals.items(), key=lambda item: item[1].fuel_miles)
            to_finish = trip_miles - positions[here]
            targets: list[tuple[int | None, float]] = [*ahead]
            if to_finish <= tank:
                targets.append((None, to_finish))  # None stands for the finish
            best_value, best_key, cursor = inf, _EMPTY, 0
            for target, distance in targets:
                while cursor < len(by_fuel) and by_fuel[cursor][1].fuel_miles < distance - _EPSILON:
                    key, state = by_fuel[cursor]
                    value = state.cost - state.fuel_miles * price
                    if value < best_value:
                        best_value, best_key = value, key
                    cursor += 1
                if best_value == inf:
                    continue
                bought = distance - arrivals[best_key].fuel_miles
                arrival = _State(
                    best_value + distance * price + self._stop_penalty,
                    0.0,
                    (here, best_key),
                    bought,
                )
                if target is None:
                    if finish is None or arrival.cost < finish.cost - _EPSILON:
                        finish = arrival
                else:
                    _relax(states[target], _EMPTY, arrival)

        if finish is None:  # pragma: no cover - ruled out by _check_reachable
            raise NoFuelPlanError(0, trip_miles, tank)
        return self._purchases(states, finish)

    def _check_reachable(self, positions: list[float], trip_miles: float) -> None:
        tank = self._vehicle.range_miles
        for start, end in itertools.pairwise([*positions, trip_miles]):
            if end - start > tank + _EPSILON:
                raise NoFuelPlanError(start, end, tank)

    def _purchases(self, states: list[dict[int, _State]], finish: _State) -> list[Purchase]:
        purchases = []
        state = finish
        while state.previous is not None:
            station, key = state.previous
            purchases.append(Purchase(station, state.bought_miles / self._vehicle.miles_per_gallon))
            state = states[station][key]
        return purchases[::-1]


def _relax(arrivals: dict[int, _State], key: int, offer: _State) -> None:
    """Keep the cheaper of the current and the offered way to arrive in this state."""
    current = arrivals.get(key)
    if current is None or offer.cost < current.cost - _EPSILON:
        arrivals[key] = offer
