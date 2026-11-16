from typing import Any

_FIRST = {"start": 0, "finish": 1}


def parameter_order(parameter: dict[str, Any]) -> tuple[int, str]:
    """Sort key for the API docs: start and finish first, then the rest by name."""
    return _FIRST.get(parameter["name"], len(_FIRST)), parameter["name"]
