# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.3
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 2 — The funding carry (cash-and-carry) — flagship strategy
#
# **Thesis.** Perpetual funding is not merely a *cost* on a leveraged long; when
# it is persistently positive it is a **harvestable carry**. Holding **+1 BTC spot
# and −1 BTC perp** (notional-matched) nets price exposure to ~zero (only the tiny,
# mean-reverting basis remains) while the short perp leg **receives** funding.
#
# The inputs this trade needs — `fundingRate`, `markPrice`, spot and perp closes —
# are already in the snapshot. We build the carry book and measure it like a
# strategy, rather than treating funding only as a drag on a directional long.

# %%
import warnings

import pandas as pd
import plotly.io as pio

from perp_spot import backtest, config, data, funding, plots, strategy

pio.renderers.default = "notebook_connected"  # embed plotly.js for static HTML export
warnings.simplefilter("ignore")
market = data.load_market(config.PRIMARY_SYMBOL)
daily, fund = market.daily, market.funding

# %% [markdown]
# ## 2.1 Funding is a sizeable, time-varying carry
#
# Quoted correctly: as an **APR on notional** and in **bps/8h** (both
# leverage-invariant). Funding accrues on the notional (~$4k at 4×), not the
# posted margin, so a margin-relative figure overstates it ~4×.

# %%
print(f"Mean funding: {fund['funding_rate'].mean() * 100:.4f}% / 8h "
      f"→ {funding.funding_apr(fund) * 100:.1f}% APR (full history)")
print(f"Share of 8h settlements with POSITIVE funding (longs pay): "
      f"{(fund['funding_rate'] > 0).mean():.1%}")

wf = backtest.walk_forward(market, freq="QE")
apr_by_q = wf.groupby("window_start")["funding_apr"].first()
print(f"Quarterly funding APR ranges {apr_by_q.min() * 100:.0f}%..{apr_by_q.max() * 100:.0f}% "
      f"(median {apr_by_q.median() * 100:.0f}%) — strongly regime-dependent.")

# Basis (top) and rolling annualized funding (bottom) as a positioning signal:
plots.fig_basis(daily).show()

# %% [markdown]
# ## 2.2 The carry book over the full history (2021–2024)
#
# One delta-neutral position held across all regimes. The equity curve is the
# accumulated funding income (plus basis convergence, minus round-trip fees).

# %%
window = funding.holding_window(daily, config.HISTORY_START, config.HISTORY_END)
carry = strategy.carry_delta_neutral(daily, fund, window, capital=config.DEFAULT_INVESTMENT)
spot_full = strategy.long_spot(daily, window, config.DEFAULT_INVESTMENT)

from perp_spot import metrics
print("Carry (Δ-neutral) over 2021–2024:")
print(metrics.summarize(carry.equity, name="Carry").to_string())
print(f"\nTotal funding income: ${carry.funding_total:,.2f} on ${config.DEFAULT_INVESTMENT:,.0f} capital")
print(f"Carry max drawdown {metrics.max_drawdown(carry.equity):.2%} vs "
      f"buy-and-hold spot {metrics.max_drawdown(spot_full.equity):.2%}")

plots.fig_equity_curves({"spot": spot_full, "carry": carry}).show()
plots.fig_cumulative_funding(
    funding.accrue_funding(fund, carry.meta["size"], window).series
).show()

# %% [markdown]
# ## 2.3 Carry vs the directional books, side by side
#
# Same window, three books: 1× spot, 4× directional perp (net of funding), and the
# delta-neutral carry.

# %%
books = backtest.run_books(market, config.CASE_START, config.CASE_END)
table = backtest.metrics_table(books)[
    ["total_return", "ann_vol", "sharpe", "sortino", "max_drawdown", "funding_total", "liquidated"]
]
table.round(3)

# %% [markdown]
# ## 2.4 Is the carry robust across regimes?
#
# The single-window number could be luck. We run every non-overlapping quarter in
# 2021–2024 and report the **distribution** of carry returns vs the directional
# books — with a block-bootstrap confidence interval on the carry's mean.

# %%
carry_q = wf[wf["strategy"] == "Carry (Δ-neutral)"]["total_return"]
print(f"Carry: profitable in {(carry_q > 0).sum()}/{len(carry_q)} quarters; "
      f"median {carry_q.median():.2%}, worst {carry_q.min():.2%}")
bs = backtest.block_bootstrap(carry_q, statistic=lambda s: s.mean(), block_size=2, n_resamples=2000)
print(f"Bootstrap mean quarterly carry return: {bs['point']:.2%} "
      f"[95% CI {bs['lo']:.2%}, {bs['hi']:.2%}]")

plots.fig_walkforward(wf, "total_return").show()

# %% [markdown]
# ### Takeaways
# 1. BTC funding has been a **double-digit APR** carry on average, but it is
#    regime-dependent (it compresses, and occasionally inverts, in bear markets).
# 2. The delta-neutral carry harvested it with a **near-zero drawdown** and was
#    profitable in essentially every quarter — a genuine risk-managed carry, not a
#    tax on a leveraged bet.
# 3. The framing that matters is asking "is funding a harvestable carry?" rather
#    than only "what does funding cost a directional long?".
