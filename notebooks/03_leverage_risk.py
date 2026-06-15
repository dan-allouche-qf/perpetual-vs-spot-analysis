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
# # 3 — Leverage, risk and liquidation
#
# **Question.** A levered long's gross return is mechanically leverage × the spot
# return, so "4× perp ≈ 4× spot, leverage wins" is true *by construction* in an
# up-window and says little. The real questions: on a **risk-adjusted** basis does
# leverage add anything, and what happens **unconditionally**, across all regimes?

# %%
import warnings

import pandas as pd

from perp_spot import backtest, config, data, metrics

warnings.simplefilter("ignore")
market = data.load_market(config.PRIMARY_SYMBOL)

# %% [markdown]
# ## 3.1 In a single bull window, Sharpe is ~unchanged; drawdown is not
#
# Leverage scales the numerator (return) **and** the denominator (vol) of the
# Sharpe ratio together — so risk-adjusted return is roughly invariant, while
# **max drawdown scales with leverage**. There is no free risk-adjusted lunch.

# %%
books = backtest.run_books(market, config.CASE_START, config.CASE_END)
spot, perp = books["spot"], books["perp"]
print(f"Window {config.CASE_START} → {config.CASE_END}")
print(f"Spot 1x : return {metrics.summarize(spot.equity)['total_return']:+.1%}  "
      f"Sharpe {metrics.sharpe(metrics.to_returns(spot.equity)):.2f}  "
      f"maxDD {metrics.max_drawdown(spot.equity):.1%}")
print(f"Perp 4x : return {metrics.summarize(perp.equity)['total_return']:+.1%}  "
      f"Sharpe {metrics.sharpe(metrics.to_returns(perp.equity)):.2f}  "
      f"maxDD {metrics.max_drawdown(perp.equity):.1%}")
print(f"\nBreak-even funding APR (4x perp net = spot): "
      f"{backtest.break_even_funding(market, config.CASE_START, config.CASE_END):.0%}  "
      f"— i.e. how expensive funding must get before leverage stops paying here.")

# %% [markdown]
# ## 3.2 The path endpoint-only P&L throws away: liquidation in a bear regime
#
# Endpoint-only P&L (first Open, last Close) cannot see a margin wipe mid-window.
# Marking to market daily with a maintenance-margin guard, the 4× long is
# **liquidated** in the 2022 sell-off while the carry is untouched.

# %%
bear = backtest.run_books(market, "2022-04-01", "2022-06-30")
for res in bear.values():
    flag = f"  LIQUIDATED {pd.Timestamp(res.liquidation_date).date()}" if res.liquidated else ""
    print(f"{res.name:18} return {res.final_equity / config.DEFAULT_INVESTMENT - 1:+7.1%}{flag}")
print("\nSee docs/figures/equity_bear.png for the equity paths.")

# %% [markdown]
# ## 3.3 Unconditionally, 4× is a coin-flip that blows up ~1 quarter in 5
#
# Across all 16 non-overlapping quarters of 2021–2024:

# %%
wf = backtest.walk_forward(market, freq="QE")
summary = wf.groupby("strategy").agg(
    median_return=("total_return", "median"),
    worst_return=("total_return", "min"),
    median_sharpe=("sharpe", "median"),
    worst_drawdown=("max_drawdown", "min"),
    liquidations=("liquidated", "sum"),
    n=("total_return", "size"),
)
summary.round(3)

# %% [markdown]
# The 4× perp's **median** quarterly return is negative and it is liquidated in
# several quarters — judging it from one bull window would be survivorship bias.
# The carry's distribution is tight and positive; spot is the honest middle.

# %% [markdown]
# ## 3.4 Does the story generalize? BTC vs ETH vs SOL
#
# Re-run the walk-forward per asset and compare median quarterly returns and
# liquidation counts.

# %%
rows = []
for sym in config.SYMBOLS:
    m = data.load_market(sym)
    w = backtest.walk_forward(m, freq="QE")
    g = w.groupby("strategy").agg(med_ret=("total_return", "median"),
                                  liq=("liquidated", "sum"),
                                  med_sharpe=("sharpe", "median"))
    g["symbol"] = sym
    rows.append(g.reset_index())
multi = pd.concat(rows).pivot_table(index="symbol", columns="strategy",
                                    values="med_ret").round(3)
print("Median quarterly return by symbol × strategy:")
print(multi.to_string())
liqs = pd.concat(rows).pivot_table(index="symbol", columns="strategy",
                                   values="liq", aggfunc="sum")
print("\nLiquidation counts (4x perp) by symbol:")
print(liqs.to_string())

# %% [markdown]
# ### Takeaways
# 1. Leverage buys **no risk-adjusted edge** (Sharpe ~invariant) while scaling
#    drawdown — and at 4× it produces outright ruin in bear regimes.
# 2. The "perp beats spot" conclusion is a single-window, single-asset artifact;
#    it does not survive a walk-forward across regimes or across BTC/ETH/SOL.
# 3. The defensible portfolio statement: *the edge here is the funding carry, not
#    the leverage* — harvested delta-neutrally, it is the only book with an
#    attractive risk-adjusted profile across all regimes.
