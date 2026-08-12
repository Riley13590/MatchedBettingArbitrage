# Runbook: Partial fill beyond tolerance

(Spec section 34.2.) Not yet reachable — no execution exists before
Milestone 5. Documented now for forward reference from
`marketedge/execution/` when it is implemented.

1. Cancel remainder if possible.
2. Calculate residual exposure.
3. Determine current hedge price.
4. Compare projected worst-case P&L with configured loss floor.
5. Reprice only if within tolerance.
6. Otherwise surface a high-priority intervention alert.
