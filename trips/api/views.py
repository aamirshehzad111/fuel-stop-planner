import time

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from trips import container
from trips.api.errors import PROBLEM_CONTENT_TYPE
from trips.api.negotiation import ExplicitFormatNegotiation
from trips.api.renderers import TripMapRenderer
from trips.api.serializers import ProblemSerializer, TripPlanQuerySerializer, TripPlanSerializer


def _problem(description: str) -> OpenApiResponse:
    return OpenApiResponse(ProblemSerializer, description=description)


class TripPlanView(APIView):
    """Plans a trip: the route, the cheapest fuel stops and the total fuel cost."""

    renderer_classes = (JSONRenderer, TripMapRenderer)
    content_negotiation_class = ExplicitFormatNegotiation

    @extend_schema(
        operation_id="plan_trip",
        tags=["Trips"],
        summary="Plan a trip's route and fuel stops",
        description=(
            "Resolves the start and finish (anywhere in the USA), makes one routing call, "
            "and picks where to buy fuel so the trip costs as little as possible, for a "
            "vehicle with a 500-mile range that does 10 miles per gallon. The vehicle starts "
            "empty: the first stop is the fill-up before setting off. Every gallon the trip "
            "burns is bought at one of the stops, so `summary.total_cost` is the trip's fuel "
            "cost.\n\nAdd `format=html` (or follow `map_url`) to see the trip on a map."
        ),
        parameters=[
            OpenApiParameter(
                "start",
                OpenApiTypes.STR,
                required=True,
                description=(
                    "Where the trip starts, anywhere in the USA: a city and state, a ZIP code, "
                    "a street address, a place name or `latitude,longitude`."
                ),
                examples=[
                    OpenApiExample("City and state", value="Chicago, IL"),
                    OpenApiExample("ZIP code", value="10001"),
                    OpenApiExample(
                        "Street address", value="1600 Pennsylvania Ave NW, Washington, DC"
                    ),
                    OpenApiExample("Coordinates", value="39.7392,-104.9903"),
                ],
            ),
            OpenApiParameter(
                "finish",
                OpenApiTypes.STR,
                required=True,
                description="Where the trip ends; same formats as `start`.",
                examples=[
                    OpenApiExample("City and state", value="Houston, TX"),
                    OpenApiExample("Place name", value="Los Angeles"),
                ],
            ),
            OpenApiParameter(
                "format",
                OpenApiTypes.STR,
                enum=["json", "html"],
                description="`html` returns the trip drawn on a map.",
            ),
        ],
        responses={
            (200, "application/json"): TripPlanSerializer,
            (200, "text/html"): OpenApiResponse(OpenApiTypes.STR, description="The map page."),
            (400, PROBLEM_CONTENT_TYPE): _problem(
                "Missing or invalid parameters (`invalid_request`), or the same place twice "
                "(`same_location`)."
            ),
            (422, PROBLEM_CONTENT_TYPE): _problem(
                "The trip can't be planned: `location_not_found`, `location_outside_usa`, "
                "`route_not_found` or `no_fuel_plan`."
            ),
            (429, PROBLEM_CONTENT_TYPE): _problem("Too many requests (`throttled`)."),
            (502, PROBLEM_CONTENT_TYPE): _problem("The routing service failed (`routing_failed`)."),
            (503, PROBLEM_CONTENT_TYPE): _problem(
                "Routing is unavailable: missing or rejected API key, quota or rate limit "
                "(`routing_unavailable`)."
            ),
            (504, PROBLEM_CONTENT_TYPE): _problem(
                "The routing service timed out (`routing_timeout`)."
            ),
        },
    )
    def get(self, request: Request) -> Response:
        query = TripPlanQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        plan = container.get_trip_planner().plan(
            query.validated_data["start"], query.validated_data["finish"]
        )

        started = time.perf_counter()
        data = TripPlanSerializer(plan, context={"request": request}).data
        timings = {**plan.timings_ms, "serialize": (time.perf_counter() - started) * 1000}

        response = Response(data)
        response["Server-Timing"] = ", ".join(
            f"{name};dur={duration:.1f}" for name, duration in timings.items()
        )
        return response
