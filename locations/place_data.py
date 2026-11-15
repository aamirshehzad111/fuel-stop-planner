"""US place data: town centers and ZIP code centers, built from public-domain sources.

Sources, in order of precedence when a name appears more than once in a state
(the Census files are its "Gazetteer" files):

1. Census incorporated places (cities, towns, villages)
2. Census designated places (unincorporated communities with a Census boundary)
3. Census county subdivisions (New England towns, townships)
4. USGS GNIS populated places (every other named community)

Within one source, same-named Census places keep the largest; same-named county
subdivisions or GNIS places are ambiguous and dropped rather than guessed.
"""

from __future__ import annotations

import csv
import gzip
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any

from core.geo import Coordinates, is_in_united_states
from locations.names import US_STATES, census_place_name, parse_state, place_key

_CENSUS_DESIGNATED_PLACE_LSAD = "57"
_COORDINATE_DECIMALS = 5


class Source(IntEnum):
    INCORPORATED_PLACE = 0
    CENSUS_DESIGNATED_PLACE = 1
    COUNTY_SUBDIVISION = 2
    POPULATED_PLACE = 3


_LARGEST_WINS = {Source.INCORPORATED_PLACE, Source.CENSUS_DESIGNATED_PLACE}


@dataclass(frozen=True, slots=True)
class SourcePlace:
    name: str
    state: str
    coordinates: Coordinates
    source: Source
    land_area: int = 0


@dataclass(frozen=True, slots=True)
class PlaceRecord:
    name: str
    state: str
    coordinates: Coordinates


@dataclass(frozen=True, slots=True)
class PostalCodeRecord:
    code: str
    coordinates: Coordinates


def _pipe_rows(lines: Iterable[str]) -> Iterator[dict[str, str]]:
    reader = csv.reader(lines, delimiter="|")
    header = [column.strip().lstrip("﻿") for column in next(reader)]
    for row in reader:
        yield dict(zip(header, (value.strip() for value in row), strict=True))


def read_census_places(lines: Iterable[str]) -> Iterator[SourcePlace]:
    for row in _pipe_rows(lines):
        if row["USPS"] not in US_STATES:
            continue
        is_cdp = row["LSAD"] == _CENSUS_DESIGNATED_PLACE_LSAD
        yield SourcePlace(
            name=census_place_name(row["NAME"]),
            state=row["USPS"],
            coordinates=Coordinates(float(row["INTPTLAT"]), float(row["INTPTLONG"])),
            source=Source.CENSUS_DESIGNATED_PLACE if is_cdp else Source.INCORPORATED_PLACE,
            land_area=int(row["ALAND"]),
        )


def read_census_county_subdivisions(lines: Iterable[str]) -> Iterator[SourcePlace]:
    for row in _pipe_rows(lines):
        if row["USPS"] not in US_STATES:
            continue
        yield SourcePlace(
            name=census_place_name(row["NAME"]),
            state=row["USPS"],
            coordinates=Coordinates(float(row["INTPTLAT"]), float(row["INTPTLONG"])),
            source=Source.COUNTY_SUBDIVISION,
            land_area=int(row["ALAND"]),
        )


def read_gnis_populated_places(lines: Iterable[str]) -> Iterator[SourcePlace]:
    for row in _pipe_rows(lines):
        state = parse_state(row["state_name"])
        if state is None:
            continue
        yield SourcePlace(
            name=row["feature_name"],
            state=state,
            coordinates=Coordinates(float(row["prim_lat_dec"]), float(row["prim_long_dec"])),
            source=Source.POPULATED_PLACE,
        )


def read_census_zctas(lines: Iterable[str]) -> Iterator[PostalCodeRecord]:
    for row in _pipe_rows(lines):
        coordinates = Coordinates(float(row["INTPTLAT"]), float(row["INTPTLONG"]))
        if is_in_united_states(coordinates):
            yield PostalCodeRecord(row["GEOID"], coordinates)


def merge_places(sources: Iterable[SourcePlace]) -> list[PlaceRecord]:
    """One place per (state, name key), following the module's precedence rules."""
    groups: dict[tuple[str, str], list[SourcePlace]] = defaultdict(list)
    for source_place in sources:
        groups[source_place.state, place_key(source_place.name)].append(source_place)

    places = []
    for group in groups.values():
        best_source = min(place.source for place in group)
        best = [place for place in group if place.source == best_source]
        if len(best) > 1 and best_source not in _LARGEST_WINS:
            continue
        chosen = max(best, key=lambda place: place.land_area)
        places.append(PlaceRecord(chosen.name, chosen.state, chosen.coordinates))
    return sorted(places, key=lambda place: (place.state, place.name))


def write_places(places: Iterable[PlaceRecord], path: Path) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["name", "state", "latitude", "longitude"])
        for place in places:
            writer.writerow([place.name, place.state, *_rounded(place.coordinates)])


def read_places(path: Path) -> Iterator[PlaceRecord]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            yield PlaceRecord(row["name"], row["state"], _coordinates(row))


def write_postal_codes(codes: Iterable[PostalCodeRecord], path: Path) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["code", "latitude", "longitude"])
        for code in codes:
            writer.writerow([code.code, *_rounded(code.coordinates)])


def read_postal_codes(path: Path) -> Iterator[PostalCodeRecord]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            yield PostalCodeRecord(row["code"], _coordinates(row))


def us_boundary_from_countries(countries: dict[str, Any]) -> dict[str, Any]:
    """The US outline from a Natural Earth countries collection, as a compact MultiPolygon."""
    feature = next(f for f in countries["features"] if f["properties"]["ADM0_A3"] == "USA")
    geometry = feature["geometry"]
    polygons = geometry["coordinates"]
    if geometry["type"] == "Polygon":
        polygons = [polygons]
    return {
        "type": "MultiPolygon",
        "coordinates": [
            [[[round(x, 4), round(y, 4)] for x, y in ring] for ring in polygon]
            for polygon in polygons
        ],
    }


def _rounded(coordinates: Coordinates) -> tuple[float, float]:
    return round(coordinates.lat, _COORDINATE_DECIMALS), round(
        coordinates.lng, _COORDINATE_DECIMALS
    )


def _coordinates(row: dict[str, str]) -> Coordinates:
    return Coordinates(float(row["latitude"]), float(row["longitude"]))
