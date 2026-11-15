"""Rebuild the place data files in `data/` from their public-domain sources.

The generated files are committed, so this only needs to run when the sources
are updated. `--from-dir` reuses files that were already downloaded.
"""

import json
import tempfile
import zipfile
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from locations.place_data import (
    merge_places,
    read_census_county_subdivisions,
    read_census_places,
    read_census_zctas,
    read_gnis_populated_places,
    us_boundary_from_countries,
    write_places,
    write_postal_codes,
)

_CENSUS = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer"
_DOWNLOAD_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class _Source:
    url: str
    filename: str  # the file inside the zip, or the download itself


CENSUS_PLACES = _Source(f"{_CENSUS}/2025_Gaz_place_national.zip", "2025_Gaz_place_national.txt")
CENSUS_COUNTY_SUBDIVISIONS = _Source(
    f"{_CENSUS}/2025_Gaz_cousubs_national.zip", "2025_Gaz_cousubs_national.txt"
)
CENSUS_ZCTAS = _Source(f"{_CENSUS}/2025_Gaz_zcta_national.zip", "2025_Gaz_zcta_national.txt")
GNIS_POPULATED_PLACES = _Source(
    "https://prd-tnm.s3.amazonaws.com/StagedProducts/GeographicNames/Topical/"
    "PopulatedPlaces_National_Text.zip",
    "PopulatedPlaces_National.txt",
)
NATURAL_EARTH_COUNTRIES = _Source(
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/"
    "ne_50m_admin_0_countries.geojson",
    "ne_50m_admin_0_countries.geojson",
)


class Command(BaseCommand):
    help = (
        "Rebuild data/us_places.csv.gz, data/us_postal_codes.csv.gz and data/us_boundary.geojson."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--from-dir", type=Path, help="Use already-downloaded source files.")
        parser.add_argument("--output-dir", type=Path, default=Path(settings.BASE_DIR) / "data")

    def handle(self, *args: Any, **options: Any) -> None:
        output: Path = options["output_dir"]
        with tempfile.TemporaryDirectory() as download_dir:
            source_dir: Path = options["from_dir"] or Path(download_dir)
            fetch = self._existing if options["from_dir"] else self._download

            def lines(source: _Source) -> list[str]:
                return fetch(source, source_dir).read_text(encoding="utf-8-sig").splitlines()

            places = merge_places(
                [
                    *read_census_places(lines(CENSUS_PLACES)),
                    *read_census_county_subdivisions(lines(CENSUS_COUNTY_SUBDIVISIONS)),
                    *read_gnis_populated_places(lines(GNIS_POPULATED_PLACES)),
                ]
            )
            postal_codes = list(read_census_zctas(lines(CENSUS_ZCTAS)))
            boundary = us_boundary_from_countries(
                json.loads("\n".join(lines(NATURAL_EARTH_COUNTRIES)))
            )

        write_places(places, output / "us_places.csv.gz")
        write_postal_codes(postal_codes, output / "us_postal_codes.csv.gz")
        (output / "us_boundary.geojson").write_text(json.dumps(boundary, separators=(",", ":")))
        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {len(places)} places, {len(postal_codes)} postal codes "
                f"and the US boundary to {output}."
            )
        )

    @staticmethod
    def _existing(source: _Source, directory: Path) -> Path:
        return directory / source.filename

    def _download(self, source: _Source, directory: Path) -> Path:
        self.stdout.write(f"Downloading {source.url}")
        target = directory / Path(source.url).name
        with requests.get(source.url, stream=True, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as response:
            response.raise_for_status()
            with target.open("wb") as file:
                for chunk in response.iter_content(chunk_size=1 << 20):
                    file.write(chunk)
        if target.suffix != ".zip":
            return target
        with zipfile.ZipFile(target) as archive:
            member = next(name for name in archive.namelist() if name.endswith(source.filename))
            (directory / source.filename).write_bytes(archive.read(member))
        return directory / source.filename
