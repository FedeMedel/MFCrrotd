# MyFly Club Route of the Day Bot

This project provides a Discord bot that publishes a randomly generated "route of the day" from [MyFly Club](https://play.myfly.club). The bot looks for airport pairs with available itineraries, formats the results into a text report, and posts them to a configured Discord channel every 24 hours.

## Features

- Queries the MyFly Club API endpoints including route search and research data.
- Configurable minimum airport size filter (default: 3).
- Displays comprehensive route information:
  - Distance between airports
  - Runway restrictions
  - Population data
  - Income per capita (PPP)
  - Country relationships and affinities
  - Flight type (International/Domestic)
  - Direct demand statistics
- Shows country flag emojis next to airport names
- Highlights best deals based on price and popularity
- Detailed itinerary information including:
  - Carrier and flight codes
  - Aircraft types
  - Flight duration
  - Amenities (meals, IFE, wifi, etc.)
  - Pricing
- Supports a `--once` CLI flag for testing

## Requirements

Python 3.12 or later is recommended. Install dependencies with:

```bash
pip install -r requirements.txt
```

## Configuration

The bot automatically loads configuration from a `.env` file if it exists, or from environment variables:

Create a `.env` file in the project root:
```
# Discord Bot Configuration
DISCORD_TOKEN=your_discord_bot_token_here
DISCORD_CHANNEL_ID=your_channel_id_here

# Airport Selection
MIN_AIRPORT_SIZE=3  # Minimum size of airports to include (1-5)

# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

Configuration options:
- `DISCORD_TOKEN`: Discord bot token
- `DISCORD_CHANNEL_ID`: Numeric ID of the channel where updates should be posted
- `MIN_AIRPORT_SIZE`: Minimum airport size to consider (1-5, defaults to 3)
- `LOG_LEVEL`: Python logging level (defaults to INFO)

All settings can be overridden via command-line arguments.

You can also provide the token and channel ID via command-line arguments to override the `.env` file.

## Running locally

With a `.env` file configured:

```bash
# Test the bot (generates route and sends to Discord)
python -m myfly_bot.bot --once

# Start the Discord bot (posts every 24 hours)
python -m myfly_bot.bot
```

With command-line arguments (overrides `.env` file):

```bash
# Test with specific settings
python -m myfly_bot.bot --once --token <TOKEN> --channel <ID> --min-airport-size 4

# Start bot with specific settings
python -m myfly_bot.bot --token <TOKEN> --channel <ID> --min-airport-size 4
```

Once connected, the bot posts every 24 hours starting from when it connects.

## Example Output

```
Random Route of the Day: 26 October 2025

Stockholm Arlanda Airport (ARN) 🇸🇪 - Singapore Changi Airport (SIN) 🇸🇬

Distance (direct): 9,875 km
Runway Restriction: 3,700m (SIN)
Population: 2,584,392 / 5,935,053
Income per Capita, PPP: $85,957 / $94,100
Relationship between Countries: 1 (Good)
Affinities: +1: Trade Relations
Flight Type: International
Direct Demand: 114 / 7 / –

No existing direct links

Tickets

Best Deal
ARN - HEL - SIN — $738 (Economy)
🛫 ARN - HEL 🛫
Finnair - AY 768 | Airbus A320neo | Duration: 55 minutes | $89 (Economy) with 65 quality including IFE, wifi
🛫 HEL - SIN 🛫
Finnair - AY 095 | Airbus A350-900 | Duration: 11 hours 30 minutes | $649 (Economy) with 82 quality including hot meal service, IFE, power outlet

Best Seller
ARN - DOH - SIN — $856 (Economy)
🛫 ARN - DOH 🛫
Qatar Airways - QR 170 | Boeing 787-9 | Duration: 6 hours 35 minutes | $499 (Economy) with 89 quality including hot meal service, IFE, wifi
🛫 DOH - SIN 🛫
Qatar Airways - QR 944 | Airbus A350-1000 | Duration: 7 hours 40 minutes | $357 (Economy) with 89 quality including hot meal service, IFE, power outlet
```

## Notes

- Network access to `https://play.myfly.club` is required at runtime
- The bot fetches data from multiple endpoints for comprehensive route information
- All numeric values are properly formatted with appropriate units and separators
