"""Discord bot entry-point for posting the MyFly Club random route of the day."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from typing import Optional
import contextlib

import discord
from discord.ext import tasks

from .api import MyFlyClient
from .formatter import format_route_message
from .generator import find_random_route_with_results

_LOGGER = logging.getLogger(__name__)


class RouteOfTheDayBot(discord.Client):
    """Discord client that posts a random route once every 24 hours."""

    def __init__(self, *, channel_id: int, **kwargs) -> None:
        intents = kwargs.pop("intents", discord.Intents.default())
        super().__init__(intents=intents, **kwargs)
        self.channel_id = channel_id
        self._channel: Optional[discord.abc.Messageable] = None
        self.api_client = MyFlyClient()
        self._initial_post_task: Optional[asyncio.Task[None]] = None

    async def setup_hook(self) -> None:  # type: ignore[override]
        self._initial_post_task = self.loop.create_task(self._initial_post())
        self.route_task.start()

    async def on_ready(self) -> None:  # pragma: no cover - event handler
        _LOGGER.info("Logged in as %s (ID: %s)", self.user, getattr(self.user, "id", "?"))

    async def get_target_channel(self) -> discord.abc.Messageable:
        if self._channel is None:
            channel = self.get_channel(self.channel_id)
            if channel is None:
                channel = await self.fetch_channel(self.channel_id)
            self._channel = channel  # type: ignore[assignment]
        return self._channel

    async def _initial_post(self) -> None:
        try:
            await self.wait_until_ready()
            await self.send_daily_route()
        finally:
            self._initial_post_task = None

    @tasks.loop(hours=24)
    async def route_task(self) -> None:  # pragma: no cover - requires discord runtime
        await self.wait_until_ready()
        await self.send_daily_route()

    async def send_daily_route(self) -> None:
        try:
            channel = await self.get_target_channel()
        except Exception:  # pragma: no cover - network/discord errors
            _LOGGER.exception("Unable to resolve target channel %s", self.channel_id)
            return

        try:
            origin, destination, route = await find_random_route_with_results(self.api_client)
            message = format_route_message(origin, destination, route)
        except Exception:  # pragma: no cover - network errors
            _LOGGER.exception("Failed to generate daily route message")
            return

        await channel.send(message)

    @route_task.before_loop
    async def before_route_task(self) -> None:  # pragma: no cover - requires discord runtime
        await self.wait_until_ready()

    async def close(self) -> None:  # type: ignore[override]
        if self._initial_post_task is not None:
            self._initial_post_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._initial_post_task
            self._initial_post_task = None
        await self.api_client.close()
        await super().close()


async def run_once(channel_id: int) -> str:
    async with MyFlyClient() as client:
        origin, destination, route = await find_random_route_with_results(client)
        return format_route_message(origin, destination, route)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once",
        action="store_true",
        help="Fetch a route once and print the message to stdout instead of starting the Discord bot.",
    )
    parser.add_argument(
        "--channel",
        type=int,
        default=int(os.getenv("DISCORD_CHANNEL_ID", "0")),
        help="Discord channel ID to post into (defaults to DISCORD_CHANNEL_ID env variable).",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=os.getenv("DISCORD_TOKEN"),
        help="Discord bot token (defaults to DISCORD_TOKEN env variable).",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Python logging level to use.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.once:
        message = asyncio.run(run_once(args.channel))
        print(message)
        return

    if not args.token:
        raise SystemExit("A Discord token must be provided via --token or DISCORD_TOKEN env var.")
    if not args.channel:
        raise SystemExit("A Discord channel ID must be provided via --channel or DISCORD_CHANNEL_ID env var.")

    intents = discord.Intents.default()
    intents.message_content = False

    bot = RouteOfTheDayBot(channel_id=args.channel, intents=intents)
    bot.run(args.token)


if __name__ == "__main__":
    main()
