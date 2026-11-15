from collections import Counter
from decimal import Decimal

import pytest

from locations.directory import PlaceDirectory
from stations.importer import import_stations
from stations.models import FuelStation
from stations.price_list import PriceList, PriceListRow

pytestmark = pytest.mark.django_db


def _row(opis_id, city, state, price="3.10"):
    return PriceListRow(
        opis_id=opis_id,
        name=f"STOP {opis_id}",
        address="I-44, EXIT 283",
        city=city,
        state=state,
        rack_id=1,
        price_per_gallon=Decimal(price),
    )


def _price_list(*rows):
    return PriceList(stations=list(rows), skipped_outside_us=0, duplicates_merged=0)


def test_stations_are_placed_at_their_town(towns):
    report = import_stations(
        _price_list(_row(7, "BIG CABIN", "OK", "3.00733333")), PlaceDirectory()
    )

    station = FuelStation.objects.get()
    assert report.imported == 1
    assert (station.opis_id, station.city, station.price_per_gallon) == (
        7,
        "BIG CABIN",
        Decimal("3.00733333"),
    )
    assert (station.latitude, station.longitude) == (36.5378, -95.2219)


def test_stations_in_unknown_towns_are_reported_not_imported(towns):
    report = import_stations(
        _price_list(_row(1, "Tomah", "WI"), _row(2, "Atlantis", "TX"), _row(3, "Atlantis", "TX")),
        PlaceDirectory(),
    )

    assert report.imported == 1
    assert report.unplaced == Counter({("Atlantis", "TX"): 2})
    assert list(FuelStation.objects.values_list("opis_id", flat=True)) == [1]


def test_import_replaces_existing_stations(towns):
    import_stations(_price_list(_row(1, "Tomah", "WI")), PlaceDirectory())

    import_stations(_price_list(_row(2, "Big Cabin", "OK")), PlaceDirectory())

    assert list(FuelStation.objects.values_list("opis_id", flat=True)) == [2]
