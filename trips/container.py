"""Composition root: builds the trip planner from settings.

Everything else depends on small interfaces; this is the one place that picks
the implementations (OpenRouteService, the database, Django's cache).
"""

from decimal import Decimal
from functools import cache

from django.conf import settings
from django.core.cache import cache as django_cache

from integrations.openrouteservice.client import OpenRouteServiceClient
from integrations.openrouteservice.directions import OpenRouteServiceRouteProvider
from integrations.openrouteservice.geocoding import OpenRouteServiceGeocoder
from locations.directory import PlaceDirectory
from locations.geocoding import CachedGeocoder
from locations.resolvers import (
    CoordinatesResolver,
    GeocoderResolver,
    PlaceNameResolver,
    PostalCodeResolver,
    ResolverChain,
)
from planning.optimizer import FuelStopOptimizer
from planning.plan import FuelPlanner
from planning.vehicle import Vehicle
from routing.caching import CachedRouteProvider
from stations.repository import DjangoStationRepository
from trips.service import TripPlanner


@cache
def get_trip_planner() -> TripPlanner:
    ors = settings.OPENROUTESERVICE
    planning = settings.FUEL_PLANNER

    client = OpenRouteServiceClient(
        ors["API_KEY"], base_url=ors["BASE_URL"], timeout_seconds=ors["TIMEOUT_SECONDS"]
    )
    directory = PlaceDirectory()
    resolver = ResolverChain(
        [
            CoordinatesResolver(),
            PostalCodeResolver(directory),
            PlaceNameResolver(directory),
            GeocoderResolver(
                CachedGeocoder(
                    OpenRouteServiceGeocoder(client), django_cache, ors["GEOCODE_CACHE_SECONDS"]
                )
            ),
        ]
    )
    router = CachedRouteProvider(
        OpenRouteServiceRouteProvider(client, ors["PROFILE"]),
        django_cache,
        ors["ROUTE_CACHE_SECONDS"],
    )
    vehicle = Vehicle(planning["VEHICLE_RANGE_MILES"], planning["MILES_PER_GALLON"])
    fuel_planner = FuelPlanner(
        vehicle,
        FuelStopOptimizer(vehicle, Decimal(planning["STOP_PENALTY_USD"])),
        planning["MAX_STATION_OFFSET_MILES"],
    )
    return TripPlanner(resolver, router, DjangoStationRepository(), fuel_planner, vehicle)
