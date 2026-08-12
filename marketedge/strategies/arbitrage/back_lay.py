"""Back-lay arbitrage cash-flow equations (spec section 13.2).

Deliberately implemented as two independent per-outcome P&L functions
rather than a single formula copied from the spec, then a hedge stake that
is *derived* by setting those two equations equal — this is the "tested
cash-flow equations" spec section 13.2 asks for, so unit tests can verify
both outcomes independently rather than trusting one formula blindly.

Backing `back_stake` at `back_odds` on a bookmaker, laying `lay_stake` at
`lay_odds` on an exchange charging `commission_rate` on net winnings:

- Selection wins: bookmaker pays `back_stake * back_odds`; the lay bet
  loses, costing `lay_stake * (lay_odds - 1)`.
- Selection loses: the back stake is lost; the lay bet wins, paying
  `lay_stake` net of commission.
"""

from __future__ import annotations

from decimal import Decimal

from marketedge.strategies.arbitrage.fees import VenueFeeModel, net_winnings


def profit_if_selection_wins(
    back_stake: Decimal, back_odds: Decimal, lay_stake: Decimal, lay_odds: Decimal
) -> Decimal:
    return back_stake * (back_odds - 1) - lay_stake * (lay_odds - 1)


def profit_if_selection_loses(
    back_stake: Decimal, lay_stake: Decimal, lay_fee_model: VenueFeeModel
) -> Decimal:
    return -back_stake + net_winnings(lay_stake, lay_fee_model)


def lay_stake_for_equal_profit(
    back_stake: Decimal,
    back_odds: Decimal,
    lay_odds: Decimal,
    commission_rate: Decimal,
) -> Decimal:
    """Solves for the lay stake that makes `profit_if_selection_wins` equal
    `profit_if_selection_loses`, i.e. spec section 13.2's
    `lay_stake = (back_stake * back_odds) / (lay_odds - c)` — derived here
    (not copied) by equating the two cash-flow functions above and solving
    for `lay_stake`."""
    denominator = lay_odds - commission_rate
    if denominator <= 0:
        raise ValueError("lay_odds must exceed the commission rate")
    return back_stake * back_odds / denominator


def worst_case_profit(
    back_stake: Decimal,
    back_odds: Decimal,
    lay_stake: Decimal,
    lay_odds: Decimal,
    lay_fee_model: VenueFeeModel,
) -> Decimal:
    """The guaranteed profit is the lower of the two outcome profits — with
    a stake computed via `lay_stake_for_equal_profit` the two are
    approximately equal (subject to money rounding), but detector code
    should never assume they're exactly equal without checking both."""
    return min(
        profit_if_selection_wins(back_stake, back_odds, lay_stake, lay_odds),
        profit_if_selection_loses(back_stake, lay_stake, lay_fee_model),
    )
