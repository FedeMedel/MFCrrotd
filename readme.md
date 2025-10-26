# MyFly Club Route of the Day Bot

This project provides a Discord bot that publishes a randomly generated "route of the day" from [MyFly Club](https://play.myfly.club). The bot looks for airport pairs with available itineraries, formats the results into a text report, and posts them to a configured Discord channel every 24 hours.

## Features

- Queries the unofficial MyFly Club API with a desktop-like user agent.
- Filters airports so only destinations of size 3 or larger are considered.
- Keeps searching random airport pairs until a route with available tickets is found.
- Highlights the best deal (lowest price) and best seller (highest sales score) among the returned itineraries.
- Formats itineraries with multi-leg routing details, including carrier, aircraft, duration, extras, and prices.
- Supports a `--once` CLI flag for testing locally without connecting to Discord.

## Requirements

Python 3.12 or later is recommended. Install dependencies with:

```bash
pip install -r requirements.txt
```

## Configuration

The bot reads its settings from environment variables (optionally via a `.env` file loaded at startup):

- `DISCORD_TOKEN`: Discord bot token.
- `DISCORD_CHANNEL_ID`: Numeric ID of the channel where updates should be posted.
- `LOG_LEVEL` (optional): Python logging level (defaults to `INFO`).

To get started quickly:

```bash
cp .env.example .env
# edit .env with your token and channel ID
```

The `python-dotenv` dependency is bundled so that running the bot from the project root automatically loads values from `.env`. You can also provide the token and channel ID via command-line arguments.

## Running locally

To generate a single route in the console (useful for testing formatting):

```bash
python -m myfly_bot.bot --once
```

To start the Discord bot:

```bash
python -m myfly_bot.bot --channel <CHANNEL_ID> --token <DISCORD_TOKEN>
```

Once connected, the bot posts immediately upon execution and every 24 hours afterwards.

## Notes

- The MyFly Club endpoints occasionally return incomplete data. The formatter is defensive and skips missing fields where necessary.
- Network access to `https://play.myfly.club` is required at runtime.
