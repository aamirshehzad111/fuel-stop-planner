from io import StringIO

import pytest
from django.core.management import call_command

from core.geo import Coordinates
from locations.models import Place, PostalCode
from locations.place_data import (
    PlaceRecord,
    PostalCodeRecord,
    write_places,
    write_postal_codes,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def place_data_files(tmp_path):
    places = tmp_path / "places.csv.gz"
    postal_codes = tmp_path / "postal_codes.csv.gz"
    write_places(
        [
            PlaceRecord("St. Louis", "MO", Coordinates(38.63, -90.24)),
            PlaceRecord("Big Cabin", "OK", Coordinates(36.54, -95.22)),
        ],
        places,
    )
    write_postal_codes([PostalCodeRecord("10001", Coordinates(40.75, -74.0))], postal_codes)
    return ["--places", str(places), "--postal-codes", str(postal_codes)]


def test_import_loads_places_and_postal_codes(place_data_files):
    out = StringIO()

    call_command("import_places", *place_data_files, stdout=out)

    assert Place.objects.count() == 2
    assert PostalCode.objects.get(code="10001").coordinates == Coordinates(40.75, -74.0)
    assert "Loaded 2 places and 1 postal codes." in out.getvalue()


def test_import_stores_a_normalized_lookup_key(place_data_files):
    call_command("import_places", *place_data_files, stdout=StringIO())

    assert Place.objects.get(name="St. Louis").key == "saintlouis"


def test_import_replaces_previous_data(place_data_files):
    call_command("import_places", *place_data_files, stdout=StringIO())
    call_command("import_places", *place_data_files, stdout=StringIO())

    assert Place.objects.count() == 2
    assert PostalCode.objects.count() == 1
