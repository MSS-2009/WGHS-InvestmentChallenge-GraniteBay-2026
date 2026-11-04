"""Universe ranking: the Russell 1000 ranked in two passes, quantitative then qualitative.

Usage: python scripts/universe_rank.py
Writes reports/universe_pass1_quant.csv (every stock), reports/universe_pass2_qual.csv (the pass-1
survivors) and reports/universe_summary.json. Yahoo prices and Nasdaq company data are cached in data/raw.

Pass 1, quantitative: the satellite screen (src/lgm/growth/satellite.py) on the whole Russell 1000
(iShares IWB holdings), ranked within each sector as the exemplar report does.
  - data: at least 48 months of prices and a price of at least $3 (the WInS minimum);
  - risk: drop the top 20% by 3-year volatility, the worst 20% by 5-year drawdown and any beta above 1.5;
  - quantitative index: 0.5 z(12-1 month momentum) + 0.5 z(3-year Sharpe ratio), z-scores within sector;
  - pass: the risk filter and the top 75% of its sector on the index.
Pass 2, qualitative: the 11 dimensions of config/qualitative.yaml (1-5), scored from data for every company in
the universe (so each has a qualitative score and sector rank), and ranked in the final list only if it passed pass 1.
  - financial quality, growth and sentiment: the model's own rules (src/lgm/growth/qualitative.py);
  - the five values dimensions: how often the company's latest 10-K Business section uses words from Laura's
    values parameters (V1-V25), per 10,000 words, as 3 + z within sector (the exemplar's Scouting Report
    method; counts from scripts/tenk_values.py); the company description where no 10-K is on file;
  - management: ROE and operating-margin trend; moat: 4-year operating margin; risk flags: 3-year
    volatility and 5-year drawdown; each against sector peers, as 3 + z within sector;
  - every score is clipped to 1-5; a company with no financial statements scores 3 on financial quality; gates: an excluded activity (tobacco, gambling, controversial weapons,
    adult entertainment), financial quality <= 2 or risk flags <= 1;
  - qualitative score = 0.35 values + 0.65 strength; final score = 0.5 z(qualitative) + 0.5 z(quant index),
    over the companies that passed pass 1 and every gate.
The automated scores are compared with the 57 companies the team scored by hand (reports/satellite_qualitative.csv).
"""
import csv
import io
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from lgm.data import nasdaq
from lgm.growth import qualitative as q
from lgm.growth.lookthrough import RAW as ISHARES, holdings
from lgm.growth.satellite import metrics, prices

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports"
CFG = yaml.safe_load((ROOT / "config" / "qualitative.yaml").read_text())

KEYWORDS = {   # regex stems for each values dimension, from the parameters each dimension maps to (V1-V25)
    "innovation_creativity": r"innovat|research|design|creat|invent|patent|pioneer|engineer|technolog|software|platform|"
                             r"breakthrough|novel|artificial intelligence|\bAI\b|experiment",
    "societal_utility": r"health|medic|patient|therap|treat|cure|safety|clean|renewable|water|food|nutrition|"
                        r"infrastructure|essential|sustainab|affordab|housing|communit",
    "people_inclusion": r"employee|team member|divers|inclusi|belong|workforce|talent|career|culture|people",
    "trust_integrity": r"trust|privacy|secur|ethic|responsib|transparen|integrity|reliab|protect|complian",
    "access_education_creators": r"educat|learn|student|school|universit|knowledge|creator|small business|entrepreneur|"
                                 r"developer|access|global|worldwide|countries|marketplace|ecosystem|partner",
}
EXCLUDED = {   # config/qualitative.yaml gates: core business in these activities
    "tobacco": r"tobacco|cigarette|nicotine",
    "gambling": r"casino|gambling|wager|sports betting|lottery",
    "controversial weapons": r"cluster munition|landmine|nuclear weapon|chemical weapon",
    "adult entertainment": r"adult entertainment",
}


def zs(s: pd.Series, by: pd.Series) -> pd.Series:
    """z-score within each group; a group with no spread scores 0."""
    g = s.groupby(by)
    sd = g.transform("std")
    return ((s - g.transform("mean")) / sd.where(sd > 0)).fillna(0.0)


def to_score(z: pd.Series) -> pd.Series:
    return (3 + z).clip(1, 5).round(1)


def tenk_counts() -> pd.DataFrame:
    """Values-word counts from each company's latest 10-K (scripts/tenk_values.py), by ticker."""
    rows = []
    for f in (ROOT / "data" / "raw" / "sec").glob("*.json"):
        r = json.loads(f.read_text())
        if r.get("words", 0) >= 1000:
            rows.append({"ticker": r["ticker"], "filing_date": r["filing_date"], "words": r["words"], **r["hits"]})
    return pd.DataFrame(rows).set_index("ticker") if rows else pd.DataFrame(columns=["filing_date", "words"])


def fin_quality(r) -> float:
    """The model's financial-quality rule; a company with no financial statements at Nasdaq scores a neutral 3,
    as the model already does for missing growth and analyst data."""
    try:
        return q.financial_quality(r)
    except ValueError:
        return 3.0


def universe() -> pd.DataFrame:
    rows = [h for h in holdings("IWB") if h["w"] > 0 and h["loc"] == "United States"]
    lines = (ISHARES / "IWB_holdings.csv").read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    k = next(i for i, l in enumerate(lines) if l.startswith("Ticker,"))
    names = {r["Ticker"]: r["Name"].title() for r in csv.DictReader(io.StringIO("\n".join(lines[k:])))}
    df = pd.DataFrame(rows)
    df["name"] = df["ticker"].map(names)
    df["yahoo"] = df["ticker"].str.replace(" ", "-").str.replace(".", "-", regex=False)
    return df.drop_duplicates("yahoo")


def pass1() -> pd.DataFrame:
    u = universe()
    px = prices(list(u["yahoo"]) + ["VTI"])
    met = metrics(px.drop(columns=["VTI"]), px["VTI"])
    d = u.set_index("yahoo").join(met, how="left")
    metric_cols = ["vol3", "beta3", "maxdd5", "mom12_1", "ret3", "sharpe3", "last_price"]
    d[metric_cols] = d[metric_cols].round(8)          # the exact values the workbook imports
    d["pass_data"] = (d["months"] >= 48) & (d["last_price"] >= 3)
    ok = d["pass_data"]
    vol_cut, dd_cut = d.loc[ok, "vol3"].quantile(0.80), d.loc[ok, "maxdd5"].quantile(0.20)
    d["pass_risk"] = ok & (d["vol3"] <= vol_cut) & (d["maxdd5"] >= dd_cut) & (d["beta3"] <= 1.5)
    e = d[ok]
    d.loc[ok, "quant_index"] = (0.5 * zs(e["mom12_1"], e["sector"]) + 0.5 * zs(e["sharpe3"], e["sector"])).round(9)
    d.loc[ok, "sector_size"] = e.groupby("sector")["sector"].transform("size")
    d.loc[ok, "quant_sector_rank"] = d.loc[ok].groupby("sector")["quant_index"].rank(ascending=False, method="min")
    d.loc[ok, "quant_sector_pct"] = d.loc[ok].groupby("sector")["quant_index"].rank(pct=True)
    d.loc[ok, "quant_rank"] = d.loc[ok, "quant_index"].rank(ascending=False, method="min")
    d["pass_quant"] = d["pass_risk"] & (d["quant_sector_pct"] > 0.25)
    d.attrs.update(vol_cut=float(vol_cut), dd_cut=float(dd_cut))
    return d.reset_index().sort_values("quant_rank")


def pass2(p1: pd.DataFrame) -> pd.DataFrame:
    s = p1.copy()
    ev = pd.DataFrame.from_dict({t: nasdaq.evidence(t) for t in s["ticker"]}, orient="index")
    d = s.set_index("ticker").join(ev, how="left")
    has = d["revenue"].notna() | d["description"].fillna("").str.len().gt(0)
    d = d[has].copy()
    text = (d["description"].fillna("") + " " + d["industry"].fillna(""))
    words = text.str.split().str.len().clip(lower=20)
    for dim, pat in KEYWORDS.items():
        d[dim + "_hits"] = text.str.count(re.compile(pat, re.I))
        d[dim] = to_score(zs(d[dim + "_hits"] / words * 100, d["sector"]))
    tenk = tenk_counts()
    has = d.index.isin(tenk.index)
    d["values_source"] = "Company description"
    d.loc[has, "values_source"] = "10-K filed " + tenk.reindex(d.index[has])["filing_date"].astype(str)
    for dim in KEYWORDS:                               # the 10-K, where one is on file, replaces the description
        dens = tenk.reindex(d.index[has])[dim] / tenk.reindex(d.index[has])["words"] * 10_000
        d.loc[has, dim] = to_score(zs(dens, d.loc[has, "sector"]))
    num = lambda c: pd.to_numeric(d[c], errors="coerce")
    d["management_capital_allocation"] = to_score(0.5 * zs(num("roe").clip(-50, 100), d["sector"])
                                                  + 0.5 * zs(num("op_margin") - num("op_margin_avg4"), d["sector"]))
    d["moat_position"] = to_score(zs(num("op_margin_avg4"), d["sector"]))
    d["risk_flags"] = to_score(0.5 * zs(-d["vol3"], d["sector"]) + 0.5 * zs(d["maxdd5"], d["sector"]))
    r = d.astype(object).where(pd.notna(d), None)
    for c in ("roe", "op_margin", "op_margin_avg4", "debt_to_equity", "fcf_conversion", "rev_cagr_3y", "rd_to_revenue",
              "net_margin"):
        r[c] = [None if v is None else float(v) for v in num(c).astype(object).where(num(c).notna(), None)]
    d["financial_quality"] = [fin_quality(x) for _, x in r.iterrows()]
    d["growth_innovation"] = [q.growth_innovation(x) for _, x in r.iterrows()]
    mom_pct = p1.set_index("ticker")["mom12_1"].rank(pct=True).fillna(0.5)   # no price history: median
    d["sentiment_momentum"] = [q.sentiment(x, float(mom_pct.get(t, 0.5))) for t, x in r.iterrows()]
    strength = q.JUDGED_STRENGTH + ["financial_quality", "growth_innovation", "sentiment_momentum"]
    d["values_score"] = d[q.VALUES].mean(axis=1)
    d["strength_score"] = d[strength].mean(axis=1)
    w = CFG["weights"]
    d["qual_score"] = (w["values"] * d["values_score"] + w["strength"] * d["strength_score"]).round(9)
    reasons = []
    for t, x in d.iterrows():
        why = [f"excluded activity: {k}" for k, pat in EXCLUDED.items() if re.search(pat, text[t], re.I)]
        if x["financial_quality"] <= 2:
            why.append("financial quality <= 2")
        if x["risk_flags"] <= 1:
            why.append("risk flags <= 1")
        reasons.append("; ".join(why))
    d["reject_reason"] = reasons
    d["accepted"] = d["reject_reason"] == ""
    d.loc[d["accepted"], "qual_sector_rank"] = d.loc[d["accepted"]].groupby("sector")["qual_score"].rank(ascending=False, method="min")
    a = d["accepted"] & d["pass_quant"].astype(bool)
    zf = lambda c: (d.loc[a, c] - d.loc[a, c].mean()) / d.loc[a, c].std()
    d.loc[a, "final_score"] = (0.5 * zf("qual_score") + 0.5 * zf("quant_index")).round(9)   # ties rank alike
    d.loc[a, "final_rank"] = d.loc[a, "final_score"].rank(ascending=False, method="min")
    d.loc[a, "final_sector_rank"] = d.loc[a].groupby("sector")["final_score"].rank(ascending=False, method="min")
    return d.reset_index().sort_values(["final_rank", "qual_score"], ascending=[True, False])


def main():
    p1 = pass1()
    cols1 = ["quant_rank", "quant_sector_rank", "sector_size", "ticker", "name", "sector", "w", "months", "last_price",
             "mom12_1", "sharpe3", "ret3", "vol3", "maxdd5", "beta3", "quant_index", "quant_sector_pct",
             "pass_data", "pass_risk", "pass_quant"]
    p1[cols1].round(9).to_csv(OUT / "universe_pass1_quant.csv", index=False)
    p2 = pass2(p1)
    cols2 = ["final_rank", "final_sector_rank", "ticker", "name", "sector", "industry", "quant_index", "quant_sector_rank",
             *q.VALUES, *q.JUDGED_STRENGTH, "financial_quality", "growth_innovation", "sentiment_momentum",
             "values_score", "strength_score", "qual_score", "qual_sector_rank", "final_score", "accepted", "pass_quant",
             "reject_reason", "analyst_rating", "rev_cagr_3y", "op_margin_avg4", "roe", "debt_to_equity",
             "values_source", *[k + "_hits" for k in KEYWORDS]]
    p2[cols2].round(9).to_csv(OUT / "universe_pass2_qual.csv", index=False)

    hand = pd.read_csv(OUT / "satellite_qualitative.csv").set_index("ticker")
    both = p2.set_index("ticker").join(hand[["values_score", "strength_score", "qual_score"]], rsuffix="_hand", how="inner")
    corr = {c: round(float(both[c].corr(both[c + "_hand"], method="spearman")), 3)
            for c in ("values_score", "strength_score", "qual_score")}
    summary = {
        "universe": int(len(p1)), "pass_data": int(p1["pass_data"].sum()), "pass_risk": int(p1["pass_risk"].sum()),
        "pass_quant": int(p1["pass_quant"].sum()), "scored_qualitative": int(len(p2)),
        "accepted": int(p2["accepted"].sum()), "final_ranked": int(p2["final_rank"].notna().sum()), "rejected": p2.loc[~p2["accepted"], "reject_reason"].value_counts().to_dict(),
        "risk_cuts": {"vol3_max": round(p1.attrs.get("vol_cut", np.nan), 4), "maxdd5_min": round(p1.attrs.get("dd_cut", np.nan), 4)},
        "hand_scored_overlap": int(len(both)), "spearman_automated_vs_hand": corr,
        "sectors": p1.loc[p1["pass_data"], "sector"].value_counts().to_dict(),
    }
    (OUT / "universe_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    show = p2[p2["final_rank"].notna()].head(15)[["final_rank", "ticker", "name", "sector", "quant_index", "qual_score", "final_score"]]
    print(show.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
