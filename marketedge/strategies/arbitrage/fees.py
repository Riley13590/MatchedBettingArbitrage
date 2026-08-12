"""Venue fee/commission model.

Exchanges (Betfair, Smarkets, Matchbook) charge commission on *net winnings
per market*, not on turnover; bookmakers pay out at the quoted odds with no
separate commission. Getting this distinction right matters because the
same gross profit nets to a different amount depending on which venue it
was won on — spec section 13.1 explicitly requires "venue-specific
fees/commission" before an opportunity's profit can be trusted.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class VenueFeeModel:
    commission_rate: Decimal  # charged on net winnings only, e.g. Decimal("0.05")


# Bootstrap defaults — spec section 33 requires these be "validated against
# actual venue statements" before any live use; Betfair's headline rate is
# 5% but varies by account (Premium Charge, promotions, etc.), so this is a
# starting assumption, not a verified constant.
DEFAULT_FEE_MODELS: dict[str, VenueFeeModel] = {
    "betfair": VenueFeeModel(Decimal("0.05")),
    "smarkets": VenueFeeModel(Decimal("0.02")),
    "matchbook": VenueFeeModel(Decimal("0.02")),
}
_NO_COMMISSION = VenueFeeModel(Decimal("0"))


def fee_model_for(venue_code: str) -> VenueFeeModel:
    """Bookmaker venues (`oddsapi:*`) and any unlisted venue default to zero
    commission — bookmakers pay quoted odds outright; an unlisted exchange
    defaulting to zero is a deliberately conservative (profit-understating,
    never profit-overstating) fallback rather than guessing a rate."""
    return DEFAULT_FEE_MODELS.get(venue_code, _NO_COMMISSION)


def net_winnings(gross_profit: Decimal, fee_model: VenueFeeModel) -> Decimal:
    """Commission applies only to net winnings on that market — a loss is
    never taxed into a smaller loss."""
    if gross_profit <= 0:
        return gross_profit
    return gross_profit * (Decimal(1) - fee_model.commission_rate)
