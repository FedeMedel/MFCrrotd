"""Async client for the unofficial MyFly Club API."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Iterable, List, Optional

import aiohttp

_LOGGER = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36"
)


class MyFlyAPIError(RuntimeError):
    """Raised when the remote API returns an error response."""


class MyFlyClient:
    """Lightweight HTTP client that wraps the MyFly Club endpoints."""

    BASE_URL = "https://play.myfly.club"

    def __init__(
        self,
        *,
        session: Optional[aiohttp.ClientSession] = None,
        request_timeout: int = 30,
    ) -> None:
        self._session = session
        self._own_session = session is None
        self._timeout = aiohttp.ClientTimeout(total=request_timeout)
        self._airports_cache: Optional[List[Dict[str, Any]]] = None
        self._airports_lock = asyncio.Lock()

    async def __aenter__(self) -> "MyFlyClient":
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        await self.close()

    async def close(self) -> None:
        """Dispose the underlying HTTP session."""
        if self._own_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=self._timeout,
                headers={"User-Agent": _USER_AGENT},
            )
        return self._session

    async def _request_json(self, path: str) -> Any:
        session = await self._ensure_session()
        url = f"{self.BASE_URL}{path}"
        async with session.get(url) as response:
            if response.status != 200:
                body = await response.text()
                raise MyFlyAPIError(
                    f"GET {url} failed with status {response.status}: {body[:200]}"
                )
            try:
                return await response.json()
            except aiohttp.ContentTypeError as exc:  # pragma: no cover - defensive
                await response.text()
                raise MyFlyAPIError(
                    f"GET {url} did not return JSON (status {response.status})."
                ) from exc

    async def list_airports(self, *, min_size: int = 3, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Return airport metadata, filtered by minimum size."""
        async with self._airports_lock:
            if self._airports_cache is None or force_refresh:
                _LOGGER.info("Downloading airport catalogue from MyFly Club")
                data = await self._request_json("/airports")
                if isinstance(data, dict):
                    airports: Iterable[Any] = data.get("airports", [])
                else:
                    airports = data
                self._airports_cache = [
                    airport
                    for airport in airports
                    if _safe_int(_lookup(airport, ["size", "Scale", "airportSize"])) >= min_size
                ]
        return list(self._airports_cache or [])

    async def get_airport(self, airport_id: int) -> Dict[str, Any]:
        """Return metadata for a single airport."""
        airport = await self._request_json(f"/airports/{airport_id}")
        return airport

    async def get_route(self, origin_id: int, destination_id: int) -> Dict[str, Any]:
        """Return details for a prospective route between two airports."""
        route = await self._request_json(f"/search-route/{origin_id}/{destination_id}")
        
        # Also fetch research link data
        try:
            research = await self._request_json(f"/research-link/{origin_id}/{destination_id}")
            if isinstance(research, dict):
                # Merge research data into route data
                if not isinstance(route, dict):
                    route = {"tickets": route} if isinstance(route, list) else {}
                route.update(research)
        except Exception as e:
            _LOGGER.warning(f"Failed to fetch research data for {origin_id}->{destination_id}: {e}")
        
        return route


def _lookup(mapping: Any, keys: Iterable[str]) -> Any:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        if key in mapping:
            return mapping[key]
    lower_map = {str(k).lower(): v for k, v in mapping.items()}
    for key in keys:
        value = lower_map.get(str(key).lower())
        if value is not None:
            return value
    return None


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
