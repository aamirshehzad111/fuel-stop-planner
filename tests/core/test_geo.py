import pytest

from core.geo import Coordinates, haversine_miles, is_in_united_states

NEW_YORK = Coordinates(40.7128, -74.0060)
LOS_ANGELES = Coordinates(34.0522, -118.2437)


def test_coordinates_reject_latitude_out_of_range():
    with pytest.raises(ValueError, match="latitude"):
        Coordinates(91, 0)


def test_coordinates_reject_longitude_out_of_range():
    with pytest.raises(ValueError, match="longitude"):
        Coordinates(0, -181)


def test_haversine_new_york_to_los_angeles():
    assert haversine_miles(NEW_YORK, LOS_ANGELES) == pytest.approx(2445.6, abs=1)


def test_haversine_same_point_is_zero():
    assert haversine_miles(NEW_YORK, NEW_YORK) == 0


@pytest.mark.parametrize(
    "point",
    [
        NEW_YORK,
        LOS_ANGELES,
        Coordinates(42.3314, -83.0458),  # Detroit
        Coordinates(25.7617, -80.1918),  # Miami, on a coastline the boundary only approximates
        Coordinates(61.2181, -149.9003),  # Anchorage
        Coordinates(21.3069, -157.8583),  # Honolulu
    ],
)
def test_points_inside_the_united_states(point):
    assert is_in_united_states(point)


@pytest.mark.parametrize(
    "point",
    [
        Coordinates(43.6532, -79.3832),  # Toronto (inside the contiguous-US bounding box)
        Coordinates(26.0, -90.0),  # Gulf of Mexico
        Coordinates(49.2827, -123.1207),  # Vancouver
        Coordinates(19.4326, -99.1332),  # Mexico City
        Coordinates(51.5074, -0.1278),  # London
        Coordinates(18.4655, -66.1057),  # San Juan, Puerto Rico (not reachable by road)
    ],
)
def test_points_outside_the_united_states(point):
    assert not is_in_united_states(point)
