from core.exceptions import ProviderResponseError
from core.geo import Coordinates
from integrations.openrouteservice.client import OpenRouteServiceClient
from locations.geocoding import GeocodedPlace


class OpenRouteServiceGeocoder:
    """Geocoder backed by OpenRouteService search (Pelias).

    The search isn't limited to the USA on purpose: "Toronto" should find
    Toronto, Canada (and be rejected as outside the USA), not Toronto, Missouri.
    """

    def __init__(self, client: OpenRouteServiceClient) -> None:
        self._client = client

    def geocode(self, text: str) -> GeocodedPlace | None:
        body = self._client.get_geocode({"text": text, "size": "1"})
        features = body.get("features") or []
        if not features:
            return None
        try:
            properties = features[0]["properties"]
            lng, lat = features[0]["geometry"]["coordinates"][:2]
            label = str(properties.get("label") or properties["name"])
            return GeocodedPlace(
                label=label.removesuffix(", USA"),
                coordinates=Coordinates(float(lat), float(lng)),
                country_code=str(properties.get("country_a", "")),
            )
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ProviderResponseError(
                "The geocoding service returned an unexpected result."
            ) from error
