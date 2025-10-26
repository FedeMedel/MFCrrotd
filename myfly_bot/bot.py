"""Discord bot entry-point for posting the MyFly Club random route of the day."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from typing import Optional

import discord
from discord.ext import tasks
from dotenv import load_dotenv

from .api import MyFlyClient
from .formatter import format_route_message
from .generator import find_random_route_with_results

_LOGGER = logging.getLogger(__name__)


class RouteOfTheDayBot(discord.Client):
    """Discord client that posts a random route once every 24 hours."""

    def __init__(self, *, channel_id: int, min_airport_size: int = 3, **kwargs) -> None:
        intents = kwargs.pop("intents", discord.Intents.default())
        super().__init__(intents=intents, **kwargs)
        self.channel_id = channel_id
        self.min_airport_size = min_airport_size
        self._channel: Optional[discord.abc.Messageable] = None
        self.api_client = MyFlyClient()

    async def setup_hook(self) -> None:  # type: ignore[override]
        # Only start the scheduled task, don't post immediately on startup
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
            origin, destination, route = await find_random_route_with_results(
                self.api_client, 
                min_airport_size=self.min_airport_size
            )
            message = format_route_message(origin, destination, route)
        except Exception:  # pragma: no cover - network errors
            _LOGGER.exception("Failed to generate daily route message")
            return

        await channel.send(message)

    @route_task.before_loop
    async def before_route_task(self) -> None:  # pragma: no cover - requires discord runtime
        await self.wait_until_ready()

    async def close(self) -> None:  # type: ignore[override]
        await self.api_client.close()
        await super().close()


async def run_once(channel_id: int, token: str, min_airport_size: int = 3) -> str:
    """Generate a route message and send it to Discord, then return the message."""
    async with MyFlyClient() as client:
        origin, destination, route = await find_random_route_with_results(client, min_airport_size=min_airport_size)
        message = format_route_message(origin, destination, route)
        
        # Send to Discord using a simple client
        intents = discord.Intents.default()
        intents.message_content = False
        
        client_discord = discord.Client(intents=intents)
        
        @client_discord.event
        async def on_ready():
            try:
                channel = client_discord.get_channel(channel_id)
                if channel is None:
                    channel = await client_discord.fetch_channel(channel_id)
                await channel.send(message)
                print(f"Message sent to Discord channel {channel_id}")
            except Exception as e:
                print(f"Error sending message to Discord: {e}")
            finally:
                await client_discord.close()
        
        try:
            await client_discord.start(token)
        except Exception as e:
            print(f"Error connecting to Discord: {e}")
            await client_discord.close()
        
        return message


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once",
        action="store_true",
        help="Fetch a route once, send it to Discord, and print the message to stdout for testing.",
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
        "--min-airport-size",
        type=int,
        default=int(os.getenv("MIN_AIRPORT_SIZE", "3")),
        help="Minimum airport size to consider (defaults to MIN_AIRPORT_SIZE env variable).",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Python logging level to use.",
    )
    return parser.parse_args()


def main() -> None:
    # Load environment variables from .env file (if it exists)
    try:
        load_dotenv()
    except Exception as e:
        # If .env file doesn't exist or has issues, continue without it
        pass
    
    args = _parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.once:
        if not args.token:
            raise SystemExit("A Discord token must be provided via --token or DISCORD_TOKEN env var for --once testing.")
        if not args.channel:
            raise SystemExit("A Discord channel ID must be provided via --channel or DISCORD_CHANNEL_ID env var for --once testing.")
        
        message = asyncio.run(run_once(args.channel, args.token, args.min_airport_size))
        print(message)
        return

    if not args.token:
        raise SystemExit("A Discord token must be provided via --token or DISCORD_TOKEN env var.")
    if not args.channel:
        raise SystemExit("A Discord channel ID must be provided via --channel or DISCORD_CHANNEL_ID env var.")

    intents = discord.Intents.default()
    intents.message_content = False

    bot = RouteOfTheDayBot(
        channel_id=args.channel, 
        min_airport_size=args.min_airport_size,
        intents=intents
    )
    bot.run(args.token)


if __name__ == "__main__":
    main()
