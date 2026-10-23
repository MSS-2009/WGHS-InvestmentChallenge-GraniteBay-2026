"""Qualitative model: scores, yes/no gates and the final satellite selection.

Values dimensions and three strength dimensions (management, moat, risk flags) are analyst
judgments recorded in config/qualitative_judgments.csv with a rationale for each company.
Financial quality, growth and sentiment are computed from Nasdaq data (reports/satellite_evidence.csv)
and the price screen, so they are reproducible.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

VALUES = ["innovation_creativity", "societal_utility", "people_inclusion", "trust_integrity", "access_education_creators"]
JUDGED_STRENGTH = ["management_capital_allocation", "moat_position", "risk_flags"]
LOW_MARGIN = ("Retail", "Auto", "oil", "Pharmaceuticals", "Clothing")   # industries judged on ROE, not margin
RATING = {"Strong Buy": 5, "Buy": 4, "Hold": 3, "Underperform": 2, "Sell": 1}


def band(x, cuts, scores):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    for c, s in zip(cuts, scores):
        if x >= c:
            return s
    return scores[-1] - 1 if scores[-1] > 1 else 1


def financial_quality(r) -> float:
    sector, ind = r["sector"], str(r["industry"])
    roe = r["roe"]
    de = r["debt_to_equity"]
    # Profitable but negative ROE means negative book equity (e.g. buybacks beyond equity): ROE is then
    # meaningless and debt/equity is undefined, but leverage is effectively unbounded, so it scores 1.
    negative_equity = de is None and roe is not None and roe < 0 and (r["net_margin"] or 0) > 0
    if negative_equity:
        roe, de = None, float("inf")
    parts = []
    if sector == "Financials":
        parts.append(band(roe, [15, 12, 9, 6], [5, 4, 3, 2]))
        parts.append(band(r["op_margin_avg4"], [30, 20, 10, 5], [5, 4, 3, 2]) if r["op_margin_avg4"] else np.nan)
    else:
        low = any(k.lower() in ind.lower() for k in LOW_MARGIN)
        if not low:
            parts.append(band(r["op_margin_avg4"], [25, 15, 8, 3], [5, 4, 3, 2]))
        if not negative_equity:
            parts.append(band(roe, [20, 15, 10, 5], [5, 4, 3, 2]) if roe is not None and roe > 0 else (3 if de is None else 1))
        if sector in ("Utilities", "Real Estate"):
            parts.append(band(-de if de is not None else None, [-1.0, -1.5, -2.0, -4.0], [5, 4, 3, 2]))
        else:
            parts.append(band(-de if de is not None else None, [-0.5, -1.0, -2.0, -4.0], [5, 4, 3, 2]) if de is not None else 3)
            parts.append(band(r["fcf_conversion"], [0.9, 0.7, 0.5, 0.3], [5, 4, 3, 2]))
    v = np.nanmean([p for p in parts if p == p])
    if r["op_margin"] is not None and r["op_margin"] < 0:
        v = min(v, 2)                                   # loss-making in the latest year
    return float(np.clip(round(v * 2) / 2, 1, 5))


def growth_innovation(r) -> float:
    g = band(r["rev_cagr_3y"] * 100 if r["rev_cagr_3y"] is not None else None, [12, 8, 4, 0], [5, 4, 3, 2])
    if r["rd_to_revenue"] and r["rd_to_revenue"] >= 0.10:
        g = min(5, g + 1)
    return float(g if g == g else 3)


def sentiment(r, mom_pct: float) -> float:
    a = RATING.get(r["analyst_rating"], 3)
    m = 1 + 4 * mom_pct
    return float(round((a + m) / 2 * 2) / 2)


def score(screen: pd.DataFrame, evidence: pd.DataFrame, judgments: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    df = judgments.set_index("ticker").join(evidence, how="left").join(
        screen.set_index("ticker")[["sector", "rq_score", "mom12_1", "vol3", "beta3", "last_price"]], how="left")
    mom_pct = screen.set_index("ticker")["mom12_1"].rank(pct=True)
    for c in ["roe", "op_margin", "op_margin_avg4", "debt_to_equity", "fcf_conversion", "rev_cagr_3y", "rd_to_revenue"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.astype({c: object for c in ["roe", "debt_to_equity", "fcf_conversion", "rev_cagr_3y", "op_margin", "op_margin_avg4"]})
    df = df.where(pd.notna(df), None)
    df["financial_quality"] = [financial_quality(r) for _, r in df.iterrows()]
    df["growth_innovation"] = [growth_innovation(r) for _, r in df.iterrows()]
    df["sentiment_momentum"] = [sentiment(r, float(mom_pct.get(t, 0.5))) for t, r in df.iterrows()]
    strength = JUDGED_STRENGTH + ["financial_quality", "growth_innovation", "sentiment_momentum"]
    df["values_score"] = df[VALUES].astype(float).mean(1)
    df["strength_score"] = df[strength].astype(float).mean(1)
    w = cfg["weights"]
    df["qual_score"] = w["values"] * df["values_score"] + w["strength"] * df["strength_score"]
    reasons = []
    for t, r in df.iterrows():
        why = []
        if isinstance(r["excluded_activity"], str) and r["excluded_activity"]:
            why.append(f"values: {r['excluded_activity']}")
        if r["values_score"] < cfg["gates"].get("values_min_average", 3.0):
            why.append(f"values: average {r['values_score']:.1f} < 3.0")
        if min(float(r[v]) for v in VALUES) <= 1:
            why.append("values: a dimension scored 1")
        if r["financial_quality"] <= 2:
            why.append("strength: financial quality <= 2")
        if float(r["risk_flags"]) <= 1:
            why.append("strength: severe risk flags")
        reasons.append("; ".join(why))
    df["reject_reason"] = reasons
    df["accepted"] = df["reject_reason"] == ""
    z = lambda s: (s - s.mean()) / s.std()
    acc = df["accepted"]
    df.loc[acc, "combined"] = 0.5 * z(df.loc[acc, "qual_score"].astype(float)) + 0.5 * z(df.loc[acc, "rq_score"].astype(float))
    return df


def select(df: pd.DataFrame, n: int, max_sector_share: float) -> pd.DataFrame:
    cap = int(np.floor(n * max_sector_share))
    picks, per = [], {}
    for t, r in df[df["accepted"]].sort_values("combined", ascending=False).iterrows():
        if per.get(r["sector"], 0) < cap:
            picks.append(t)
            per[r["sector"]] = per.get(r["sector"], 0) + 1
        if len(picks) == n:
            break
    return df.loc[picks]


def hrp_weights(returns: pd.DataFrame, method: str = "single") -> pd.Series:
    """Hierarchical risk parity (Lopez de Prado, 2016): cluster by correlation (`method` is the linkage),
    then split risk top-down by inverse variance. Robust to the estimation error that breaks mean-variance."""
    from scipy.cluster.hierarchy import leaves_list, linkage
    from scipy.spatial.distance import squareform

    cov, corr = returns.cov().values, returns.corr().values
    dist = np.sqrt(np.clip((1 - corr) / 2, 0, 1))
    order = leaves_list(linkage(squareform(dist, checks=False), method))
    w = np.ones(len(order))

    def cvar(idx):
        c = cov[np.ix_(idx, idx)]
        ivp = 1 / np.diag(c)
        ivp /= ivp.sum()
        return ivp @ c @ ivp

    clusters = [list(order)]
    while clusters:
        nxt = []
        for c in clusters:
            if len(c) <= 1:
                continue
            a, b = c[: len(c) // 2], c[len(c) // 2:]
            va, vb = cvar(a), cvar(b)
            alpha = 1 - va / (va + vb)
            w[a] *= alpha
            w[b] *= 1 - alpha
            nxt += [a, b]
        clusters = nxt
    return pd.Series(w / w.sum(), index=returns.columns)
