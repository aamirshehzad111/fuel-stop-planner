"""Parsing and cleanup of the truck-stop fuel price list (CSV)."""

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from locations.names import US_STATES

_COLUMNS = {
    "opis_id": "OPIS Truckstop ID",
    "name": "Truckstop Name",
    "address": "Address",
    "city": "City",
    "state": "State",
    "rack_id": "Rack ID",
    "price": "Retail Price",
}


class PriceListError(ValueError):
    """The price list is malformed."""


@dataclass(frozen=True, slots=True)
class PriceListRow:
    opis_id: int
    name: str
    address: str
    city: str
    state: str
    rack_id: int
    price_per_gallon: Decimal


@dataclass(frozen=True, slots=True)
class PriceList:
    stations: list[PriceListRow]
    skipped_outside_us: int
    duplicates_merged: int


def read_price_list(path: Path) -> PriceList:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return parse_price_list(file)


def parse_price_list(lines: Iterable[str]) -> PriceList:
    """Parse the price list, keeping US stations and the lowest price per station ID.

    The list repeats some station IDs with different prices; a driver can get the
    lowest posted price, so that one is kept.
    """
    reader = csv.DictReader(lines)
    missing = [column for column in _COLUMNS.values() if column not in (reader.fieldnames or [])]
    if missing:
        raise PriceListError(f"missing columns: {', '.join(missing)}")

    cheapest: dict[int, PriceListRow] = {}
    us_rows = skipped_outside_us = 0
    for line_number, record in enumerate(reader, start=2):
        row = _parse_row(record, line_number)
        if row.state not in US_STATES:
            skipped_outside_us += 1
            continue
        us_rows += 1
        current = cheapest.get(row.opis_id)
        if current is None or row.price_per_gallon < current.price_per_gallon:
            cheapest[row.opis_id] = row

    return PriceList(
        stations=sorted(cheapest.values(), key=lambda row: row.opis_id),
        skipped_outside_us=skipped_outside_us,
        duplicates_merged=us_rows - len(cheapest),
    )


def _parse_row(record: dict[str, str], line_number: int) -> PriceListRow:
    value = {field: (record[column] or "").strip() for field, column in _COLUMNS.items()}
    try:
        price = Decimal(value["price"])
    except InvalidOperation:
        price = Decimal(0)
    if not price.is_finite() or price <= 0:
        raise PriceListError(f"line {line_number}: invalid price {value['price']!r}")
    try:
        opis_id, rack_id = int(value["opis_id"]), int(value["rack_id"])
    except ValueError as error:
        raise PriceListError(f"line {line_number}: invalid station or rack ID") from error
    return PriceListRow(
        opis_id=opis_id,
        name=value["name"],
        address=value["address"],
        city=value["city"],
        state=value["state"].upper(),
        rack_id=rack_id,
        price_per_gallon=price,
    )
