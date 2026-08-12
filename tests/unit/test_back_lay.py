from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from marketedge.strategies.arbitrage.back_lay import (
    lay_stake_for_equal_profit,
    profit_if_selection_loses,
    profit_if_selection_wins,
)
from marketedge.strategies.arbitrage.fees import VenueFeeModel

decimal_odds = st.decimals(
    min_value="1.10", max_value="20", places=2, allow_nan=False, allow_infinity=False
).map(Decimal)
commission = st.decimals(min_value="0", max_value="0.10", places=3, allow_nan=False).map(Decimal)
stake = st.decimals(min_value="1", max_value="10000", places=2, allow_nan=False).map(Decimal)


def test_lay_stake_produces_equal_profit_both_outcomes() -> None:
    back_stake = Decimal("100")
    back_odds = Decimal("2.20")
    lay_odds = Decimal("2.10")
    fee_model = VenueFeeModel(Decimal("0.05"))

    lay_stake = lay_stake_for_equal_profit(
        back_stake, back_odds, lay_odds, fee_model.commission_rate
    )

    win_profit = profit_if_selection_wins(back_stake, back_odds, lay_stake, lay_odds)
    lose_profit = profit_if_selection_loses(back_stake, lay_stake, fee_model)

    assert abs(win_profit - lose_profit) < Decimal("0.0001")
    # A genuine arb (back price exceeds the lay price by enough) profits
    # regardless of outcome.
    assert win_profit > 0
    assert lose_profit > 0


def test_lay_stake_rejects_lay_odds_below_commission() -> None:
    with pytest.raises(ValueError):
        lay_stake_for_equal_profit(Decimal("100"), Decimal("2.0"), Decimal("0.01"), Decimal("0.05"))


@given(stake, decimal_odds, decimal_odds, commission)
def test_win_and_lose_profit_converge_for_any_valid_inputs(
    back_stake: Decimal, back_odds: Decimal, lay_odds: Decimal, commission_rate: Decimal
) -> None:
    if lay_odds <= commission_rate:
        return  # invalid combination, lay_stake_for_equal_profit itself rejects it
    fee_model = VenueFeeModel(commission_rate)
    lay_stake = lay_stake_for_equal_profit(back_stake, back_odds, lay_odds, commission_rate)

    win_profit = profit_if_selection_wins(back_stake, back_odds, lay_stake, lay_odds)
    lose_profit = profit_if_selection_loses(back_stake, lay_stake, fee_model)

    # The two cash-flow equations were set equal to derive lay_stake, so
    # they must agree for every valid input, not just the hand-picked case.
    assert abs(win_profit - lose_profit) < Decimal("0.01")
