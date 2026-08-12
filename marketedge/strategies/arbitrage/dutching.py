"""Multi-book dutching (spec section 13.1).

```text
inv_sum = sum(1/O_i for O_i in odds)
if inv_sum >= 1: no arbitrage
stake_i = bankroll * (1/O_i) / inv_sum
return_i = stake_i * O_i
```

Stakes are rounded to money (2dp) — spec section 27.1's property test
tolerates up to £0.02 of return spread for exactly this reason ("returns
equalised" is a target of rounded currency stakes, not a mathematical
identity on raw reals).
"""

from __future__ import annotations

from decimal import Decimal

from marketedge.domain.money import to_money
from marketedge.domain.odds import overround


def dutch_stakes(bankroll: Decimal, odds: list[Decimal]) -> list[Decimal] | None:
    """Returns one stake per outcome (rounded to money) that equalises
    return across all outcomes, or `None` if `odds` implies no arbitrage
    (`overround(odds) >= 1`)."""
    if not odds:
        raise ValueError("odds must be non-empty")
    if bankroll <= 0:
        raise ValueError("bankroll must be positive")

    inv_sum = overround(odds)
    if inv_sum >= 1:
        return None

    return [to_money(bankroll * (Decimal(1) / o) / inv_sum) for o in odds]


def worst_case_profit(stakes: list[Decimal], odds: list[Decimal]) -> Decimal:
    """The guaranteed profit across all outcomes — the *minimum* net return
    minus total stake, per spec section 13.1 ("Use the minimum net outcome
    P&L as the opportunity's guaranteed profit")."""
    if len(stakes) != len(odds):
        raise ValueError("stakes and odds must be the same length")
    total_stake = sum(stakes, Decimal(0))
    returns = [stake * price for stake, price in zip(stakes, odds, strict=True)]
    return min(returns) - total_stake
