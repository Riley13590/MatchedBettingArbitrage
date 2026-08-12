from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from marketedge.strategies.arbitrage.dutching import dutch_stakes, worst_case_profit

# Odds chosen so overround < 1 is achievable but not guaranteed — the
# property test below only asserts the invariant when dutch_stakes returns
# a result (i.e. when the input happened to be an arbitrage).
arb_odds = st.lists(
    st.decimals(
        min_value="1.50", max_value="10", places=2, allow_nan=False, allow_infinity=False
    ).map(Decimal),
    min_size=2,
    max_size=5,
)


def test_dutch_stakes_two_way_arb() -> None:
    # 1/2.10 + 1/2.10 = 0.952 < 1 -> arbitrage
    stakes = dutch_stakes(Decimal("100"), [Decimal("2.10"), Decimal("2.10")])
    assert stakes is not None
    assert len(stakes) == 2
    returns = [s * Decimal("2.10") for s in stakes]
    assert abs(returns[0] - returns[1]) <= Decimal("0.02")


def test_dutch_stakes_no_arb_returns_none() -> None:
    assert dutch_stakes(Decimal("100"), [Decimal("1.90"), Decimal("1.90")]) is None


def test_dutch_stakes_rejects_empty_odds() -> None:
    with pytest.raises(ValueError):
        dutch_stakes(Decimal("100"), [])


def test_dutch_stakes_rejects_non_positive_bankroll() -> None:
    with pytest.raises(ValueError):
        dutch_stakes(Decimal("0"), [Decimal("2.0"), Decimal("2.0")])


def test_worst_case_profit_matches_min_return_minus_stake() -> None:
    stakes = [Decimal("52.38"), Decimal("47.62")]
    odds = [Decimal("2.10"), Decimal("2.10")]
    assert worst_case_profit(stakes, odds) == min(
        s * o for s, o in zip(stakes, odds, strict=True)
    ) - sum(stakes)


@given(st.decimals(min_value="10", max_value="100000", places=2).map(Decimal), arb_odds)
def test_dutch_equalises_returns_within_rounding_tolerance(
    bankroll: Decimal, odds: list[Decimal]
) -> None:
    stakes = dutch_stakes(bankroll, odds)
    if stakes is None:
        return  # not an arbitrage for this random sample — nothing to assert
    returns = [s * o for s, o in zip(stakes, odds, strict=True)]
    # Each stake is rounded to the nearest penny (error <= 0.005), and that
    # error is then multiplied by that outcome's own odds when computing
    # its return — so the achievable spread across outcomes scales with the
    # largest odds in play, not a flat constant.
    tolerance = Decimal("0.01") * max(odds) * len(odds)
    assert max(returns) - min(returns) <= tolerance
