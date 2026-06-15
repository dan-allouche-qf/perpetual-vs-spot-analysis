"""Funding accrual, funding APR and the perp-spot basis.

A single :class:`HoldingWindow`, derived from the price bars actually held, is the
source of truth for both the price legs and the funding accrual, so the two never
drift apart. Funding accrues strictly inside ``(open_ts, close_ts]`` — exclusive
at the open instant (a position opened exactly on a settlement does not pay it),
inclusive at the close — which matches how a perp position is actually charged.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import config


@dataclass(frozen=True)
class HoldingWindow:
    """The single source of truth for a position's life, derived from price bars.

    A position opens at the OPEN of the first bar on/after ``start`` and closes at
    the CLOSE of the last bar on/before ``end``. ``open_ts`` is that first bar's
    open instant; ``close_ts`` its last bar's close instant (next midnight).
    """

    open_ts: pd.Timestamp
    close_ts: pd.Timestamp
    open_row: pd.Series
    close_row: pd.Series
    bars: pd.DataFrame  # the daily rows actually held (inclusive of both ends)


def _to_utc(ts) -> pd.Timestamp:
    """Coerce a date-like (naive or tz-aware) to a UTC Timestamp."""
    ts = pd.Timestamp(ts)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def holding_window(daily: pd.DataFrame, start, end) -> HoldingWindow:
    """Build the holding window from the aligned daily frame for [start, end]."""
    start = _to_utc(start)
    end = _to_utc(end)
    if start >= end:
        raise ValueError("start must be before end")
    bars = daily[(daily["date"] >= start) & (daily["date"] <= end)]
    if bars.empty:
        raise ValueError(f"No price bars in window {start.date()}..{end.date()}")
    open_row = bars.iloc[0]
    close_row = bars.iloc[-1]
    open_ts = open_row["date"]
    # A daily bar opened at 00:00 closes one day later; that close instant is the
    # exit time and the inclusive upper bound for funding accrual.
    close_ts = close_row["date"] + pd.Timedelta(days=1)
    return HoldingWindow(open_ts, close_ts, open_row, close_row, bars)


@dataclass(frozen=True)
class FundingResult:
    total: float          # net funding cash flow (>0 = longs PAID)
    n_settlements: int
    avg_rate: float       # mean funding rate per 8h over the window
    apr: float            # annualized funding rate (rate * settlements/yr)
    series: pd.Series     # per-settlement funding amount, indexed by funding_time


def accrue_funding(
    funding: pd.DataFrame,
    position_size: float,
    window: HoldingWindow,
) -> FundingResult:
    """Sum funding over settlements strictly inside ``(open_ts, close_ts]``.

    For each settlement *i*: ``amount_i = mark_price_i * position_size * rate_i``.
    A positive rate means longs pay shorts, so for a long perp this is a cost
    (``total > 0``); a negative rate means longs *receive* (``total < 0``). The
    sign is handled purely by arithmetic, so a funding-income regime needs no
    special-casing — which is exactly what the carry strategy relies on.
    """
    if funding.empty or "funding_time" not in funding.columns:
        return FundingResult(0.0, 0, 0.0, 0.0, pd.Series(dtype=float))

    mask = (funding["funding_time"] > window.open_ts) & (
        funding["funding_time"] <= window.close_ts
    )
    sub = funding.loc[mask]
    if sub.empty:
        return FundingResult(0.0, 0, 0.0, 0.0, pd.Series(dtype=float))

    notional = sub["mark_price"] * position_size
    amounts = (notional * sub["funding_rate"]).to_numpy()
    series = pd.Series(amounts, index=sub["funding_time"].to_numpy(), name="funding_amount")
    avg_rate = float(sub["funding_rate"].mean())
    return FundingResult(
        total=float(series.sum()),
        n_settlements=int(len(sub)),
        avg_rate=avg_rate,
        apr=avg_rate * config.FUNDING_SETTLEMENTS_PER_YEAR,
        series=series,
    )


def funding_apr(funding: pd.DataFrame) -> float:
    """Annualized funding rate over the whole funding frame (mean rate * 1095)."""
    if funding.empty:
        return 0.0
    return float(funding["funding_rate"].mean()) * config.FUNDING_SETTLEMENTS_PER_YEAR


def cumulative_funding_apr(funding: pd.DataFrame, window: int = 90) -> pd.Series:
    """Rolling annualized funding rate (per-settlement), useful as a carry signal."""
    if funding.empty:
        return pd.Series(dtype=float)
    roll = funding.set_index("funding_time")["funding_rate"].rolling(window * 3).mean()
    return roll * config.FUNDING_SETTLEMENTS_PER_YEAR
