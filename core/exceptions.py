"""Errors shared across the project.

`DomainError`s mean the request was understood but can't be planned (an
unknown place, no road between two points). `ProviderError`s mean an external
service failed. The API turns each into a problem-details response.
"""


class DomainError(Exception):
    """The request is valid but the trip can't be planned."""


class LocationNotFoundError(DomainError):
    def __init__(self, query: str) -> None:
        super().__init__(
            f"Could not find {query!r}. Try a city and state (e.g. 'Dallas, TX'), "
            "a ZIP code, a street address or 'latitude,longitude'."
        )
        self.query = query


class LocationOutsideUnitedStatesError(DomainError):
    def __init__(self, query: str, label: str | None = None, hint: str = "") -> None:
        place = f"{query!r} ({label})" if label and label != query else repr(query)
        message = f"{place} is outside the USA. Only trips within the USA can be planned."
        super().__init__(f"{message} {hint}".strip())
        self.query = query


class SameLocationError(DomainError):
    def __init__(self) -> None:
        super().__init__("The start and finish are the same place.")


class RouteNotFoundError(DomainError):
    """No drivable route between the two points."""


class NoFuelPlanError(DomainError):
    """A stretch of the route is longer than the vehicle's range with no station on it."""

    def __init__(self, gap_start_mile: float, gap_end_mile: float, range_miles: float) -> None:
        super().__init__(
            f"No fuel station from the price list between mile {gap_start_mile:.0f} and mile "
            f"{gap_end_mile:.0f} of the route, a stretch longer than the vehicle's "
            f"{range_miles:.0f}-mile range."
        )
        self.gap_start_mile = gap_start_mile
        self.gap_end_mile = gap_end_mile


class NoStationAlongRouteError(NoFuelPlanError):
    """No station from the price list is near the route at all."""


class ProviderError(Exception):
    """An external service failed."""


class ProviderUnavailableError(ProviderError):
    """The service refused the request: missing or rejected key, quota or rate limit."""

    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ProviderTimeoutError(ProviderError):
    """The service took too long to answer."""


class ProviderResponseError(ProviderError):
    """The service answered with an error or something unreadable."""
