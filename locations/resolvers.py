"""Turning a start or finish typed by a person into a point in the USA.

Resolvers are tried in order; the first that recognizes the text wins:

1. `CoordinatesResolver`  "41.8781,-87.6298"
2. `PostalCodeResolver`   "10001"              (local lookup, no external call)
3. `PlaceNameResolver`    "Chicago, IL"        (local lookup, no external call)
4. `GeocoderResolver`     anything else: "New York", a street address, a landmark
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from core.exceptions import LocationNotFoundError, LocationOutsideUnitedStatesError
from core.geo import Coordinates, is_in_united_states
from locations.directory import PlaceDirectory
from locations.geocoding import Geocoder
from locations.names import parse_state

_COORDINATES = re.compile(r"^(?P<lat>[-+]?\d+(?:\.\d+)?)\s*[,\s]\s*(?P<lng>[-+]?\d+(?:\.\d+)?)$")
_POSTAL_CODE = re.compile(r"^(?P<code>\d{5})(?:-\d{4})?$")
_CITY_STATE = re.compile(
    r"^(?P<city>[^,\d][^,]*?)\s*,\s*(?P<state>[^,\d]+?)(?:\s+\d{5}(?:-\d{4})?)?"
    r"(?:\s*,\s*(?:USA|US|United States))?$",
    re.IGNORECASE,
)
_US_COUNTRY_CODE = "USA"


@dataclass(frozen=True, slots=True)
class ResolvedLocation:
    query: str
    label: str
    coordinates: Coordinates


class LocationResolver(Protocol):
    """Resolves text it recognizes; returns None to let the next resolver try."""

    def resolve(self, query: str) -> ResolvedLocation | None: ...


class CoordinatesResolver:
    def resolve(self, query: str) -> ResolvedLocation | None:
        match = _COORDINATES.match(query)
        if match is None:
            return None
        lat, lng = float(match["lat"]), float(match["lng"])
        try:
            point = Coordinates(lat, lng)
        except ValueError as error:
            raise LocationNotFoundError(query) from error
        if not is_in_united_states(point):
            raise LocationOutsideUnitedStatesError(query, hint=_swapped_hint(lat, lng))
        return ResolvedLocation(query, f"{lat:.5f}, {lng:.5f}", point)


class PostalCodeResolver:
    def __init__(self, directory: PlaceDirectory) -> None:
        self._directory = directory

    def resolve(self, query: str) -> ResolvedLocation | None:
        match = _POSTAL_CODE.match(query)
        if match is None:
            return None
        postal_code = self._directory.find_postal_code(match["code"])
        if postal_code is None:
            return None
        return ResolvedLocation(query, f"ZIP {postal_code.code}", postal_code.coordinates)


class PlaceNameResolver:
    def __init__(self, directory: PlaceDirectory) -> None:
        self._directory = directory

    def resolve(self, query: str) -> ResolvedLocation | None:
        match = _CITY_STATE.match(query)
        if match is None:
            return None
        state = parse_state(match["state"])
        if state is None:
            return None
        place = self._directory.find_place(match["city"], state)
        if place is None:
            return None
        return ResolvedLocation(query, f"{place.name}, {state}", place.coordinates)


class GeocoderResolver:
    def __init__(self, geocoder: Geocoder) -> None:
        self._geocoder = geocoder

    def resolve(self, query: str) -> ResolvedLocation | None:
        place = self._geocoder.geocode(query)
        if place is None:
            return None
        if place.country_code != _US_COUNTRY_CODE or not is_in_united_states(place.coordinates):
            raise LocationOutsideUnitedStatesError(
                query,
                place.label,
                hint="If you meant a US town, add its state, e.g. 'Springfield, IL'.",
            )
        return ResolvedLocation(query, place.label, place.coordinates)


class ResolverChain:
    """Tries each resolver in turn; raises LocationNotFoundError if none recognizes the text."""

    def __init__(self, resolvers: Sequence[LocationResolver]) -> None:
        self._resolvers = resolvers

    def resolve(self, query: str) -> ResolvedLocation:
        text = query.strip()
        if not any(character.isalnum() for character in text):
            raise LocationNotFoundError(text)  # nothing a geocoder could search for
        for resolver in self._resolvers:
            location = resolver.resolve(text)
            if location is not None:
                return location
        raise LocationNotFoundError(text)


def _swapped_hint(lat: float, lng: float) -> str:
    if -90 <= lng <= 90 and is_in_united_states(Coordinates(lng, lat)):
        return f"Coordinates go as latitude,longitude; did you mean '{lng},{lat}'?"
    return ""
