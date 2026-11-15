import pytest

from core.exceptions import LocationNotFoundError, LocationOutsideUnitedStatesError
from core.geo import Coordinates
from locations.directory import PlaceDirectory
from locations.geocoding import GeocodedPlace
from locations.models import Place, PostalCode
from locations.names import place_key
from locations.resolvers import (
    CoordinatesResolver,
    GeocoderResolver,
    PlaceNameResolver,
    PostalCodeResolver,
    ResolvedLocation,
    ResolverChain,
)

pytestmark = pytest.mark.django_db

WHITE_HOUSE = GeocodedPlace(
    "1600 Pennsylvania Avenue NW, Washington, DC", Coordinates(38.897473, -77.036548), "USA"
)
NEW_YORK = GeocodedPlace("New York, NY", Coordinates(40.68295, -73.9708), "USA")
TORONTO = GeocodedPlace("Toronto, ON, Canada", Coordinates(43.64877, -79.38171), "CAN")
SAN_JUAN = GeocodedPlace("San Juan, PR", Coordinates(18.4655, -66.1057), "PRI")


class FakeGeocoder:
    def __init__(self, places):
        self.places = places
        self.queries = []

    def geocode(self, text):
        self.queries.append(text)
        return self.places.get(text)


@pytest.fixture
def geocoder():
    return FakeGeocoder(
        {
            "New York": NEW_YORK,
            "1600 Pennsylvania Ave NW, Washington, DC": WHITE_HOUSE,
            "Toronto, ON": TORONTO,
            "San Juan, Puerto Rico": SAN_JUAN,
        }
    )


@pytest.fixture
def resolver(geocoder):
    for name, state, lat, lng in [
        ("Chicago", "IL", 41.83705, -87.68494),
        ("St. Louis", "MO", 38.63, -90.24),
        ("New York", "NY", 40.66271, -73.93868),
    ]:
        Place.objects.create(
            name=name, state=state, key=place_key(name), latitude=lat, longitude=lng
        )
    PostalCode.objects.create(code="10001", latitude=40.75063, longitude=-73.99718)
    directory = PlaceDirectory()
    return ResolverChain(
        [
            CoordinatesResolver(),
            PostalCodeResolver(directory),
            PlaceNameResolver(directory),
            GeocoderResolver(geocoder),
        ]
    )


@pytest.mark.parametrize("query", ["41.8781,-87.6298", " 41.8781 , -87.6298 ", "41.8781 -87.6298"])
def test_coordinates_are_used_as_given(resolver, geocoder, query):
    location = resolver.resolve(query)

    assert location == ResolvedLocation(
        query=query.strip(), label="41.87810, -87.62980", coordinates=Coordinates(41.8781, -87.6298)
    )
    assert geocoder.queries == []


def test_coordinates_outside_the_us_are_rejected(resolver):
    with pytest.raises(LocationOutsideUnitedStatesError, match="outside the USA"):
        resolver.resolve("51.5,-0.12")


def test_swapped_coordinates_get_a_hint(resolver):
    with pytest.raises(LocationOutsideUnitedStatesError, match="latitude,longitude"):
        resolver.resolve("-87.6298,41.8781")


def test_impossible_coordinates_are_not_found(resolver):
    with pytest.raises(LocationNotFoundError):
        resolver.resolve("91,0")


@pytest.mark.parametrize("query", ["10001", "10001-1234"])
def test_zip_codes_are_looked_up_locally(resolver, geocoder, query):
    location = resolver.resolve(query)

    assert location.label == "ZIP 10001"
    assert location.coordinates == Coordinates(40.75063, -73.99718)
    assert geocoder.queries == []


@pytest.mark.parametrize(
    ("query", "label"),
    [
        ("Chicago, IL", "Chicago, IL"),
        ("chicago, illinois", "Chicago, IL"),
        (" Chicago ,  IL ", "Chicago, IL"),
        ("Chicago, IL 60601", "Chicago, IL"),
        ("Chicago, IL, USA", "Chicago, IL"),
        ("St Louis, MO", "St. Louis, MO"),
        ("new york, ny", "New York, NY"),
    ],
)
def test_city_and_state_are_looked_up_locally(resolver, geocoder, query, label):
    location = resolver.resolve(query)

    assert location.label == label
    assert geocoder.queries == []


def test_a_bare_town_name_is_geocoded(resolver, geocoder):
    location = resolver.resolve("New York")

    assert location == ResolvedLocation("New York", "New York, NY", Coordinates(40.68295, -73.9708))
    assert geocoder.queries == ["New York"]


def test_a_street_address_is_geocoded(resolver, geocoder):
    location = resolver.resolve("1600 Pennsylvania Ave NW, Washington, DC")

    assert location.label == "1600 Pennsylvania Avenue NW, Washington, DC"
    assert geocoder.queries == ["1600 Pennsylvania Ave NW, Washington, DC"]


def test_an_unknown_town_in_a_known_state_falls_back_to_the_geocoder(resolver, geocoder):
    with pytest.raises(LocationNotFoundError):
        resolver.resolve("Atlantis, TX")

    assert geocoder.queries == ["Atlantis, TX"]


@pytest.mark.parametrize("query", ["Toronto, ON", "San Juan, Puerto Rico"])
def test_places_outside_the_us_are_rejected(resolver, query):
    with pytest.raises(LocationOutsideUnitedStatesError, match="outside the USA"):
        resolver.resolve(query)


def test_nothing_found_anywhere(resolver):
    with pytest.raises(LocationNotFoundError, match="Could not find 'Atlantis, ZZ'"):
        resolver.resolve("Atlantis, ZZ")
