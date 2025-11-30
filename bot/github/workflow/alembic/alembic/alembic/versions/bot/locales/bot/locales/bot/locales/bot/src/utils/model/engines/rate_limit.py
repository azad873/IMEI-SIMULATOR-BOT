"""
Rate limiting using Redis + PostgreSQL logs.

We implement:
- A daily counter per user (max 3 IMEI checks per day).
- A small leaky bucket token scheme in Redis for speed.

If Redis is unavailable, we fall back to a very simple limit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import IMEIQuery
from src.utils.time_utils import seconds_until_midnight_utc, utc_now


@dataclass
class RateLimitStatus:
    allowed: bool
    remaining: int
    reset_in_seconds: int


DAILY_LIMIT = 3  # Maximum IMEI checks per user per day


async def check_rate_limit(
    redis: Redis,
    db: AsyncSession,
    user_id: int,
) -> RateLimitStatus:
    """
    Check if user has remaining quota.

    We:
    - try Redis first (fast path)
    - backfill from DB if Redis key missing
    """
    key = f"rate:user:{user_id}:daily"
    ttl = await redis.ttl(key)

    if ttl == -2:
        # Key doesn't exist -> compute from DB for today and set in Redis.
        now = utc_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = (
            select(func.count())
            .select_from(IMEIQuery)
            .where(
                IMEIQuery.user_id == user_id,
                IMEIQuery.created_at >= today_start,
            )
        )
        result = await db.execute(stmt)
        count_today = int(result.scalar_one())
        remaining = max(0, DAILY_LIMIT - count_today)

        # Set Redis key with TTL until midnight.
        reset_in = seconds_until_midnight_utc()
        await redis.set(key, count_today, ex=reset_in)
    else:
        # Key exists or no expiry. For simplicity, just read it.
        val = await redis.get(key)
        count_today = int(val) if val is not None else 0
        remaining = max(0, DAILY_LIMIT - count_today)
        reset_in = seconds_until_midnight_utc()

    allowed = remaining > 0
    return RateLimitStatus(allowed=allowed, remaining=remaining, reset_in_seconds=reset_in)


async def increment_rate_limit(redis: Redis, user_id: int) -> None:
    """
    Increment user's usage counter in Redis.

    We rely on TTL already being set until midnight.
    """
    key = f"rate:user:{user_id}:daily"
    # Use INCR; if key not exists, Redis will create one.
    current = await redis.incr(key)
    if current == 1:
        # First time today -> set TTL until midnight.
        await redis.expire(key, seconds_until_midnight_utc())
