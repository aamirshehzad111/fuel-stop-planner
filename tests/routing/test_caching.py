import numpy as np
import pytest
from django.core.cache import cache

from core.exceptions import RouteNotFoundError
from core.geo import Coordinates
from routing.caching import CachedRouteProvider
from routing.route import Route

CHICAGO = Coordinates(41.8370, -87.6847)
MILWAUKEE = Coordinates(43.0500, -87.9670)


class CountingProvider:
    def __init__(self, error=None):
        self.calls = 0
        self.error = error

    def route(self, origin, destination):
        self.calls += 1
        if self.error:
            raise self.error
        return Route(
            distance_miles=98.7,
            duration_hours=1.9,
            path=np.array([[origin.lat, origin.lng], [destination.lat, destination.lng]]),
        )


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


def test_repeated_trip_is_served_from_the_cache():
    inner = CountingProvider()
    provider = CachedRouteProvider(inner, cache, timeout_seconds=60)

    first = provider.route(CHICAGO, MILWAUKEE)
    second = provider.route(CHICAGO, MILWAUKEE)

    assert inner.calls == 1
    assert second.distance_miles == first.distance_miles
    np.testing.assert_array_equal(second.path, first.path)


def test_points_within_a_metre_share_a_cache_entry():
    inner = CountingProvider()
    provider = CachedRouteProvider(inner, cache, timeout_seconds=60)

    provider.route(CHICAGO, MILWAUKEE)
    provider.route(Coordinates(41.837001, -87.684701), MILWAUKEE)

    assert inner.calls == 1


def test_different_trips_are_cached_separately():
    inner = CountingProvider()
    provider = CachedRouteProvider(inner, cache, timeout_seconds=60)

    provider.route(CHICAGO, MILWAUKEE)
    provider.route(MILWAUKEE, CHICAGO)

    assert inner.calls == 2


def test_failures_are_not_cached():
    inner = CountingProvider(error=RouteNotFoundError("no route"))
    provider = CachedRouteProvider(inner, cache, timeout_seconds=60)

    for _ in range(2):
        with pytest.raises(RouteNotFoundError):
            provider.route(CHICAGO, MILWAUKEE)

    assert inner.calls == 2
