# Venue Matrix

Runtime-validated assumptions, not permanent truths (spec section 3). The
`venues` table is the source of truth at runtime; this document records the
values seeded at migration time and their evidence.

| Venue | data_allowed | execution_allowed | geo_status | terms_status | Role | Evidence |
|---|---|---|---|---|---|---|
| Betfair Exchange | true | false (until M5 explicit enable) | GB_OK | OK | Primary executable exchange | developer.betfair.com |
| Smarkets | false | false | UNVERIFIED | UNVERIFIED | Secondary executable adapter — Milestone 9 | smarkets.com/developers |
| Matchbook | false | false | UNVERIFIED | UNVERIFIED | Secondary executable adapter — Milestone 9 | Matchbook API docs |
| odds_provider (aggregator) | false | false | UNVERIFIED | UNVERIFIED | Gate on the odds-data *provider itself* (The Odds API); individual bookmaker prices are attributed to their own dynamically-created venue rows below, not this row | the-odds-api.com |
| Polymarket | false | false | GB_CLOSE_ONLY | RESTRICTED | Data-only if/when enabled; GB is close-only for new orders | Polymarket geo-restriction docs |
| Kalshi | false | false | UNVERIFIED | UNVERIFIED | Data-only unless execution eligibility positively verified | Kalshi API docs |

Static rows above are seeded via `marketedge/config/venue_rules.py` and the
`0001_initial_schema` migration's `venues` seed data.

## Bookmaker venues (Milestone 2, dynamic)

Every individual bookmaker The Odds API returns (William Hill, Bet365, ...)
gets its own venue row, created on first sighting by
`VenueRepository.upsert_bookmaker` (`marketedge/storage/repositories/venues.py`),
coded `oddsapi:<bookmaker_key>`. This is deliberate: spec section 40.3's
discovery hierarchy requires attributing signals down to the specific
bookmaker, and spec section 42 requires every metric be filterable by
bookmaker — a single generic "odds_provider" venue for every book would
lose that.

Every dynamically-created bookmaker venue starts:

```text
data_allowed = true
execution_allowed = false
geo_status = "UNVERIFIED"
terms_status = "UNVERIFIED"
```

`execution_allowed=false` is permanent for every bookmaker — spec section 2
keeps bookmaker-side execution manual regardless of any future capability
check, unlike exchanges where the gate can eventually flip. `geo_status`/
`terms_status` start `UNVERIFIED` because nobody has independently
confirmed that specific book's GB licensing/terms yet; update the row (or
extend `upsert_bookmaker` with a known-bookmaker table) once reviewed —
there is no code path that does this automatically.

Nothing here grants execution — the execution layer checks the live
`venues.execution_allowed` column, and `connectors/betfair/execution.py`
additionally requires `BETFAIR_EXECUTION_ALLOWED=true` in the environment.
Both gates must be green; this table alone changes nothing at runtime.
