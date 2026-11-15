from core.geo import BoundingBox, Coordinates
from planning.station import Station
from stations.models import FuelStation


class DjangoStationRepository:
    """Reads fuel stations from the database as domain objects."""

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
