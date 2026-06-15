"""Central configuration: symbols, date ranges, trading frictions and parameters.

Everything the analysis depends on is a named constant here, so every figure and
headline number is traceable to a single source of truth and glued to code rather
than hard-coded in prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "raw"
FIG_DIR = ROOT / "docs" / "figures"

# --------------------------------------------------------------------------- #
# Universe and history
# --------------------------------------------------------------------------- #
# USDT-margined symbols available on both Binance spot and futures.
SYMBOLS: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
PRIMARY_SYMBOL = "BTCUSDT"

# Full snapshot window (spans the 2021 bull, the 2022 bear and the 2023-2024
# recovery so the backtest is exposed to multiple regimes, not one lucky path).
HISTORY_START = "2021-01-01"
HISTORY_END = "2024-12-31"

# An illustrative 2024-Q1 window used for the single-window case study, alongside
# the regime-wide walk-forward over the full history.
CASE_START = "2024-01-01"
CASE_END = "2024-03-20"

# --------------------------------------------------------------------------- #
# Position / trading assumptions
# --------------------------------------------------------------------------- #
DEFAULT_LEVERAGE = 4.0  # 25% initial margin
DEFAULT_INVESTMENT = 1_000.0  # margin posted, in USDT

# Binance taker fees (round-trip costs are charged on notional at entry/exit).
SPOT_TAKER_FEE = 0.0010  # 0.10%
PERP_TAKER_FEE = 0.0005  # 0.05%

# Funding settles every 8h (00:00, 08:00, 16:00 UTC) -> 3 per day.
FUNDING_INTERVAL_HOURS = 8
FUNDING_SETTLEMENTS_PER_YEAR = 365 * 24 / FUNDING_INTERVAL_HOURS  # 1095

# Maintenance-margin rate used by the liquidation guard. Binance's lowest BTC
# tier is ~0.4%; we use a conservative flat rate for the simplified check.
MAINTENANCE_MARGIN_RATE = 0.005

# Crypto trades 365 days/year; used to annualize vol and Sharpe.
TRADING_DAYS_PER_YEAR = 365

# Risk-free rate assumed for Sharpe (0% keeps the comparison transparent).
RISK_FREE_RATE = 0.0


@dataclass(frozen=True)
class BootstrapConfig:
    """Parameters for the stationary/block bootstrap of backtest distributions."""

    block_size: int = 21  # ~1 trading month, preserves autocorrelation
    n_resamples: int = 2_000
    confidence: float = 0.95
    seed: int = 7


BOOTSTRAP = BootstrapConfig()


@dataclass(frozen=True)
class AssetConfig:
    """Per-asset overrides (extendable; defaults inherit the globals above)."""

    symbol: str
    leverage: float = DEFAULT_LEVERAGE
    maintenance_margin_rate: float = MAINTENANCE_MARGIN_RATE
    metadata: dict = field(default_factory=dict)


ASSETS: dict[str, AssetConfig] = {s: AssetConfig(symbol=s) for s in SYMBOLS}
