from django.core.cache.backends.base import BaseCache

from core.geo import Coordinates
from routing.route import Route, RouteProvider

_KEY_VERSION = 1
_DECIMALS = 5  # about one metre


class CachedRouteProvider:
    """Decorates a RouteProvider so a repeated trip costs no external call.

    Points are rounded to five decimals (about a metre) to form the cache key.
    Failures are not cached.
    """

    def __init__(self, inner: RouteProvider, cache: BaseCache, timeout_seconds: int) -> None:
        self._inner = inner
        self._cache = cache
        self._timeout_seconds = timeout_seconds

    def route(self, origin: Coordinates, destination: Coordinates) -> Route:
        key = f"route:v{_KEY_VERSION}:{_point(origin)}:{_point(destination)}"
        cached = self._cache.get(key)
        if isinstance(cached, Route):
            return cached
        route = self._inner.route(origin, destination)
        self._cache.set(key, route, self._timeout_seconds)
        return route


def _point(point: Coordinates) -> str:
    return f"{point.lat:.{_DECIMALS}f},{point.lng:.{_DECIMALS}f}"
