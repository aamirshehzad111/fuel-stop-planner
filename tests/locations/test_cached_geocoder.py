import pytest
from django.core.cache import cache

from core.geo import Coordinates
from locations.geocoding import CachedGeocoder, GeocodedPlace

CHICAGO = GeocodedPlace("Chicago, IL", Coordinates(41.88, -87.63), "USA")


class CountingGeocoder:
    def __init__(self):
        self.calls = 0

    def geocode(self, text):
        self.calls += 1
        return CHICAGO if text.lower().strip() == "chicago" else None


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


def test_repeated_queries_are_served_from_the_cache():
    inner = CountingGeocoder()
    geocoder = CachedGeocoder(inner, cache, timeout_seconds=60)

    assert geocoder.geocode("Chicago") == CHICAGO
    assert geocoder.geocode("  CHICAGO ") == CHICAGO
    assert inner.calls == 1


def test_misses_are_cached_too():
    inner = CountingGeocoder()
    geocoder = CachedGeocoder(inner, cache, timeout_seconds=60)

    assert geocoder.geocode("asdfgh") is None
    assert geocoder.geocode("asdfgh") is None
    assert inner.calls == 1
