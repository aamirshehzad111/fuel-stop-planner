from django.db import models

from core.geo import Coordinates


class Place(models.Model):
    """A US town center, looked up by a normalized name key within a state."""

    name = models.CharField(max_length=150)
    state = models.CharField(max_length=2)
    key = models.CharField(max_length=150)
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        ordering = ["state", "name"]
        constraints = [
            models.UniqueConstraint(fields=["state", "key"], name="unique_place_key_per_state"),
        ]

    def __str__(self) -> str:
        return f"{self.name}, {self.state}"

    @property
    def coordinates(self) -> Coordinates:
        return Coordinates(self.latitude, self.longitude)


class PostalCode(models.Model):
    """A five-digit ZIP code area, represented by its center."""

    code = models.CharField(max_length=5, primary_key=True)
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code

    @property
    def coordinates(self) -> Coordinates:
        return Coordinates(self.latitude, self.longitude)
