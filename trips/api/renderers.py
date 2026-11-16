from collections.abc import Mapping
from typing import Any

from django.template.loader import render_to_string
from django.utils.html import json_script
from rest_framework.renderers import BaseRenderer
from rest_framework.utils.encoders import JSONEncoder


class TripMapRenderer(BaseRenderer):
    """Renders a trip plan (or an error) as an HTML page with a Leaflet map."""

    media_type = "text/html"
    format = "html"
    charset = "utf-8"

    def render(
        self,
        data: Any,
        accepted_media_type: str | None = None,
        renderer_context: Mapping[str, Any] | None = None,
    ) -> bytes:
        context = renderer_context or {}
        response = context.get("response")
        failed = response is not None and response.status_code >= 400
        template = "trips/problem.html" if failed else "trips/map.html"
        page = render_to_string(
            template,
            {"plan": data, "plan_json": json_script(data, "trip-plan", encoder=JSONEncoder)},
            request=getattr(context.get("request"), "_request", None),
        )
        return page.encode(self.charset)
