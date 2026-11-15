import pytest

from locations.models import Place
from locations.names import place_key


@pytest.fixture
def towns(db):
    for name, state, lat, lng in [
        ("Big Cabin", "OK", 36.5378, -95.2219),
        ("Tomah", "WI", 43.9786, -90.5040),
    ]:
        Place.objects.create(
            name=name, state=state, key=place_key(name), latitude=lat, longitude=lng
        )
