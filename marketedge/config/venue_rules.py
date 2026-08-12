"""Default venue capability seed data.

Mirrors docs/venue-matrix.md. This is the *default* row inserted by the
initial migration; the live `venues` table in Postgres is the runtime
source of truth (spec section 3 — "runtime-validated assumptions, not
permanent truths"). Changing a venue's capability at runtime means updating
the database row, not this module.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VenueSeed:
    code: str
    name: str
    data_allowed: bool
    execution_allowed: bool
    geo_status: str
    terms_status: str
    evidence_url: str


DEFAULT_VENUES: tuple[VenueSeed, ...] = (
    VenueSeed(
        code="betfair",
        name="Betfair Exchange",
        data_allowed=True,
        execution_allowed=False,
        geo_status="GB_OK",
        terms_status="OK",
        evidence_url="https://developer.betfair.com",
    ),
    VenueSeed(
        code="smarkets",
        name="Smarkets",
        data_allowed=False,
        execution_allowed=False,
        geo_status="UNVERIFIED",
        terms_status="UNVERIFIED",
        evidence_url="https://docs.smarkets.com",
    ),
    VenueSeed(
        code="matchbook",
        name="Matchbook",
        data_allowed=False,
        execution_allowed=False,
        geo_status="UNVERIFIED",
        terms_status="UNVERIFIED",
        evidence_url="https://www.matchbook.com/bet/api",
    ),
    VenueSeed(
        code="odds_provider",
        name="Bookmaker odds provider",
        data_allowed=False,
        execution_allowed=False,
        geo_status="UNVERIFIED",
        terms_status="UNVERIFIED",
        evidence_url="",
    ),
    VenueSeed(
        code="polymarket",
        name="Polymarket",
        data_allowed=False,
        execution_allowed=False,
        geo_status="GB_CLOSE_ONLY",
        terms_status="RESTRICTED",
        evidence_url="https://docs.polymarket.com",
    ),
    VenueSeed(
        code="kalshi",
        name="Kalshi",
        data_allowed=False,
        execution_allowed=False,
        geo_status="UNVERIFIED",
        terms_status="UNVERIFIED",
        evidence_url="https://trading-api.readme.io/",
    ),
)
