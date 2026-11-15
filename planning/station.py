from dataclasses import dataclass
from decimal import Decimal

from core.geo import Coordinates


@dataclass(frozen=True, slots=True)
class Station:
    """A fuel station and its retail price."""

    id: int
    name: str
    address: str
    city: str
    state: str
    price_per_gallon: Decimal
    coordinates: Coordinates
