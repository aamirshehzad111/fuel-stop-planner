import pytest


@pytest.mark.django_db
def test_openapi_schema_is_served(client):
    response = client.get("/api/schema/")

    assert response.status_code == 200
    assert b"Fuel Stop Planner API" in response.content


@pytest.mark.django_db
def test_interactive_docs_are_served(client):
    response = client.get("/api/docs/")

    assert response.status_code == 200
