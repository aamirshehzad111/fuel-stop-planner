import pytest

from planning.vehicle import Vehicle


def test_tank_holds_range_divided_by_mileage():
    assert Vehicle(range_miles=500, miles_per_gallon=10).tank_gallons == 50


@pytest.mark.parametrize(("range_miles", "mpg"), [(0, 10), (500, 0), (-1, 10)])
def test_vehicle_needs_positive_range_and_mileage(range_miles, mpg):
    with pytest.raises(ValueError, match="positive"):
        Vehicle(range_miles=range_miles, miles_per_gallon=mpg)
