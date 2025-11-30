"""
Basic tests for fake tracking engine.

We don't hit external APIs; instead we just verify deterministic behavior
by calling the lower-level helpers.
"""

from datetime import datetime

from src.engines.fake_tracking import _daily_seed, _hash_to_base_coord


def test_daily_seed_changes_per_day():
    d1 = datetime(2024, 1, 1)
    d2 = datetime(2024, 1, 2)
    assert _daily_seed(d1) != _daily_seed(d2)


def test_base_coord_deterministic():
    imei = "490154203237518"
    seed = "2024-01-01"
    c1 = _hash_to_base_coord(imei, seed)
    c2 = _hash_to_base_coord(imei, seed)
    assert c1 == c2
    # Coordinates should be in plausible range
    lat, lon = c1
    assert -90 <= lat <= 90
    assert -180 <= lon <= 180
