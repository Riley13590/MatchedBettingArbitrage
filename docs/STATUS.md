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

## Next milestone

Milestone 3 — arbitrage detector in paper mode + economics instrumentation
(spec section 28, M3; section 42 for the mandatory arb-economics metrics).
Do not begin real-money execution work before the Milestone 3 discovery
economics are in and Gate B (spec section 44) is reviewed.
