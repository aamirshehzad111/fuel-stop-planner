import pytest
from django.core.management import call_command

from trips.container import get_trip_planner
from trips.service import TripPlanner


def test_container_builds_the_planner_from_settings():
    get_trip_planner.cache_clear()

    planner = get_trip_planner()

    assert isinstance(planner, TripPlanner)
    assert planner is get_trip_planner()


@pytest.mark.django_db
def test_openapi_schema_is_valid_and_warning_free(tmp_path):
    call_command(
        "spectacular", "--validate", "--fail-on-warn", "--file", str(tmp_path / "schema.yaml")
    )

    schema = (tmp_path / "schema.yaml").read_text()
    assert "/api/v1/trips/plan/" in schema
    assert "application/problem+json" in schema
