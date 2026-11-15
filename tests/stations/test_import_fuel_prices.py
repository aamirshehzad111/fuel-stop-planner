from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from stations.models import FuelStation

pytestmark = pytest.mark.django_db

PRICES = """\
OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price
7,WOODSHED OF BIG CABIN,"I-44, EXIT 283 & US-69",Big Cabin,OK,307,3.00733333
7,WOODSHED,"I-44, EXIT 283 & US-69",Big Cabin,OK,307,3.10
9,KWIK TRIP #796,"I-94, EXIT 143",Tomah,WI,420,3.28733333
11,NOWHERE STOP,I-10,Atlantis,TX,1,2.99
12,FLYING J,HWY 2,Edmonton,AB,1,1.659
"""


def test_command_imports_and_summarizes(towns, tmp_path):
    path = tmp_path / "prices.csv"
    path.write_text(PRICES)
    out = StringIO()

    call_command("import_fuel_prices", str(path), stdout=out)

    assert FuelStation.objects.count() == 2
    assert out.getvalue().splitlines() == [
        "Imported 2 stations.",
        "Merged 1 duplicate rows (kept the lowest price per station).",
        "Skipped 1 rows outside the US.",
        "Could not place 1 stations in 1 towns: Atlantis, TX (1).",
    ]


def test_command_reports_a_malformed_file(towns, tmp_path):
    path = tmp_path / "prices.csv"
    path.write_text("OPIS Truckstop ID,City\n1,Tomah\n")

    with pytest.raises(CommandError, match="missing columns"):
        call_command("import_fuel_prices", str(path), stdout=StringIO())
