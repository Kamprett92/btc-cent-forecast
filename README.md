# BTC 4h-ahead point forecast — make.fun btc-cent-forecast-01

Forecasts Bitcoin's USD price 240 minutes after each checkpoint, from the
last 72 hours of 1-minute closes. Score is mean absolute error in cents
against the actual close; the house baseline is persistence (the
checkpoint's own close), and a prize needs a lower score than it.

## Model: shrunk drift blend (log space)

1. **12h linear trend** of log-price, extrapolated 240 min, shrunk x0.5.
2. **Median 4h log-return** over the last 12h, weight 0.5. For MAE scoring
   the conditional *median* is the right target, and the median is robust
   to BTC's fat-tailed jumps.
3. **Blend 60% trend + 40% median drift**, total drift capped at ±0.5%,
   so a violent trend can never throw the guess far from the last close.
4. `forecast = last_close * exp(drift)`, rounded to 5 decimals.

## Backtest (kit practice window, Nov 7–11)

- Rolling 66 checkpoints: model 38,232c vs persistence 40,950c (~7% better)
- Real 5 practice targets: model 42,851c vs persistence 47,055c (~9% better,
  wins 4 of 5 — the miss, p03, was a sharp reversal)

Caveat: the final is scored on Nov 15–17 prices, a different regime than
the practice window, so the edge may not hold. The shrinkage and drift cap
bound the downside: worst case it is close to persistence.

## Format

Input: `{"schema":"makefun/btc-cent-case/v1","case","at","horizon_minutes",
"markets":[{"id":"btc-usdc","prices":[...4320 closes...]}]}`

Output: `{"forecasts":[{"case":"<id>","price":<number>}]}` — exactly one row.

Stdlib only, deterministic, offline, well under the 8s/case cap.
