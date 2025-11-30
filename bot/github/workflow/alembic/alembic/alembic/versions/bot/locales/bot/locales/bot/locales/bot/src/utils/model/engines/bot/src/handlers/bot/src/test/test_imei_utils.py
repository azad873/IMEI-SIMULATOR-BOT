"""
Simple tests for IMEI helper functions.

We use pytest; run with `pytest -q`.
"""

from src.utils.imei import is_valid_imei, mask_imei, suffix_imei


def test_valid_imei():
    # A known-good IMEI example; Luhn-valid.
    assert is_valid_imei("490154203237518")


def test_invalid_imei_length():
    assert not is_valid_imei("12345")


def test_invalid_imei_chars():
    assert not is_valid_imei("49015420323751X")


def test_mask_imei():
    masked = mask_imei("490154203237518")
    assert masked.startswith("49015420")
    assert masked.endswith("********")
    assert len(masked) == 16


def test_suffix_imei():
    assert suffix_imei("490154203237518") == "7518"
