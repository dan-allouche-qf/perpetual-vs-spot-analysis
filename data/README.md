# Data snapshot

The Parquet files under `raw/` are a committed snapshot so the notebooks run
**offline** and reproduce identically — including from US IPs, where the live
`api.binance.com` endpoint returns HTTP 451.

## Source

All data is downloaded from **[data.binance.vision](https://data.binance.vision)**,
Binance's public, geo-neutral historical dump (monthly CSV archives):

| File | Endpoint | Schema (parsed) |
|------|----------|-----------------|
| `<sym>_spot.parquet` | `spot/monthly/klines/<SYM>/1d` | `date, open, high, low, close, volume` |
| `<sym>_perp.parquet` | `futures/um/monthly/klines/<SYM>/1d` | `date, open, high, low, close, volume` |
| `<sym>_funding.parquet` | `futures/um/monthly/fundingRate/<SYM>` + `markPriceKlines/<SYM>/8h` | `funding_time, funding_rate, mark_price` |

The funding mark price at each 8h settlement is taken from the 8h
`markPriceKlines` bar, matched to the (≈1ms-jittered) funding timestamp with a
nearest-`merge_asof`; the handful of missing mark bars (<0.6% of settlements)
are interpolated from time-adjacent bars.

## Coverage

- Symbols: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`
- Window: `2021-01-01` → `2024-12-31` (spans the 2021 bull, the 2022 bear and the
  2023–2024 recovery — multiple regimes, not one window)
- Granularity: daily klines (1461 bars/symbol) + 8h funding (~4383 settlements/symbol)

## Rebuild

```bash
make data                      # all symbols, from data.binance.vision
python -m scripts.fetch_data --symbols BTCUSDT --source api   # REST fallback
```
