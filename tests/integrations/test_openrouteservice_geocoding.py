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
# Whole states or countries are never a trip's start or finish ("LA" is not Louisiana).
POINT_LIKE_LAYERS = "venue,address,street,neighbourhood,borough,localadmin,locality"


@pytest.fixture
def geocoder():
    return OpenRouteServiceGeocoder(OpenRouteServiceClient("key", base_url=BASE))


@responses.activate
def test_best_match_is_returned(geocoder):
    responses.get(
        SEARCH,
        json=FIXTURE,
        match=[
            responses.matchers.query_param_matcher(
                {"text": "New York", "size": "10", "layers": POINT_LIKE_LAYERS}
            )
        ],
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


def _feature(label, country, confidence, lng=-90.0, lat=40.0):
    return {
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": {"label": label, "country_a": country, "confidence": confidence},
    }


@responses.activate
def test_a_us_match_wins_a_tie(geocoder):
    responses.get(
        SEARCH,
        json={
            "features": [
                _feature("Toronto, ON, Canada", "CAN", 1),
                _feature("Toronto, MO, USA", "USA", 1),
            ]
        },
    )

    assert geocoder.geocode("Toronto").label == "Toronto, MO"


@responses.activate
def test_a_better_us_match_beats_a_weak_foreign_one_ranked_first(geocoder):
    responses.get(
        SEARCH,
        json={
            "features": [_feature("Laos", "LAO", 0.1), _feature("Los Angeles, CA, USA", "USA", 0.6)]
        },
    )

    assert geocoder.geocode("LA").label == "Los Angeles, CA"


@responses.activate
def test_a_clearly_better_foreign_match_still_wins(geocoder):
    responses.get(
        SEARCH,
        json={
            "features": [
                _feature("Paris, France", "FRA", 1),
                _feature("Paris, TX, USA", "USA", 0.6),
            ]
        },
    )

    assert geocoder.geocode("Paris, France").country_code == "FRA"


@responses.activate
def test_the_top_ranked_us_match_is_kept(geocoder):
    # The geocoder ranks well-known places first even when a lesser one matches the text better.
    responses.get(
        SEARCH,
        json={
            "features": [
                _feature("Times Square, New York, NY, USA", "USA", 0.8),
                _feature("Times Square, Tucson, AZ, USA", "USA", 1),
            ]
        },
    )

    assert geocoder.geocode("Times Square").label == "Times Square, New York, NY"
