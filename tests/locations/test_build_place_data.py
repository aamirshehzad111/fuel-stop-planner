import json
import shutil
from io import StringIO
from pathlib import Path

from django.core.management import call_command

from locations.place_data import read_places, read_postal_codes

FIXTURES = Path(__file__).parent / "fixtures"


def test_build_place_data_from_downloaded_files(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    for fixture, name in [
        ("census_places.txt", "2025_Gaz_place_national.txt"),
        ("census_county_subdivisions.txt", "2025_Gaz_cousubs_national.txt"),
        ("census_zctas.txt", "2025_Gaz_zcta_national.txt"),
        ("gnis_populated_places.txt", "PopulatedPlaces_National.txt"),
    ]:
        shutil.copy(FIXTURES / fixture, sources / name)
    square = [[[-100.0, 40.0], [-99.0, 40.0], [-99.0, 41.0], [-100.0, 40.0]]]
    (sources / "ne_50m_admin_0_countries.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "properties": {"ADM0_A3": "USA"},
                        "geometry": {"type": "Polygon", "coordinates": square},
                    }
                ],
            }
        )
    )
    output = tmp_path / "output"
    output.mkdir()
    out = StringIO()

    call_command(
        "build_place_data", "--from-dir", str(sources), "--output-dir", str(output), stdout=out
    )

    places = {(place.state, place.name) for place in read_places(output / "us_places.csv.gz")}
    assert ("OK", "Oklahoma City") in places
    assert ("PA", "Breezewood") in places
    assert [code.code for code in read_postal_codes(output / "us_postal_codes.csv.gz")] == ["10001"]
    assert json.loads((output / "us_boundary.geojson").read_text())["type"] == "MultiPolygon"
    assert "Wrote 6 places, 1 postal codes and the US boundary" in out.getvalue()
