from collections import Counter
from dataclasses import dataclass, field

from django.db import transaction

from locations.directory import PlaceDirectory
from stations.models import FuelStation
from stations.price_list import PriceList

_BATCH_SIZE = 2000


@dataclass(frozen=True, slots=True)
class StationImportReport:
    imported: int
    unplaced: Counter[tuple[str, str]] = field(default_factory=Counter)  # (city, state) -> count


@transaction.atomic
def import_stations(price_list: PriceList, directory: PlaceDirectory) -> StationImportReport:
    """Replace all stations with the price list's, placing each at its town's center.

    Stations whose town can't be found are left out and reported.
    """
    towns = directory.find_places({(row.city, row.state) for row in price_list.stations})
    stations, unplaced = [], Counter[tuple[str, str]]()
    for row in price_list.stations:
        place = towns.get((row.city, row.state))
        if place is None:
            unplaced[row.city, row.state] += 1
            continue
        stations.append(
            FuelStation(
                opis_id=row.opis_id,
                name=row.name,
                address=row.address,
                city=row.city,
                state=row.state,
                rack_id=row.rack_id,
                price_per_gallon=row.price_per_gallon,
                latitude=place.latitude,
                longitude=place.longitude,
            )
        )

    FuelStation.objects.all().delete()
    FuelStation.objects.bulk_create(stations, batch_size=_BATCH_SIZE)
    return StationImportReport(imported=len(stations), unplaced=unplaced)
