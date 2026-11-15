import re
from dataclasses import dataclass
from typing import Protocol

from django.core.cache.backends.base import BaseCache

from core.geo import Coordinates


@dataclass(frozen=True, slots=True)
class GeocodedPlace:
    label: str
    coordinates: Coordinates
    country_code: str  # ISO 3166-1 alpha-3, e.g. "USA"


class Geocoder(Protocol):
    """Turns free text (a town, an address, a landmark) into a place."""

    def geocode(self, text: str) -> GeocodedPlace | None: ...


class CachedGeocoder:
    """Decorates a Geocoder so a repeated query costs no external call. Misses are cached too."""

    _KEY_VERSION = 1
    _MISS = "miss"

    def __init__(self, inner: Geocoder, cache: BaseCache, timeout_seconds: int) -> None:
        self._inner = inner
        self._cache = cache
        self._timeout_seconds = timeout_seconds

    def geocode(self, text: str) -> GeocodedPlace | None:
        normalized = re.sub(r"\s+", " ", text).strip().lower()
        key = f"geocode:v{self._KEY_VERSION}:{normalized}"
        cached = self._cache.get(key)
        if isinstance(cached, GeocodedPlace):
            return cached
        if cached == self._MISS:
            return None
        place = self._inner.geocode(text)
        self._cache.set(key, place or self._MISS, self._timeout_seconds)
        return place
