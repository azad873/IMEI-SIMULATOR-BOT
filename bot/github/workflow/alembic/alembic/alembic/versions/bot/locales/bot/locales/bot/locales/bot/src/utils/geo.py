"""
Geo-related helpers.

We call:
- OSRM demo server to snap coordinates to nearest road (optional).
- Geoapify static map API to generate a map image URL.

In production you might want to cache results and handle errors carefully.
"""

from __future__ import annotations

import io
from typing import List, Tuple

import aiohttp

from .config import settings

Coordinate = Tuple[float, float]


async def snap_to_road(session: aiohttp.ClientSession, coord: Coordinate) -> Coordinate:
    """
    Snap a (lat, lon) coordinate to the nearest road using OSRM demo server.

    If anything fails, we simply return the original coordinate.
    """
    lat, lon = coord
    url = f"https://router.project-osrm.org/nearest/v1/driving/{lon},{lat}"

    try:
        async with session.get(url, timeout=5) as resp:
            if resp.status != 200:
                return coord
            data = await resp.json()
            waypoints = data.get("waypoints")
            if not waypoints:
                return coord
            # OSRM returns location as [lon, lat]
            snapped_lon, snapped_lat = waypoints[0]["location"]
            return float(snapped_lat), float(snapped_lon)
    except Exception:
        return coord


async def generate_static_map(
    session: aiohttp.ClientSession,
    coords: List[Coordinate],
) -> bytes:
    """
    Generate a static map PNG using Geoapify Static Maps API.

    Returns the raw PNG bytes that we can send as a photo to Telegram.
    """
    if not coords:
        raise ValueError("No coordinates provided")

    # Build the path parameter from coordinates in lon,lat format
    path_points = "|".join(f"{lon},{lat}" for lat, lon in coords)

    # We'll roughly center the map on the first coordinate
    first_lat, first_lon = coords[0]

    params = {
        "style": "osm-bright",
        "width": 600,
        "height": 400,
        "center": f"lonlat:{first_lon},{first_lat}",
        "zoom": 12,
        "path": f"color:0x0080FF|weight:4|{path_points}",
        "apiKey": settings.GEOAPIFY_API_KEY,
    }

    url = "https://maps.geoapify.com/v1/staticmap"

    async with session.get(url, params=params, timeout=10) as resp:
        resp.raise_for_status()
        content = await resp.read()

    return content
