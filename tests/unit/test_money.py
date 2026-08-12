from decimal import Decimal

import pytest

from marketedge.domain.money import floor_stake, to_money, to_odds


def test_to_money_rounds_half_up() -> None:
    assert to_money(Decimal("10.005")) == Decimal("10.01")
    assert to_money(Decimal("10.004")) == Decimal("10.00")


def test_to_odds_quantizes_to_five_dp() -> None:
    assert to_odds(Decimal("2.123456789")) == Decimal("2.12346")


def test_floor_stake_never_rounds_up() -> None:
    assert floor_stake(Decimal("10.999"), Decimal("0.01")) == Decimal("10.99")


def test_floor_stake_rejects_non_positive_increment() -> None:
    with pytest.raises(ValueError):
        floor_stake(Decimal("10"), Decimal("0"))
