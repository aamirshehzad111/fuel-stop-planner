from decimal import Decimal

import pytest

from stations.models import FuelStation

pytestmark = pytest.mark.django_db


def test_admin_lists_and_searches_stations(admin_client):
    FuelStation.objects.create(
        opis_id=7,
        name="WOODSHED OF BIG CABIN",
        address="I-44, EXIT 283",
        city="Big Cabin",
        state="OK",
        rack_id=307,
        price_per_gallon=Decimal("3.00733333"),
        latitude=36.5,
        longitude=-95.2,
    )

    response = admin_client.get("/admin/stations/fuelstation/", {"q": "woodshed"})

    assert response.status_code == 200
    assert b"WOODSHED OF BIG CABIN" in response.content
