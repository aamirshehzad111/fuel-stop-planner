from collections.abc import Iterable

from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.renderers import BaseRenderer
from rest_framework.request import Request


class ExplicitFormatNegotiation(DefaultContentNegotiation):
    """JSON unless the URL asks for another representation with `?format=`.

    Browsers send `Accept: text/html`; ignoring Accept keeps the API answering
    JSON everywhere, while `?format=html` (the `map_url`) still gets the map.
    """

    def select_renderer(
        self,
        request: Request,
        renderers: Iterable[BaseRenderer],
        format_suffix: str | None = None,
    ) -> tuple[BaseRenderer, str]:
        available = list(renderers)
        if format_suffix or request.query_params.get(self.settings.URL_FORMAT_OVERRIDE):
            return super().select_renderer(request, available, format_suffix)
        return available[0], available[0].media_type
