#!/usr/bin/env python3
"""BTC 4h-ahead point forecast for make.fun btc-cent-forecast-01.

Reads one case at a time: BTC/USDC 1-minute closes for the 72 hours up to a
checkpoint, writes ONE number: the predicted price 240 minutes after it.

Model: shrunk drift blend, in log space.
  1. 12h linear trend of log-price, extrapolated 240 min, shrunk x0.5.
  2. Median 4h log-return over the last 12h, weight 0.5 (a median is the
     MAE-optimal drift estimate and is robust to BTC's fat-tailed jumps).
  3. Blend 60% trend + 40% median drift; cap total drift at +-0.5% so a
     violent trend can never throw the guess far from the last close.
  4. forecast = last_close * exp(drift), rounded to 5 decimals.

Score is mean absolute error in cents, so the conditional median is what
matters, not the mean -- hence the median drift and the heavy shrinkage.
Backtest on the kit's practice window (Nov 7-11, 66 rolling checkpoints +
5 real 4h-ahead practice targets):
  persistence baseline: rolling 40,950c / real5 47,055c
  this model:           rolling 38,232c / real5 42,851c  (~7-9% better)
Caveat: the final is scored on Nov 15-17 prices, a different regime than
the practice window, so the edge may not hold -- but the shrinkage and
the drift cap bound the downside: worst case it is close to persistence.
Stdlib only, deterministic, no network.
"""
import json
import math
import os
import statistics
from pathlib import Path

INPUT_DIR = os.environ.get('MAKEFUN_INPUT_DIR', '/input')
OUTPUT_DIR = os.environ.get('MAKEFUN_OUTPUT_DIR', '/output')

HORIZON = 240            # minutes ahead to forecast
TREND_WINDOW = 720       # minutes of log-price for the linear trend (12h)
TREND_SHRINK = 0.5       # shrinkage on the extrapolated trend
DRIFT_LOOKBACK_H = 12    # hours of trailing 4h returns for the median drift
DRIFT_WEIGHT = 0.5       # weight on the median drift
TREND_MIX = 0.6          # blend weight on the trend component
DRIFT_CAP = 0.005        # cap on total log-drift (+-0.5%)

MIN_PRICE = 0.00001
MAX_PRICE = 9_999_999.99999


def price5(x):
    return round(min(MAX_PRICE, max(MIN_PRICE, x)) * 1e5) / 1e5 + 0.0


def trend_log_drift(prices):
    w = prices[-TREND_WINDOW:] if len(prices) > TREND_WINDOW else prices
    n = len(w)
    if n < 2:
        return 0.0
    logs = [math.log(p) for p in w]
    mx = (n - 1) / 2.0
    my = sum(logs) / n
    num = 0.0
    den = 0.0
    for i, lp in enumerate(logs):
        dx = i - mx
        num += dx * (lp - my)
        den += dx * dx
    slope = num / den if den else 0.0
    return slope * HORIZON * TREND_SHRINK


def median_drift_log(prices):
    rets = []
    start = max(0, len(prices) - HORIZON - DRIFT_LOOKBACK_H * 60)
    for t in range(start, len(prices) - HORIZON, 60):
        rets.append(math.log(prices[t + HORIZON] / prices[t]))
    if not rets:
        return 0.0
    return statistics.median(rets) * DRIFT_WEIGHT


def forecast(prices):
    if not prices:
        raise ValueError('market has no prices')
    last = prices[-1]
    if not (isinstance(last, (int, float)) and math.isfinite(last) and last > 0):
        raise ValueError('last price is not a positive finite number')
    drift = TREND_MIX * trend_log_drift(prices) + (1.0 - TREND_MIX) * median_drift_log(prices)
    drift = max(-DRIFT_CAP, min(DRIFT_CAP, drift))
    return price5(last * math.exp(drift))


def main():
    inp = Path(INPUT_DIR)
    out = Path(OUTPUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(f for f in inp.iterdir() if f.name.endswith('.in'))
    for f in files:
        case_id = f.name[:-3]
        case = json.loads(f.read_text())
        markets = case.get('markets')
        if not isinstance(markets, list) or len(markets) != 1:
            raise ValueError(f'{f.name} does not hold exactly one market')
        price = forecast(markets[0]['prices'])
        (out / f'{case_id}.out').write_text(
            json.dumps({'forecasts': [{'case': case_id, 'price': price}]}) + '\n')


if __name__ == '__main__':
    main()
