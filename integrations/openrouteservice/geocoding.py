from typing import Any

from core.exceptions import ProviderResponseError
from core.geo import Coordinates
from integrations.openrouteservice.client import OpenRouteServiceClient
from locations.geocoding import GeocodedPlace

_RESULTS = "10"
# Only point-like places: a whole state or country is never a trip's start or finish
# (otherwise "LA" can match Louisiana as well as Los Angeles).
_POINT_LIKE_LAYERS = "venue,address,street,neighbourhood,borough,localadmin,locality"
_US = "USA"
# A US match this close to the top match's confidence counts as just as good.
_TIE_MARGIN = 0.05


class OpenRouteServiceGeocoder:
    """Geocoder backed by OpenRouteService search (Pelias).

    The search covers the whole world, so a place clearly abroad ("Toronto, ON",
    "Mexico City") comes back as such and can be rejected. The geocoder's ranking is
    kept, except that when its top match is abroad, a US match that fits the text as
    well is preferred: a bare "Paris" is Paris, TX, and "Toronto" is Toronto, MO.
    """

    def __init__(self, client: OpenRouteServiceClient) -> None:
        self._client = client

    def geocode(self, text: str) -> GeocodedPlace | None:
        body = self._client.get_geocode(
            {"text": text, "size": _RESULTS, "layers": _POINT_LIKE_LAYERS}
        )
        features = body.get("features") or []
        if not features:
            return None
        try:
            matches = [_match(feature) for feature in features]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ProviderResponseError(
                "The geocoding service returned an unexpected result."
            ) from error

        top, top_confidence = matches[0]
        if top.country_code == _US:
            return top
        return next(
            (
                place
                for place, confidence in matches
                if place.country_code == _US and confidence >= top_confidence - _TIE_MARGIN
            ),
            top,
        )


def _match(feature: dict[str, Any]) -> tuple[GeocodedPlace, float]:
    properties = feature["properties"]
    lng, lat = feature["geometry"]["coordinates"][:2]
    label = str(properties.get("label") or properties["name"])
    place = GeocodedPlace(
        label=label.removesuffix(", USA"),
        coordinates=Coordinates(float(lat), float(lng)),
        country_code=str(properties.get("country_a", "")),
    )
    return place, float(properties.get("confidence", 0))
