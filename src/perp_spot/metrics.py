"""Risk and risk-adjusted performance metrics.

All functions operate on a daily **equity path** (or a return series), so the
whole trajectory — and therefore drawdown and liquidation — is visible rather
than just the endpoints. Comparing strategies on raw return alone is misleading
when they run at different leverage; these add the risk denominator (Sharpe,
Sortino, max drawdown, Calmar, VaR/CVaR, hit-rate).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

ANN = config.TRADING_DAYS_PER_YEAR


def to_returns(equity: pd.Series) -> pd.Series:
    """Simple daily returns from an equity path."""
    return equity.pct_change().dropna()


def annualized_return(returns: pd.Series) -> float:
    """Geometric annualized return from daily returns."""
    returns = returns.dropna()
    if returns.empty:
        return float("nan")
    growth = float((1.0 + returns).prod())
    years = len(returns) / ANN
    if years <= 0 or growth <= 0:
        return float("nan")
    return growth ** (1.0 / years) - 1.0


def annualized_volatility(returns: pd.Series) -> float:
    """Annualized volatility of daily returns (x sqrt(365) for crypto)."""
    return float(returns.dropna().std(ddof=1) * np.sqrt(ANN))


def sharpe(returns: pd.Series, rf: float = config.RISK_FREE_RATE) -> float:
    """Annualized Sharpe ratio."""
    r = returns.dropna()
    sd = r.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return float("nan")
    excess = r.mean() - rf / ANN
    return float(excess / sd * np.sqrt(ANN))


def sortino(returns: pd.Series, rf: float = config.RISK_FREE_RATE) -> float:
    """Annualized Sortino ratio (downside deviation in the denominator)."""
    r = returns.dropna()
    downside = r[r < 0]
    dd = np.sqrt((downside**2).mean()) if len(downside) else np.nan
    if not dd or np.isnan(dd):
        return float("nan")
    excess = r.mean() - rf / ANN
    return float(excess / dd * np.sqrt(ANN))


def drawdown_series(equity: pd.Series) -> pd.Series:
    """Drawdown path: equity / running-peak - 1 (<= 0)."""
    peak = equity.cummax()
    return equity / peak - 1.0


def max_drawdown(equity: pd.Series) -> float:
    """Maximum peak-to-trough drawdown (negative number)."""
    if equity.empty:
        return float("nan")
    return float(drawdown_series(equity).min())


def calmar(equity: pd.Series) -> float:
    """Annualized return divided by |max drawdown|."""
    mdd = max_drawdown(equity)
    if not mdd or np.isnan(mdd):
        return float("nan")
    return annualized_return(to_returns(equity)) / abs(mdd)


def historical_var(returns: pd.Series, level: float = 0.95) -> float:
    """Historical Value-at-Risk: the loss at the (1-level) quantile (negative)."""
    r = returns.dropna()
    if r.empty:
        return float("nan")
    return float(np.quantile(r, 1.0 - level))


def historical_cvar(returns: pd.Series, level: float = 0.95) -> float:
    """Conditional VaR / expected shortfall: mean loss beyond the VaR (negative)."""
    r = returns.dropna()
    var = historical_var(r, level)
    tail = r[r <= var]
    return float(tail.mean()) if len(tail) else float("nan")


def hit_rate(returns: pd.Series) -> float:
    """Fraction of strictly positive return days."""
    r = returns.dropna()
    return float((r > 0).mean()) if len(r) else float("nan")


def summarize(equity: pd.Series, *, name: str | None = None) -> pd.Series:
    """All headline metrics for one equity path, as a labelled Series."""
    r = to_returns(equity)
    total_ret = float(equity.iloc[-1] / equity.iloc[0] - 1.0) if len(equity) > 1 else float("nan")
    out = {
        "total_return": total_ret,
        "ann_return": annualized_return(r),
        "ann_vol": annualized_volatility(r),
        "sharpe": sharpe(r),
        "sortino": sortino(r),
        "max_drawdown": max_drawdown(equity),
        "calmar": calmar(equity),
        "var_95": historical_var(r, 0.95),
        "cvar_95": historical_cvar(r, 0.95),
        "hit_rate": hit_rate(r),
    }
    return pd.Series(out, name=name)
