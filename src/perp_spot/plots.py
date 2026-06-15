"""Reusable plotting helpers.

Plotly builders (``fig_*``) power the interactive notebooks; Matplotlib builders
(``hero_*``) render the static PNGs committed under ``docs/figures/`` so the repo
shows a chart on GitHub without anyone running code.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy import stats as sstats

from . import metrics

PALETTE = {
    "spot": "#2E86AB",
    "perp": "#E4572E",
    "carry": "#1B998B",
    "basis": "#6A4C93",
    "funding": "#F18F01",
    "grid": "#E6E6E6",
}
_STRAT_COLOR = {"Spot 1x": PALETTE["spot"], "Carry (Δ-neutral)": PALETTE["carry"]}


def _color_for(name: str) -> str:
    if name.startswith("Perp"):
        return PALETTE["perp"]
    return _STRAT_COLOR.get(name, PALETTE["basis"])


# --------------------------------------------------------------------------- #
# Plotly (interactive notebooks)
# --------------------------------------------------------------------------- #
def fig_basis(daily: pd.DataFrame, roll: int = 30) -> go.Figure:
    """Perp-spot basis in bps over time, with a rolling mean."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=daily["date"], y=daily["basis_bps"], mode="lines",
                             name="Basis (bps)", line=dict(color=PALETTE["basis"], width=1),
                             opacity=0.5))
    fig.add_trace(go.Scatter(x=daily["date"], y=daily["basis_bps"].rolling(roll).mean(),
                             mode="lines", name=f"{roll}d mean",
                             line=dict(color=PALETTE["basis"], width=2.5)))
    fig.add_hline(y=0, line_dash="dot", line_color="gray")
    fig.update_layout(title="Perp-Spot Basis (bps)", template="plotly_white",
                      yaxis_title="bps", height=420)
    return fig


def fig_equity_curves(results: dict) -> go.Figure:
    """Equity paths for a set of StrategyResults."""
    fig = go.Figure()
    for res in results.values():
        fig.add_trace(go.Scatter(x=res.equity.index, y=res.equity.values, mode="lines",
                                 name=res.name, line=dict(color=_color_for(res.name), width=2)))
        if res.liquidated:
            fig.add_vline(x=res.liquidation_date, line_dash="dash", line_color=PALETTE["perp"],
                          annotation_text="liquidation")
    fig.update_layout(title="Equity Curves", template="plotly_white",
                      yaxis_title="Equity ($)", height=460)
    return fig


def fig_drawdowns(results: dict) -> go.Figure:
    fig = go.Figure()
    for res in results.values():
        dd = metrics.drawdown_series(res.equity)
        fig.add_trace(go.Scatter(x=dd.index, y=dd.values, mode="lines", name=res.name,
                                 line=dict(color=_color_for(res.name), width=1.5)))
    fig.update_layout(title="Drawdowns", template="plotly_white",
                      yaxis_title="Drawdown", yaxis_tickformat=".0%", height=380)
    return fig


def fig_cumulative_funding(funding_series: pd.Series) -> go.Figure:
    """Cumulative funding income (for the carry book's short-perp leg)."""
    cum = funding_series.cumsum()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cum.index, y=cum.values, mode="lines",
                             name="Cumulative funding", line=dict(color=PALETTE["funding"], width=2)))
    fig.update_layout(title="Cumulative Funding Income", template="plotly_white",
                      yaxis_title="$", height=380)
    return fig


def fig_walkforward(wf: pd.DataFrame, metric: str = "total_return") -> go.Figure:
    """Distribution of a per-window metric across strategies (box + points)."""
    fig = go.Figure()
    for name, sub in wf.groupby("strategy"):
        fig.add_trace(go.Box(y=sub[metric], name=name, boxpoints="all", jitter=0.4,
                             marker_color=_color_for(name)))
    fig.update_layout(title=f"Walk-forward {metric} by strategy", template="plotly_white",
                      height=440, showlegend=False)
    return fig


def fig_return_distribution(returns: pd.Series) -> go.Figure:
    """Histogram of daily returns with a fitted normal overlay."""
    r = returns.dropna()
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=r, histnorm="probability density", nbinsx=80,
                               name="Returns", marker_color=PALETTE["spot"], opacity=0.6))
    xs = np.linspace(r.min(), r.max(), 200)
    fig.add_trace(go.Scatter(x=xs, y=sstats.norm.pdf(xs, r.mean(), r.std()),
                             mode="lines", name="Normal fit", line=dict(color=PALETTE["perp"], width=2)))
    fig.update_layout(title="Daily Return Distribution vs Normal", template="plotly_white",
                      height=400)
    return fig


# --------------------------------------------------------------------------- #
# Matplotlib (static hero figures for docs/figures/)
# --------------------------------------------------------------------------- #
def hero_equity(results: dict, title: str, path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for res in results.values():
        ax.plot(res.equity.index, res.equity.values, label=res.name,
                color=_color_for(res.name), lw=2)
        if res.liquidated:
            ax.axvline(res.liquidation_date, color=PALETTE["perp"], ls="--", lw=1)
            ax.annotate("liquidated", (res.liquidation_date, 0), color=PALETTE["perp"], fontsize=9)
    ax.axhline(results["spot"].equity.iloc[0], color="gray", lw=0.8, ls=":")
    ax.set_title(title, fontweight="bold")
    ax.set_ylabel("Equity ($)")
    ax.legend(frameon=False)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def hero_walkforward(wf: pd.DataFrame, path) -> None:
    order = ["Spot 1x", "Perp 4x", "Carry (Δ-neutral)"]
    order = [s for s in order if s in set(wf["strategy"])]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    data = [wf.loc[wf["strategy"] == s, "total_return"].to_numpy() for s in order]
    bp = ax.boxplot(data, tick_labels=order, showmeans=True, patch_artist=True)
    for patch, s in zip(bp["boxes"], order, strict=False):
        patch.set_facecolor(_color_for(s))
        patch.set_alpha(0.5)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("Quarterly return distribution across regimes (2021-2024)", fontweight="bold")
    ax.set_ylabel("Quarterly total return")
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def hero_basis_funding(daily: pd.DataFrame, funding: pd.DataFrame, path) -> None:
    from .funding import cumulative_funding_apr
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True)
    a1.plot(daily["date"], daily["basis_bps"], color=PALETTE["basis"], lw=0.7, alpha=0.5)
    a1.plot(daily["date"], daily["basis_bps"].rolling(30).mean(), color=PALETTE["basis"], lw=2)
    a1.axhline(0, color="gray", ls=":")
    a1.set_ylabel("Basis (bps)")
    a1.set_title("Basis and annualized funding (carry signal)", fontweight="bold")
    a1.grid(alpha=0.3)
    apr = cumulative_funding_apr(funding, window=30)
    a2.plot(apr.index, apr.to_numpy() * 100, color=PALETTE["funding"], lw=1.5)
    a2.axhline(0, color="gray", ls=":")
    a2.set_ylabel("Funding APR (%)")
    a2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def hero_distribution(returns: pd.Series, path) -> None:
    r = returns.dropna()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.6))
    a1.hist(r, bins=80, density=True, color=PALETTE["spot"], alpha=0.6)
    xs = np.linspace(r.min(), r.max(), 200)
    a1.plot(xs, sstats.norm.pdf(xs, r.mean(), r.std()), color=PALETTE["perp"], lw=2, label="Normal")
    a1.set_title("Daily returns vs Normal", fontweight="bold")
    a1.legend(frameon=False)
    a1.grid(alpha=0.3)
    sstats.probplot(r, dist="norm", plot=a2)
    a2.get_lines()[0].set_color(PALETTE["spot"])
    a2.get_lines()[1].set_color(PALETTE["perp"])
    a2.set_title("QQ-plot (fat tails)", fontweight="bold")
    a2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
