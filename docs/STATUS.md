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
  *default enabled sports* config (`SPORTS_ENABLED`) is football/tennis.
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
for the bootstrap markets (football/tennis, configurable) appear and
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

## Next milestone

Milestone 2 — external bookmaker-odds feed + multi-sport discovery
(spec section 28, M2; section 41 for the polling/budget experiment design).
Do not begin real-money execution work before the Milestone 3 discovery
economics are in and Gate B (spec section 44) is reviewed.
