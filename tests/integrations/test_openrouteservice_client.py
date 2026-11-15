import pytest
import requests
import responses

from core.exceptions import ProviderResponseError, ProviderTimeoutError, ProviderUnavailableError
from integrations.openrouteservice.client import (
    OpenRouteServiceClient,
    OpenRouteServiceRequestError,
)

BASE = "https://ors.test"
DIRECTIONS = f"{BASE}/v2/directions/driving-car/geojson"
PAYLOAD = {"coordinates": [[-87.68, 41.84], [-87.97, 43.05]]}


@pytest.fixture
def client():
    return OpenRouteServiceClient("secret-key", base_url=BASE, timeout_seconds=5)


@responses.activate
def test_directions_are_posted_with_the_api_key(client):
    responses.post(
        DIRECTIONS,
        json={"type": "FeatureCollection"},
        match=[
            responses.matchers.header_matcher({"Authorization": "secret-key"}),
            responses.matchers.json_params_matcher(PAYLOAD),
        ],
    )

    assert client.post_directions("driving-car", PAYLOAD) == {"type": "FeatureCollection"}


@responses.activate
def test_geocode_sends_query_parameters(client):
    responses.get(
        f"{BASE}/geocode/search",
        json={"features": []},
        match=[responses.matchers.query_param_matcher({"text": "Chicago", "size": "1"})],
    )

    assert client.get_geocode({"text": "Chicago", "size": "1"}) == {"features": []}


@responses.activate
def test_missing_api_key_fails_without_calling_the_service():
    client = OpenRouteServiceClient("", base_url=BASE)

    with pytest.raises(ProviderUnavailableError, match="ORS_API_KEY"):
        client.post_directions("driving-car", PAYLOAD)

    assert len(responses.calls) == 0


@pytest.mark.parametrize("status", [401, 403])
@responses.activate
def test_rejected_key_or_used_up_quota_is_unavailable(client, status):
    responses.post(
        DIRECTIONS, json={"error": "Access to this API has been disallowed"}, status=status
    )

    with pytest.raises(ProviderUnavailableError, match="API key"):
        client.post_directions("driving-car", PAYLOAD)


@responses.activate
def test_rate_limit_is_unavailable_with_a_retry_hint(client):
    responses.post(
        DIRECTIONS, json={"error": "Rate limit exceeded"}, status=429, headers={"Retry-After": "30"}
    )

    with pytest.raises(ProviderUnavailableError, match="rate limit") as error:
        client.post_directions("driving-car", PAYLOAD)

    assert error.value.retry_after_seconds == 30


@pytest.mark.parametrize("status", [500, 502, 503])
@responses.activate
def test_server_errors_are_bad_responses(client, status):
    responses.post(DIRECTIONS, body="Bad Gateway", status=status)

    with pytest.raises(ProviderResponseError):
        client.post_directions("driving-car", PAYLOAD)


@responses.activate
def test_timeout(client):
    responses.post(DIRECTIONS, body=requests.Timeout())

    with pytest.raises(ProviderTimeoutError):
        client.post_directions("driving-car", PAYLOAD)


@responses.activate
def test_connection_failure_is_unavailable(client):
    responses.post(DIRECTIONS, body=requests.ConnectionError())

    with pytest.raises(ProviderUnavailableError, match="reach"):
        client.post_directions("driving-car", PAYLOAD)


@responses.activate
def test_non_json_success_is_a_bad_response(client):
    responses.post(DIRECTIONS, body="<html>maintenance</html>", status=200)

    with pytest.raises(ProviderResponseError):
        client.post_directions("driving-car", PAYLOAD)


@responses.activate
def test_request_errors_keep_the_service_error_code(client):
    responses.post(
        DIRECTIONS,
        json={"error": {"code": 2010, "message": "Could not find routable point"}},
        status=404,
    )

    with pytest.raises(OpenRouteServiceRequestError) as error:
        client.post_directions("driving-car", PAYLOAD)

    assert error.value.code == 2010
    assert "routable point" in str(error.value)


@responses.activate
def test_directions_accept_geojson(client):
    # The service refuses GeoJSON directions when the request only accepts application/json.
    responses.post(DIRECTIONS, json={})

    client.post_directions("driving-car", PAYLOAD)

    assert "application/geo+json" in responses.calls[0].request.headers["Accept"]
