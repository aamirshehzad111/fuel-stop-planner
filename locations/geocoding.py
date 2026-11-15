from dataclasses import dataclass
from typing import Protocol

from core.geo import Coordinates


@dataclass(frozen=True, slots=True)
class GeocodedPlace:
    label: str
    coordinates: Coordinates
    country_code: str  # ISO 3166-1 alpha-3, e.g. "USA"


class Geocoder(Protocol):
    """Turns free text (a town, an address, a landmark) into a place."""

    def geocode(self, text: str) -> GeocodedPlace | None: ...
