import pytest

from locations.names import census_place_name, parse_state, place_key


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("St. Louis", "Saint Louis"),
        ("Ft Worth", "Fort Worth"),
        ("Mt. Vernon", "Mount Vernon"),
        ("Mc Calla", "McCalla"),
        ("De Forest", "DeForest"),
        ("O'Fallon", "OFallon"),
        ("Winston-Salem", "Winston Salem"),
        ("S Coffeyville", "South Coffeyville"),
        ("El Centro                ", "el centro"),
        ("Hawk Point & Sons", "hawk point and sons"),
    ],
)
def test_place_key_treats_spelling_variants_as_equal(a, b):
    assert place_key(a) == place_key(b)


def test_place_key_keeps_different_towns_apart():
    assert place_key("Kansas City") != place_key("Kansas")


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("IL", "IL"),
        ("il", "IL"),
        ("Illinois", "IL"),
        ("new york", "NY"),
        ("D.C.", "DC"),
        ("District of Columbia", "DC"),
        (" TX ", "TX"),
    ],
)
def test_parse_state_recognises_codes_and_names(text, code):
    assert parse_state(text) == code


@pytest.mark.parametrize("text", ["ON", "Ontario", "PR", "XX", ""])
def test_parse_state_rejects_non_states(text):
    assert parse_state(text) is None


@pytest.mark.parametrize(
    ("census_name", "town"),
    [
        ("Oklahoma City city", "Oklahoma City"),
        ("Big Cabin town", "Big Cabin"),
        ("Elk Grove Village village", "Elk Grove Village"),
        ("Ehrenberg CDP", "Ehrenberg"),
        ("Juneau city and borough", "Juneau"),
        ("Indianapolis city (balance)", "Indianapolis"),
        ("Nashville-Davidson metropolitan government (balance)", "Nashville-Davidson"),
        ("Autaugaville CCD", "Autaugaville"),
        ("Hampden town", "Hampden"),
    ],
)
def test_census_place_name_drops_the_legal_description(census_name, town):
    assert census_place_name(census_name) == town


def test_place_key_ignores_accents():
    assert place_key("Cañon City") == place_key("Canon City")
