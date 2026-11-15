from collections import defaultdict
from collections.abc import Iterable

from locations.models import Place, PostalCode
from locations.names import place_key

type Town = tuple[str, str]  # (name, state code)


class PlaceDirectory:
    """Looks up US towns and ZIP codes."""

    def find_place(self, name: str, state: str) -> Place | None:
        return Place.objects.filter(state=state, key=place_key(name)).first()

    def find_places(self, towns: Iterable[Town]) -> dict[Town, Place]:
        """Batch lookup; towns that are not found are left out of the result."""
        wanted: dict[str, dict[str, list[Town]]] = defaultdict(lambda: defaultdict(list))
        for town in towns:
            name, state = town
            wanted[state][place_key(name)].append(town)

        found: dict[Town, Place] = {}
        for state, towns_by_key in wanted.items():
            for place in Place.objects.filter(state=state, key__in=towns_by_key):
                for town in towns_by_key[place.key]:
                    found[town] = place
        return found

    def find_postal_code(self, code: str) -> PostalCode | None:
        return PostalCode.objects.filter(code=code).first()
