"""Strategy books: P&L identities, funding sign, liquidation and delta-neutrality."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from conftest import funding_frame
from perp_spot import data, funding, strategy


def _daily(prices_spot, prices_perp, start="2024-01-01"):
    dates = pd.date_range(start, periods=len(prices_spot), freq="D", tz="UTC")
    mk = lambda p: pd.DataFrame({  # noqa: E731
        "date": dates, "open": p, "high": p, "low": p, "close": p, "volume": 1.0})
    return data.build_aligned_frame(mk(list(map(float, prices_spot))),
                                    mk(list(map(float, prices_perp))))


def test_zero_funding_net_equals_gross():
    d = _daily([100, 102, 104, 106, 110], [100, 102, 104, 106, 110])
    w = funding.holding_window(d, "2024-01-01", "2024-01-05")
    res = strategy.long_perp(d, pd.DataFrame(), w, investment=1000, leverage=4)
    size = 1000 * 4 / 100
    expected = 1000 + size * (110 - 100) - (1000 * 4 * 0.0005 * 2)
    assert res.funding_total == 0.0
    assert res.final_equity == pytest.approx(expected)


def test_negative_funding_helps_the_long():
    d = _daily([100, 102, 104, 106, 110], [100, 102, 104, 106, 110])
    w = funding.holding_window(d, "2024-01-01", "2024-01-05")
    fr = funding_frame(["2024-01-02 00:00", "2024-01-03 00:00"], [-0.001, -0.001], mark=104.0)
    res_neg = strategy.long_perp(d, fr, w, investment=1000, leverage=4)
    res_none = strategy.long_perp(d, pd.DataFrame(), w, investment=1000, leverage=4)
    assert res_neg.final_equity > res_none.final_equity  # long receives funding


def test_liquidation_caps_loss_at_margin():
    # A -30% perp move at 4x wipes the margin -> liquidated, equity floored at 0.
    d = _daily([100, 100, 70], [100, 100, 70])
    w = funding.holding_window(d, "2024-01-01", "2024-01-03")
    res = strategy.long_perp(d, pd.DataFrame(), w, investment=1000, leverage=4)
    assert res.liquidated is True
    assert res.final_equity == 0.0
    assert res.equity.min() >= 0.0  # never goes negative


def test_carry_is_pure_funding_when_prices_flat():
    # Flat, equal spot & perp -> zero price/basis P&L; only funding income remains.
    d = _daily([100, 100, 100, 100, 100], [100, 100, 100, 100, 100])
    w = funding.holding_window(d, "2024-01-01", "2024-01-05")
    fr = funding_frame(["2024-01-02 00:00", "2024-01-03 00:00"], [0.001, 0.001], mark=100.0)
    res = strategy.carry_delta_neutral(d, fr, w, capital=1000)
    size = 1000 / 100
    gross_funding = 100 * size * 0.001 * 2
    assert res.final_equity == pytest.approx(1000 + gross_funding - res.fees)
    assert res.funding_total > 0  # short perp leg receives positive funding


def test_carry_is_price_neutral():
    # Identical spot & perp move, zero funding -> carry nets to ~capital (minus fees).
    d = _daily([100, 130, 90, 110, 150], [100, 130, 90, 110, 150])
    w = funding.holding_window(d, "2024-01-01", "2024-01-05")
    res = strategy.carry_delta_neutral(d, pd.DataFrame(), w, capital=1000)
    assert res.final_equity == pytest.approx(1000 - res.fees)


def test_spot_total_return_matches_price_move():
    d = _daily([100, 110, 121], [100, 110, 121])
    w = funding.holding_window(d, "2024-01-01", "2024-01-03")
    res = strategy.long_spot(d, w, investment=1000)
    # +21% price move, less 2x 0.1% taker fees on $1000 notional.
    assert res.final_equity == pytest.approx(1000 * 1.21 - 2.0)
    assert res.equity.iloc[0] == pytest.approx(1000)  # anchored at capital


def test_equity_path_is_monotonic_index():
    d = _daily([100, 102, 104], [100, 102, 104])
    w = funding.holding_window(d, "2024-01-01", "2024-01-03")
    res = strategy.long_spot(d, w, investment=1000)
    assert res.equity.index.is_monotonic_increasing
    assert len(res.equity) == len(w.bars) + 1  # anchor + one mark per bar
    assert not np.isnan(res.equity).any()
