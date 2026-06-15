"""Data layer.

Primary source is **data.binance.vision** (Binance's public, geo-neutral CSV
dumps). Hitting ``api.binance.com`` directly returns HTTP 451 from some regions
(e.g. US IPs), so for reproducibility we download the monthly dumps once, persist
a Parquet snapshot under ``data/raw/`` (committed to the repo), and load from it
offline by default. The REST API is available behind an explicit refresh flag.

Parsed schemas
--------------
klines  -> DataFrame[date, open, high, low, close, volume]   (one row per UTC day)
funding -> DataFrame[funding_time, funding_rate, mark_price]  (3 rows per UTC day)
"""

from __future__ import annotations

import io
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config

VISION_BASE = "https://data.binance.vision/data"

# Canonical kline column order used by every Binance kline/markPrice dump.
_KLINE_COLS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore",
]
_MARKET_PATH = {"spot": "spot", "perp": "futures/um"}


# --------------------------------------------------------------------------- #
# HTTP session with retry/backoff
# --------------------------------------------------------------------------- #
def _session(max_retries: int = 4) -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=max_retries,
        backoff_factor=1.0,  # exponential: 1s, 2s, 4s, ...
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def date_to_millis(date_str: str) -> int:
    """Convert a ``YYYY-MM-DD`` date to UNIX epoch milliseconds (UTC, tz-aware)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)


def _months(start: str, end: str) -> list[str]:
    """List of ``YYYY-MM`` strings covering [start, end] inclusive."""
    s = pd.Timestamp(start).to_period("M")
    e = pd.Timestamp(end).to_period("M")
    return [str(p) for p in pd.period_range(s, e, freq="M")]


# --------------------------------------------------------------------------- #
# binance.vision dump readers
# --------------------------------------------------------------------------- #
def _read_zip_csv(content: bytes, names: list[str]) -> pd.DataFrame:
    """Read a single-CSV zip into a DataFrame, tolerating an optional header row.

    Spot kline dumps ship headerless; futures kline / funding / markPrice dumps
    ship with a header. We detect it by checking whether the first field parses
    as an integer timestamp.
    """
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        name = zf.namelist()[0]
        raw = zf.read(name)
    first = raw.split(b"\n", 1)[0].split(b",", 1)[0].strip()
    has_header = not first.isdigit()
    return pd.read_csv(
        io.BytesIO(raw),
        header=0 if has_header else None,
        names=None if has_header else names,
    )


def _fetch_one(session: requests.Session, url: str) -> bytes | None:
    """Download one dump; return None on 404 (e.g. month before listing)."""
    resp = session.get(url, timeout=60)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.content


def _fetch_concat(urls: list[str], names: list[str], workers: int = 8) -> pd.DataFrame:
    """Download many monthly dumps concurrently and concat them in order."""
    session = _session()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        contents = list(ex.map(lambda u: _fetch_one(session, u), urls))
    frames = [
        _read_zip_csv(c, names) for c in contents if c is not None
    ]
    if not frames:
        raise RuntimeError(f"No data downloaded for {len(urls)} urls (all 404?).")
    return pd.concat(frames, ignore_index=True)


def fetch_klines_vision(symbol: str, market: str, start: str, end: str) -> pd.DataFrame:
    """Daily klines for ``symbol`` from binance.vision. ``market`` in {spot, perp}."""
    mp = _MARKET_PATH[market]
    urls = [
        f"{VISION_BASE}/{mp}/monthly/klines/{symbol}/1d/{symbol}-1d-{m}.zip"
        for m in _months(start, end)
    ]
    df = _fetch_concat(urls, _KLINE_COLS)
    return _normalize_klines(df, start, end)


def fetch_funding_vision(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Funding rates joined with the 8h mark price at each settlement time."""
    months = _months(start, end)
    fr_urls = [
        f"{VISION_BASE}/futures/um/monthly/fundingRate/{symbol}/{symbol}-fundingRate-{m}.zip"
        for m in months
    ]
    mp_urls = [
        f"{VISION_BASE}/futures/um/monthly/markPriceKlines/{symbol}/8h/{symbol}-8h-{m}.zip"
        for m in months
    ]
    fr = _fetch_concat(fr_urls, ["calc_time", "funding_interval_hours", "last_funding_rate"])
    mp = _fetch_concat(mp_urls, _KLINE_COLS)

    fr = pd.DataFrame(
        {
            "funding_time": pd.to_datetime(fr["calc_time"], unit="ms", utc=True),
            "funding_rate": pd.to_numeric(fr["last_funding_rate"], errors="coerce"),
        }
    ).sort_values("funding_time")
    # Mark price at the funding instant = open of the 8h bar at that settlement.
    # Funding timestamps carry ~1ms jitter off the exact 8h grid, so we match the
    # nearest mark bar with merge_asof rather than an exact-equality join.
    mp = pd.DataFrame(
        {
            "mark_time": pd.to_datetime(mp["open_time"].astype("int64"), unit="ms", utc=True),
            "mark_price": pd.to_numeric(mp["open"], errors="coerce"),
        }
    ).sort_values("mark_time")
    out = pd.merge_asof(
        fr, mp, left_on="funding_time", right_on="mark_time",
        direction="nearest", tolerance=pd.Timedelta("1h"),
    ).drop(columns="mark_time")
    # A handful of 8h mark bars are missing from the dumps (isolated exchange-data
    # gaps, <0.6% of settlements). Mark price is near-constant over 8h, so we fill
    # these from the time-adjacent bars rather than dropping funding events.
    out["mark_price"] = out["mark_price"].interpolate(limit_direction="both")
    out = out[(out["funding_time"] >= pd.Timestamp(start, tz="UTC"))
              & (out["funding_time"] <= pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1))]
    out = out.sort_values("funding_time").reset_index(drop=True)
    _assert_no_nan(out, ["funding_rate", "mark_price"], f"{symbol} funding")
    return out


def _normalize_klines(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Coerce raw kline rows to a tidy daily frame and validate it."""
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df["open_time"].astype("int64"), unit="ms", utc=True).dt.normalize(),
            "open": pd.to_numeric(df["open"], errors="coerce"),
            "high": pd.to_numeric(df["high"], errors="coerce"),
            "low": pd.to_numeric(df["low"], errors="coerce"),
            "close": pd.to_numeric(df["close"], errors="coerce"),
            "volume": pd.to_numeric(df["volume"], errors="coerce"),
        }
    )
    out = out.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    lo = pd.Timestamp(start, tz="UTC")
    hi = pd.Timestamp(end, tz="UTC")
    out = out[(out["date"] >= lo) & (out["date"] <= hi)].reset_index(drop=True)
    _assert_no_nan(out, ["open", "high", "low", "close"], "klines")
    return out


def _assert_no_nan(df: pd.DataFrame, cols: list[str], label: str) -> None:
    n = int(df[cols].isna().sum().sum())
    if n:
        raise ValueError(f"{label}: {n} NaN values after coercion in {cols}")


# --------------------------------------------------------------------------- #
# Snapshot persistence
# --------------------------------------------------------------------------- #
def _snapshot_path(symbol: str, kind: str):
    return config.DATA_DIR / f"{symbol.lower()}_{kind}.parquet"


def build_snapshot(symbol: str, start: str, end: str) -> dict[str, pd.DataFrame]:
    """Download the full spot/perp/funding triple for one symbol from binance.vision."""
    return {
        "spot": fetch_klines_vision(symbol, "spot", start, end),
        "perp": fetch_klines_vision(symbol, "perp", start, end),
        "funding": fetch_funding_vision(symbol, start, end),
    }


def save_snapshot(symbol: str, frames: dict[str, pd.DataFrame]) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    for kind, df in frames.items():
        df.to_parquet(_snapshot_path(symbol, kind), index=False)


def load_snapshot(symbol: str) -> dict[str, pd.DataFrame]:
    """Load the committed Parquet snapshot for one symbol (offline)."""
    frames = {}
    for kind in ("spot", "perp", "funding"):
        path = _snapshot_path(symbol, kind)
        if not path.exists():
            raise FileNotFoundError(
                f"Missing snapshot {path}. Run `make data` (or `python -m scripts.fetch_data`)."
            )
        frames[kind] = pd.read_parquet(path)
    return frames


# --------------------------------------------------------------------------- #
# Aligned market frame
# --------------------------------------------------------------------------- #
@dataclass
class Market:
    """One symbol's aligned daily prices + raw funding, with derived columns."""

    symbol: str
    daily: pd.DataFrame  # date, spot_*, perp_*, basis, basis_bps, returns
    funding: pd.DataFrame  # funding_time, funding_rate, mark_price


def build_aligned_frame(spot: pd.DataFrame, perp: pd.DataFrame) -> pd.DataFrame:
    """Inner-join spot & perp on the UTC date (not by positional index).

    Spot and perp come from two different hosts, so a single missing or extra bar
    would mispair every subsequent date if aligned by row position — and the ~1.0
    level-correlation would mask it. We join on the date key and assert that the
    two series cover the same dates.
    """
    merged = spot.merge(perp, on="date", how="inner", suffixes=("_spot", "_perp"))
    if merged.empty:
        raise ValueError("Spot/perp have no overlapping dates after merge.")
    # Coverage sanity: the inner join must not silently drop a large fraction.
    coverage = len(merged) / max(len(spot), len(perp))
    if coverage < 0.95:
        raise ValueError(
            f"Spot/perp date coverage only {coverage:.1%}; series are misaligned."
        )
    if not merged["date"].is_monotonic_increasing or merged["date"].duplicated().any():
        raise ValueError("Merged dates are not strictly increasing / unique.")

    out = pd.DataFrame(
        {
            "date": merged["date"],
            "spot_open": merged["open_spot"],
            "spot_close": merged["close_spot"],
            "perp_open": merged["open_perp"],
            "perp_close": merged["close_perp"],
        }
    )
    out["basis"] = out["perp_close"] - out["spot_close"]
    out["basis_bps"] = 1e4 * out["basis"] / out["spot_close"]
    out["spot_ret"] = out["spot_close"].pct_change()
    out["perp_ret"] = out["perp_close"].pct_change()
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# REST API fallback (api.binance.com may be geo-blocked; used behind --refresh)
#
# Klines page on the last bar's close-time; the fundingRate endpoint returns
# dict records, so funding pages on its own ``fundingTime`` key.
# --------------------------------------------------------------------------- #
_API_KLINES = {
    "spot": "https://api.binance.com/api/v3/klines",
    "perp": "https://fapi.binance.com/fapi/v1/klines",
}
_API_FUNDING = "https://fapi.binance.com/fapi/v1/fundingRate"


def fetch_klines_api(symbol: str, market: str, start: str, end: str) -> pd.DataFrame:
    """Daily klines via the REST API, paginating on close-time + 1ms."""
    session = _session()
    url = _API_KLINES[market]
    start_ms, end_ms = date_to_millis(start), date_to_millis(end)
    rows: list[list] = []
    cursor = start_ms
    while cursor < end_ms:
        params: dict[str, str | int] = {"symbol": symbol, "interval": "1d",
                  "startTime": cursor, "endTime": end_ms, "limit": 1000}
        seg = session.get(url, params=params, timeout=30).json()
        if isinstance(seg, dict) and "code" in seg:
            raise RuntimeError(f"API error: {seg.get('msg')}")
        if not seg:
            break
        rows.extend(seg)
        if len(seg) < 1000:
            break
        cursor = int(seg[-1][6]) + 1  # close-time of last kline + 1ms
    return _normalize_klines(pd.DataFrame(rows, columns=_KLINE_COLS), start, end)


def fetch_funding_api(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Funding rates via REST, paginating on fundingTime (the dict's own key)."""
    session = _session()
    start_ms, end_ms = date_to_millis(start), date_to_millis(end)
    records: list[dict] = []
    cursor = start_ms
    while cursor < end_ms:
        params: dict[str, str | int] = {"symbol": symbol, "startTime": cursor,
                  "endTime": end_ms, "limit": 1000}
        seg = session.get(_API_FUNDING, params=params, timeout=30).json()
        if isinstance(seg, dict) and "code" in seg:
            raise RuntimeError(f"API error: {seg.get('msg')}")
        if not seg:
            break
        records.extend(seg)
        if len(seg) < 1000:
            break
        cursor = int(seg[-1]["fundingTime"]) + 1  # records are dicts: page on the time key
    df = pd.DataFrame(records)
    out = pd.DataFrame(
        {
            "funding_time": pd.to_datetime(df["fundingTime"], unit="ms", utc=True),
            "funding_rate": pd.to_numeric(df["fundingRate"], errors="coerce"),
            "mark_price": pd.to_numeric(df.get("markPrice"), errors="coerce"),
        }
    )
    return out.sort_values("funding_time").reset_index(drop=True)


def build_snapshot_api(symbol: str, start: str, end: str) -> dict[str, pd.DataFrame]:
    return {
        "spot": fetch_klines_api(symbol, "spot", start, end),
        "perp": fetch_klines_api(symbol, "perp", start, end),
        "funding": fetch_funding_api(symbol, start, end),
    }


def load_market(symbol: str, *, refresh: bool = False, start: str | None = None,
                end: str | None = None) -> Market:
    """Load one symbol as an aligned :class:`Market` (offline snapshot by default)."""
    if refresh:
        start = start or config.HISTORY_START
        end = end or config.HISTORY_END
        frames = build_snapshot(symbol, start, end)
        save_snapshot(symbol, frames)
    else:
        frames = load_snapshot(symbol)
    daily = build_aligned_frame(frames["spot"], frames["perp"])
    funding = frames["funding"].sort_values("funding_time").reset_index(drop=True)
    return Market(symbol=symbol, daily=daily, funding=funding)
