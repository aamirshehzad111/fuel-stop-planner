import pytest

from locations.models import Place, PostalCode

pytestmark = pytest.mark.django_db


def test_admin_lists_and_searches_places(admin_client):
    Place.objects.create(
        name="Big Cabin", state="OK", key="bigcabin", latitude=36.5, longitude=-95.2
    )

    response = admin_client.get("/admin/locations/place/", {"q": "cabin"})

    assert response.status_code == 200
    assert b"Big Cabin" in response.content


def test_admin_lists_postal_codes(admin_client):
    PostalCode.objects.create(code="10001", latitude=40.75, longitude=-74.0)

    response = admin_client.get("/admin/locations/postalcode/")

    assert response.status_code == 200
    assert b"10001" in response.content
