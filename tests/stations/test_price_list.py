from decimal import Decimal

import pytest

from stations.price_list import PriceListError, PriceListRow, parse_price_list

HEADER = "OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price"


def _parse(*rows):
    return parse_price_list([HEADER, *rows])


def test_rows_are_parsed_and_trimmed():
    price_list = _parse(
        '7,WOODSHED OF BIG CABIN,"I-44, EXIT 283 & US-69",Big Cabin   ,OK,307,3.00733333'
    )

    assert price_list.stations == [
        PriceListRow(
            opis_id=7,
            name="WOODSHED OF BIG CABIN",
            address="I-44, EXIT 283 & US-69",
            city="Big Cabin",
            state="OK",
            rack_id=307,
            price_per_gallon=Decimal("3.00733333"),
        )
    ]


def test_duplicate_station_ids_keep_the_lowest_price():
    price_list = _parse(
        "20,PILOT TRAVEL CENTER #1243,I-8 EXIT 119,Gila Bend,AZ,930,3.899",
        "20,PILOT #1243,I-8 EXIT 119,Gila Bend,AZ,930,3.859",
        "20,PILOT #1243,I-8 EXIT 119,Gila Bend,AZ,930,3.999",
    )

    assert [(row.name, row.price_per_gallon) for row in price_list.stations] == [
        ("PILOT #1243", Decimal("3.859"))
    ]
    assert price_list.duplicates_merged == 2


def test_rows_outside_the_us_are_skipped():
    price_list = _parse(
        "1,FLYING J,HWY 2,Edmonton,AB,1,1.659",
        "2,ESSO,HWY 401,Toronto,ON,2,1.559",
        "3,LOVES,I-40 EXIT 1,Amarillo,TX,3,2.999",
    )

    assert [row.opis_id for row in price_list.stations] == [3]
    assert price_list.skipped_outside_us == 2


def test_stations_are_ordered_by_id():
    price_list = _parse("9,B,X,Tomah,WI,1,3.2", "7,A,X,Big Cabin,OK,1,3.0")

    assert [row.opis_id for row in price_list.stations] == [7, 9]


def test_missing_columns_are_reported():
    with pytest.raises(PriceListError, match="missing columns: Retail Price"):
        parse_price_list(
            ["OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID", "1,A,B,C,TX,1"]
        )


@pytest.mark.parametrize("price", ["", "abc", "-1", "0"])
def test_invalid_prices_are_reported_with_their_line(price):
    with pytest.raises(PriceListError, match="line 2: invalid price"):
        _parse(f"7,A,X,Big Cabin,OK,307,{price}")
