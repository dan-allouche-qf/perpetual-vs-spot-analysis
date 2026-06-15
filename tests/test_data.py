"""Data layer: date-alignment guard, zip header detection, and the funding pager."""

from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from perp_spot import data


def _zip(csv_text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("file.csv", csv_text)
    return buf.getvalue()


def _klines(dates, price):
    return pd.DataFrame({"date": dates, "open": float(price), "high": float(price),
                         "low": float(price), "close": float(price), "volume": 1.0})


def test_read_zip_csv_detects_headerless():
    df = data._read_zip_csv(_zip("1,2,3,4\n5,6,7,8"), ["a", "b", "c", "d"])
    assert list(df.columns) == ["a", "b", "c", "d"]
    assert len(df) == 2


def test_read_zip_csv_detects_header():
    df = data._read_zip_csv(_zip("a,b,c\n1,2,3"), ["x", "y", "z"])
    assert list(df.columns) == ["a", "b", "c"]  # used the file's own header
    assert len(df) == 1


def test_aligned_frame_merges_on_date_not_position():
    dates = pd.date_range("2024-01-01", periods=4, freq="D", tz="UTC")
    spot = _klines(dates, 100)
    # perp is shifted by one day; only 3 dates overlap -> coverage 3/4 = 75% < 95%.
    perp = _klines(dates + pd.Timedelta(days=1), 100)
    with pytest.raises(ValueError, match="coverage"):
        data.build_aligned_frame(spot, perp)


def test_aligned_frame_basis_and_returns():
    dates = pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC")
    spot = _klines(dates, 100)
    perp = _klines(dates, 101)  # perp 1% above spot
    out = data.build_aligned_frame(spot, perp)
    assert (out["basis"] == 1.0).all()
    assert out["basis_bps"].iloc[0] == pytest.approx(100.0)  # 1/100 * 1e4


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeFundingSession:
    """Returns >1000 dict rows across two pages, paginating on fundingTime."""

    EIGHT_H = 8 * 3600 * 1000

    def __init__(self):
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        start = int(params["startTime"])
        self.calls += 1
        n = 1000 if self.calls == 1 else 10  # first page full -> forces a 2nd page
        page = [
            {"symbol": "BTCUSDT", "fundingTime": start + i * self.EIGHT_H,
             "fundingRate": "0.0001", "markPrice": "100.0"}
            for i in range(n)
        ]
        return _FakeResp(page)


def test_funding_pager_handles_multipage(monkeypatch):
    """The funding cursor advances via each record's ``fundingTime`` key (records
    are dicts), so a window larger than one 1000-row page pages correctly."""
    monkeypatch.setattr(data, "_session", lambda *a, **k: _FakeFundingSession())
    df = data.fetch_funding_api("BTCUSDT", "2021-01-01", "2024-12-31")
    assert len(df) == 1010  # 1000 + 10, i.e. it paged a second time
    assert df["funding_time"].is_monotonic_increasing
    assert df["funding_rate"].notna().all()
