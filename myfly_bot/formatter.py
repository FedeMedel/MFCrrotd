"""Utilities for turning MyFly Club API responses into Discord messages."""
from __future__ import annotations

import datetime as _dt
import math
import statistics
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

_DATE_FORMAT = "%d %B %Y"


def format_route_message(
    origin: Dict[str, Any],
    destination: Dict[str, Any],
    route: Any,
    *,
    reference_date: Optional[_dt.date] = None,
) -> str:
    """Create a human-friendly message describing the route and its tickets."""

    date = reference_date or _dt.datetime.utcnow().date()
    header_lines = [
        f"Random Route of the Day:  {date.strftime(_DATE_FORMAT)}",
        "",
        _format_airport_pair(origin, destination),
        "",
    ]

    summary_block = _build_summary_block(origin, destination, route)
    if summary_block:
        header_lines.extend(summary_block)
        header_lines.append("")

    link_block = _format_direct_links(route)
    if link_block:
        header_lines.extend(link_block)
        header_lines.append("")

    tickets_block = _format_tickets(route)
    if tickets_block:
        header_lines.extend(tickets_block)
    else:
        header_lines.append("No available itineraries were returned by the API.")

    return "\n".join(header_lines).strip()


def _format_airport_pair(origin: Dict[str, Any], destination: Dict[str, Any]) -> str:
    origin_name = _airport_title(origin)
    dest_name = _airport_title(destination)
    return f"{origin_name} - {dest_name}"


def _get_country_flag(country_code: str) -> str:
    """Convert a two-letter country code to a flag emoji."""
    if len(country_code) != 2:
        return ""
    
    # Convert country code to regional indicator symbols
    # Each letter is converted to a regional indicator symbol by adding 0x1F1E6-1
    try:
        char1 = chr(ord(country_code[0].upper()) - ord('A') + 0x1F1E6)
        char2 = chr(ord(country_code[1].upper()) - ord('A') + 0x1F1E6)
        return char1 + char2
    except (ValueError, IndexError):
        return ""

def _airport_title(airport: Dict[str, Any]) -> str:
    name = _first_non_empty(
        airport.get("name"),
        airport.get("Name"),
    )
    code = _first_non_empty(
        airport.get("iata"),
        airport.get("IATA"),
        airport.get("code"),
    )
    country = _country_code(airport)
    flag = _get_country_flag(country) if country else ""
    
    pieces = []
    if name:
        pieces.append(str(name))
    if code:
        pieces.append(f"({code})")
    if country:
        if flag:
            pieces.append(f"{flag}")  # Add flag emoji
        else:
            pieces.append(f"({country})")  # Fallback to country code if emoji fails
    return " ".join(pieces) or "Unknown Airport"


def _build_summary_block(
    origin: Dict[str, Any],
    destination: Dict[str, Any],
    route: Any,
) -> List[str]:
    lines: List[str] = []

    # Distance
    distance_km = _extract_distance_km(route)
    if distance_km:
        lines.append(f"Distance (direct): {distance_km:,.0f} km")

    # Runway
    runway = _extract_runway_limit(destination)
    if runway:
        lines.append(f"Runway Restriction: {runway} ({_airport_code(destination)})")

    # Population
    pop_origin, pop_dest = _extract_population_pair(origin, destination)
    if pop_origin or pop_dest:
        lines.append(
            "Population: "
            f"{pop_origin if pop_origin else 'Unknown'} / "
            f"{pop_dest if pop_dest else 'Unknown'}"
        )

    # Income per Capita
    income_origin = _extract_income_ppp(origin)
    income_dest = _extract_income_ppp(destination)
    if income_origin is not None or income_dest is not None:
        lines.append(
            "Income per Capita, PPP: "
            f"${income_origin:,.0f if income_origin else '–'} / "
            f"${income_dest:,.0f if income_dest else '–'}"
        )

    # Relationship and Affinities
    relation = _safe_lookup(route, ["relationship", "relationshipBetweenCountries"])
    if relation is not None:
        relationship_text = {
            -2: "Very Poor",
            -1: "Poor",
            0: "Neutral",
            1: "Good",
            2: "Very Good"
        }.get(relation, str(relation))
        lines.append(f"Relationship between Countries: {relation} ({relationship_text})")

    affinity = _safe_lookup(route, ["affinities", "affinity"])
    if affinity is not None:
        lines.append(f"Affinities: {affinity}")

    # Flight Type
    if origin.get("countryCode") != destination.get("countryCode"):
        lines.append("Flight Type: International")
    else:
        lines.append("Flight Type: Domestic")

    # Direct Demand
    demand = _extract_direct_demand(route)
    if demand:
        lines.append(f"Direct Demand: {demand}")

    lines.append("")  # Add blank line before charms

    return lines


def _format_direct_links(route: Any) -> List[str]:
    # If route is a list, we can't extract direct links
    if isinstance(route, list):
        return ["No existing direct links"]
    
    links = _safe_lookup(route, ["existingLinks", "links", "directLinks"])
    if isinstance(links, Sequence) and links:
        lines = ["Existing direct links:"]
        for link in links:
            airline = _first_non_empty(
                _safe_lookup(link, ["airline", "carrier", "name"]),
                _safe_lookup(_safe_lookup(link, ["airline", "carrier"]), ["name", "code"]),
            )
            frequency = _safe_lookup(link, ["frequency", "flightsPerWeek"])
            lines.append(f"- {airline or 'Unknown carrier'} ({frequency or 'n/a'} per week)")
        return lines
    return ["No existing direct links"]


def _format_tickets(route: Any) -> List[str]:
    itineraries = _collect_itineraries(route)
    if not itineraries:
        return []

    prices = [_extract_price(itinerary) for itinerary in itineraries]
    price_values = [p[0] for p in prices if p[0] is not None]
    if price_values:
        min_price = min(price_values)
    else:
        min_price = math.inf

    sales_values = [
        _extract_sales_score(itinerary)
        for itinerary in itineraries
    ]
    best_seller_score = max((v for v in sales_values if v is not None), default=None)


    # DEBUG: Print extracted prices and sales scores

    # Sort itineraries by best deal and best seller
    def get_itinerary_type(itin):
        price, _ = _extract_price(itin)
        sales_score = _extract_sales_score(itin)
        return (price or float('inf'), -(sales_score or 0))
    
    # Sort itineraries by price (ascending) and sales score (descending)
    sorted_itineraries = sorted(enumerate(itineraries), key=lambda x: get_itinerary_type(x[1]))
    
    # Take the best 2 itineraries
    best_indices = [idx for idx, _ in sorted_itineraries[:2]]
    if not best_indices:
        best_indices = [0] if itineraries else []

    lines = ["Tickets", ""]
    if not best_indices and itineraries:
        # fallback: show first itinerary if no remarks found
        best_indices = [0]

    for idx_pos, idx in enumerate(best_indices):
        itinerary = itineraries[idx]
        # Determine if this is best deal or best seller based on its position
        if idx_pos == 0:
            lines.append("Best Deal")
        else:
            lines.append("Best Seller")

        # Calculate total price for MyFly API format
        total_price = 0
        if "route" in itinerary and isinstance(itinerary["route"], list):
            for segment in itinerary["route"]:
                segment_price = segment.get("price", 0)
                if isinstance(segment_price, (int, float)):
                    total_price += segment_price
        if total_price > 0:
            price_amount = total_price
            price_currency = "$"
        else:
            price_amount, price_currency = prices[idx]

        # Itinerary header line
        header = _format_itinerary_header(itinerary)
        if price_amount is not None and price_amount > 0:
            header += f" — ${price_amount:,.0f} (Economy)"
        lines.append(header)

        segments = _collect_segments(itinerary)
        for segment in segments:
            lines.extend(_format_segment(segment))

        if idx_pos != len(best_indices) - 1:
            lines.append("")

    return lines


def _collect_itineraries(route: Any) -> List[Dict[str, Any]]:
    # Handle case where route is a list (direct itineraries)
    if isinstance(route, list):
        # Check if it's a list of objects with 'route' property (MyFly API format)
        if route and isinstance(route[0], dict) and "route" in route[0]:
            return route
        return route
    
    # Handle case where route is a dictionary
    if isinstance(route, dict):
        for key in ("tickets", "itineraries", "results", "routes", "options"):
            value = route.get(key)
            if isinstance(value, list) and value:
                return value
    return []


def _format_itinerary_header(itinerary: Dict[str, Any]) -> str:
    title = _first_non_empty(
        itinerary.get("name"),
        itinerary.get("summary"),
        itinerary.get("title"),
    )
    if not title:
        # For MyFly API format, create title from route segments
        if "route" in itinerary and isinstance(itinerary["route"], list):
            segments = itinerary["route"]
            if segments:
                # Get airport codes from first and last segments
                first_segment = segments[0]
                last_segment = segments[-1]
                origin_code = _safe_lookup(first_segment, ["fromAirportIata", "fromAirportCode"])
                dest_code = _safe_lookup(last_segment, ["toAirportIata", "toAirportCode"])
                if origin_code and dest_code:
                    # Include intermediate stops without duplicates
                    codes = []
                    # Add origin
                    codes.append(origin_code)
                    # Add intermediate stops
                    for segment in segments:
                        from_code = _safe_lookup(segment, ["fromAirportIata", "fromAirportCode"])
                        to_code = _safe_lookup(segment, ["toAirportIata", "toAirportCode"])
                        if from_code and from_code not in codes:
                            codes.append(from_code)
                        if to_code and to_code not in codes:
                            codes.append(to_code)
                    title = " - ".join(codes)
    
    if not title:
        stops = _collect_stop_codes(itinerary)
        if stops:
            title = " - ".join(stops)
    if not title:
        origin = _safe_lookup(itinerary, ["origin", "from"])
        destination = _safe_lookup(itinerary, ["destination", "to"])
        origin_code = _airport_code(origin)
        dest_code = _airport_code(destination)
        if origin_code and dest_code:
            title = f"{origin_code} - {dest_code}"
    return title or "Itinerary"


def _collect_stop_codes(data: Dict[str, Any]) -> List[str]:
    stops: List[str] = []
    for key in ("stops", "path", "codes"):
        value = data.get(key)
        if isinstance(value, str):
            return [part.strip() for part in value.split("-") if part.strip()]
        if isinstance(value, Sequence):
            for item in value:
                code = _airport_code(item)
                if code:
                    stops.append(code)
    if not stops:
        segments = _collect_segments(data)
        for segment in segments:
            origin_code = _airport_code(_safe_lookup(segment, ["origin", "from"]))
            if origin_code:
                stops.append(origin_code)
        dest_code = _airport_code(_safe_lookup(segments[-1] if segments else {}, ["destination", "to"]))
        if dest_code:
            stops.append(dest_code)
    return stops


def _collect_segments(itinerary: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Handle MyFly API format where segments are in 'route' property
    if "route" in itinerary and isinstance(itinerary["route"], list):
        return itinerary["route"]
    
    # Handle other formats
    for key in ("segments", "legs", "hops", "flights"):
        value = itinerary.get(key)
        if isinstance(value, list) and value:
            return value
    return []


def _format_segment(segment: Dict[str, Any]) -> List[str]:
    # Handle MyFly API format
    if "fromAirportIata" in segment and "toAirportIata" in segment:
        origin_code = segment.get("fromAirportIata", "")
        destination_code = segment.get("toAirportIata", "")
        mode = _segment_mode(segment)
        
        travel_line = _format_segment_travel_line(mode, origin_code, destination_code)
        detail_line = _format_segment_detail_line(segment)
        
        lines = [travel_line]
        if detail_line:
            lines.append(detail_line)
        return lines
    
    # Handle other formats
    origin = _safe_lookup(segment, ["origin", "from", "departure", "start"])
    destination = _safe_lookup(segment, ["destination", "to", "arrival", "end"])
    origin_code = _airport_code(origin)
    destination_code = _airport_code(destination)
    mode = _segment_mode(segment)

    travel_line = _format_segment_travel_line(mode, origin_code, destination_code)
    detail_line = _format_segment_detail_line(segment)

    lines = [travel_line]
    if detail_line:
        lines.append(detail_line)
    return lines


def _format_segment_travel_line(mode: str, origin_code: str, destination_code: str) -> str:
    if mode == "ground":
        emoji = "🚌"
        suffix = "🚌"
    elif mode == "train":
        emoji = "🚆"
        suffix = "🚆"
    else:
        emoji = "🛫"
        suffix = "🛬"
    origin_code = origin_code or "???"
    destination_code = destination_code or "???"
    return f"{emoji} {origin_code} - {destination_code} {suffix}"


def _format_segment_detail_line(segment: Dict[str, Any]) -> str:
    # Handle MyFly API format
    if "airlineName" in segment:
        carrier = segment.get("airlineName", "")
        flight_code = segment.get("flightCode", "")
        aircraft = segment.get("airplaneModelName", "")
        duration_minutes = segment.get("duration", 0)
        price_amount = segment.get("price", 0)
        quality = segment.get("computedQuality", 0)
        features = segment.get("features", [])
        
        # For ground transportation, return a simpler format
        if segment.get("transportType") == "GENERIC_TRANSIT":
            return "Local Transit | Duration: " + _format_duration(duration_minutes)
        
        details: List[str] = []
        if carrier and flight_code:
            details.append(f"{carrier} - {flight_code}")
        elif carrier:
            details.append(str(carrier))
        elif flight_code:
            details.append(str(flight_code))

        if aircraft:
            details.append(f"| {aircraft}")
        if duration_minutes:
            duration_str = _format_duration(duration_minutes)
            if duration_str:
                details.append(f"| Duration: {duration_str}")
        if price_amount > 0:
            details.append(f"| ${price_amount:,.0f} (Economy)")
        if quality > 0:
            details.append(f"with {quality} quality")
        
        # Improved amenities formatting
        if features:
            amenities = []
            for feature in features:
                if feature == "IFE":
                    amenities.append("IFE")
                elif feature == "WIFI":
                    amenities.append("power outlet")
                    amenities.append("wifi")
                elif "MEAL" in feature:
                    if "HOT" in feature:
                        amenities.append("hot meal service")
                    else:
                        amenities.append("beverage service")
            if amenities:
                details.append(f"including {', '.join(amenities)}")
        
        if not details:
            return ""
        return " ".join(details)
    
    # Handle other formats
    carrier = _first_non_empty(
        _safe_lookup(segment, ["carrier", "airline", "operator"]),
        _safe_lookup(_safe_lookup(segment, ["carrier", "airline", "operator"]), ["name", "code"]),
    )
    flight_number = _first_non_empty(
        _safe_lookup(segment, ["flightNumber", "number", "designator"]),
        _compose_flight_designator(
            _safe_lookup(segment, ["carrier", "airline", "operator"]),
            _safe_lookup(segment, ["flight", "flightCode"]),
        ),
    )
    aircraft = _first_non_empty(
        _safe_lookup(segment, ["aircraft", "equipment"]),
        _safe_lookup(_safe_lookup(segment, ["aircraft", "equipment"]), ["name", "code"]),
    )
    duration = _format_duration(_safe_lookup(segment, ["duration", "travelTime", "durationMinutes"]))
    price_amount, price_currency = _extract_price(segment)
    quality = _safe_lookup(segment, ["quality", "productQuality"])
    extras = _extract_extras(segment)

    details: List[str] = []
    if carrier:
        details.append(str(carrier))
    if flight_number:
        details.append(str(flight_number))
    if aircraft:
        details.append(f"| {aircraft}")
    if duration:
        details.append(f"| Duration: {duration}")
    if price_amount is not None:
        details.append(f"| {price_amount:,.0f} {price_currency or ''}".rstrip())
    if quality is not None:
        details.append(f"with {quality} quality")
    if extras:
        details.append(f"including {', '.join(extras)}")

    if not details:
        return ""

    return " ".join(details)


def _extract_extras(segment: Dict[str, Any]) -> List[str]:
    extras: List[str] = []
    if _safe_lookup(segment, ["ife", "inFlightEntertainment", "hasIFE"]):
        extras.append("IFE")
    if _safe_lookup(segment, ["wifi", "hasWifi"]):
        extras.append("Wi-Fi")
    if _safe_lookup(segment, ["meals", "hasMeal"]):
        extras.append("meals")
    return extras


def _format_duration(value: Any) -> str:
    minutes = None
    if isinstance(value, dict):
        minutes = value.get("minutes") or value.get("totalMinutes")
        if minutes is None and value.get("hours") is not None:
            minutes = 60 * int(value.get("hours")) + int(value.get("minutes", 0))
    elif isinstance(value, (int, float)):
        minutes = int(value)
    elif isinstance(value, str):
        return value

    if not minutes:
        return ""

    hours, mins = divmod(int(minutes), 60)
    if hours and mins:
        return f"{hours} hours {mins} minutes"
    if hours:
        return f"{hours} hours"
    return f"{mins} minutes"




def _extract_price(data: Dict[str, Any]) -> Tuple[Optional[float], Optional[str]]:
    candidates = [
        _safe_lookup(data, ["price", "totalPrice", "fare", "cost"]),
        _safe_lookup(data, ["economyPrice", "economyFare"]),
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        if isinstance(candidate, dict):
            amount = candidate.get("amount") or candidate.get("value") or candidate.get("total")
            currency = candidate.get("currency") or candidate.get("currencyCode")
            if amount is not None:
                try:
                    return float(amount), currency
                except (TypeError, ValueError):
                    continue
        else:
            try:
                return float(candidate), None
            except (TypeError, ValueError):
                continue
    return None, None


def _extract_sales_score(itinerary: Dict[str, Any]) -> Optional[float]:
    candidates = [
        _safe_lookup(itinerary, ["sales", "bookings", "popularity", "demand"]),
        _safe_lookup(itinerary, ["score", "ranking"]),
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        if isinstance(candidate, dict):
            values = [v for v in candidate.values() if isinstance(v, (int, float))]
            if values:
                return statistics.mean(values)
        elif isinstance(candidate, (int, float)):
            return float(candidate)
    return None




def _extract_distance_km(route: Any) -> Optional[float]:
    # If route is a list, we can't extract distance information
    if isinstance(route, list):
        return None
    
    distance = _safe_lookup(route, ["distance", "distances", "distanceKm"])
    if isinstance(distance, (int, float)):
        return float(distance)
    if isinstance(distance, dict):
        direct = _safe_lookup(distance, ["direct", "directKm", "directDistanceKm", "km"])
        if isinstance(direct, (int, float)):
            return float(direct)
    return None


def _extract_runway_limit(airport: Dict[str, Any]) -> Optional[str]:
    # First try to get runway information from the detailed airport data
    runway_details = _safe_lookup(
        airport,
        [
            "runways",
            "runway",
            "Runways",
        ],
    )
    if isinstance(runway_details, list) and runway_details:
        # Get the longest runway length
        lengths = []
        for runway in runway_details:
            if isinstance(runway, dict):
                length = runway.get("length") or runway.get("lengthMeters") or runway.get("meters")
                if length:
                    try:
                        lengths.append(int(length))
                    except (TypeError, ValueError):
                        continue
        if lengths:
            return f"{max(lengths):,}m"
            
    # Fallback to legacy fields
    runway = _safe_lookup(
        airport,
        [
            "runwayLimit",
            "runwayRestriction",
            "maxRunwayLength",
            "maxRunway",
            "longestRunway",
        ],
    )
    if runway is None:
        return None
    if isinstance(runway, dict):
        length = runway.get("length") or runway.get("meters") or runway.get("m")
        if length is None:
            return None
        return f"{int(length):,}m"
    if isinstance(runway, (int, float)):
        return f"{int(runway):,}m"
    if isinstance(runway, str):
        return runway
    return None


def _extract_income_ppp(airport: Dict[str, Any]) -> Optional[float]:
    """Extract income per capita (PPP) from airport data."""
    catchment = _safe_lookup(airport, ["catchment", "catchmentArea"])
    if isinstance(catchment, dict):
        income = catchment.get("incomePerCapitaPPP") or catchment.get("incomePPP")
        if income is not None:
            try:
                return float(income)
            except (ValueError, TypeError):
                pass
    return None


def _extract_population_pair(
    origin: Dict[str, Any], destination: Dict[str, Any]
) -> Tuple[Optional[str], Optional[str]]:
    return _format_population(origin), _format_population(destination)


def _format_population(airport: Dict[str, Any]) -> Optional[str]:
    # First try to get population from detailed airport data
    catchment = _safe_lookup(
        airport,
        [
            "catchment",
            "catchmentArea",
            "populationCatchment",
        ],
    )
    if isinstance(catchment, dict):
        population = catchment.get("population") or catchment.get("total")
        if isinstance(population, (int, float)):
            return f"{int(population):,}"

    # Fallback to direct population fields
    population = _safe_lookup(
        airport,
        [
            "population",
            "catchmentPopulation",
            "metroPopulation",
            "populationCatchment",
        ],
    )
    if isinstance(population, (int, float)):
        return f"{int(population):,}"
    return None


def _extract_charms_pair(
    origin: Dict[str, Any], destination: Dict[str, Any]
) -> Optional[Tuple[str, str]]:
    origin_charms = _format_charms(origin)
    destination_charms = _format_charms(destination)
    if origin_charms or destination_charms:
        return origin_charms or "none", destination_charms or "none"
    return None





def _extract_direct_demand(route: Any) -> Optional[str]:
    # If route is a list, we can't extract demand information
    if isinstance(route, list):
        return None
    
    demand = _safe_lookup(route, ["directDemand", "demand", "demandProfile"])
    if isinstance(demand, dict):
        eco = _safe_lookup(demand, ["economy", "eco", "Y"])
        bus = _safe_lookup(demand, ["business", "C"])
        first = _safe_lookup(demand, ["first", "F"])
        components = [
            str(int(eco)) if isinstance(eco, (int, float)) else "–",
            str(int(bus)) if isinstance(bus, (int, float)) else "–",
            str(int(first)) if isinstance(first, (int, float)) else "–",
        ]
        return " / ".join(components)
    if isinstance(demand, Sequence):
        values = [str(int(v)) if isinstance(v, (int, float)) else "–" for v in demand]
        if values:
            return " / ".join(values)
    return None


def _segment_mode(segment: Dict[str, Any]) -> str:
    # Handle MyFly API format
    if "transportType" in segment:
        transport_type = segment["transportType"]
        if transport_type == "FLIGHT":
            return "flight"
        elif transport_type == "GENERIC_TRANSIT":
            return "ground"
        elif transport_type == "TRAIN":
            return "train"
        return transport_type.lower()
    
    # Handle other formats
    mode = _safe_lookup(segment, ["mode", "type", "transport"])
    if isinstance(mode, str):
        normalized = mode.strip().lower()
        if normalized in {"flight", "air", "plane", "aircraft"}:
            return "flight"
        if normalized in {"bus", "ground", "coach"}:
            return "ground"
        if normalized in {"train", "rail"}:
            return "train"
        return normalized
    return "flight"


def _safe_lookup(value: Any, keys: Iterable[str]) -> Any:
    if not isinstance(value, dict):
        return None
    for key in keys:
        if key in value:
            return value[key]
    lowered = {str(k).lower(): v for k, v in value.items()}
    for key in keys:
        match = lowered.get(str(key).lower())
        if match is not None:
            return match
    return None


def _airport_code(airport: Any) -> str:
    if isinstance(airport, dict):
        return _first_non_empty(
            airport.get("iata"),
            airport.get("IATA"),
            airport.get("code"),
            airport.get("icao"),
            airport.get("ICAO"),
        ) or ""
    if isinstance(airport, str):
        return airport
    return ""


def _country_code(airport: Dict[str, Any]) -> str:
    country = _safe_lookup(airport, ["country", "nation", "countryCode"])
    if isinstance(country, dict):
        return _first_non_empty(country.get("code"), country.get("iso2"), country.get("name")) or ""
    if isinstance(country, str):
        return country
    return ""


def _compose_flight_designator(carrier: Any, fallback: Any) -> Optional[str]:
    carrier_code = None
    if isinstance(carrier, dict):
        carrier_code = _first_non_empty(carrier.get("code"), carrier.get("iata"))
    elif isinstance(carrier, str):
        carrier_code = carrier
    if carrier_code and fallback:
        return f"{carrier_code} {fallback}"
    return None


def _first_non_empty(*values: Any) -> Optional[str]:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None
