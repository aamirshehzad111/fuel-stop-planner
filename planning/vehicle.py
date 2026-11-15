from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Vehicle:
    range_miles: float
    miles_per_gallon: float

    def __post_init__(self) -> None:
        if self.range_miles <= 0 or self.miles_per_gallon <= 0:
            raise ValueError("range and miles per gallon must be positive")

    @property
    def tank_gallons(self) -> float:
        return self.range_miles / self.miles_per_gallon
