from __future__ import annotations
from langchain.tools import tool
import os
from typing import Optional

import requests

BASE_URL = "https://api.opentripmap.com/0.1/en/places"

@tool
def get_nearby_attractions(destination: str, radius: int = 10_000, limit: int = 20, api_key: Optional[str] = None) -> list[dict]:
    '''Fetch nearby tourist attractions / places for a destination.'''

    key = api_key or os.environ.get("OPENTRIPMAP_API_KEY")
    if not key:
        raise ValueError(
            "An OpenTripMap API key is required. Pass api_key= or set "
            "the OPENTRIPMAP_API_KEY environment variable."
        )

    # Step 1: resolve the destination name to coordinates.
    geo_response = requests.get(
        f"{BASE_URL}/geoname",
        params={"name": destination, "apikey": key},
        timeout=10,
    )
    geo_response.raise_for_status()
    geo_data = geo_response.json()

    if "lat" not in geo_data or "lon" not in geo_data:
        raise ValueError(f"Could not resolve destination: {destination!r}")

    lat, lon = geo_data["lat"], geo_data["lon"]

    # Step 2: search for nearby points of interest around that location.
    radius_response = requests.get(
        f"{BASE_URL}/radius",
        params={
            "radius": radius,
            "lon": lon,
            "lat": lat,
            "limit": limit,
            "apikey": key,
            "format": "json",
        },
        timeout=10,
    )
    radius_response.raise_for_status()
    places_data = radius_response.json()

    results = []
    for place in places_data:
        results.append(
            {
                "name": place.get("name") or "Unnamed place",
                "category": place.get("kinds", ""),
                "distance_m": round(place.get("dist", 0), 1),
                "rating": place.get("rate"),
                "xid": place.get("xid"),
            }
        )

    return results
