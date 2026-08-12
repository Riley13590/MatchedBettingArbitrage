# Status

## Milestone 0 — Project skeleton: COMPLETE

- Monorepo layout matches `docs/architecture.md`.
- `docker-compose.yml` brings up `postgres`, `redis`, `api`, `worker-ingest`,
  `web`.
- FastAPI `GET /v1/health` returns service status.
- React + TypeScript (Vite) shell renders and polls `/v1/health`.
- PostgreSQL schema (spec section 8, full) managed via SQLAlchemy 2 models +
  Alembic; one migration (`0001_initial_schema`).
- Redis wired for the M1 latest-quote cache.
- CI (`.github/workflows/ci.yml`): ruff, mypy, pytest for Python; eslint +
  tsc + build for the web app.

**How to run:**

```bash
cp .env.example .env
docker compose up --build
curl http://localhost:8000/v1/health
```

**Tests run:** `pytest tests/unit` (odds/money/mapper), `pytest tests/contract`
(Betfair fixture parsing).

**Known gaps:** no auth on the API yet (no mutating endpoints exist to
protect); `quotes` not partitioned; no live integration test against real
Betfair endpoints (by design — contract tests use sanitised fixtures).

## Milestone 1 — Canonical model + one exchange feed: COMPLETE

- `marketedge/domain`: `CanonicalEvent`, `CanonicalMarket`,
  `CanonicalSelection`, `Quote`, `VenueCapability` (spec 7.1-7.3, exact).
- `marketedge/connectors/base.py`: `MarketDataConnector` /
  `ExecutionConnector` protocols (spec section 9, exact).
- `marketedge/connectors/betfair`: certificate-login client
  (`client.py`), JSON-RPC `listEventTypes` / `listCompetitions` /
  `listEvents` / `listMarketCatalogue` / `listMarketBook`, a real Exchange
  Stream API client over TLS (`stream.py`, newline-delimited JSON protocol,
  `authentication` + `marketSubscription` messages, heartbeat handling),
  and a vendor→canonical `mapper.py`. `list_events` enumerates event types
  from Betfair rather than hard-coding football/tennis IDs — only the
  *default enabled sports* config (`SPORTS_ENABLED`) is `Soccer`/`Tennis`
  (matched against each connector's own catalogue naming, not a private
  taxonomy — see `docs/architecture.md` §6 note 7).
- `marketedge/ingestion`: orchestrator wires the connector's
  `stream_quotes()` (falls back to polling `list_quotes` if streaming is
  unavailable) into `quote_processor`, which writes latest quotes to Redis
  and appends every quote to Postgres.
- `marketedge/storage/repositories`: venues/events/markets/selections/quotes
  repositories used by both ingestion and the API.
- API: `GET /v1/venues`, `GET /v1/events`, `GET /v1/markets/{id}` read from
  Postgres/Redis.
- Web: dashboard lists live events and best-price quotes, polling the API.
- Execution: `connectors/betfair/execution.py` exists as a protocol-shaped
  stub; refuses to run unless `venues.execution_allowed=true` **and**
  `BETFAIR_EXECUTION_ALLOWED=true`. Neither is set by default. No order can
  be placed in M1 — there is no caller of `ExecutionConnector` yet
  (Milestone 5).

**Exit criteria check (spec section 28, Milestone 1):** live Betfair prices
for the bootstrap markets (Soccer/Tennis, configurable) appear and
persist via `docker compose up` + real `BETFAIR_*` credentials in `.env`;
without credentials the stack still starts cleanly in `PAPER` mode with the
connector reporting `connector_up{venue="betfair"}=0` and no ingestion
error loop. The connector enumerates sports/markets from Betfair's
catalogue endpoints at runtime rather than hard-coding them.

**How to verify locally:**

```bash
docker compose up --build
curl http://localhost:8000/v1/venues
curl http://localhost:8000/v1/events
pytest tests/unit tests/contract
```

**Tests run:** unit tests for `domain/odds.py`, `domain/money.py`, and the
Betfair mapper; contract tests replaying sanitised
`tests/fixtures/betfair_*.json` payloads through `client.py`'s parsing and
`mapper.py`; a deterministic replay test in `tests/replay/` feeding a fixed
quote sequence through the ingestion pipeline and asserting the same rows
land in the (test) database.

**Known gaps / explicitly deferred (see `docs/architecture.md` §5):** no
bookmaker odds feed (Milestone 2), no market matching beyond a single venue
(nothing to match against yet), no arbitrage detection (Milestone 3), no
risk engine or execution enablement (Milestones 4-5), Stream API
reconnect/backoff is basic (exponential backoff only, no circuit breaker
metrics yet — tracked for Milestone 4 alongside `connector_up`).

## Milestone 2 — External bookmaker-odds feed + multi-sport discovery: COMPLETE

- `marketedge/connectors/odds_provider`: client for The Odds API (spec
  section 41.1's named reference provider) — `list_sports()` discovers the
  sport catalogue dynamically at runtime (never hard-coded), `get_odds()`
  fetches one sport's full bundled snapshot (every bookmaker, every market,
  every price) in a single call, and every response's `x-requests-*`
  headers are captured as `RequestUsage`. Deliberately does **not**
  implement the `MarketDataConnector` protocol — see
  `docs/architecture.md` §5 for why forcing a bundled-response API through
  the Betfair-shaped waterfall would multiply metered costs.
- `marketedge/connectors/drafts.py`: `EventDraft`/`MarketDraft`/
  `RunnerDraft`/`QuoteDraft` extracted from the Betfair mapper into a
  shared module both connectors' mappers now use.
- `marketedge/matching`: real implementation, no longer a stub —
  `aliases.py` (pure fuzzy participant-name normalisation),
  `alias_resolver.py` (DB-backed override layer, spec 11.2),
  `confidence.py` (spec 11.3's scoring formula, exact weights),
  `event_matcher.py` (0.98 auto-match / 0.90 review / below reject gates),
  `selection_matcher.py` (assigns HOME/AWAY/DRAW/OVER/UNDER/YES/NO
  consistently within one vendor's own naming, which is what lets two
  vendors' selections converge on the same canonical row).
- `EventRepository.upsert_from_vendor` now searches existing canonical
  events (same sport, ±6h) for a match before creating a new one — a
  Betfair event and the equivalent odds-provider event for the same
  fixture converge onto one canonical `events` row instead of duplicating
  it per venue. Verified directly in
  `tests/integration/test_cross_venue_matching.py`.
- Every bookmaker The Odds API returns becomes its own dynamically-created
  venue (`oddsapi:<key>`, `VenueRepository.upsert_bookmaker`) —
  `data_allowed=true`, `execution_allowed=false` always, `geo_status`/
  `terms_status` start `UNVERIFIED` (see `docs/venue-matrix.md`).
- `marketedge/ingestion/discovery_scheduler.py`: adaptive per-sport
  polling (spec 41.3's `>24h`/`6-24h`/`1-6h`/`<1h` buckets, configurable
  via `.env`).
- `marketedge/ingestion/budget.py` + `api_usage` table: every metered
  request recorded with credits used/remaining; monthly soft/hard budget
  caps (spec 41.2/41.6) — the odds-provider loop defers non-urgent sports
  past the soft cap and stops discovery entirely at the hard cap rather
  than erroring.
- `marketedge/ingestion/odds_provider_ingestion.py`: the scheduler-driven
  loop tying the above together; `orchestrator.py` now runs it concurrently
  with Betfair ingestion (`asyncio.gather`) — either source idling because
  it isn't configured never stops the other.
- Migration `0002_odds_provider_and_matching`: `api_usage`,
  `participant_aliases` tables.
- API: `GET /v1/events` now returns `match_confidence`/`needs_review` per
  event; new `GET /v1/analytics/api-usage` (credits used this month, by
  sport, provider-reported remaining, budget status) — spec 41.2's
  dashboard requirements.
- Web: dashboard shows a match-confidence badge per event and an
  API-budget card with a progress bar and per-sport credit breakdown.
- `scripts/seed_aliases.py`: bootstraps a small set of known Premier
  League naming variants into `participant_aliases`.

**Exit criteria check (spec section 28, Milestone 2):** "equivalent
bookmaker and exchange markets are safely joined across multiple supported
sports" — proven directly by
`tests/integration/test_cross_venue_matching.py` (a Betfair sighting and an
odds-provider sighting of the same fixture converge to one canonical event
and one canonical selection despite different vendor IDs and runner
naming; an unrelated fixture at a similar time never merges). "The system
can report API-credit usage and quote freshness by sport/market" — `GET
/v1/analytics/api-usage` and the `api_usage` table satisfy the credit-usage
half; per-quote freshness (`quote.age_ms`) was already available from M1
and is now attributable per sport via `ResolvedQuote.sport`.

**How to verify locally:**

```bash
docker compose up --build
curl http://localhost:8000/v1/events              # match_confidence per event
curl http://localhost:8000/v1/analytics/api-usage
pytest tests/unit tests/contract tests/integration tests/replay
```

**Tests run:** unit tests for `matching/aliases.py`, `matching/confidence.py`,
`matching/event_matcher.py`, `matching/selection_matcher.py`, and the
odds-provider mapper; contract tests replaying sanitised
`tests/fixtures/oddsapi_*.json` payloads through the real client + mapper;
integration tests proving cross-venue event/selection joining and that
unrelated events never merge (against a real Postgres, migrations 0001+0002
applied). Full suite: 61 tests passing.

**Known gaps / explicitly deferred (see `docs/architecture.md` §6):** no
review UI to promote a confirmed `REVIEW`-band match into a permanent
alias-table row (API surfaces `needs_review`, nothing writes back yet);
bookmaker geo/terms status is `UNVERIFIED` until manually reviewed per
book; competition-name mismatches between Betfair and The Odds API are a
known source of lower (but usually still passing) match confidence; no
exchange-triggered bookmaker refresh yet (spec section 41.4 — material
Betfair price moves don't yet trigger an out-of-cycle odds-provider poll);
totals/handicap line extraction is best-effort (spreads take the first
outcome's point) since the default config only enables `h2h` markets.

## Milestone 3 — Arbitrage detector in paper mode + economics instrumentation: COMPLETE

- `marketedge/strategies/arbitrage/dutching.py`: spec §13.1's multi-way
  dutching, stakes rounded to money, `worst_case_profit` = minimum net
  outcome P&L across all outcomes. Hypothesis property test proves stakes
  equalise returns within rounding tolerance for arbitrary bankroll/odds.
- `marketedge/strategies/arbitrage/back_lay.py`: spec §13.2's back-lay
  hedge — deliberately implemented as two independent cash-flow functions
  (`profit_if_selection_wins`/`profit_if_selection_loses`), with the hedge
  stake *derived* by setting them equal and solving, not copied from the
  spec formula. Hypothesis property test proves the two outcomes converge
  for any valid back/lay odds and commission rate.
- `marketedge/strategies/arbitrage/fees.py`: venue commission model
  (bootstrap rates, explicitly flagged as unvalidated against real venue
  statements per spec §33) — commission taxes net winnings only, never a
  loss.
- `marketedge/strategies/arbitrage/detector.py`: pure detection given an
  already-fetched quote snapshot — `detect_dutching` (best BACK price per
  outcome, any venue) and `detect_back_lay_for_selection` (bookmaker BACK
  vs exchange LAY for one outcome). Both apply the capital solver (spec
  §31's `capital_solver.apply_limits` — maximum bankroll every leg's
  liquidity supports), net-of-fee worst-case profit, and every configured
  filter (`ARBITRAGE_MIN_NET_ROI`/`MIN_PROFIT_GBP`/`MAX_QUOTE_AGE_MS`/
  `MIN_SECONDS_TO_START`/`IN_PLAY`, spec §13.4 exact filter set) before
  returning an opportunity.
- `marketedge/strategies/arbitrage/runner.py`: a new `worker-strategy`
  service scans known markets every 5 seconds, builds the latest-quote
  snapshot per selection from Postgres, runs both detectors, persists new
  opportunities, and — the arb-lifetime/survival-curve deliverable —
  closes any previously-open opportunity the moment a scan cycle no longer
  re-detects it, recording `lifetime_ms` and a best-effort feed-validity
  classification (`PRICE_MOVED` when the market was still reachable and
  simply stopped arbing; honestly `UNKNOWN`, not a guess, when the market
  fell out of the scan set entirely).
- Migration `0003`: `opportunities` gains segment fields (`sport`,
  `competition`, `market_family`, `venues`, `time_to_start_bucket`),
  economics fields (`quote_age_ms_at_detection`, `executable_stake_gbp`,
  `executable_edge_gbp`, `lifetime_ms`), and feed-validity fields
  (`verification_outcome`, `verified_at`, `verified_bookmaker_price`,
  `verified_exchange_price`) — spec §40.5/§41.5/§42.
- API: `GET /v1/opportunities` (real data, was a 501 stub),
  `GET /v1/opportunities/{id}` (includes the full leg snapshot),
  `GET /v1/opportunities/segments` — spec §40.5's segment ranking, ordered
  by `total_executable_edge_gbp` (spec §40.4's primary commercial-
  usefulness metric), not raw count or raw ROI.
- Web: opportunities table showing net ROI, worst-case £, executable £
  edge, quote age, status and observed lifetime per opportunity.
- `docker-compose.yml`: new `worker-strategy` service running
  `python -m marketedge.strategies.arbitrage.runner`, with no execution
  credentials (same isolation pattern as `worker-ingest` —
  docs/adr/003-execution-isolation.md).

**Exit criteria check (spec section 28, Milestone 3):** "paper
opportunities are mathematically reproducible with exact outcome P&L" —
proven by `tests/replay/test_replay_arbitrage.py` (identical input snapshot
run through the detector twice produces identical ROI/profit/leg figures)
and by the Hypothesis property tests on the underlying dutching/back-lay
math. "Every opportunity carries enough telemetry to determine whether it
was economically executable, not merely theoretically profitable" — every
persisted row carries `executable_stake_gbp`/`executable_edge_gbp`
(liquidity-bounded, not just the theoretical bankroll figure),
`quote_age_ms_at_detection`, and a `lifetime_ms`/`verification_outcome`
once closed — verified end-to-end against a real Postgres in
`tests/integration/test_arbitrage_runner.py`.

**How to verify locally:**

```bash
docker compose up --build
curl http://localhost:8000/v1/opportunities
curl "http://localhost:8000/v1/opportunities/segments?hours=24"
pytest tests/unit tests/replay tests/integration
```

**Tests run:** unit + Hypothesis property tests for dutching/back-lay/fees;
unit tests for the detector against hand-built quote snapshots (arb found,
no-arb, missing price, stale quote, liquidity-capped bankroll, below
min-profit); replay tests proving detector determinism; integration tests
against a real Postgres proving the runner detects, persists exactly once
per open opportunity (no duplicate rows across scan cycles), and correctly
closes + timestamps an opportunity once prices move. Full suite: 88 tests
passing.

**Known gaps / explicitly deferred:** no manual/secondary verification
workflow yet (spec §41.5's `verified_bookmaker_price`/
`verified_exchange_price`/`verified_at` columns exist but nothing populates
them — only the automatic `PRICE_MOVED`/`UNKNOWN` classification runs);
`MARKET_SUSPENDED`/`BAD_MAPPING`/`INSUFFICIENT_LIQUIDITY`/`STALE_FEED`
outcomes are defined but not yet automatically assigned; fee/commission
rates are bootstrap defaults, not validated against real venue statements
(spec §33's data-quality gate); no arb-survival-curve dashboard (2s/5s/
10s/30s buckets) — the raw `lifetime_ms` data needed for it is now
recorded, but the aggregation/chart isn't built; the runner does a full
scan every 5 seconds rather than reacting to individual quote updates,
which is adequate at current data volumes but not the event-driven design
spec section 31's pseudocode implies; `confidence` on every arbitrage
opportunity is a placeholder `1.0` (arb math has no model uncertainty,
unlike value betting where this field will carry real meaning in
Milestone 8).

## Next milestone

Milestone 4 — risk engine (spec section 28, M4): freshness, liquidity,
exposure, daily limits, duplicate checks, kill switch. No execution
capability exists yet regardless, but the risk engine is the prerequisite
gate spec section 18 requires before Milestone 5 can add real order
placement. Do not begin real-money execution work before Gate B (spec
section 44 — discovery economics) is reviewed against live data.
