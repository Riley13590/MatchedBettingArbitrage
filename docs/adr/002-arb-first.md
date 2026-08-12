# ADR 002: Arbitrage Before Value Betting

## Status

Accepted — product roadmap (spec sections 4, 44).

## Context

The system will eventually support two pricing strategies: arbitrage
(deterministic, guaranteed profit given executable prices) and value
betting (positive expected value against an estimated fair price, which
carries model and variance risk). Both need the same underlying
infrastructure: data quality, market matching, fee/commission modelling,
liquidity awareness, latency handling, and execution mechanics.

## Decision

Build and validate arbitrage first (Milestones 1-6), and treat it as the
system's integration test: if the platform cannot correctly identify,
price, and (eventually) execute a deterministic arbitrage after fees and
slippage, it cannot be trusted to run a probabilistic value strategy, where
an equivalent bug would silently look like "bad luck" instead of loudly
failing.

Value betting (Milestone 8+) is only evaluated on calibration and
closing-line value (CLV), never on short-run realised P&L, and never
promoted from paper mode to live stakes based on realised profit alone
(spec section 15, "Promotion rule").

## Consequences

- M1-M3 contain zero value-betting logic beyond empty package stubs
  (`marketedge/pricing`, `marketedge/strategies/value`) — this is
  intentional, not an oversight.
- The arbitrage detector's correctness bar (Gate A, spec section 44:
  deterministic replay, no impossible arb survives fixtures) must be met
  before any value-betting work starts.
- Discovery economics (Gate B) — feed validity, executable £ edge, sample
  size — must also be measured on the arbitrage engine before real-money
  execution work (Milestone 5+) begins, independent of the value engine.
