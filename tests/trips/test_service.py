from decimal import Decimal

import pytest

from core.exceptions import (
    FuelPricesNotLoadedError,
    LocationNotFoundError,
    NoFuelPlanError,
    SameLocationError,
)
from planning.optimizer import FuelStopOptimizer
from planning.plan import FuelPlanner
from planning.vehicle import Vehicle
from tests.trips.fakes import FakeResolver, InMemoryStations, StraightRouter, station
from trips.service import TripPlanner

VEHICLE = Vehicle(range_miles=500, miles_per_gallon=10)


def _planner(stations, router=None):
    return TripPlanner(
        resolver=FakeResolver(),
        router=router or StraightRouter(),
        stations=stations,
        fuel_planner=FuelPlanner(
            VEHICLE, FuelStopOptimizer(VEHICLE, Decimal(5)), max_offset_miles=5
        ),
        vehicle=VEHICLE,
    )


def test_a_trip_is_resolved_routed_once_and_fuelled():
    router = StraightRouter()
    stations = InMemoryStations(
        [station(1, 40.0, -100.0, "3.20"), station(2, 44.0, -100.0, "3.00")]
    )

    plan = _planner(stations, router).plan("Origin, NE", "Far, ND")

    assert (plan.start.label, plan.finish.label) == ("Origin, NE", "Far, ND")
    assert router.calls == 1
    assert [stop.station.id for stop in plan.fuel.stops] == [1, 2]
    assert plan.vehicle == VEHICLE


def test_stations_are_fetched_around_the_route():
    stations = InMemoryStations([station(1, 40.0, -100.0, "3.20")])

    _planner(stations).plan("Origin, NE", "Midway, NE")

    (box,) = stations.boxes
    assert box.south < 40.0 < 42.0 < box.north
    assert box.west < -100.0 < box.east


def test_each_step_is_timed():
    stations = InMemoryStations([station(1, 40.0, -100.0, "3.20")])

    plan = _planner(stations).plan("Origin, NE", "Midway, NE")

    assert set(plan.timings_ms) == {"resolve", "route", "stations", "plan"}
    assert all(duration >= 0 for duration in plan.timings_ms.values())


def test_the_same_place_twice_is_rejected_before_routing():
    router = StraightRouter()

    with pytest.raises(SameLocationError):
        _planner(InMemoryStations([station(1, 40.0, -100.0, "3.20")]), router).plan(
            "Origin, NE", "origin, ne"
        )

    assert router.calls == 0


def test_unknown_places_are_reported():
    with pytest.raises(LocationNotFoundError):
        _planner(InMemoryStations([station(1, 40.0, -100.0, "3.20")])).plan(
            "Atlantis, ZZ", "Far, ND"
        )


def test_a_short_trip_with_no_station_on_the_way_is_priced_at_the_nearest_station():
    nearest = station(7, 40.0, -97.0, "3.10", city="Elsewhere")  # ~160 miles east of the start
    stations = InMemoryStations([nearest, station(8, 30.0, -90.0, "2.00")])

    plan = _planner(stations).plan("Origin, NE", "Midway, NE")

    (stop,) = plan.fuel.stops
    assert stop.departure
    assert stop.station == nearest
    assert stop.route_mile == 0
    assert float(stop.gallons) == pytest.approx(plan.route.distance_miles / 10, abs=0.01)
    assert stop.cost == (stop.gallons * Decimal("3.10")).quantize(Decimal("0.01"))
    assert "nearest" in plan.fuel.notes[0]
    assert "Elsewhere, NE" in plan.fuel.notes[0]


def test_a_long_trip_with_no_station_on_the_way_has_no_plan():
    stations = InMemoryStations([station(7, 40.0, -97.0, "3.10")])

    with pytest.raises(NoFuelPlanError):
        _planner(stations).plan("Origin, NE", "Far, ND")


def test_planning_without_fuel_prices_says_how_to_load_them():
    router = StraightRouter()

    with pytest.raises(FuelPricesNotLoadedError, match="make data"):
        _planner(InMemoryStations([]), router).plan("Origin, NE", "Midway, NE")

    assert router.calls == 0
