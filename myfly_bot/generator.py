"""Logic for drawing a random MyFly Club route that has available tickets."""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Dict, Sequence, Tuple

from .api import MyFlyClient

_LOGGER = logging.getLogger(__name__)


async def find_random_route_with_results(
    client: MyFlyClient,
    *,
    min_airport_size: int = 3,
    max_attempts: int = 200,
    retry_delay_seconds: float = 0.0,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Return a random origin/destination pair with at least one itinerary.

    The function keeps trying random airport pairs until it finds route data that
    contains bookable tickets. Only airports with ``size >= min_airport_size``
    are considered.
    """

    airports = await client.list_airports(min_size=min_airport_size)
    if len(airports) < 2:
        raise RuntimeError("Not enough airports to generate a random route.")

    for attempt in range(1, max_attempts + 1):
        origin, destination = random.sample(airports, k=2)
        origin_id = _coerce_int(origin.get("id"))
        destination_id = _coerce_int(destination.get("id"))
        if origin_id <= 0 or destination_id <= 0:
            continue

        _LOGGER.info(
            "Attempt %s/%s: checking route %s -> %s",
            attempt,
            max_attempts,
            _airport_display(origin),
            _airport_display(destination),
        )

        try:
            route = await client.get_route(origin_id, destination_id)
        except Exception:  # pragma: no cover - network exceptions
            _LOGGER.exception("Unable to fetch route %s -> %s", origin_id, destination_id)
            if retry_delay_seconds:
                await asyncio.sleep(retry_delay_seconds)
            continue

        if _has_itineraries(route):
            return origin, destination, route

        if retry_delay_seconds:
            await asyncio.sleep(retry_delay_seconds)

    raise RuntimeError(
        "Unable to locate a random route with available flights after "
        f"{max_attempts} attempts."
    )


def _has_itineraries(route: Dict[str, Any]) -> bool:
    for key in ("tickets", "itineraries", "results", "routes", "options"):
        value = route.get(key)
        if isinstance(value, Sequence) and value:
            return True
    return False


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _airport_display(airport: Dict[str, Any]) -> str:
    code = airport.get("iata") or airport.get("IATA") or airport.get("code")
    name = airport.get("name") or airport.get("Name")
    if code and name:
        return f"{code} ({name})"
    if name:
        return str(name)
    if code:
        return str(code)
    return "<unknown airport>"
