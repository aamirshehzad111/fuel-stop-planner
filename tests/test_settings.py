from django.conf import settings


def test_vehicle_has_a_500_mile_range():
    assert settings.FUEL_PLANNER["VEHICLE_RANGE_MILES"] == 500


def test_vehicle_does_10_miles_per_gallon():
    assert settings.FUEL_PLANNER["MILES_PER_GALLON"] == 10


def test_stations_count_when_within_5_miles_of_the_route():
    assert settings.FUEL_PLANNER["MAX_STATION_OFFSET_MILES"] == 5


def test_each_stop_counts_as_10_dollars_when_choosing_stops():
    assert settings.FUEL_PLANNER["STOP_PENALTY_USD"] == 10
