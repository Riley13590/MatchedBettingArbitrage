# ADR 003: Execution Service Isolation

## Status

Accepted — Milestone 0/1 scaffolding, enforced from Milestone 5 onward.

## Context

Exchange execution is the most safety-critical subsystem: a bug in the
frontend, API gateway, or a strategy module must never be able to place,
cancel, or replace a real order. Spec section 5.1 explicitly calls for
isolating the execution worker; section 24 requires it be reachable only on
a private network.

## Decision

1. `worker-execution` will be a separate deployable service/container from
   `api` and `worker-ingest`, added to `docker-compose.yml` when Milestone 5
   introduces real order placement. Only it will hold exchange execution
   credentials (`BETFAIR_APP_KEY` + cert/key paths). Until then, no service
   in `docker-compose.yml` receives execution credentials at all —
   `worker-ingest` only reads `BETFAIR_APP_KEY`/cert paths for market-data
   calls, which Betfair's API also requires for read-only endpoints, and
   never receives write-capable credentials because none exist yet.
2. `apps/api` (the FastAPI gateway) never calls a vendor execution API
   directly. In M1 there is no execution capability at all —
   `apps/api/routes/orders.py` returns `501 Not Implemented` for every
   route. When execution lands (Milestone 5), the API will only be able to
   reach the execution worker through an internal, non-public interface,
   and every order still requires a prior `RiskDecision.approved=True`
   (spec section 18) — the risk engine itself runs outside the execution
   worker so a compromised or buggy execution process cannot forge its own
   approval.
3. `connectors/betfair/execution.py` is a protocol-shaped stub in M1: it
   type-checks against `ExecutionConnector` but every method raises
   `ExecutionDisabledError` unless both (`venues.execution_allowed=true`
   in Postgres) and (`BETFAIR_EXECUTION_ALLOWED=true` in the execution
   worker's environment) are true. Both are false by default.
4. No code path in this repository can flip either gate at runtime; both
   require a human editing configuration/environment and redeploying.

## Consequences

- Milestones 0-4 can be developed, tested, and demoed with zero exchange
  credentials in `api` or `worker-ingest` at all.
- When Milestone 5 adds real order placement, the blast radius of an API or
  strategy bug is bounded: it can at most request an order through the
  execution worker's interface, which independently re-validates risk.
- Slightly more deployment complexity (one more service) is accepted
  deliberately, per spec section 17's framing of execution as the highest
  safety-criticality subsystem.
