import numpy as np
import pytest

from planning.geometry import cumulative_miles, densify, simplify

# A path along the 40th parallel and up a meridian: [lat, lng] rows.
L_SHAPE = np.array([[40.0, -100.0], [40.0, -99.0], [41.0, -99.0]])


def test_cumulative_miles_starts_at_zero_and_adds_up_segments():
    miles = cumulative_miles(np.array([[40.0, -100.0], [41.0, -100.0], [42.0, -100.0]]))

    assert miles[0] == 0
    assert miles[1] == pytest.approx(69.1, abs=0.1)
    assert miles[2] == pytest.approx(138.2, abs=0.1)


def test_densify_bounds_the_spacing_and_keeps_the_original_points():
    dense = densify(L_SHAPE, max_step_miles=0.5)

    steps = np.diff(cumulative_miles(dense))
    assert steps.max() <= 0.5 + 1e-9
    for point in L_SHAPE:
        assert (np.abs(dense - point).sum(axis=1) < 1e-12).any()


def test_densify_leaves_short_segments_alone():
    path = np.array([[40.0, -100.0], [40.0, -100.001]])

    np.testing.assert_array_equal(densify(path, max_step_miles=1), path)


def test_simplify_drops_points_on_a_straight_line_but_keeps_corners():
    dense = densify(L_SHAPE, max_step_miles=1)

    simple = simplify(dense, tolerance_degrees=1e-6)

    np.testing.assert_allclose(simple, L_SHAPE, atol=1e-9)


def test_simplify_keeps_a_two_point_path():
    path = np.array([[40.0, -100.0], [41.0, -99.0]])

    np.testing.assert_array_equal(simplify(path, tolerance_degrees=0.1), path)
