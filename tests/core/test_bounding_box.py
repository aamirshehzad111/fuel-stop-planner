import pytest

from core.geo import BoundingBox, Coordinates


def test_bounding_box_around_points():
    box = BoundingBox.around([Coordinates(40, -100), Coordinates(35, -90), Coordinates(38, -95)])

    assert box == BoundingBox(south=35, west=-100, north=40, east=-90)


def test_bounding_box_around_requires_points():
    with pytest.raises(ValueError, match="at least one point"):
        BoundingBox.around([])


def test_expanded_grows_every_side_by_the_distance():
    box = BoundingBox(south=40, west=-100, north=41, east=-99).expanded(miles=69.172)

    assert box.south == pytest.approx(39)
    assert box.north == pytest.approx(42)
    # A degree of longitude is shorter than a degree of latitude away from the equator.
    assert box.west < -101
    assert box.east > -98


def test_contains():
    box = BoundingBox(south=40, west=-100, north=41, east=-99)

    assert box.contains(Coordinates(40.5, -99.5))
    assert not box.contains(Coordinates(42, -99.5))
