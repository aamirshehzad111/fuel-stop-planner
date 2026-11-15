import logging
from collections.abc import Mapping
from typing import Any

import requests

from core.exceptions import ProviderResponseError, ProviderTimeoutError, ProviderUnavailableError

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.openrouteservice.org"


class OpenRouteServiceRequestError(ProviderResponseError):
    """The service rejected the request with one of its own error codes."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


class OpenRouteServiceClient:
    """HTTP client for OpenRouteService. Turns transport and auth failures into ProviderErrors."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 20,
        session: requests.Session | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._session = session or requests.Session()

    def post_directions(self, profile: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/v2/directions/{profile}/geojson", json=payload)

    def get_geocode(self, params: Mapping[str, str]) -> dict[str, Any]:
        return self._request("GET", "/geocode/search", params=params)

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if not self._api_key:
            raise ProviderUnavailableError("Routing is not configured: set ORS_API_KEY.")
        try:
            response = self._session.request(
                method,
                f"{self._base_url}{path}",
                headers={
                    "Authorization": self._api_key,
                    "Accept": "application/json, application/geo+json",
                },
                timeout=self._timeout_seconds,
                **kwargs,
            )
        except requests.Timeout as error:
            raise ProviderTimeoutError("The routing service took too long to respond.") from error
        except requests.RequestException as error:
            raise ProviderUnavailableError("Could not reach the routing service.") from error

        if response.status_code in (401, 403):
            raise ProviderUnavailableError(
                "The routing service rejected the API key, or its daily quota is used up."
            )
        if response.status_code == 429:
            raise ProviderUnavailableError(
                "The routing service's rate limit was reached; try again shortly.",
                retry_after_seconds=_retry_after(response),
            )
        body = _json(response)
        if response.ok and isinstance(body, dict):
            return body
        detail = body.get("error") if isinstance(body, dict) else None
        if response.status_code < 500 and isinstance(detail, dict) and "code" in detail:
            raise OpenRouteServiceRequestError(int(detail["code"]), str(detail.get("message", "")))
        logger.warning("OpenRouteService %s %s failed: %s", method, path, response.status_code)
        raise ProviderResponseError(f"The routing service failed (HTTP {response.status_code}).")


def _json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def _retry_after(response: requests.Response) -> int | None:
    value = response.headers.get("Retry-After", "")
    return int(value) if value.isdigit() else None
