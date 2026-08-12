from decimal import Decimal

from marketedge.domain.models import CanonicalMarket


def _market(**overrides: object) -> CanonicalMarket:
    base = dict(
        market_id="m1",
        event_id="e1",
        market_type="MATCH_ODDS",
        period="FULL_TIME",
        line=None,
        settlement_scope="REGULATION_ONLY",
    )
    base.update(overrides)
    return CanonicalMarket(**base)  # type: ignore[arg-type]


def test_identical_markets_are_settlement_compatible() -> None:
    assert _market().is_settlement_compatible(_market())


def test_different_settlement_scope_is_incompatible() -> None:
    a = _market(settlement_scope="REGULATION_ONLY")
    b = _market(settlement_scope="TO_QUALIFY")
    assert not a.is_settlement_compatible(b)


def test_different_line_is_incompatible() -> None:
    a = _market(market_type="TOTAL", line=Decimal("2.5"))
    b = _market(market_type="TOTAL", line=Decimal("3.0"))
    assert not a.is_settlement_compatible(b)


def test_different_period_is_incompatible() -> None:
    a = _market(period="FULL_TIME")
    b = _market(period="SET_1")
    assert not a.is_settlement_compatible(b)
