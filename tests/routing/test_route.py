import numpy as np
import pytest

from routing.route import Route


def test_route_keeps_its_path_as_latitude_longitude_rows():
    route = Route(
        distance_miles=1.0, duration_hours=0.1, path=np.array([[41.0, -87.0], [41.1, -87.1]])
    )

    assert route.path.shape == (2, 2)
    assert route.start == (41.0, -87.0)
    assert route.end == (41.1, -87.1)


@pytest.mark.parametrize("path", [np.zeros((1, 2)), np.zeros((3,)), np.zeros((3, 3))])
def test_route_rejects_malformed_paths(path):
    with pytest.raises(ValueError, match="path"):
        Route(distance_miles=1.0, duration_hours=0.1, path=path)
