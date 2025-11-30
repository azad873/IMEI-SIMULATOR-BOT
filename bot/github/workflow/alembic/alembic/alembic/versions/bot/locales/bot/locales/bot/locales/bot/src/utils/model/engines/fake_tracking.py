"""
Fake tracking engine.

Responsible for generating:
- deterministic pseudo-random coordinates per IMEI & day
- 5 timestamps in the last 24 hours
- fake addresses (placeholder strings)
- static map via Geoapify
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import List, Tuple

import aiohttp

from src.utils.config import settings
from src.utils.geo import Coordinate, generate_static_map, snap_to_road
from src.utils.time_utils import utc_now

# A data class makes it easy to pass the full result around.
@dataclass
class FakeLocationPoint:
    timestamp: datetime
    coord: Coordinate
    address: str


@dataclass
class FakeTrackResult:
    imei_prefix: str
    points: List[FakeLocationPoint]
    map_png: bytes
    seed_date: datetime


def _daily_seed(now: datetime | None = None) -> str:
    """
    Compute a simple daily seed string based on UTC date.

    Requirement: 'Rotate daily_seed every 24 h at 00:00 UTC'.
    """
    if now is None:
        now = utc_now()
    return now.strftime("%Y-%m-%d")


def _hash_to_base_coord(imei: str, seed: str) -> Coordinate:
    """
    Use HMAC-SHA256(IMEI + daily_seed, SECRET_KEY) to produce a base lat/lon.

    We map the hash into roughly valid latitude and longitude ranges.
    """
    key = settings.SECRET_KEY.encode("utf-8")
    msg = (imei + seed).encode("utf-8")
    digest = hmac.new(key, msg, hashlib.sha256).digest()

    # Use first 8 bytes for latitude, next 8 bytes for longitude.
    lat_int = int.from_bytes(digest[:8], "big")
    lon_int = int.from_bytes(digest[8:16], "big")

    # Map to ranges:
    # lat in [-85, 85], lon in [-180, 180]
    lat = (lat_int / 2**64) * 170.0 - 85.0
    lon = (lon_int / 2**64) * 360.0 - 180.0

    return lat, lon


async def generate_fake_track(imei: str) -> FakeTrackResult:
    """
    Generate a deterministic fake track for a given IMEI.

    Steps:
    1. Compute daily seed and base coordinate.
    2. Use a random.Random seeded from hash to generate small offsets.
    3. Pick 5 time points in the last 24 hours, 2–6 hours apart.
    4. Optionally snap each coordinate to nearest road (OSRM).
    5. Generate static map PNG with a polyline over the points.
    """
    now = utc_now()
    seed_str = _daily_seed(now)

    base_lat, base_lon = _hash_to_base_coord(imei, seed_str)

    # Seed deterministic random generator with HMAC again for stable results.
    seed_digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        (imei + seed_str).encode("utf-8"),
        hashlib.sha256,
    ).digest()
    seed_int = int.from_bytes(seed_digest, "big")
    rnd = random.Random(seed_int)

    # Generate 5 coordinates around base point within ±0.3 degrees.
    coords: List[Coordinate] = []
    for _ in range(5):
        dlat = (rnd.random() - 0.5) * 0.6  # (-0.3, 0.3)
        dlon = (rnd.random() - 0.5) * 0.6
        coords.append((base_lat + dlat, base_lon + dlon))

    # Generate times in the last 24 hours.
    points: List[FakeLocationPoint] = []
    start_time = now - timedelta(hours=24)
    current_time = start_time + timedelta(hours=rnd.uniform(0, 4))

    async with aiohttp.ClientSession() as session:
        snapped_coords: List[Coordinate] = []
        for coord in coords:
            snapped = await snap_to_road(session, coord)
            snapped_coords.append(snapped)

        # Build timestamps with random gaps between 2–6 hours.
        for coord in snapped_coords:
            # Ensure we don't go beyond 'now'
            if current_time > now:
                current_time = now - timedelta(minutes=rnd.randint(0, 60))
            # Fake address: we don't do real reverse geocoding to keep this purely simulated.
            address = f"Near {coord[0]:.3f}, {coord[1]:.3f}"
            points.append(
                FakeLocationPoint(
                    timestamp=current_time,
                    coord=coord,
                    address=address,
                )
            )
            current_time = current_time + timedelta(hours=rnd.uniform(2, 6))

        # Ensure points are sorted by time
        points.sort(key=lambda p: p.timestamp)

        # Generate static map image with polyline.
        map_png = await generate_static_map(session, [p.coord for p in points])

    imei_prefix = imei[:8]

    return FakeTrackResult(
        imei_prefix=imei_prefix,
        points=points,
        map_png=map_png,
        seed_date=now.replace(hour=0, minute=0, second=0, microsecond=0),
    )
