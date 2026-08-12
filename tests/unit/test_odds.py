from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from marketedge.domain.odds import (
    exchange_midpoint,
    implied_probability,
    odds_from_probability,
    overround,
    proportional_devig,
)

decimal_odds = st.decimals(
    min_value="1.01", max_value="1000", places=2, allow_nan=False, allow_infinity=False
).map(Decimal)


def test_implied_probability_basic() -> None:
    assert implied_probability(Decimal("2.0")) == Decimal("0.5")


def test_implied_probability_rejects_non_positive() -> None:
    with pytest.raises(ValueError):
        implied_probability(Decimal("0"))


def test_odds_from_probability_is_inverse() -> None:
    assert odds_from_probability(Decimal("0.5")) == Decimal("2")


def test_overround_detects_arb() -> None:
    # 1/2.10 + 1/2.10 = 0.952 < 1 -> theoretical arbitrage exists
    assert overround([Decimal("2.10"), Decimal("2.10")]) < 1


def test_overround_no_arb_when_book_has_margin() -> None:
    # A typical bookmaker two-way market with overround > 1
    assert overround([Decimal("1.90"), Decimal("1.90")]) > 1


def test_proportional_devig_sums_to_one() -> None:
    probs = proportional_devig([Decimal("1.90"), Decimal("1.90"), Decimal("4.5")])
    assert abs(sum(probs) - Decimal(1)) < Decimal("0.0001")


def test_exchange_midpoint_between_back_and_lay() -> None:
    mid = exchange_midpoint(Decimal("2.00"), Decimal("2.04"))
    # fair odds should sit between the back and lay prices
    assert Decimal("2.00") < mid < Decimal("2.04")


@given(st.lists(decimal_odds, min_size=2, max_size=6))
def test_proportional_devig_always_sums_to_one(odds: list[Decimal]) -> None:
    probs = proportional_devig(odds)
    assert abs(sum(probs, Decimal(0)) - Decimal(1)) < Decimal("0.0000001")


@given(decimal_odds)
def test_probability_odds_round_trip(odds: Decimal) -> None:
    probability = implied_probability(odds)
    round_tripped = odds_from_probability(probability)
    assert abs(round_tripped - odds) < Decimal("0.001")
