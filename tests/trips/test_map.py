import json
import re

URL = "/api/v1/trips/plan/"
TRIP = {"start": "Origin, NE", "finish": "Far, ND", "format": "html"}


def test_map_page_draws_the_route_and_stops(client, fake_planner):
    response = client.get(URL, TRIP)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/html")
    html = response.content.decode()
    assert "leaflet" in html
    assert "Origin, NE" in html
    assert "STOP 2" in html
    match = re.search(r'<script id="trip-plan" type="application/json">(.*?)</script>', html)
    assert match is not None
    data = json.loads(match.group(1))
    assert len(data["fuel_stops"]) == 2
    assert data["route"]["geometry"]["type"] == "LineString"


def test_map_page_shows_errors(client, failing_planner):
    from core.exceptions import LocationNotFoundError

    failing_planner(LocationNotFoundError("Atlantis"))

    response = client.get(URL, {**TRIP, "start": "Atlantis"})

    assert response.status_code == 422
    assert response["Content-Type"].startswith("text/html")
    assert "Could not find" in response.content.decode()


def test_map_tiles_tell_openstreetmap_which_site_asks(client, fake_planner):
    # OpenStreetMap serves an "Access blocked" tile to requests without a Referer, and
    # Django's default Referrer-Policy (same-origin) stops browsers sending one.
    html = client.get(URL, TRIP).content.decode()

    assert 'referrerPolicy: "strict-origin-when-cross-origin"' in html


def test_map_can_zoom_in_half_steps_to_frame_the_route(client, fake_planner):
    html = client.get(URL, TRIP).content.decode()

    assert "zoomSnap: 0.5" in html
