import logging

import pytest
from rest_framework.throttling import AnonRateThrottle

from core.exceptions import (
    LocationNotFoundError,
    LocationOutsideUnitedStatesError,
    NoFuelPlanError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RouteNotFoundError,
    SameLocationError,
)

URL = "/api/v1/trips/plan/"
TRIP = {"start": "Origin, NE", "finish": "Far, ND"}


@pytest.fixture(autouse=True)
def _fresh_throttle(settings):
    from django.core.cache import cache

    cache.clear()


def test_plan_is_returned_as_json(client, fake_planner):
    response = client.get(URL, TRIP)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    body = response.json()
    assert set(body) == {"start", "finish", "route", "fuel_stops", "summary", "notes", "map_url"}
    assert body["start"] == {
        "query": "Origin, NE",
        "label": "Origin, NE",
        "latitude": 40.0,
        "longitude": -100.0,
    }
    assert body["route"]["distance_miles"] == pytest.approx(594.2, abs=0.1)
    assert body["route"]["geometry"]["type"] == "LineString"
    assert body["route"]["geometry"]["coordinates"][0] == [-100.0, 40.0]  # GeoJSON: [lng, lat]


def test_fuel_stops_add_up_to_the_summary(client, fake_planner):
    body = client.get(URL, TRIP).json()

    stops, summary = body["fuel_stops"], body["summary"]
    assert [stop["sequence"] for stop in stops] == [1, 2]
    assert [stop["departure"] for stop in stops] == [True, False]
    assert stops[0]["station"]["name"] == "STOP 1"
    assert set(stops[0]["station"]) == {
        "id",
        "name",
        "address",
        "city",
        "state",
        "latitude",
        "longitude",
    }
    for stop in stops:
        assert stop["cost"] == pytest.approx(round(stop["gallons"] * stop["price_per_gallon"], 2))
    assert summary["stop_count"] == 2
    assert summary["total_gallons"] == pytest.approx(sum(stop["gallons"] for stop in stops))
    assert summary["total_cost"] == pytest.approx(sum(stop["cost"] for stop in stops))
    assert summary["total_gallons"] == pytest.approx(body["route"]["distance_miles"] / 10, abs=0.02)
    assert (summary["miles_per_gallon"], summary["range_miles"], summary["currency"]) == (
        10,
        500,
        "USD",
    )


def test_map_url_shows_the_same_trip_as_a_map(client, fake_planner):
    body = client.get(URL, TRIP).json()

    assert body["map_url"].startswith("http://testserver/api/v1/trips/plan/?")
    assert "format=html" in body["map_url"]
    assert "start=Origin%2C+NE" in body["map_url"]


def test_server_timing_reports_each_step(client, fake_planner):
    response = client.get(URL, TRIP)

    names = [part.split(";")[0].strip() for part in response["Server-Timing"].split(",")]
    assert names == ["resolve", "route", "stations", "plan", "serialize"]


def _assert_problem(response, status, code):
    assert response.status_code == status
    assert response["Content-Type"] == "application/problem+json"
    body = response.json()
    assert body["status"] == status
    assert body["code"] == code
    assert body["title"]
    assert body["detail"]
    return body


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"start": "Origin, NE"},
        {"start": " ", "finish": "Far, ND"},
        {"start": "x" * 201, "finish": "y"},
    ],
)
def test_bad_parameters_are_rejected(client, fake_planner, params):
    body = _assert_problem(client.get(URL, params), 400, "invalid_request")

    assert body["errors"]


def test_missing_parameters_are_named(client, fake_planner):
    body = _assert_problem(client.get(URL), 400, "invalid_request")

    assert set(body["errors"]) == {"start", "finish"}


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (LocationNotFoundError("Atlantis"), 422, "location_not_found"),
        (LocationOutsideUnitedStatesError("Toronto"), 422, "location_outside_usa"),
        (SameLocationError(), 400, "same_location"),
        (RouteNotFoundError("No drivable route."), 422, "route_not_found"),
        (NoFuelPlanError(0, 550, 500), 422, "no_fuel_plan"),
        (ProviderUnavailableError("Routing is not configured."), 503, "routing_unavailable"),
        (ProviderTimeoutError("Too slow."), 504, "routing_timeout"),
        (ProviderResponseError("Bad gateway."), 502, "routing_failed"),
    ],
)
def test_planning_errors_become_problem_details(client, failing_planner, error, status, code):
    failing_planner(error)

    body = _assert_problem(client.get(URL, TRIP), status, code)

    assert body["detail"] == str(error)
    assert body["instance"] == URL


def test_rate_limited_routing_says_when_to_retry(client, failing_planner):
    failing_planner(ProviderUnavailableError("Rate limit.", retry_after_seconds=30))

    response = client.get(URL, TRIP)

    assert response["Retry-After"] == "30"


def test_unexpected_errors_are_logged_and_hidden(client, failing_planner, caplog):
    failing_planner(RuntimeError("database password is hunter2"))

    with caplog.at_level(logging.ERROR):
        body = _assert_problem(client.get(URL, TRIP), 500, "internal_error")

    assert "hunter2" not in body["detail"]
    assert "hunter2" in caplog.text


def test_only_get_is_allowed(client, fake_planner):
    _assert_problem(client.post(URL, TRIP), 405, "method_not_allowed")


def test_browsers_get_json_unless_they_ask_for_the_map(client, fake_planner):
    response = client.get(URL, TRIP, HTTP_ACCEPT="text/html,application/xhtml+xml,*/*;q=0.8")

    assert response["Content-Type"] == "application/json"


def test_unknown_formats_are_not_found(client, fake_planner):
    _assert_problem(client.get(URL, {**TRIP, "format": "xml"}), 404, "not_found")


def test_requests_are_rate_limited(client, fake_planner, monkeypatch):
    monkeypatch.setitem(AnonRateThrottle.THROTTLE_RATES, "anon", "2/minute")

    for _ in range(2):
        assert client.get(URL, TRIP).status_code == 200
    response = client.get(URL, TRIP)

    _assert_problem(response, 429, "throttled")
    assert int(response["Retry-After"]) > 0
