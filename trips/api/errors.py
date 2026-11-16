"""Errors as RFC 9457 problem details (`application/problem+json`).

Every error has the same shape, with a stable `code` for programs and a `detail`
for people:

    {"type": "about:blank", "title": "Unprocessable Content", "status": 422,
     "code": "location_not_found", "detail": "Could not find 'Atlantis'. ...",
     "instance": "/api/v1/trips/plan/"}

Validation errors add `errors`, keyed by parameter.
"""

import logging
from http import HTTPStatus
from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from core.exceptions import (
    FuelPricesNotLoadedError,
    LocationNotFoundError,
    LocationOutsideUnitedStatesError,
    NoFuelPlanError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RouteNotFoundError,
    SameLocationError,
)

logger = logging.getLogger(__name__)

PROBLEM_CONTENT_TYPE = "application/problem+json"

# Error type -> (HTTP status, code). 400 = the request itself is wrong; 422 = it's
# well-formed but the trip can't be planned; 5xx = the routing service failed.
PROBLEMS: dict[type[Exception], tuple[int, str]] = {
    SameLocationError: (400, "same_location"),
    LocationNotFoundError: (422, "location_not_found"),
    LocationOutsideUnitedStatesError: (422, "location_outside_usa"),
    RouteNotFoundError: (422, "route_not_found"),
    NoFuelPlanError: (422, "no_fuel_plan"),
    ProviderUnavailableError: (503, "routing_unavailable"),
    ProviderTimeoutError: (504, "routing_timeout"),
    ProviderResponseError: (502, "routing_failed"),
    FuelPricesNotLoadedError: (503, "fuel_prices_not_loaded"),
}


def problem_details_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    request: Request | None = context.get("request")

    for error_type, (status, code) in PROBLEMS.items():
        if isinstance(exc, error_type):
            response = _problem(request, status, code, str(exc))
            if isinstance(exc, ProviderUnavailableError) and exc.retry_after_seconds:
                response["Retry-After"] = str(exc.retry_after_seconds)
            return response

    # Django's own errors, as Django REST framework treats them.
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    drf_response = drf_exception_handler(exc, context)
    if drf_response is not None and isinstance(exc, exceptions.APIException):
        if isinstance(exc, exceptions.ValidationError):
            response = _problem(
                request, 400, "invalid_request", "Check the request parameters.", errors=exc.detail
            )
        else:
            code = exc.default_code if isinstance(exc.default_code, str) else "error"
            response = _problem(request, drf_response.status_code, code, str(exc.detail))
        for header in ("Allow", "Retry-After", "WWW-Authenticate"):
            if header in drf_response:
                response[header] = drf_response[header]
        return response

    if settings.DEBUG:
        return None  # let Django show its debug page
    logger.exception("Unhandled error while planning a trip", exc_info=exc)
    return _problem(request, 500, "internal_error", "Something went wrong on our side.")


def _problem(
    request: Request | None, status: int, code: str, detail: str, errors: Any = None
) -> Response:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": HTTPStatus(status).phrase,
        "status": status,
        "code": code,
        "detail": detail,
    }
    if request is not None:
        body["instance"] = request.path
    if errors is not None:
        body["errors"] = errors
    renderer = getattr(request, "accepted_renderer", None)
    is_json = renderer is None or renderer.format == "json"
    return Response(body, status=status, content_type=PROBLEM_CONTENT_TYPE if is_json else None)
