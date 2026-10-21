"""Stock satellite: quantitative screen of the S&P 500, then the qualitative model.

Quantitative screen (documented choices, in order):
1. Universe: iShares Core S&P 500 (IVV) holdings; WInS minimum price $3; at least 48 months of data.
2. Risk filter ("weed out high-risk names"): drop the top 20% by 3-year volatility, the top 20%
   by 5-year maximum drawdown, and any beta above 1.5.
3. Return-quality filter (replaces raw past return, which is mostly noise): drop the bottom 25% by
   a composite of 12-1 month momentum and 3-year risk-adjusted return (z-scores, equal weight).
4. Concentration: the satellite may not add look-through tech/communication or China/Taiwan
   exposure beyond the market (checked in scripts/build_satellite.py, which stops if it does).
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

from ..data import yahoo
from .lookthrough import holdings

TECH = {"Information Technology", "Communication"}


def universe() -> pd.DataFrame:
    rows = [h for h in holdings("IVV") if h["w"] > 0]
    df = pd.DataFrame(rows)
    df["yahoo"] = df["ticker"].str.replace(" ", "-").str.replace(".", "-", regex=False)
    return df


def prices(tickers: list[str], start: str = "2018-01-01", pause: float = 0.25) -> pd.DataFrame:
    cols = {}
    for t in tickers:
        try:
            cached = (yahoo.RAW / f"{t}_1mo.csv").exists()
            h = yahoo.history(t, start=start, interval="1mo")
            cols[t] = h["adjclose"].resample("ME").last()
            if not cached:
                time.sleep(pause)
        except Exception:
            continue
    return pd.DataFrame(cols)


def metrics(px: pd.DataFrame, market: pd.Series, end: str = "2026-09-30", rf: float = 0.04) -> pd.DataFrame:
    px = px.loc[:end]
    r = px.pct_change().iloc[1:]
    m = market.loc[:end].pct_change().iloc[1:]
    last36, last60 = r.iloc[-36:], r.iloc[-60:]
    vol3 = last36.std() * np.sqrt(12)
    beta = last36.apply(lambda s: np.cov(s.fillna(0), m.iloc[-36:].fillna(0))[0, 1] / m.iloc[-36:].var())
    p60 = px.iloc[-61:]
    mdd = (p60 / p60.cummax() - 1).min()
    mom = px.iloc[-2] / px.iloc[-13] - 1                       # 12-1 month momentum
    ret3 = (1 + last36).prod() ** (1 / 3) - 1
    sharpe3 = (ret3 - rf) / vol3
    n_obs = r.notna().sum()
    return pd.DataFrame({"vol3": vol3, "beta3": beta, "maxdd5": mdd, "mom12_1": mom, "ret3": ret3,
                         "sharpe3": sharpe3, "months": n_obs, "last_price": px.iloc[-1]})


def quant_screen(u: pd.DataFrame, met: pd.DataFrame) -> pd.DataFrame:
    df = u.set_index("yahoo").join(met, how="inner")
    df["pass_data"] = (df["months"] >= 48) & (df["last_price"] >= 3)
    d = df[df["pass_data"]].copy()
    vol_cut, dd_cut = d["vol3"].quantile(0.80), d["maxdd5"].quantile(0.20)
    d["pass_risk"] = (d["vol3"] <= vol_cut) & (d["maxdd5"] >= dd_cut) & (d["beta3"] <= 1.5)
    z = lambda s: (s - s.mean()) / s.std()
    d["rq_score"] = 0.5 * z(d["mom12_1"]) + 0.5 * z(d["sharpe3"])
    d["pass_return"] = d["rq_score"] >= d["rq_score"].quantile(0.25)
    d["pass_quant"] = d["pass_risk"] & d["pass_return"]
    d.attrs.update({"vol_cut": float(vol_cut), "dd_cut": float(dd_cut)})
    return d


def shortlist(screen: pd.DataFrame, size: int = 64, lo: int = 3, hi: int = 9) -> pd.DataFrame:
    """Sector-balanced shortlist for the qualitative model: each sector's quota is its share of the
    names passing the quant screen (clipped to [lo, hi]), filled by return-quality score."""
    q = screen[screen["pass_quant"]]
    counts = q.groupby("sector").size()
    quota = (counts / counts.sum() * size).round().clip(lower=lo, upper=hi).astype(int)
    return pd.concat([g.sort_values("rq_score", ascending=False).head(quota[s]) for s, g in q.groupby("sector")])

