"""
Utility functions for handling IMEI numbers.

We only VALIDATE and MASK IMEIs; we never store or log the full string.
"""

from __future__ import annotations


def is_valid_imei(imei: str) -> bool:
    """
    Check if a string is a valid 15-digit IMEI using the Luhn algorithm.

    The algorithm:
    - length must be 15 and digits only
    - double every second digit from the right
    - sum digits; result % 10 must be 0
    """
    if len(imei) != 15 or not imei.isdigit():
        return False

    total = 0
    # We process from right to left, keeping a position counter
    for i, ch in enumerate(reversed(imei)):
        digit = int(ch)
        if i % 2 == 1:  # every second digit (Luhn)
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def mask_imei(imei: str) -> str:
    """
    Return a masked IMEI representation.

    Requirement says: "Never log full IMEI: store first 8 + ''".
    So we keep first 8 digits, then add 8 asterisks.
    """
    prefix = imei[:8]
    return prefix + "********"


def suffix_imei(imei: str) -> str:
    """
    Return last 4 digits (or shorter if IMEI shorter), used only for UI.

    This is safer than printing full IMEI but still recognizable by the user.
    """
    return imei[-4:]
