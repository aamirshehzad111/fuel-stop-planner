from decimal import Decimal

import pytest

from planning.optimizer import FuelStopOptimizer
from planning.plan import FuelPlanner
from planning.vehicle import Vehicle
from tests.trips.fakes import FakeResolver, InMemoryStations, StraightRouter, station
from trips import container
from trips.service import TripPlanner

VEHICLE = Vehicle(range_miles=500, miles_per_gallon=10)


@pytest.fixture
def fake_planner(monkeypatch):
    """Serve the API from in-memory places, a straight-line router and two stations."""
    planner = TripPlanner(
        resolver=FakeResolver(),
        router=StraightRouter(),
        stations=InMemoryStations(
            [station(1, 40.0, -100.0, "3.20", city="Origin"), station(2, 44.0, -100.0, "3.00")]
        ),
        fuel_planner=FuelPlanner(
            VEHICLE, FuelStopOptimizer(VEHICLE, Decimal(5)), max_offset_miles=5
        ),
        vehicle=VEHICLE,
    )
    monkeypatch.setattr(container, "get_trip_planner", lambda: planner)
    return planner


class FailingPlanner:
    def __init__(self, error):
        self.error = error

    def plan(self, start, finish):
        raise self.error


@pytest.fixture
def failing_planner(monkeypatch):
    def install(error):
        monkeypatch.setattr(container, "get_trip_planner", lambda: FailingPlanner(error))

    return install
