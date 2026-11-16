from typing import Any
from urllib.parse import urlencode

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers

from planning.geometry import simplify
from trips.service import TripPlan

# About 100 m: the line still follows the roads at map scale, and a cross-country
# route shrinks from ~20,000 points to ~1,700 (about 40 KB).
_GEOMETRY_TOLERANCE_DEGREES = 0.001
_COORDINATE_DECIMALS = 5


@extend_schema_field(OpenApiTypes.DOUBLE)
class RoundedFloatField(serializers.Field[float, Any, float, Any]):
    """A read-only number rounded to a fixed number of decimals."""

    def __init__(self, decimals: int, **kwargs: Any) -> None:
        self.decimals = decimals
        super().__init__(read_only=True, **kwargs)

    def to_representation(self, value: float) -> float:
        return round(float(value), self.decimals)


class MoneyField(serializers.DecimalField):
    """A decimal amount rendered as a JSON number."""

    def __init__(self, decimal_places: int, **kwargs: Any) -> None:
        super().__init__(
            max_digits=14, decimal_places=decimal_places, coerce_to_string=False, **kwargs
        )


class TripPlanQuerySerializer(serializers.Serializer[None]):
    start = serializers.CharField(
        max_length=200,
        help_text=(
            "Where the trip starts, anywhere in the USA: a city and state ('Chicago, IL'), "
            "a ZIP code, a street address, a place name or 'latitude,longitude'."
        ),
    )
    finish = serializers.CharField(max_length=200, help_text="Where the trip ends; same formats.")


class LocationSerializer(serializers.Serializer[Any]):
    query = serializers.CharField(help_text="What was asked for.")
    # DRF removes declared fields from the class, so this doesn't shadow Field.label.
    label = serializers.CharField(help_text="What it was understood as.")  # type: ignore[assignment]
    latitude = RoundedFloatField(_COORDINATE_DECIMALS, source="coordinates.lat")
    longitude = RoundedFloatField(_COORDINATE_DECIMALS, source="coordinates.lng")


class GeoJsonLineStringSerializer(serializers.Serializer[Any]):
    type = serializers.ChoiceField(choices=["LineString"])
    coordinates = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField(), min_length=2, max_length=2),
        help_text="[longitude, latitude] pairs, as in GeoJSON.",
    )


class RouteSerializer(serializers.Serializer[Any]):
    distance_miles = RoundedFloatField(1)
    duration_hours = RoundedFloatField(1)
    geometry = serializers.SerializerMethodField()

    @extend_schema_field(GeoJsonLineStringSerializer)
    def get_geometry(self, route: Any) -> dict[str, Any]:
        path = simplify(route.path, _GEOMETRY_TOLERANCE_DEGREES)
        return {
            "type": "LineString",
            "coordinates": [
                [round(float(lng), _COORDINATE_DECIMALS), round(float(lat), _COORDINATE_DECIMALS)]
                for lat, lng in path
            ],
        }


class StationSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(help_text="OPIS truck stop ID.")
    name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    latitude = RoundedFloatField(
        _COORDINATE_DECIMALS, source="coordinates.lat", help_text="The town's center."
    )
    longitude = RoundedFloatField(_COORDINATE_DECIMALS, source="coordinates.lng")


class FuelStopSerializer(serializers.Serializer[Any]):
    sequence = serializers.IntegerField()
    departure = serializers.BooleanField(
        help_text=(
            "The first fill-up: at the first station on the route, normally in the start town."
        )
    )
    route_mile = RoundedFloatField(1, help_text="How far along the route the station is.")
    distance_from_route_miles = RoundedFloatField(1, source="offset_miles")
    price_per_gallon = MoneyField(8)
    gallons = MoneyField(2)
    cost = MoneyField(2, help_text="gallons x price_per_gallon, in USD.")
    station = StationSerializer()


class SummarySerializer(serializers.Serializer[Any]):
    stop_count = serializers.SerializerMethodField()
    total_gallons = MoneyField(2, source="fuel.total_gallons")
    total_cost = MoneyField(2, source="fuel.total_cost")
    currency = serializers.SerializerMethodField()
    miles_per_gallon = serializers.FloatField(source="vehicle.miles_per_gallon")
    range_miles = serializers.FloatField(source="vehicle.range_miles")

    def get_stop_count(self, plan: TripPlan) -> int:
        return len(plan.fuel.stops)

    def get_currency(self, plan: TripPlan) -> str:
        return "USD"


class TripPlanSerializer(serializers.Serializer[TripPlan]):
    start = LocationSerializer()
    finish = LocationSerializer()
    route = RouteSerializer()
    fuel_stops = FuelStopSerializer(many=True, source="fuel.stops")
    summary = SummarySerializer(source="*")
    notes = serializers.ListField(child=serializers.CharField(), source="fuel.notes")
    map_url = serializers.SerializerMethodField(help_text="The same trip drawn on a map.")

    def get_map_url(self, plan: TripPlan) -> str:
        request = self.context["request"]
        query = urlencode(
            {"start": plan.start.query, "finish": plan.finish.query, "format": "html"}
        )
        url: str = request.build_absolute_uri(f"{request.path}?{query}")
        return url


ProblemSerializer = inline_serializer(
    name="Problem",
    fields={
        "type": serializers.CharField(),
        "title": serializers.CharField(),
        "status": serializers.IntegerField(),
        "code": serializers.CharField(help_text="Stable machine-readable error code."),
        "detail": serializers.CharField(),
        "instance": serializers.CharField(),
        "errors": serializers.DictField(
            child=serializers.ListField(child=serializers.CharField()),
            required=False,
            help_text="Validation errors by parameter (400 invalid_request only).",
        ),
    },
)
