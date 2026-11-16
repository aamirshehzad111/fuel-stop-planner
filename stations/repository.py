from core.geo import BoundingBox, Coordinates, haversine_miles
from planning.station import Station
from stations.models import FuelStation

# Search radii for find_nearest; the last one covers the contiguous US from anywhere in it.
_NEAREST_SEARCH_MILES = (25, 100, 400, 3000)


class DjangoStationRepository:
    """Reads fuel stations from the database as domain objects."""

    def find_nearest(self, point: Coordinates) -> Station | None:
        """The station closest to a point, searching outwards in growing boxes."""
        for radius in _NEAREST_SEARCH_MILES:
            box = BoundingBox(point.lat, point.lng, point.lat, point.lng).expanded(radius)
            stations = self.find_within(box)
            if stations:
                nearest = min(stations, key=lambda s: haversine_miles(point, s.coordinates))
                # A station in the box's corner may be farther than one outside it.
                if haversine_miles(point, nearest.coordinates) <= radius:
                    return nearest
        return None

    def find_within(self, box: BoundingBox) -> list[Station]:
        rows = FuelStation.objects.filter(
            latitude__range=(box.south, box.north),
            longitude__range=(box.west, box.east),
        ).values_list(
            "opis_id",
            "name",
            "address",
            "city",
            "state",
            "price_per_gallon",
            "latitude",
            "longitude",
        )
        return [
            Station(
                id=opis_id,
                name=name,
                address=address,
                city=city,
                state=state,
                price_per_gallon=price,
                coordinates=Coordinates(lat, lng),
            )
            for opis_id, name, address, city, state, price, lat, lng in rows
        ]
