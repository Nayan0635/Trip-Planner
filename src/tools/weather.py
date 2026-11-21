from __future__ import annotations
from langchain.tools import tool
import os
from typing import Optional

import requests

GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"


@tool
def get_current_weather(
    location: str,
    units: str = "metric",
    api_key: Optional[str] = None,
) -> dict:
    '''Fetch current weather conditions for a city or location'''
    key = api_key or os.environ.get("OPENWEATHERMAP_API_KEY")
    if not key:
        raise ValueError(
            "An OpenWeatherMap API key is required. Pass api_key= or set "
            "the OPENWEATHERMAP_API_KEY environment variable."
        )

    # Step 1: Resolve location name to latitude and longitude
    geo_response = requests.get(
        GEOCODING_URL,
        params={"q": location, "limit": 1, "appid": key},
        timeout=10,
    )
    geo_response.raise_for_status()
    geo_results = geo_response.json()

    if not isinstance(geo_results, list) or not geo_results:
        raise ValueError(f"Could not resolve location: {location!r}")

    lat = geo_results[0]["lat"]
    lon = geo_results[0]["lon"]

    # Step 2: Fetch current weather using coordinates
    weather_response = requests.get(
        WEATHER_URL,
        params={"lat": lat, "lon": lon, "appid": key, "units": units},
        timeout=10,
    )
    weather_response.raise_for_status()
    data = weather_response.json()

    country = data.get("sys", {}).get("country", "") or geo_results[0].get("country", "")
    resolved_name = data.get("name") or geo_results[0].get("name", location)

    return {
        "location": f"{resolved_name}, {country}".strip(", "),
        "temperature": data["main"]["temp"],
        "feels_like": data["main"]["feels_like"],
        "conditions": data["weather"][0]["description"] if data.get("weather") else "unknown",
        "humidity": data["main"]["humidity"],
        "wind_speed": data.get("wind", {}).get("speed"),
        "units": units,
    }
