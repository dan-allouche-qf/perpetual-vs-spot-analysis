"""The three position books, each returning a daily mark-to-market equity path.

Every book is marked to market each day, so the intra-window path — and therefore
drawdown and liquidation — is visible rather than just the endpoints. All three
take their data as explicit arguments (no module-level globals), so they are pure
and unit-testable.

Books
-----
* :func:`long_spot`            – unlevered buy-and-hold (the baseline).
* :func:`long_perp`            – levered directional long, net of funding, with a
                                 maintenance-margin liquidation guard.
* :func:`carry_delta_neutral`  – the flagship: +spot / -perp, notional-matched,
                                 harvesting funding at ~zero price exposure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config
from .funding import HoldingWindow, accrue_funding


@dataclass
class StrategyResult:
    name: str
    equity: pd.Series                  # daily equity path, indexed by date
    funding_total: float = 0.0         # signed funding cash flow over the window
    fees: float = 0.0                  # total round-trip taker fees paid
    liquidated: bool = False
    liquidation_date: pd.Timestamp | None = None
    meta: dict = field(default_factory=dict)

    @property
    def final_equity(self) -> float:
        return float(self.equity.iloc[-1])

    @property
    def pnl(self) -> float:
        return float(self.equity.iloc[-1] - self.equity.iloc[0])


def _anchor(open_ts: pd.Timestamp, capital: float, bars: pd.DataFrame,
            close_values: np.ndarray, name: str) -> pd.Series:
    """Build an equity path anchored at the posted capital on the open instant.

    Without the anchor, ``equity[0]`` would be the first bar's *close* (already
    including day-0's move), so total_return would be measured off the wrong base.
    We index daily marks at each bar's close (date + 1 day) and prepend
    ``(open_ts, capital)`` so total_return = final / capital - 1 is exact.
    """
    close_idx = pd.DatetimeIndex(bars["date"]) + pd.Timedelta(days=1)
    idx = pd.DatetimeIndex([open_ts]).append(close_idx)
    vals = np.concatenate([[capital], close_values])
    return pd.Series(vals, index=idx, name=name)


def _daily_cum_funding(funding: pd.DataFrame, window: HoldingWindow,
                       position_size: float) -> pd.Series:
    """Cumulative funding cost attributed to each held day (long convention).

    Positive = a long position PAID. Each 8h settlement is assigned to its UTC
    day, summed, reindexed onto the held bars and cumulated.
    """
    dates = window.bars["date"]
    res = accrue_funding(funding, position_size, window)
    if res.series.empty:
        return pd.Series(0.0, index=dates.to_numpy())
    per_settle = res.series.copy()
    per_settle.index = pd.DatetimeIndex(per_settle.index).normalize()
    per_day = per_settle.groupby(level=0).sum()
    aligned = per_day.reindex(dates.to_numpy(), fill_value=0.0)
    return aligned.cumsum()


def long_spot(daily: pd.DataFrame, window: HoldingWindow,
              investment: float = config.DEFAULT_INVESTMENT) -> StrategyResult:
    """Unlevered long: buy at the first Open, mark to market daily at Close."""
    bars = window.bars
    open_px = window.open_row["spot_open"]
    size = investment / open_px
    fees = investment * config.SPOT_TAKER_FEE * 2  # round trip on notional
    close_vals = investment + size * (bars["spot_close"].to_numpy() - open_px) - fees
    equity = _anchor(window.open_ts, investment, bars, close_vals, "Spot 1x")
    return StrategyResult("Spot 1x", equity, fees=fees,
                          meta={"size": size, "open_px": open_px})


def long_perp(daily: pd.DataFrame, funding: pd.DataFrame, window: HoldingWindow,
              investment: float = config.DEFAULT_INVESTMENT,
              leverage: float = config.DEFAULT_LEVERAGE,
              maintenance_margin_rate: float = config.MAINTENANCE_MARGIN_RATE,
              ) -> StrategyResult:
    """Levered directional long perp, net of funding, with a liquidation guard.

    position_size (BTC) = investment * leverage / perp_open. Equity is the posted
    margin plus levered price P&L minus cumulative funding and round-trip fees.
    If equity ever falls below ``maintenance_margin_rate * current_notional`` the
    position is liquidated: the loss is capped at the margin (equity floored at 0)
    and stays there — the ruin a daily mark-to-market path makes visible.
    """
    bars = window.bars
    open_px = window.open_row["perp_open"]
    notional0 = investment * leverage
    size = notional0 / open_px
    fees = notional0 * config.PERP_TAKER_FEE * 2

    close = bars["perp_close"].to_numpy()
    price_pnl = size * (close - open_px)
    cum_funding = _daily_cum_funding(funding, window, size).to_numpy()
    close_vals = investment + price_pnl - cum_funding - fees

    # Liquidation guard: maintenance margin on the live notional (size * mark px).
    notional_t = size * close
    breached = close_vals <= maintenance_margin_rate * notional_t
    liquidated = bool(breached.any())
    liq_date = None
    funding_at_exit = float(cum_funding[-1])
    if liquidated:
        k = int(np.argmax(breached))  # first breach
        liq_date = bars["date"].to_numpy()[k]
        close_vals = close_vals.copy()
        close_vals[k:] = 0.0  # margin wiped; position closed
        funding_at_exit = float(cum_funding[k])

    eq = _anchor(window.open_ts, investment, bars, close_vals, f"Perp {leverage:g}x")
    return StrategyResult(
        f"Perp {leverage:g}x", eq,
        funding_total=funding_at_exit,
        fees=fees, liquidated=liquidated, liquidation_date=liq_date,
        meta={"size": size, "open_px": open_px, "notional0": notional0, "leverage": leverage},
    )


def carry_delta_neutral(daily: pd.DataFrame, funding: pd.DataFrame, window: HoldingWindow,
                        capital: float = config.DEFAULT_INVESTMENT) -> StrategyResult:
    """Flagship: long spot + short perp (notional-matched), harvesting funding.

    Hold +size BTC spot and -size BTC perp where size = capital / spot_open, so
    net price exposure is the (tiny, mean-reverting) basis only. The short perp
    RECEIVES funding when the rate is positive, so funding flips from a cost to
    income. Equity = capital + spot leg P&L - perp leg P&L + funding income - fees.
    """
    bars = window.bars
    spot_open = window.open_row["spot_open"]
    perp_open = window.open_row["perp_open"]
    size = capital / spot_open

    spot_leg = size * (bars["spot_close"].to_numpy() - spot_open)
    perp_leg = size * (bars["perp_close"].to_numpy() - perp_open)  # we are SHORT -> subtract
    # Funding: long convention is a cost; the short perp leg receives it -> +.
    funding_income = _daily_cum_funding(funding, window, size).to_numpy()
    # Round-trip taker fees on BOTH legs.
    fees = size * spot_open * config.SPOT_TAKER_FEE * 2 + size * perp_open * config.PERP_TAKER_FEE * 2

    close_vals = capital + spot_leg - perp_leg + funding_income - fees
    eq = _anchor(window.open_ts, capital, bars, close_vals, "Carry (Δ-neutral)")
    return StrategyResult(
        "Carry (Δ-neutral)", eq,
        funding_total=float(funding_income[-1]), fees=fees,
        meta={"size": size, "spot_open": spot_open, "perp_open": perp_open, "capital": capital},
    )
