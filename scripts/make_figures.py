"""Regenerate the committed hero figures under docs/figures/ from the snapshot.

Run with `make figures` (or `python -m scripts.make_figures`). Every figure is
computed from the package + committed data, so the images in the README are
always reproducible and never drift from the code.
"""

from __future__ import annotations

from perp_spot import backtest, config, data, plots

# Representative windows: a bull quarter (leverage shines) and the 2022 bear
# (leverage is liquidated while the carry survives) — the core contrast.
BULL = ("2024-01-01", "2024-03-20")
BEAR = ("2022-04-01", "2022-06-30")


def main() -> None:
    config.FIG_DIR.mkdir(parents=True, exist_ok=True)
    m = data.load_market(config.PRIMARY_SYMBOL)

    plots.hero_equity(backtest.run_books(m, *BULL),
                      "BTC bull quarter (2024 Q1): leverage wins, carry is flat-but-safe",
                      config.FIG_DIR / "equity_bull.png")

    plots.hero_equity(backtest.run_books(m, *BEAR),
                      "BTC 2022 bear: the 4x long is liquidated; the carry survives",
                      config.FIG_DIR / "equity_bear.png")

    wf = backtest.walk_forward(m, freq="QE")
    plots.hero_walkforward(wf, config.FIG_DIR / "walkforward.png")

    plots.hero_basis_funding(m.daily, m.funding, config.FIG_DIR / "basis_funding.png")
    plots.hero_distribution(m.daily["spot_ret"], config.FIG_DIR / "return_distribution.png")

    print(f"Wrote hero figures to {config.FIG_DIR}")


if __name__ == "__main__":
    main()
