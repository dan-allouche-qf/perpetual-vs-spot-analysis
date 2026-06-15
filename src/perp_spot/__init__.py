"""perp_spot: funding-carry and leverage research on crypto perpetual vs spot markets.

The package is organized as small, dependency-injected modules so the analysis
notebooks stay thin and the financial math is unit-tested in isolation:

- ``config``    : symbols, date ranges, leverage, fees and backtest parameters.
- ``data``      : load the committed parquet snapshot (or refresh from
                  data.binance.vision) into a single date-aligned frame.
- ``funding``   : window-correct funding accrual, funding APR and the basis.
- ``metrics``   : returns and risk-adjusted statistics (Sharpe, Sortino, max
                  drawdown, Calmar, VaR/CVaR, hit-rate).
- ``stats``     : stationarity / cointegration / distribution diagnostics.
- ``strategy``  : the spot, leveraged-perp and delta-neutral carry books.
- ``backtest``  : daily mark-to-market equity paths, walk-forward and bootstrap.
- ``plots``     : reusable Plotly/Matplotlib helpers.
"""

from __future__ import annotations

__version__ = "0.1.0"
