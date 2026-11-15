import itertools
import random
from decimal import Decimal

import numpy as np
import pytest
from scipy.optimize import linprog

from core.exceptions import NoFuelPlanError
from planning.optimizer import FuelStopOptimizer, Purchase, StopOption
from planning.vehicle import Vehicle

VEHICLE = Vehicle(range_miles=500, miles_per_gallon=10)


def _options(*stations):
    return [StopOption(mile=mile, price_per_gallon=Decimal(str(price))) for mile, price in stations]


def _optimize(stations, trip_miles, stop_penalty=0):
    optimizer = FuelStopOptimizer(VEHICLE, stop_penalty=Decimal(stop_penalty))
    return optimizer.optimize(_options(*stations), trip_miles)


def _approx(purchases):
    return [(p.option_index, round(p.gallons, 6)) for p in purchases]


def test_a_short_trip_fills_up_once_with_exactly_the_fuel_it_needs():
    assert _approx(_optimize([(0, 3.5)], trip_miles=300)) == [(0, 30)]


def test_the_first_option_must_be_at_the_start():
    with pytest.raises(ValueError, match="start"):
        _optimize([(20, 3.5)], trip_miles=450)


def test_buys_just_enough_to_reach_a_cheaper_station():
    purchases = _optimize([(0, 4.0), (100, 3.0)], trip_miles=400)

    assert _approx(purchases) == [(0, 10), (1, 30)]


def test_fills_up_where_fuel_is_cheapest_and_tops_up_later():
    purchases = _optimize([(0, 3.0), (300, 4.0)], trip_miles=700)

    assert _approx(purchases) == [(0, 50), (1, 20)]


def test_skips_stations_it_does_not_need():
    purchases = _optimize([(0, 3.0), (200, 4.5), (400, 4.4), (450, 2.9)], trip_miles=900)

    assert _approx(purchases) == [(0, 45), (3, 45)]


def test_without_a_stop_cost_it_makes_a_tiny_stop_to_save_a_few_dollars():
    purchases = _optimize([(0, 3.5), (16, 3.2)], trip_miles=300)

    assert _approx(purchases) == [(0, 1.6), (1, 28.4)]


def test_a_stop_cost_avoids_stops_that_save_less_than_it():
    purchases = _optimize([(0, 3.5), (16, 3.2)], trip_miles=300, stop_penalty=10)

    assert _approx(purchases) == [(0, 30)]


def test_a_stretch_longer_than_the_range_has_no_plan():
    with pytest.raises(NoFuelPlanError) as error:
        _optimize([(0, 3.0), (100, 3.0), (700, 3.0)], trip_miles=900)

    assert (error.value.gap_start_mile, error.value.gap_end_mile) == (100, 700)


def test_a_last_stretch_longer_than_the_range_has_no_plan():
    with pytest.raises(NoFuelPlanError) as error:
        _optimize([(0, 3.0), (100, 3.0)], trip_miles=700)

    assert (error.value.gap_start_mile, error.value.gap_end_mile) == (100, 700)


def test_no_station_within_range_of_the_start_has_no_plan():
    with pytest.raises(NoFuelPlanError) as error:
        _optimize([(0, 3.0), (650, 3.0)], trip_miles=900)

    assert (error.value.gap_start_mile, error.value.gap_end_mile) == (0, 650)


def test_no_stations_has_no_plan():
    with pytest.raises(NoFuelPlanError):
        _optimize([], trip_miles=100)


def test_options_must_be_in_route_order():
    with pytest.raises(ValueError, match="route order"):
        _optimize([(0, 3.0), (200, 3.0), (100, 3.0)], trip_miles=300)


def _lp_cost(positions, per_mile, subset, trip, tank):
    """Cheapest purchases (miles of fuel) at the given stops, by linear programming."""
    stops = sorted(subset)
    k = len(stops)
    a_ub, b_ub = [], []
    for i, stop in enumerate(stops):
        # Arriving at a stop: fuel bought so far >= distance driven so far.
        row = np.zeros(k)
        row[:i] = -1
        a_ub.append(row)
        b_ub.append(-positions[stop])
        # Tank capacity after buying at this stop.
        row = np.zeros(k)
        row[: i + 1] = 1
        a_ub.append(row)
        b_ub.append(tank + positions[stop])
    row = -np.ones(k)  # reach the finish
    a_ub.append(row)
    b_ub.append(-trip)
    result = linprog(
        c=[per_mile[s] for s in stops], A_ub=a_ub, b_ub=b_ub, bounds=[(0, None)] * k, method="highs"
    )
    return result.fun if result.status == 0 else None


@pytest.mark.parametrize("stop_penalty", [0, 7])
def test_matches_brute_force_on_random_trips(stop_penalty):
    rng = random.Random(20261116 + stop_penalty)
    checked = 0
    for _ in range(150):
        trip = rng.uniform(100, 1600)
        count = rng.randint(1, 6)
        positions = sorted([0.0] + [rng.uniform(0, trip) for _ in range(count - 1)])
        prices = [round(rng.uniform(2.8, 4.6), 3) for _ in positions]
        per_mile = [price / 10 for price in prices]

        best = None
        for size in range(1, count + 1):
            for rest in itertools.combinations(range(1, count), size - 1):
                cost = _lp_cost(positions, per_mile, (0, *rest), trip, tank=500)
                if cost is not None:
                    total = cost + stop_penalty * size
                    best = total if best is None else min(best, total)

        try:
            purchases = _optimize(list(zip(positions, prices, strict=True)), trip, stop_penalty)
        except NoFuelPlanError:
            assert best is None
            continue
        assert best is not None
        assert sum(p.gallons for p in purchases) == pytest.approx(trip / 10)
        total = sum(p.gallons * prices[p.option_index] for p in purchases)
        assert total + stop_penalty * len(purchases) == pytest.approx(best, abs=1e-6)
        checked += 1
    assert checked > 50


def test_purchases_are_value_objects():
    assert Purchase(option_index=0, gallons=1.5) == Purchase(option_index=0, gallons=1.5)
