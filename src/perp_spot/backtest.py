"""Backtest orchestration: book comparison, walk-forward and bootstrap.

A single window is one realized path and proves little. The same books are run
over many non-overlapping windows spanning bull, bear and chop regimes, and
results are reported as distributions with bootstrap confidence intervals rather
than a single number.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, metrics, strategy
from .data import Market
from .funding import accrue_funding, funding_apr, holding_window


def run_books(
    market: Market, start, end, *,
    investment: float = config.DEFAULT_INVESTMENT,
    leverage: float = config.DEFAULT_LEVERAGE,
) -> dict[str, strategy.StrategyResult]:
    """Run the spot / levered-perp / delta-neutral-carry books over one window."""
    window = holding_window(market.daily, start, end)
    return {
        "spot": strategy.long_spot(market.daily, window, investment),
        "perp": strategy.long_perp(market.daily, market.funding, window, investment, leverage),
        "carry": strategy.carry_delta_neutral(market.daily, market.funding, window, investment),
    }


def metrics_table(results: dict[str, strategy.StrategyResult]) -> pd.DataFrame:
    """Stack :func:`metrics.summarize` for each book into one comparison table."""
    cols = {res.name: metrics.summarize(res.equity, name=res.name) for res in results.values()}
    table = pd.DataFrame(cols).T
    table["funding_total"] = [res.funding_total for res in results.values()]
    table["liquidated"] = [res.liquidated for res in results.values()]
    return table


def regime_windows(daily: pd.DataFrame, freq: str = "QE") -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Non-overlapping calendar windows (default: quarter-end) covering the data.

    Non-overlapping quarters give roughly independent samples across regimes,
    rather than overlapping sub-windows of the same trend.
    """
    dates = pd.DatetimeIndex(daily["date"])
    period_freq = freq[0] if freq in {"QE", "ME", "YE"} else freq
    periods = dates.tz_localize(None).to_period(period_freq)
    windows = []
    for p in periods.unique():
        sub = dates[periods == p]
        if len(sub) >= 5:  # skip stub windows
            windows.append((sub.min(), sub.max()))
    return windows


def walk_forward(
    market: Market, *, freq: str = "QE",
    investment: float = config.DEFAULT_INVESTMENT,
    leverage: float = config.DEFAULT_LEVERAGE,
) -> pd.DataFrame:
    """Run all books over each non-overlapping window; one tidy row per (window, book)."""
    rows = []
    for start, end in regime_windows(market.daily, freq):
        books = run_books(market, start, end, investment=investment, leverage=leverage)
        window = holding_window(market.daily, start, end)
        fwin = market.funding[
            (market.funding["funding_time"] > window.open_ts)
            & (market.funding["funding_time"] <= window.close_ts)
        ]
        apr = funding_apr(fwin)
        for res in books.values():
            m = metrics.summarize(res.equity, name=res.name)
            rows.append({
                "symbol": market.symbol,
                "window_start": start, "window_end": end,
                "strategy": res.name,
                "total_return": m["total_return"],
                "sharpe": m["sharpe"],
                "max_drawdown": m["max_drawdown"],
                "funding_apr": apr,
                "liquidated": res.liquidated,
            })
    return pd.DataFrame(rows)


def block_bootstrap(
    returns: pd.Series, *,
    statistic=metrics.sharpe,
    block_size: int | None = None,
    n_resamples: int | None = None,
    confidence: float | None = None,
    seed: int | None = None,
) -> dict:
    """Stationary block bootstrap of a statistic over a daily return series.

    Resamples contiguous blocks (preserving autocorrelation) to build a sampling
    distribution and a percentile confidence interval for ``statistic``.
    """
    cfg = config.BOOTSTRAP
    block_size = block_size or cfg.block_size
    n_resamples = n_resamples or cfg.n_resamples
    confidence = confidence or cfg.confidence
    seed = cfg.seed if seed is None else seed

    r = pd.Series(returns).dropna().to_numpy()
    n = r.size
    if n < block_size * 2:
        return {"point": float(statistic(pd.Series(r))) if n else float("nan"),
                "lo": float("nan"), "hi": float("nan"), "n": n}

    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block_size))
    stats_out = np.empty(n_resamples)
    starts_pool = n - block_size + 1
    for i in range(n_resamples):
        starts = rng.integers(0, starts_pool, size=n_blocks)
        sample = np.concatenate([r[s:s + block_size] for s in starts])[:n]
        stats_out[i] = statistic(pd.Series(sample))

    alpha = (1.0 - confidence) / 2.0
    return {
        "point": float(statistic(pd.Series(r))),
        "lo": float(np.nanquantile(stats_out, alpha)),
        "hi": float(np.nanquantile(stats_out, 1.0 - alpha)),
        "mean": float(np.nanmean(stats_out)),
        "n": n,
    }


def break_even_funding(
    market: Market, start, end, *,
    investment: float = config.DEFAULT_INVESTMENT,
    leverage: float = config.DEFAULT_LEVERAGE,
) -> float:
    """Funding APR at which the levered long's net P&L equals the spot long's.

    Solves for the average funding rate that erases the leverage edge over the
    window, given the realized price path — i.e. "how expensive must funding get
    before leverage stops paying?".
    """
    window = holding_window(market.daily, start, end)
    spot = strategy.long_spot(market.daily, window, investment)
    perp = strategy.long_perp(market.daily, market.funding, window, investment, leverage)
    size = perp.meta["size"]
    realized_funding = accrue_funding(market.funding, size, window)
    # perp.pnl already nets realized funding; add it back to get gross, then find
    # the funding total that brings gross down to the spot pnl.
    gross_perp = perp.pnl + realized_funding.total
    edge = gross_perp - spot.pnl  # extra dollars leverage earned before funding
    # Average notional over the window (funding accrues on notional).
    avg_notional = float((size * window.bars["perp_close"]).mean())
    n = max(realized_funding.n_settlements, 1)
    breakeven_rate = edge / (avg_notional * n)
    return breakeven_rate * config.FUNDING_SETTLEMENTS_PER_YEAR
