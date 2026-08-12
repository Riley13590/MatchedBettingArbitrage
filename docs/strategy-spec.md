# Strategy Spec

## Arbitrage (Milestone 3 — implemented, paper mode only)

Two arb families, both in `marketedge/strategies/arbitrage/`:

### Multi-way dutching (`dutching.py`, `detector.py::detect_dutching`)

For a canonical market's `N` mutually exclusive outcomes, take the best
executable BACK price for each outcome — regardless of which venue it came
from, so a dutch can legitimately span multiple bookmakers plus exchanges
(spec section 13.1's "multi-book"):

```text
inv_sum = Σ (1 / O_i)
arbitrage exists iff inv_sum < 1
stake_i = bankroll * (1/O_i) / inv_sum   (rounded to money)
```

The detector then:

1. Solves for the maximum bankroll every leg's liquidity can actually
   support (`max_executable_bankroll` — spec 13.1's "capital_solver"),
   capped by `ARBITRAGE_DEFAULT_BANKROLL_GBP`.
2. Computes worst-case profit **net of each leg's own venue commission**
   (`fees.py` — bookmakers pay zero commission, exchanges pay commission
   on net winnings only, never on a loss).
3. Rejects the opportunity unless it survives every configured filter
   (`ARBITRAGE_MIN_NET_ROI`, `ARBITRAGE_MIN_PROFIT_GBP`,
   `ARBITRAGE_MAX_QUOTE_AGE_MS`, `ARBITRAGE_MIN_SECONDS_TO_START`,
   `ARBITRAGE_IN_PLAY`) — spec section 13.4, exact filter set.

### Back-lay (`back_lay.py`, `detector.py::detect_back_lay_for_selection`)

For one outcome: back a bookmaker's price, lay the same outcome on an
exchange. The hedge stake is *derived*, not copied from the spec, by
setting the win-case and lose-case cash-flow equations equal and solving
for `lay_stake` (see `back_lay.py`'s docstring for the algebra) — which
lands on spec section 13.2's formula:

```text
lay_stake = (back_stake * back_odds) / (lay_odds - commission_rate)
```

Both `profit_if_selection_wins` and `profit_if_selection_loses` are unit
tested independently, plus a Hypothesis property test asserting they
converge for any valid input — spec 13.2's explicit ask ("tested cash-flow
equations rather than hardcoding a copied formula").

### Fee model (`fees.py`)

Bootstrap commission rates (`DEFAULT_FEE_MODELS`) — **not yet validated
against actual venue statements**, which spec section 33's data-quality
gate requires before any live use:

```text
betfair:   5%
smarkets:  2%
matchbook: 2%
bookmakers (oddsapi:*): 0%
unlisted venue: 0% (conservative — never overstates profit)
```

### Persistence + economics telemetry

Every surviving opportunity is written to `opportunities` (spec section
8.2 core columns) plus the Milestone 3 telemetry columns added in
migration `0003`: `sport`, `competition`, `market_family`, `venues`,
`time_to_start_bucket`, `quote_age_ms_at_detection`,
`executable_stake_gbp`, `executable_edge_gbp`, `lifetime_ms`,
`verification_outcome` — enough to answer "was this economically
executable, not merely theoretically profitable" per the Milestone 3 exit
criteria, and to rank segments by spec section 40.4's
`executable_edge_gbp = net_worst_case_roi * max_executable_size` rather
than raw ROI or raw count.

### Lifetime tracking + feed-validity classification

`runner.py` (`ArbitrageRunner`) scans known markets every 5 seconds,
keeping an in-memory map of currently-open opportunities keyed by
`(market_id, kind)`. An opportunity is closed — `status=EXPIRED`,
`lifetime_ms` recorded — the moment a scan cycle no longer re-detects it.
Classification (spec section 41.5) is deliberately conservative: `
PRICE_MOVED` when the market was still reachable this cycle and simply
stopped being an arb (the common, knowable case); `UNKNOWN` when the
market fell out of the scan set entirely (event started, dropped past the
horizon) and the real reason can't be distinguished from the data
available. `MARKET_SUSPENDED`, `BAD_MAPPING`, `INSUFFICIENT_LIQUIDITY`,
`STALE_FEED` are defined in the spec's classification but not yet
automatically assigned — spec section 41.5 also describes a
manual/secondary verification step (`verified_bookmaker_price`,
`verified_exchange_price`, `verified_at` columns exist and are reserved
for it), which is not built yet.

## Fair value / CLV (Milestone 8 — not started)

See spec sections 14-15 for the authoritative formulas when this lands.

## Stake sizing beyond dutching (Milestone 8 — not started)

See spec section 16 (fractional Kelly, bankroll caps) when value betting
lands.
