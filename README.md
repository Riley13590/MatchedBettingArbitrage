# MatchedBettingArbitrage — MarketEdge UK

Modular quantitative betting-market platform: ingests authorised market data,
normalises it into a canonical schema, detects true arbitrage, and (later)
estimates fair value and manages exchange execution.

Full specification: see the build spec provided at project handoff. This
repository implements it milestone by milestone — see `docs/STATUS.md` for
current progress.

> **Product boundary.** Personal-use market-data, arbitrage, value-analysis
> and exchange-execution tooling. No CAPTCHA solving, geoblock/operator-control
> bypass, browser automation of bookmaker accounts, or credential sharing.
> Execution is disabled by default and gated per-venue by explicit capability
> and eligibility checks (see `marketedge/domain/models.py::VenueCapability`).

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

- API: http://localhost:8000/v1/health
- Web dashboard: http://localhost:5173
- Postgres: localhost:5432
- Redis: localhost:6379

## Repository layout

```text
apps/api/          FastAPI gateway (routes only — no business logic)
apps/web/          React + TypeScript dashboard shell
marketedge/         Core domain, connectors, ingestion, storage
docs/               Architecture, ADRs, runbooks, status
tests/              unit / integration / contract / replay
scripts/            operational scripts
```

See `docs/architecture.md` for the component diagram and repo-tree rationale,
and `docs/adr/` for key design decisions.

## Development

```bash
make install   # python + node deps
make lint      # ruff + mypy + eslint
make test      # pytest (unit/integration)
make up        # docker compose up
```

## Current milestone status

See `docs/STATUS.md`.
