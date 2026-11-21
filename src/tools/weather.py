from __future__ import annotations
from langchain.tools import tool
import os
from typing import Optional

import requests

BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

@tool
def get_current_weather(location: str, units: str = "metric", api_key: Optional[str] = None) -> dict:
    '''Fetches current weather information (temperature, conditions, humidity) for a given city or location'''
    key = api_key or os.environ.get("OPENWEATHERMAP_API_KEY")
    if not key:
        raise ValueError(
            "An OpenWeatherMap API key is required. Pass api_key= or set "
            "the OPENWEATHERMAP_API_KEY environment variable."
        )

    response = requests.get(
        BASE_URL,
        params={"q": location, "appid": key, "units": units},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    country = data.get("sys", {}).get("country", "")
    resolved_name = data.get("name", location)

    return {
        "location": f"{resolved_name}, {country}".strip(", "),
        "temperature": data["main"]["temp"],
        "feels_like": data["main"]["feels_like"],
        "conditions": data["weather"][0]["description"] if data.get("weather") else "unknown",
        "humidity": data["main"]["humidity"],
        "wind_speed": data.get("wind", {}).get("speed"),
        "units": units,
    }
