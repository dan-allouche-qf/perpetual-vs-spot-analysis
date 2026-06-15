"""Interactive Dash explorer for the spot / perp / carry books.

Run as a standalone server: ``python -m scripts.app`` (or ``make app``). Keeping
the Dash server in a script (rather than inline in a notebook cell) means "Run
All" on the notebooks never blocks on a long-running server.
"""

from __future__ import annotations

import argparse
import socket

import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html

from perp_spot import backtest, config, data, metrics, plots


def find_free_port(start_port: int = 8050, max_attempts: int = 20) -> int:
    """Find a free localhost port, starting from ``start_port``."""
    for i in range(max_attempts):
        port = start_port + i
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found after {max_attempts} attempts")


def build_app(symbol: str) -> Dash:
    market = data.load_market(symbol)
    daily = market.daily
    app = Dash(__name__)
    app.title = f"Perp vs Spot — {symbol}"

    app.layout = html.Div(
        style={"maxWidth": "1000px", "margin": "0 auto", "fontFamily": "system-ui"},
        children=[
            html.H2(f"Spot · Perp · Carry explorer — {symbol}"),
            html.P("Pick a window; the books are marked to market daily, funding is "
                   "accrued correctly, and a 4x liquidation guard is applied."),
            dcc.DatePickerRange(
                id="dates",
                min_date_allowed=daily["date"].min().date(),
                max_date_allowed=daily["date"].max().date(),
                start_date=config.CASE_START,
                end_date=config.CASE_END,
                display_format="YYYY-MM-DD",
            ),
            html.Div(id="summary", style={"margin": "16px 0", "whiteSpace": "pre-wrap",
                                          "fontFamily": "monospace"}),
            dcc.Graph(id="equity"),
        ],
    )

    @app.callback(
        Output("equity", "figure"), Output("summary", "children"),
        Input("dates", "start_date"), Input("dates", "end_date"),
    )
    def update(start, end):  # type: ignore[no-untyped-def]
        if not start or not end or start >= end:
            return go.Figure(), "Select a valid date range (start < end)."
        try:
            books = backtest.run_books(market, start, end)
        except ValueError as e:
            return go.Figure(), f"No data for this window: {e}"
        fig = plots.fig_equity_curves(books)
        lines = []
        for res in books.values():
            s = metrics.summarize(res.equity)
            flag = " [LIQUIDATED]" if res.liquidated else ""
            lines.append(
                f"{res.name:18} ret {s['total_return']:+7.1%}  Sharpe {s['sharpe']:5.2f}  "
                f"maxDD {s['max_drawdown']:6.1%}  funding ${res.funding_total:8.2f}{flag}"
            )
        return fig, "\n".join(lines)

    return app


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbol", default=config.PRIMARY_SYMBOL)
    p.add_argument("--port", type=int, default=None)
    args = p.parse_args()
    app = build_app(args.symbol)
    port = args.port or find_free_port()
    print(f"Dash running at http://127.0.0.1:{port}")
    app.run(debug=False, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
