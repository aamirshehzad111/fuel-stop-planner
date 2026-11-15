import json
from pathlib import Path

import pytest
import responses

from core.geo import Coordinates
from integrations.openrouteservice.client import OpenRouteServiceClient
from integrations.openrouteservice.geocoding import OpenRouteServiceGeocoder
from locations.geocoding import GeocodedPlace

BASE = "https://ors.test"
SEARCH = f"{BASE}/geocode/search"
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "ors_geocode.json").read_text())


@pytest.fixture
def geocoder():
    return OpenRouteServiceGeocoder(OpenRouteServiceClient("key", base_url=BASE))


@responses.activate
def test_best_match_is_returned(geocoder):
    responses.get(
        SEARCH,
        json=FIXTURE,
        match=[responses.matchers.query_param_matcher({"text": "New York", "size": "1"})],
    )

    assert geocoder.geocode("New York") == GeocodedPlace(
        label="New York, NY", coordinates=Coordinates(40.68295, -73.9708), country_code="USA"
    )


@responses.activate
def test_places_abroad_keep_their_country(geocoder):
    feature = {
        "geometry": {"type": "Point", "coordinates": [-79.38171, 43.64877]},
        "properties": {"label": "Toronto, ON, Canada", "country_a": "CAN"},
    }
    responses.get(SEARCH, json={"features": [feature]})

    assert geocoder.geocode("Toronto") == GeocodedPlace(
        label="Toronto, ON, Canada",
        coordinates=Coordinates(43.64877, -79.38171),
        country_code="CAN",
    )


@responses.activate
def test_no_match_returns_none(geocoder):
    responses.get(SEARCH, json={"features": []})

    assert geocoder.geocode("asdfghjkl qwerty") is None
