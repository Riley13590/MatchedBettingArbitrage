# ADR 001: Canonical Event/Market/Selection Model

## Status

Accepted — Milestone 1.

## Context

MarketEdge ingests prices from multiple venues (Betfair now; a bookmaker
odds provider, Smarkets, and Matchbook later) that each describe the same
real-world event, market and outcome differently: different IDs, different
naming ("Man Utd" vs "Manchester United"), different market taxonomies
(`MATCH_ODDS` vs `MONEYLINE`), and — critically — sometimes subtly
*different* settlement rules that must never be treated as equivalent
(90-minute result vs to-qualify; regulation-only vs including overtime;
Asian handicap -1.0 vs -1.5). Incorrect equivalence is the highest-severity
data risk in this system: it can manufacture a false arbitrage.

Vendors will be added and removed over the product's life. Strategy code
(arbitrage detection, fair-value estimation, risk checks) must not need to
change when a venue is added, and must never be able to accidentally
import or branch on vendor-specific types.

## Decision

1. Define a single **canonical domain model**
   (`marketedge/domain/models.py`) — `CanonicalEvent`, `CanonicalMarket`,
   `CanonicalSelection`, `Quote`, `VenueCapability` — as frozen dataclasses,
   independent of any vendor SDK, matching spec section 7 field-for-field.
2. Every `CanonicalMarket` carries `period`, `line`, and `settlement_scope`
   as first-class, mandatory fields (not optional metadata). Two markets
   are only comparable/hedgeable when all three match, in addition to
   `market_type` and event identity. This is enforced structurally: there
   is no code path in `marketedge/pricing` or `marketedge/strategies` that
   can compare `Quote`s from two `CanonicalSelection`s belonging to markets
   with different `settlement_scope`.
3. Vendor adapters (`marketedge/connectors/<venue>/mapper.py`) are the
   *only* place a raw vendor payload is converted to canonical DTOs. No
   other module may import a vendor SDK type or reference a vendor field
   name (`connectors/betfair` is the only package permitted to know what a
   Betfair `marketId` or `runnerId` is).
4. Connectors implement one of two `typing.Protocol`s
   (`marketedge/connectors/base.py`): `MarketDataConnector` (read-only) and
   `ExecutionConnector` (order placement). Strategy, risk, and API code
   depend only on these protocols, never on concrete connector classes.
5. `VenueCapability` (`data_allowed`, `execution_allowed`, `geo_status`,
   `terms_status`) is a runtime-checked gate, not a compile-time constant.
   The execution layer refuses to initialise a connector's execution path
   unless `execution_allowed=True` in the live `venues` table.
6. Event/market/selection *matching* across venues (alias tables, fuzzy
   confidence scoring per spec section 11) is a separate concern from the
   canonical model itself and lives in `marketedge/matching/` — introduced
   in Milestone 2 once there are two venues to match between. The model in
   this ADR is what matching produces and what everything downstream
   consumes.

## Consequences

- Adding a venue means writing a connector + mapper; no changes to
  `domain`, `strategies`, `risk`, or `pricing`.
- Settlement-scope bugs are caught at the type/field level (missing
  `settlement_scope` is a constructor error, not a runtime surprise deep in
  the arb detector).
- `Quote` always carries both `received_at_utc` and, where available,
  `source_timestamp_utc`, so latency and staleness can be computed
  uniformly across venues from day one — required for the freshness gate
  (spec section 10.2) that every strategy will enforce from Milestone 3
  onward.
- The cost is one extra translation layer per venue; accepted deliberately
  per spec section 6's "Agent rule."
