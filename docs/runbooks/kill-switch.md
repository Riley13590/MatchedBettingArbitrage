# Runbook: Kill switch

`POST /v1/system/kill-switch` / `POST /v1/system/resume` are stubbed in M1
(`apps/api/routes/settings.py`) and return `501` — there is nothing to kill
yet (no execution capability exists before Milestone 4/5). The endpoint
shape is reserved now so the risk engine (Milestone 4) can implement it
without an API contract change.

Intended behaviour once implemented (spec sections 2.1, 18, 23.3):

1. `kill_switch=true` is checked as pre-trade risk gate #2 (spec section
   18) — no order reaches an execution connector while it is active.
2. Activating the kill switch does not cancel already-open orders by
   itself; that is a separate explicit action once implemented.
3. `kill_switch_active` is exported as a Prometheus gauge from the moment
   the risk engine exists, regardless of whether any strategy is live.
