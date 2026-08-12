"""Decimal helpers for money/odds/stake arithmetic.

Spec section 29 rule 3: `Decimal` for money and final odds/stake arithmetic,
never binary floating point. This module centralises rounding so strategy
code doesn't scatter ad-hoc `quantize()` calls.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

TWO_DP = Decimal("0.01")
FIVE_DP = Decimal("0.00001")


def to_money(value: Decimal | str | float | int) -> Decimal:
    """Quantize to 2dp using round-half-up — the convention for displayed
    GBP amounts and settled P&L."""
    return Decimal(str(value)).quantize(TWO_DP, rounding=ROUND_HALF_UP)


def to_odds(value: Decimal | str | float | int) -> Decimal:
    """Quantize to 5dp — enough precision for implied-probability round trips
    without losing information vendors provide at 2-3dp."""
    return Decimal(str(value)).quantize(FIVE_DP, rounding=ROUND_HALF_UP)


def floor_stake(value: Decimal, increment: Decimal = Decimal("0.01")) -> Decimal:
    """Round a stake down to the nearest tradable increment. Rounding a
    stake *up* can request more capital than approved by the risk engine,
    so floor is the only safe direction."""
    if increment <= 0:
        raise ValueError("increment must be positive")
    units = (value / increment).to_integral_value(rounding=ROUND_DOWN)
    return (units * increment).quantize(increment)
