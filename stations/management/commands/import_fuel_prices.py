from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from locations.directory import PlaceDirectory
from stations.importer import import_stations
from stations.price_list import PriceListError, read_price_list

_LISTED_TOWNS = 10


class Command(BaseCommand):
    help = "Load the fuel price list, placing each station at its town (replaces existing rows)."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "path",
            nargs="?",
            type=Path,
            default=Path(settings.BASE_DIR) / "data" / "fuel_prices.csv",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            price_list = read_price_list(options["path"])
        except PriceListError as error:
            raise CommandError(f"{options['path']}: {error}") from error

        report = import_stations(price_list, PlaceDirectory())

        self.stdout.write(self.style.SUCCESS(f"Imported {report.imported} stations."))
        self.stdout.write(
            f"Merged {price_list.duplicates_merged} duplicate rows "
            "(kept the lowest price per station)."
        )
        self.stdout.write(f"Skipped {price_list.skipped_outside_us} rows outside the US.")
        if report.unplaced:
            towns = ", ".join(
                f"{city}, {state} ({count})"
                for (city, state), count in report.unplaced.most_common(_LISTED_TOWNS)
            )
            more = len(report.unplaced) - _LISTED_TOWNS
            self.stdout.write(
                self.style.WARNING(
                    f"Could not place {report.unplaced.total()} stations in "
                    f"{len(report.unplaced)} towns: {towns}"
                    + (f" and {more} more." if more > 0 else ".")
                )
            )
