"""Time-series and distribution diagnostics.

These turn qualitative claims into tested ones:

* **Market integration.** Correlating two non-stationary PRICE LEVELS gives ~1.0
  by construction (a spurious-regression artifact), so it is uninformative. The
  right evidence is a stationary, mean-reverting basis, a cointegration test on
  the levels, and the correlation of RETURNS — all provided here.
* **Return distribution.** Crypto daily returns are leptokurtic, not Gaussian.
  ``distribution_summary`` reports skew, excess kurtosis and a Jarque-Bera
  p-value so the normality assumption is tested rather than assumed.
"""

from __future__ import annotations

import warnings
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from scipy import stats as sstats
from statsmodels.tsa.stattools import adfuller, coint, kpss


@dataclass(frozen=True)
class StationarityResult:
    test: str
    statistic: float
    pvalue: float
    stationary: bool

    def as_dict(self) -> dict:
        return asdict(self)


def adf(series: pd.Series, alpha: float = 0.05) -> StationarityResult:
    """Augmented Dickey-Fuller. Null = unit root; reject (p<alpha) => stationary."""
    x = pd.Series(series).dropna().to_numpy()
    stat, pvalue = adfuller(x, autolag="AIC")[:2]
    return StationarityResult("ADF", float(stat), float(pvalue), bool(pvalue < alpha))


def kpss_test(series: pd.Series, alpha: float = 0.05) -> StationarityResult:
    """KPSS. Null = stationary; fail to reject (p>alpha) => stationary."""
    x = pd.Series(series).dropna().to_numpy()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # p-value clipped at table bounds
        stat, pvalue = kpss(x, regression="c", nlags="auto")[:2]
    return StationarityResult("KPSS", float(stat), float(pvalue), bool(pvalue > alpha))


@dataclass(frozen=True)
class CointegrationResult:
    statistic: float
    pvalue: float
    cointegrated: bool

    def as_dict(self) -> dict:
        return asdict(self)


def engle_granger(y: pd.Series, x: pd.Series, alpha: float = 0.05) -> CointegrationResult:
    """Engle-Granger cointegration test on two price-level series."""
    df = pd.concat([pd.Series(y), pd.Series(x)], axis=1).dropna()
    stat, pvalue, _ = coint(df.iloc[:, 0], df.iloc[:, 1])
    return CointegrationResult(float(stat), float(pvalue), bool(pvalue < alpha))


def half_life(series: pd.Series) -> float:
    """Ornstein-Uhlenbeck mean-reversion half-life from an AR(1) fit.

    Regress Δb_t on b_{t-1}: Δb_t = α + β·b_{t-1} + ε. The half-life of mean
    reversion is -ln(2)/ln(1+β) (in the series' native period, here 1 day).
    """
    b = pd.Series(series).dropna()
    lag = b.shift(1)
    delta = (b - lag).dropna()
    lag = lag.loc[delta.index]
    beta = np.polyfit(lag.to_numpy(), delta.to_numpy(), 1)[0]
    if beta >= 0:
        return float("inf")  # not mean-reverting
    return float(-np.log(2) / np.log(1 + beta))


@dataclass(frozen=True)
class DistributionSummary:
    n: int
    mean: float
    std: float
    skew: float
    excess_kurtosis: float
    jb_stat: float
    jb_pvalue: float
    is_normal: bool

    def as_dict(self) -> dict:
        return asdict(self)


def distribution_summary(returns: pd.Series, alpha: float = 0.05) -> DistributionSummary:
    """Skew, excess kurtosis and a Jarque-Bera normality test on daily returns."""
    r = pd.Series(returns).dropna().to_numpy()
    jb_stat, jb_p = sstats.jarque_bera(r)
    return DistributionSummary(
        n=int(r.size),
        mean=float(r.mean()),
        std=float(r.std(ddof=1)),
        skew=float(sstats.skew(r)),
        excess_kurtosis=float(sstats.kurtosis(r, fisher=True)),  # 0 for a normal
        jb_stat=float(jb_stat),
        jb_pvalue=float(jb_p),
        is_normal=bool(jb_p > alpha),
    )


def levene_equal_variance(a: pd.Series, b: pd.Series, alpha: float = 0.05) -> dict:
    """Levene's test that two return series share the same variance.

    A significance test for "are spot and perp equally volatile?", rather than
    eyeballing two near-equal standard deviations.
    """
    stat, pvalue = sstats.levene(pd.Series(a).dropna(), pd.Series(b).dropna())
    return {"statistic": float(stat), "pvalue": float(pvalue),
            "equal_variance": bool(pvalue > alpha)}
