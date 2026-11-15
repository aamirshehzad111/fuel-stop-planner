from pathlib import Path

import pytest

from core.geo import Coordinates
from locations.place_data import (
    PlaceRecord,
    PostalCodeRecord,
    merge_places,
    read_census_county_subdivisions,
    read_census_places,
    read_census_zctas,
    read_gnis_populated_places,
    read_places,
    read_postal_codes,
    us_boundary_from_countries,
    write_places,
    write_postal_codes,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _lines(name):
    return (FIXTURES / name).read_text(encoding="utf-8-sig").splitlines()


@pytest.fixture(scope="module")
def merged():
    places = merge_places(
        [
            *read_census_places(_lines("census_places.txt")),
            *read_census_county_subdivisions(_lines("census_county_subdivisions.txt")),
            *read_gnis_populated_places(_lines("gnis_populated_places.txt")),
        ]
    )
    return {(place.state, place.name): place for place in places}


def test_census_place_names_lose_their_legal_description(merged):
    assert ("OK", "Oklahoma City") in merged


def test_census_place_takes_precedence_over_other_sources(merged):
    assert merged["OK", "Oklahoma City"].coordinates == Coordinates(35.467396, -97.513272)


def test_incorporated_place_beats_a_larger_census_designated_place(merged):
    assert merged["TN", "Franklin"].coordinates == Coordinates(35.925060, -86.868890)


def test_largest_of_same_named_places_is_kept(merged):
    assert merged["CA", "Lakeside"].coordinates == Coordinates(32.856183, -116.904493)


def test_county_subdivision_fills_in_when_there_is_no_place(merged):
    assert ("MA", "Hampden") in merged


def test_ambiguous_county_subdivisions_are_dropped(merged):
    assert ("PA", "Washington") not in merged


def test_unique_populated_place_fills_in_when_census_has_none(merged):
    assert merged["PA", "Breezewood"].coordinates == Coordinates(39.9978522, -78.24057)


def test_ambiguous_populated_places_are_dropped(merged):
    assert ("KY", "Midway") not in merged


def test_territories_are_skipped(merged):
    assert not any(state == "PR" for state, _ in merged)


def test_accented_names_are_kept_as_written(merged):
    assert ("CO", "Cañon City") in merged


def test_zctas_outside_the_us_are_skipped():
    codes = list(read_census_zctas(_lines("census_zctas.txt")))

    assert codes == [PostalCodeRecord("10001", Coordinates(40.750633, -73.997177))]


def test_places_round_trip_through_a_compressed_file(tmp_path):
    places = [PlaceRecord("Cañon City", "CO", Coordinates(38.44189, -105.2209))]

    write_places(places, tmp_path / "places.csv.gz")

    assert list(read_places(tmp_path / "places.csv.gz")) == places


def test_postal_codes_round_trip_through_a_compressed_file(tmp_path):
    codes = [PostalCodeRecord("10001", Coordinates(40.75063, -73.99718))]

    write_postal_codes(codes, tmp_path / "zips.csv.gz")

    assert list(read_postal_codes(tmp_path / "zips.csv.gz")) == codes


def test_us_boundary_is_taken_from_the_countries_collection():
    square = [[[-100.123456, 40.0], [-99.0, 40.0], [-99.0, 41.0], [-100.123456, 40.0]]]
    countries = {
        "type": "FeatureCollection",
        "features": [
            {"properties": {"ADM0_A3": "CAN"}, "geometry": {"type": "Polygon", "coordinates": []}},
            {
                "properties": {"ADM0_A3": "USA"},
                "geometry": {"type": "Polygon", "coordinates": square},
            },
        ],
    }

    boundary = us_boundary_from_countries(countries)

    assert boundary == {
        "type": "MultiPolygon",
        "coordinates": [[[[-100.1235, 40.0], [-99.0, 40.0], [-99.0, 41.0], [-100.1235, 40.0]]]],
    }


def test_rebuilding_the_same_data_gives_identical_files(tmp_path):
    places = [PlaceRecord("Big Cabin", "OK", Coordinates(36.53787, -95.22136))]

    write_places(places, tmp_path / "first.csv.gz")
    write_places(places, tmp_path / "second.csv.gz")

    assert (tmp_path / "first.csv.gz").read_bytes() == (tmp_path / "second.csv.gz").read_bytes()
