from decimal import Decimal

import numpy as np
import pytest

from core.exceptions import NoFuelPlanError, NoStationAlongRouteError
from core.geo import Coordinates
from planning.geometry import cumulative_miles
from planning.optimizer import FuelStopOptimizer
from planning.plan import FuelPlanner
from planning.station import Station
from planning.vehicle import Vehicle
from routing.route import Route

VEHICLE = Vehicle(range_miles=500, miles_per_gallon=10)
# Due north along the -100 meridian, about 594 miles.
PATH = np.array([[40.0, -100.0], [48.6, -100.0]])
ROUTE = Route(distance_miles=float(cumulative_miles(PATH)[-1]), duration_hours=9, path=PATH)
MILES_PER_DEGREE_LAT = 69.09


def _station(id, lat, lng, price):
    return Station(
        id=id,
        name=f"STOP {id}",
        address="US-83",
        city="Town",
        state="NE",
        price_per_gallon=Decimal(price),
        coordinates=Coordinates(lat, lng),
    )


@pytest.fixture
def planner():
    return FuelPlanner(VEHICLE, FuelStopOptimizer(VEHICLE), max_offset_miles=5)


def test_plan_buys_at_the_cheapest_station_in_town_and_again_further_on(planner):
    stations = [
        _station(1, 40.0, -100.0, "3.50"),
        _station(2, 40.0, -100.0, "3.40"),  # same town, cheaper
        _station(3, 44.0, -100.0, "3.00"),
        _station(4, 42.0, -97.0, "2.00"),  # far off the route
    ]

    plan = planner.plan(ROUTE, stations)

    assert [stop.station.id for stop in plan.stops] == [2, 3]
    first, second = plan.stops
    assert first.sequence == 1
    assert first.departure
    assert not second.departure
    assert first.route_mile == 0
    assert second.route_mile == pytest.approx(4 * MILES_PER_DEGREE_LAT, abs=0.5)
    assert first.gallons == Decimal(str(round(second.route_mile / 10, 2)))
    assert float(first.gallons + second.gallons) == pytest.approx(
        ROUTE.distance_miles / 10, abs=0.02
    )


def test_costs_are_gallons_times_price_in_cents(planner):
    plan = planner.plan(
        ROUTE, [_station(1, 40.0, -100.0, "3.00733333"), _station(2, 44.0, -100.0, "3.5")]
    )

    for stop in plan.stops:
        assert stop.cost == (stop.gallons * stop.price_per_gallon).quantize(Decimal("0.01"))
    assert plan.total_cost == sum(stop.cost for stop in plan.stops)
    assert plan.total_gallons == sum(stop.gallons for stop in plan.stops)


def test_the_departure_fill_up_is_priced_at_the_first_station_on_the_route(planner):
    plan = planner.plan(
        ROUTE, [_station(1, 41.0, -100.0, "3.00"), _station(2, 44.0, -100.0, "3.5")]
    )

    departure = plan.stops[0]
    assert departure.departure
    assert departure.route_mile == 0
    assert departure.station.id == 1
    assert departure.price_per_gallon == Decimal("3.00")
    assert len(plan.notes) == 1
    assert "mile 69" in plan.notes[0]


def test_a_far_first_station_still_plans_when_every_stretch_is_in_range(planner):
    # No station for the first 345 miles, the next one 208 miles further on.
    stations = [_station(1, 45.0, -100.0, "3.00"), _station(2, 48.0, -100.0, "3.10")]

    plan = planner.plan(ROUTE, stations)

    assert plan.stops[0].departure
    assert all(stop.gallons <= 50 for stop in plan.stops)
    assert float(plan.total_gallons) == pytest.approx(ROUTE.distance_miles / 10, abs=0.02)


def test_a_first_station_near_the_start_needs_no_note(planner):
    plan = planner.plan(
        ROUTE, [_station(1, 40.05, -100.0, "3.00"), _station(2, 44.0, -100.0, "3.0")]
    )

    assert plan.notes == ()


def test_stops_that_round_to_no_fuel_are_left_out(planner):
    # Routing paths can have points metres apart. A slightly cheaper station 0.007
    # miles on makes the cheapest plan buy 0.0007 gallons first.
    path = np.array([[40.0, -100.0], [40.0001, -100.0], [48.6, -100.0]])
    route = Route(distance_miles=float(cumulative_miles(path)[-1]), duration_hours=9, path=path)
    stations = [
        _station(1, 40.0, -100.0, "3.50"),
        _station(2, 40.0001, -100.0, "3.49"),
        _station(3, 44.0, -100.0, "3.49"),
    ]

    plan = planner.plan(route, stations)

    assert all(stop.gallons > 0 for stop in plan.stops)
    assert [stop.sequence for stop in plan.stops] == list(range(1, len(plan.stops) + 1))


def test_no_station_along_the_route_has_no_plan(planner):
    with pytest.raises(NoFuelPlanError):
        planner.plan(ROUTE, [_station(4, 42.0, -97.0, "2.00")])


def test_a_single_fill_up_can_be_priced_at_a_station_off_the_route(planner):
    elsewhere = _station(9, 40.0, -97.0, "3.10")
    short = Route(138.2, 2.3, np.array([[40.0, -100.0], [42.0, -100.0]]))

    plan = planner.plan_single_fill_up(short, elsewhere, distance_from_start_miles=158.6)

    (stop,) = plan.stops
    assert (stop.departure, stop.route_mile, stop.gallons) == (True, 0, Decimal("13.82"))
    assert plan.total_cost == Decimal("42.84")
    assert "159 miles" in plan.notes[0]


def test_a_single_fill_up_is_only_possible_within_range(planner):
    with pytest.raises(NoFuelPlanError):
        planner.plan_single_fill_up(
            ROUTE, _station(9, 40.0, -97.0, "3.10"), distance_from_start_miles=1
        )


def test_no_station_along_the_route_is_its_own_error(planner):
    with pytest.raises(NoStationAlongRouteError):
        planner.plan(ROUTE, [_station(4, 42.0, -97.0, "2.00")])
