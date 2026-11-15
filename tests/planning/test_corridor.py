import numpy as np
import pytest

from planning.corridor import RouteCorridor

# Due north along the -100 meridian from 40N to 42N (about 138 miles).
PATH = np.array([[40.0, -100.0], [42.0, -100.0]])
MILES_PER_DEGREE_LNG_AT_40_6N = 52.5


def test_a_point_beside_the_route_is_placed_at_its_milepost():
    corridor = RouteCorridor(PATH, route_miles=138.3)
    one_mile_east = -100 + 1 / MILES_PER_DEGREE_LNG_AT_40_6N

    located = corridor.locate(np.array([[40.6, one_mile_east]]), max_offset_miles=5)

    assert located.indices.tolist() == [0]
    assert located.route_miles[0] == pytest.approx(0.3 * 138.3, abs=0.3)
    assert located.offsets_miles[0] == pytest.approx(1, abs=0.05)


def test_points_too_far_from_the_route_are_left_out():
    corridor = RouteCorridor(PATH, route_miles=138.3)

    located = corridor.locate(np.array([[41.0, -99.0], [41.0, -100.0]]), max_offset_miles=5)

    assert located.indices.tolist() == [1]


def test_mileposts_are_scaled_to_the_reported_route_length():
    # Road distance from the routing service can differ slightly from the drawn path.
    corridor = RouteCorridor(PATH, route_miles=150)

    located = corridor.locate(np.array([[42.0, -100.0]]), max_offset_miles=1)

    assert located.route_miles[0] == pytest.approx(150)


def test_locating_nothing_returns_nothing():
    located = RouteCorridor(PATH, route_miles=138.3).locate(np.empty((0, 2)), max_offset_miles=5)

    assert located.indices.size == 0
