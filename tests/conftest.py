"""Shared fixtures: tiny synthetic frames with hand-computable answers."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from perp_spot import data


def _klines(dates, prices) -> pd.DataFrame:
    """Build a minimal kline frame where open == close == price (flat intraday)."""
    p = np.asarray(prices, dtype=float)
    return pd.DataFrame({
        "date": dates, "open": p, "high": p, "low": p, "close": p, "volume": 1.0,
    })


@pytest.fixture
def dates5() -> pd.DatetimeIndex:
    return pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")


@pytest.fixture
def flat_daily(dates5) -> pd.DataFrame:
    """5 days, spot == perp == 100 (no price move): isolates funding effects."""
    spot = _klines(dates5, [100.0] * 5)
    perp = _klines(dates5, [100.0] * 5)
    return data.build_aligned_frame(spot, perp)


@pytest.fixture
def rising_daily(dates5) -> pd.DataFrame:
    spot = _klines(dates5, [100, 102, 104, 106, 110])
    perp = _klines(dates5, [100, 102, 104, 106, 110])
    return data.build_aligned_frame(spot, perp)


def funding_frame(times, rates, mark=100.0) -> pd.DataFrame:
    return pd.DataFrame({
        "funding_time": pd.to_datetime(list(times), utc=True),  # tz-aware UTC
        "funding_rate": np.asarray(rates, dtype=float),
        "mark_price": float(mark) if np.isscalar(mark) else np.asarray(mark, dtype=float),
    })


@pytest.fixture
def real_btc():
    """The committed BTC snapshot, skipped if it has not been built yet."""
    try:
        return data.load_market("BTCUSDT")
    except FileNotFoundError:
        pytest.skip("BTC snapshot not built; run `make data`")
