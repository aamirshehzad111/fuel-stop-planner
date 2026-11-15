from decimal import Decimal

import pytest

from core.geo import BoundingBox, Coordinates
from planning.station import Station
from stations.models import FuelStation
from stations.repository import DjangoStationRepository

pytestmark = pytest.mark.django_db


@pytest.fixture
def stations():
    for opis_id, lat, lng in [(1, 36.5, -95.2), (2, 43.9, -90.5), (3, 35.2, -101.8)]:
        FuelStation.objects.create(
            opis_id=opis_id,
            name=f"STOP {opis_id}",
            address="I-40",
            city="Town",
            state="OK",
            rack_id=1,
            price_per_gallon=Decimal("3.25"),
            latitude=lat,
            longitude=lng,
        )


def test_find_within_returns_stations_inside_the_box(stations):
    found = DjangoStationRepository().find_within(
        BoundingBox(south=35, west=-102, north=37, east=-95)
    )

    assert sorted(station.id for station in found) == [1, 3]


def test_find_within_returns_domain_stations(stations):
    found = DjangoStationRepository().find_within(
        BoundingBox(south=36, west=-96, north=37, east=-95)
    )

    assert found == [
        Station(
            id=1,
            name="STOP 1",
            address="I-40",
            city="Town",
            state="OK",
            price_per_gallon=Decimal("3.25"),
            coordinates=Coordinates(36.5, -95.2),
        )
    ]
