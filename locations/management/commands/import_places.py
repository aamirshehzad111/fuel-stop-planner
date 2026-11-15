from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from locations.importer import import_places
from locations.place_data import read_places, read_postal_codes

DATA_DIR = Path(settings.BASE_DIR) / "data"


class Command(BaseCommand):
    help = "Load US town centers and ZIP code centers into the database (replaces existing rows)."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--places", type=Path, default=DATA_DIR / "us_places.csv.gz")
        parser.add_argument(
            "--postal-codes", type=Path, default=DATA_DIR / "us_postal_codes.csv.gz"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        result = import_places(
            read_places(options["places"]), read_postal_codes(options["postal_codes"])
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded {result.places} places and {result.postal_codes} postal codes."
            )
        )
