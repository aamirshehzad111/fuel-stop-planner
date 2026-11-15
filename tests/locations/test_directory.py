import pytest

from core.geo import Coordinates
from locations.directory import PlaceDirectory
from locations.models import Place, PostalCode
from locations.names import place_key

pytestmark = pytest.mark.django_db


@pytest.fixture
def directory():
    for name, state, lat, lng in [
        ("St. Louis", "MO", 38.63, -90.24),
        ("Springfield", "IL", 39.78, -89.65),
        ("Springfield", "MO", 37.21, -93.29),
    ]:
        Place.objects.create(
            name=name, state=state, key=place_key(name), latitude=lat, longitude=lng
        )
    PostalCode.objects.create(code="10001", latitude=40.75, longitude=-74.0)
    return PlaceDirectory()


def test_find_place_matches_spelling_variants(directory):
    place = directory.find_place("saint louis", "MO")

    assert place is not None
    assert place.name == "St. Louis"


def test_find_place_respects_the_state(directory):
    place = directory.find_place("Springfield", "MO")

    assert place is not None
    assert place.coordinates == Coordinates(37.21, -93.29)


def test_find_place_returns_none_for_unknown_towns(directory):
    assert directory.find_place("Atlantis", "MO") is None


def test_find_places_looks_up_many_towns_at_once(directory):
    found = directory.find_places([("ST LOUIS", "MO"), ("Springfield", "IL"), ("Nowhere", "TX")])

    assert {town: place.name for town, place in found.items()} == {
        ("ST LOUIS", "MO"): "St. Louis",
        ("Springfield", "IL"): "Springfield",
    }


def test_find_postal_code(directory):
    postal_code = directory.find_postal_code("10001")

    assert postal_code is not None
    assert postal_code.coordinates == Coordinates(40.75, -74.0)


def test_find_postal_code_returns_none_for_unknown_codes(directory):
    assert directory.find_postal_code("99999") is None
