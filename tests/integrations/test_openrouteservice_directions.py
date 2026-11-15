import json
from pathlib import Path

import pytest
import responses

from core.exceptions import ProviderResponseError, RouteNotFoundError
from core.geo import Coordinates
from integrations.openrouteservice.client import OpenRouteServiceClient
from integrations.openrouteservice.directions import OpenRouteServiceRouteProvider

BASE = "https://ors.test"
DIRECTIONS = f"{BASE}/v2/directions/driving-car/geojson"
CHICAGO = Coordinates(41.8370, -87.6847)
MILWAUKEE = Coordinates(43.0500, -87.9670)
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "ors_directions.json").read_text())


@pytest.fixture
def provider():
    return OpenRouteServiceRouteProvider(OpenRouteServiceClient("key", base_url=BASE))


@responses.activate
def test_route_is_parsed_into_miles_hours_and_a_lat_lng_path(provider):
    responses.post(DIRECTIONS, json=FIXTURE)

    route = provider.route(CHICAGO, MILWAUKEE)

    assert route.distance_miles == pytest.approx(98.69, abs=0.01)
    assert route.duration_hours == pytest.approx(1.916, abs=0.001)
    assert route.path.shape == (12, 2)
    assert tuple(route.path[0]) == (41.836994, -87.684743)


@responses.activate
def test_request_asks_for_a_road_from_anywhere_and_no_turn_instructions(provider):
    responses.post(
        DIRECTIONS,
        json=FIXTURE,
        match=[
            responses.matchers.json_params_matcher(
                {
                    "coordinates": [[-87.6847, 41.837], [-87.967, 43.05]],
                    "instructions": False,
                    "radiuses": [-1, -1],
                }
            )
        ],
    )

    provider.route(CHICAGO, MILWAUKEE)


@pytest.mark.parametrize("code", [2009, 2010])
@responses.activate
def test_unroutable_points_mean_no_route(provider, code):
    responses.post(DIRECTIONS, json={"error": {"code": code, "message": "x"}}, status=404)

    with pytest.raises(RouteNotFoundError, match="No drivable route"):
        provider.route(CHICAGO, MILWAUKEE)


@responses.activate
def test_too_long_route_is_explained(provider):
    responses.post(DIRECTIONS, json={"error": {"code": 2004, "message": "x"}}, status=400)

    with pytest.raises(RouteNotFoundError, match="6,000 km"):
        provider.route(CHICAGO, MILWAUKEE)


@responses.activate
def test_other_service_errors_stay_service_errors(provider):
    responses.post(DIRECTIONS, json={"error": {"code": 2003, "message": "x"}}, status=400)

    with pytest.raises(ProviderResponseError):
        provider.route(CHICAGO, MILWAUKEE)


@responses.activate
def test_unexpected_payload_is_a_bad_response(provider):
    responses.post(DIRECTIONS, json={"type": "FeatureCollection", "features": []})

    with pytest.raises(ProviderResponseError):
        provider.route(CHICAGO, MILWAUKEE)
