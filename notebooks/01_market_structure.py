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
# # 1 — Market structure: basis, integration and return distributions
#
# **Question.** Are the BTC spot and perpetual markets "integrated", and are daily
# returns well-behaved? A tempting shortcut answers both with one number — the
# 0.999999 correlation of **price levels** — but that is statistically unsafe.
# Here we test integration and normality properly.
#
# *Run order:* this notebook reads the committed snapshot in `data/raw/`, so it
# runs offline. Build/refresh it with `make data`.

# %%
import warnings

import pandas as pd
import plotly.io as pio

from perp_spot import config, data, plots, stats

pio.renderers.default = "notebook_connected"  # embed plotly.js for static HTML export
warnings.simplefilter("ignore")
pd.options.display.float_format = lambda x: f"{x:,.4f}"

market = data.load_market(config.PRIMARY_SYMBOL)
daily = market.daily
print(f"{config.PRIMARY_SYMBOL}: {len(daily)} daily bars, "
      f"{daily['date'].min().date()} → {daily['date'].max().date()}")

# %% [markdown]
# ## 1.1 Why "0.999999 correlation of prices" proves nothing
#
# Spot and perp prices are two strongly trending, non-stationary (I(1)) series.
# Pearson correlation of their **levels** is ~1.0 essentially by construction —
# the classic spurious-regression artifact (Yule 1926; Granger–Newbold 1974). It
# measures a shared trend, not co-movement. The economically meaningful object is
# the correlation of **returns**, and — better — the **basis** the funding
# mechanism actually controls.

# %%
level_corr = daily["spot_close"].corr(daily["perp_close"])
return_corr = daily["spot_ret"].corr(daily["perp_ret"])
print(f"Correlation of PRICE LEVELS  : {level_corr:.6f}   <- spurious, trend-driven")
print(f"Correlation of DAILY RETURNS : {return_corr:.6f}   <- the meaningful number")

# %% [markdown]
# ## 1.2 The basis is small and mean-reverting — the real integration evidence
#
# `basis = perp_close − spot_close`, expressed in basis points of spot. If the
# markets are integrated, the basis is **stationary** and mean-reverting with a
# short half-life, and the two price levels are **cointegrated**.

# %%
print(f"Basis (bps):  mean {daily['basis_bps'].mean():+.2f}   "
      f"std {daily['basis_bps'].std():.2f}   "
      f"half-life {stats.half_life(daily['basis_bps']):.1f} days")
print("ADF  (H0: unit root) :", stats.adf(daily["basis_bps"]).as_dict())
print("KPSS (H0: stationary):", stats.kpss_test(daily["basis_bps"]).as_dict())
print("Engle–Granger spot~perp:", stats.engle_granger(daily["perp_close"], daily["spot_close"]).as_dict())

plots.fig_basis(daily).show()

# %% [markdown]
# **Read-out.** The basis sits within a few bps of zero with a half-life of a few
# days, ADF strongly rejects a unit root, and the price levels are cointegrated —
# *that* is what "integration / an effective funding mechanism" means, stated as a
# tested property rather than a spurious correlation.

# %% [markdown]
# ## 1.3 Daily returns are fat-tailed, not normal
#
# A common assumption is that returns are normally distributed. We test it.

# %%
dist = stats.distribution_summary(daily["spot_ret"])
print(f"n = {dist.n}")
print(f"skew              : {dist.skew:+.3f}")
print(f"excess kurtosis   : {dist.excess_kurtosis:+.3f}   (0 for a Normal)")
print(f"Jarque–Bera p     : {dist.jb_pvalue:.2e}")
print(f"=> Normal? {dist.is_normal}  (heavy tails -> downside/liquidation risk is "
      f"understated by Gaussian assumptions)")

plots.fig_return_distribution(daily["spot_ret"]).show()

# %% [markdown]
# ## 1.4 "Spot and perp have identical volatility" — significance, not eyeballing
#
# Annualize the daily-return std (×√365) and test equality of variances with
# Levene's test instead of comparing "2.86% vs 2.87%" by eye.

# %%
ann = config.TRADING_DAYS_PER_YEAR ** 0.5
print(f"Annualized vol — spot {daily['spot_ret'].std() * ann:.1%}, "
      f"perp {daily['perp_ret'].std() * ann:.1%}")
print("Levene equal-variance:", stats.levene_equal_variance(daily["spot_ret"], daily["perp_ret"]))

# %% [markdown]
# ### Takeaways
# 1. Use **return** correlation, basis stationarity and cointegration — not
#    level correlation — to argue market integration.
# 2. BTC daily returns are **leptokurtic**; Gaussian vol/VaR understate the tails,
#    which is exactly why leverage is dangerous (notebook 3).
# 3. Annualized BTC vol is ~50–60%; the spot-vs-perp vol gap is not significant.
