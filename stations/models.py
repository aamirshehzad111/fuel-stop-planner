from django.db import models

from core.geo import Coordinates


class FuelStation(models.Model):
    """A truck stop from the price list, placed at its town's center."""

    opis_id = models.PositiveIntegerField("OPIS truck stop ID", primary_key=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    rack_id = models.PositiveIntegerField("rack ID")
    price_per_gallon = models.DecimalField(max_digits=12, decimal_places=8)
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        ordering = ["opis_id"]
        indexes = [models.Index(fields=["latitude", "longitude"], name="station_position_idx")]

    def __str__(self) -> str:
        return f"{self.name} ({self.city}, {self.state})"

    @property
    def coordinates(self) -> Coordinates:
        return Coordinates(self.latitude, self.longitude)
