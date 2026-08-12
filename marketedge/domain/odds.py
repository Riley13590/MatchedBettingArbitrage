"""Odds/probability conversion primitives.

Spec section 12. These are pure functions with no I/O, exhaustively unit
tested (spec section 27.1) since every downstream P&L calculation depends
on them being exactly right.
"""

from __future__ import annotations

from decimal import Decimal


def implied_probability(decimal_odds: Decimal) -> Decimal:
    """p_raw = 1 / odds (spec section 12.1)."""
    if decimal_odds <= 0:
        raise ValueError("decimal_odds must be positive")
    return Decimal(1) / decimal_odds


def odds_from_probability(probability: Decimal) -> Decimal:
    """Inverse of implied_probability — fair decimal odds for a probability."""
    if not (0 < probability <= 1):
        raise ValueError("probability must be in (0, 1]")
    return Decimal(1) / probability


def overround(prices: list[Decimal]) -> Decimal:
    """Sum of implied probabilities across mutually exclusive outcomes
    (spec section 4.1's `arb_sum`). A value < 1 indicates a theoretical
    (not yet executable) arbitrage."""
    if not prices:
        raise ValueError("prices must be non-empty")
    return sum((implied_probability(p) for p in prices), Decimal(0))


def proportional_devig(prices: list[Decimal]) -> list[Decimal]:
    """Baseline proportional de-vig (spec section 12.2).

    Normalises raw implied probabilities so they sum to 1. This is a
    baseline only — spec section 12.2 notes alternative methods (power,
    Shin, odds-ratio) belong behind the same interface once introduced,
    which is a Milestone 8 concern.
    """
    if not prices:
        raise ValueError("prices must be non-empty")
    raw = [implied_probability(p) for p in prices]
    normalizer = sum(raw, Decimal(0))
    if normalizer <= 0:
        raise ValueError("normalizer must be positive")
    return [p / normalizer for p in raw]


def exchange_midpoint(best_back: Decimal, best_lay: Decimal) -> Decimal:
    """Fair decimal odds from an exchange's best back/lay, converted through
    probability space rather than averaged in odds-space directly (spec
    section 12.3 — the naive odds-space average is explicitly wrong)."""
    if best_back <= 0 or best_lay <= 0:
        raise ValueError("prices must be positive")
    p_back = implied_probability(best_back)
    p_lay = implied_probability(best_lay)
    p_mid = (p_back + p_lay) / 2
    return odds_from_probability(p_mid)
