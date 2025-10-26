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

    The airport dictionaries returned will include additional details fetched from
    the /airports/{id} endpoint.
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
            # Fetch route information
            route = await client.get_route(origin_id, destination_id)
            if _has_itineraries(route):
                # Fetch detailed airport information
                origin_details = await client.get_airport(origin_id)
                destination_details = await client.get_airport(destination_id)
                # Update the airport dictionaries with the additional details
                origin.update(origin_details)
                destination.update(destination_details)
                return origin, destination, route
        except Exception:  # pragma: no cover - network exceptions
            _LOGGER.exception("Unable to fetch route or airport details %s -> %s", origin_id, destination_id)
            if retry_delay_seconds:
                await asyncio.sleep(retry_delay_seconds)
            continue

        # Removed duplicate return here since we now handle it in the try block above

        if retry_delay_seconds:
            await asyncio.sleep(retry_delay_seconds)

    raise RuntimeError(
        "Unable to locate a random route with available flights after "
        f"{max_attempts} attempts."
    )


def _has_itineraries(route: Any) -> bool:
    # Handle case where route is a list (direct itineraries)
    if isinstance(route, Sequence) and not isinstance(route, str):
        return len(route) > 0
    
    # Handle case where route is a dictionary
    if isinstance(route, dict):
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
