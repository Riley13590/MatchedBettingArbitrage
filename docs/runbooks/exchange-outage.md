# Runbook: Exchange disconnect while exposed

(Spec section 34.1.) Not yet operationally exercised — no live exposure is
possible until Milestone 5+. Documented now so the ingestion connector's
reconnect behaviour (`marketedge/connectors/betfair/stream.py`) is built
against it from the start.

1. Freeze new orders.
2. Mark connector degraded (`connector_up{venue="betfair"}` → 0).
3. Query REST current orders/balances if available.
4. Reconcile known order IDs.
5. If state remains unknown, require manual intervention.
6. Do not restart automatic strategies until state is consistent.
