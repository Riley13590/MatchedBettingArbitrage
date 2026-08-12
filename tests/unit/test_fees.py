from decimal import Decimal

from marketedge.strategies.arbitrage.fees import DEFAULT_FEE_MODELS, fee_model_for, net_winnings


def test_fee_model_for_known_exchange() -> None:
    assert fee_model_for("betfair") == DEFAULT_FEE_MODELS["betfair"]


def test_fee_model_for_bookmaker_venue_is_zero_commission() -> None:
    model = fee_model_for("oddsapi:williamhill")
    assert model.commission_rate == Decimal("0")


def test_net_winnings_applies_commission_to_profit_only() -> None:
    model = fee_model_for("betfair")
    assert net_winnings(Decimal("100"), model) == Decimal("95.00")


def test_net_winnings_never_taxes_a_loss() -> None:
    model = fee_model_for("betfair")
    assert net_winnings(Decimal("-50"), model) == Decimal("-50")
