from django.conf import settings


def test_vehicle_has_a_500_mile_range():
    assert settings.FUEL_PLANNER["VEHICLE_RANGE_MILES"] == 500


def test_vehicle_does_10_miles_per_gallon():
    assert settings.FUEL_PLANNER["MILES_PER_GALLON"] == 10
