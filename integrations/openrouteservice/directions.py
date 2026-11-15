from typing import Any

import numpy as np

from core.exceptions import ProviderResponseError, RouteNotFoundError
from core.geo import METERS_PER_MILE, Coordinates
from integrations.openrouteservice.client import (
    OpenRouteServiceClient,
    OpenRouteServiceRequestError,
)
from routing.route import Route

_ROUTE_TOO_LONG = 2004
_POINT_NOT_ROUTABLE = 2010
_ROUTE_NOT_FOUND = 2009
_SECONDS_PER_HOUR = 3600


class OpenRouteServiceRouteProvider:
    """RouteProvider backed by the OpenRouteService directions API (one call per route)."""

    def __init__(self, client: OpenRouteServiceClient, profile: str = "driving-car") -> None:
        self._client = client
        self._profile = profile

    def route(self, origin: Coordinates, destination: Coordinates) -> Route:
        payload = {
            "coordinates": [[origin.lng, origin.lat], [destination.lng, destination.lat]],
            "instructions": False,
            # Snap to the nearest road however far it is (town centers can sit in a park).
            "radiuses": [-1, -1],
        }
        try:
            body = self._client.post_directions(self._profile, payload)
        except OpenRouteServiceRequestError as error:
            if error.code == _ROUTE_TOO_LONG:
                raise RouteNotFoundError(
                    "The trip is longer than the routing service allows (6,000 km)."
                ) from error
            if error.code in (_POINT_NOT_ROUTABLE, _ROUTE_NOT_FOUND):
                raise RouteNotFoundError("No drivable route between these locations.") from error
            raise
        return _parse_route(body)


def _parse_route(body: dict[str, Any]) -> Route:
    try:
        feature = body["features"][0]
        summary = feature["properties"]["summary"]
        path = np.array(feature["geometry"]["coordinates"], dtype=np.float64)[:, ::-1]
        return Route(
            distance_miles=float(summary.get("distance", 0)) / METERS_PER_MILE,
            duration_hours=float(summary.get("duration", 0)) / _SECONDS_PER_HOUR,
            path=np.ascontiguousarray(path),
        )
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ProviderResponseError("The routing service returned an unexpected route.") from error
