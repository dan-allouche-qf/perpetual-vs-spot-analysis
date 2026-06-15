"""Risk metrics on known inputs, plus the Sharpe-invariance-under-leverage property."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from perp_spot import metrics


def test_max_drawdown_known_path():
    equity = pd.Series([100, 120, 60, 90])  # peak 120 -> trough 60 = -50%
    assert metrics.max_drawdown(equity) == pytest.approx(-0.5)


def test_drawdown_never_positive():
    equity = pd.Series([100, 101, 102, 103])
    assert metrics.drawdown_series(equity).max() <= 0


def test_sharpe_zero_vol_is_nan():
    flat = pd.Series([0.0, 0.0, 0.0])
    assert np.isnan(metrics.sharpe(flat))


def test_var_cvar_ordering():
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0, 0.02, 5000))
    var = metrics.historical_var(r, 0.95)
    cvar = metrics.historical_cvar(r, 0.95)
    assert cvar <= var <= 0  # expected shortfall is deeper than VaR


def test_hit_rate():
    r = pd.Series([0.1, -0.1, 0.2, 0.0, 0.3])
    assert metrics.hit_rate(r) == pytest.approx(3 / 5)


def test_annualized_vol_scales_with_sqrt_n():
    r = pd.Series([0.01, -0.01] * 100)
    assert metrics.annualized_volatility(r) == pytest.approx(
        r.std(ddof=1) * np.sqrt(metrics.ANN)
    )


def test_sharpe_invariant_under_leverage():
    """Scaling every return by k (leverage) leaves the Sharpe ratio unchanged.

    A key insight for the leverage analysis: leverage scales numerator AND
    denominator together, so risk-adjusted return is ~unchanged (funding drag
    aside) while drawdown scales with k.
    """
    rng = np.random.default_rng(1)
    r = pd.Series(rng.normal(0.001, 0.02, 1000))
    assert metrics.sharpe(3 * r) == pytest.approx(metrics.sharpe(r), rel=1e-9)


def test_summarize_returns_all_keys():
    equity = pd.Series(np.linspace(1000, 1500, 50))
    s = metrics.summarize(equity, name="x")
    for key in ("total_return", "sharpe", "sortino", "max_drawdown", "calmar",
                "var_95", "cvar_95", "hit_rate", "ann_vol", "ann_return"):
        assert key in s.index
    assert s["total_return"] == pytest.approx(0.5)
