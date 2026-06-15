"""Funding accrual: the core position math."""

from __future__ import annotations

import pandas as pd
import pytest

from conftest import funding_frame
from perp_spot import funding


def test_holding_window_strict_open_inclusive_close(flat_daily):
    w = funding.holding_window(flat_daily, "2024-01-01", "2024-01-05")
    assert w.open_ts == pd.Timestamp("2024-01-01", tz="UTC")
    # last bar is 2024-01-05 (00:00 open); it closes the next midnight.
    assert w.close_ts == pd.Timestamp("2024-01-06", tz="UTC")


def test_holding_window_rejects_inverted_dates(flat_daily):
    with pytest.raises(ValueError):
        funding.holding_window(flat_daily, "2024-01-05", "2024-01-01")


def test_zero_rate_means_zero_cost(flat_daily):
    w = funding.holding_window(flat_daily, "2024-01-01", "2024-01-05")
    times = pd.date_range("2024-01-01 08:00", "2024-01-05", freq="8h", tz="UTC")
    fr = funding_frame(times, [0.0] * len(times))
    res = funding.accrue_funding(fr, position_size=1.0, window=w)
    assert res.total == 0.0
    assert res.n_settlements > 0  # settlements exist, they just cost nothing


def test_hand_computed_sum(flat_daily):
    # Two settlements inside the window, mark price 100, size 2 BTC.
    # amount = mark * size * rate = 100 * 2 * rate
    w = funding.holding_window(flat_daily, "2024-01-01", "2024-01-05")
    fr = funding_frame(
        ["2024-01-02 00:00", "2024-01-03 08:00"], [0.0010, 0.0020], mark=100.0
    )
    res = funding.accrue_funding(fr, position_size=2.0, window=w)
    assert res.n_settlements == 2
    assert res.total == pytest.approx(100 * 2 * 0.0010 + 100 * 2 * 0.0020)  # = 0.6


def test_negative_rate_is_income_for_long(flat_daily):
    w = funding.holding_window(flat_daily, "2024-01-01", "2024-01-05")
    fr = funding_frame(["2024-01-02 00:00"], [-0.0010], mark=100.0)
    res = funding.accrue_funding(fr, position_size=1.0, window=w)
    assert res.total < 0  # a long RECEIVES when the rate is negative


def test_open_boundary_settlement_excluded(flat_daily):
    # A settlement stamped exactly at the open instant must NOT be charged
    # (accrual is strict '>' at the open boundary).
    w = funding.holding_window(flat_daily, "2024-01-01", "2024-01-05")
    fr = funding_frame(["2024-01-01 00:00"], [0.0010], mark=100.0)
    res = funding.accrue_funding(fr, position_size=1.0, window=w)
    assert res.n_settlements == 0
    assert res.total == 0.0


def test_empty_funding_returns_zero(flat_daily):
    w = funding.holding_window(flat_daily, "2024-01-01", "2024-01-05")
    res = funding.accrue_funding(pd.DataFrame(), position_size=1.0, window=w)
    assert res.total == 0.0 and res.n_settlements == 0


def test_apr_uses_settlements_per_year(flat_daily):
    fr = funding_frame(["2024-01-02 00:00", "2024-01-02 08:00"], [0.0001, 0.0001])
    apr = funding.funding_apr(fr)
    assert apr == pytest.approx(0.0001 * 1095)


def test_real_btc_case_window_funding(real_btc):
    w = funding.holding_window(real_btc.daily, "2024-01-01", "2024-03-20")
    size = (1000 / w.open_row["perp_open"]) * 4
    res = funding.accrue_funding(real_btc.funding, size, w)
    # ~240 8h settlements over ~80 days; total ≈ $260 on a $4k notional.
    assert 235 <= res.n_settlements <= 243
    assert 230 < res.total < 290
