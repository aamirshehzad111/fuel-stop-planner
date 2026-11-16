"""In-memory stand-ins for the trip planner's collaborators."""

from decimal import Decimal

import numpy as np

from core.exceptions import LocationNotFoundError
from core.geo import BoundingBox, Coordinates, haversine_miles
from locations.resolvers import ResolvedLocation
from planning.geometry import cumulative_miles
from planning.station import Station
from routing.route import Route

PLACES = {
    "Origin, NE": ResolvedLocation("Origin, NE", "Origin, NE", Coordinates(40.0, -100.0)),
    "Midway, NE": ResolvedLocation("Midway, NE", "Midway, NE", Coordinates(42.0, -100.0)),
    "Far, ND": ResolvedLocation("Far, ND", "Far, ND", Coordinates(48.6, -100.0)),
    "origin, ne": ResolvedLocation("origin, ne", "Origin, NE", Coordinates(40.0, -100.0)),
}


def station(id, lat, lng, price, city="Town"):
    return Station(
        id=id,
        name=f"STOP {id}",
        address="US-83",
        city=city,
        state="NE",
        price_per_gallon=Decimal(price),
        coordinates=Coordinates(lat, lng),
    )


class FakeResolver:
    def resolve(self, query):
        try:
            return PLACES[query]
        except KeyError:
            raise LocationNotFoundError(query) from None


class StraightRouter:
    """Routes along the straight line between the two points."""

    def __init__(self):
        self.calls = 0

    def route(self, origin, destination):
        self.calls += 1
        path = np.array([[origin.lat, origin.lng], [destination.lat, destination.lng]])
        miles = float(cumulative_miles(path)[-1])
        return Route(distance_miles=miles, duration_hours=miles / 60, path=path)


class InMemoryStations:
    def __init__(self, stations):
        self.stations = stations
        self.boxes = []

    def has_stations(self):
        return bool(self.stations)

    def find_within(self, box: BoundingBox):
        self.boxes.append(box)
        return [s for s in self.stations if box.contains(s.coordinates)]

    def find_nearest(self, point):
        return min(
            self.stations,
            key=lambda s: haversine_miles(point, s.coordinates),
            default=None,
        )
