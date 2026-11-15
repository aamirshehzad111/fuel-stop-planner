from collections.abc import Iterable
from dataclasses import dataclass

from django.db import transaction

from locations.models import Place, PostalCode
from locations.names import place_key
from locations.place_data import PlaceRecord, PostalCodeRecord

_BATCH_SIZE = 5000


@dataclass(frozen=True, slots=True)
class PlaceImportResult:
    places: int
    postal_codes: int


@transaction.atomic
def import_places(
    places: Iterable[PlaceRecord], postal_codes: Iterable[PostalCodeRecord]
) -> PlaceImportResult:
    """Replace the place and postal code tables with the given places and postal codes."""
    Place.objects.all().delete()
    PostalCode.objects.all().delete()

    unique_places = {
        (place.state, place_key(place.name)): place for place in places
    }  # the build step already deduplicates; this guards hand-edited files
    Place.objects.bulk_create(
        (
            Place(
                name=place.name,
                state=state,
                key=key,
                latitude=place.coordinates.lat,
                longitude=place.coordinates.lng,
            )
            for (state, key), place in unique_places.items()
        ),
        batch_size=_BATCH_SIZE,
    )
    created_codes = PostalCode.objects.bulk_create(
        (
            PostalCode(
                code=code.code, latitude=code.coordinates.lat, longitude=code.coordinates.lng
            )
            for code in postal_codes
        ),
        batch_size=_BATCH_SIZE,
    )
    return PlaceImportResult(places=len(unique_places), postal_codes=len(created_codes))
