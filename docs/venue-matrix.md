# Venue Matrix

Runtime-validated assumptions, not permanent truths (spec section 3). The
`venues` table is the source of truth at runtime; this document records the
values seeded at M0/M1 and their evidence.

| Venue | data_allowed | execution_allowed | geo_status | terms_status | V1 role | Evidence |
|---|---|---|---|---|---|---|
| Betfair Exchange | true | false (until M5 explicit enable) | GB_OK | OK | Primary executable exchange; only connector implemented in M1 | developer.betfair.com |
| Smarkets | false | false | UNVERIFIED | UNVERIFIED | Secondary executable adapter — Milestone 9 | smarkets.com/developers |
| Matchbook | false | false | UNVERIFIED | UNVERIFIED | Secondary executable adapter — Milestone 9 | Matchbook API docs |
| UK bookmakers (odds provider) | false | false | UNVERIFIED | UNVERIFIED | Price source — Milestone 2 | provider-specific |
| Polymarket | false | false | GB_CLOSE_ONLY | RESTRICTED | Data-only if/when enabled; GB is close-only for new orders | Polymarket geo-restriction docs |
| Kalshi | false | false | UNVERIFIED | UNVERIFIED | Data-only unless execution eligibility positively verified | Kalshi API docs |

Seeded via `marketedge/config/venue_rules.py` and the `0001_initial_schema`
migration's `venues` seed data. Nothing here grants execution — the
execution layer checks the live `venues.execution_allowed` column, and
`connectors/betfair/execution.py` additionally requires
`BETFAIR_EXECUTION_ALLOWED=true` in the environment. Both gates must be
green; this table alone changes nothing at runtime.
