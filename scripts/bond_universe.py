"""Bond universe ranking: every outstanding Treasury note and bond, and every US-listed bond or
low-risk ETF, scored with the same two-pass approach as the stock ranking (scripts/universe_rank.py).

Usage: python scripts/bond_universe.py
Writes reports/treasury_universe.csv, reports/bond_funds_universe.csv and reports/bond_universe_summary.json.

Treasury universe: every marketable Treasury note and bond outstanding on Sep 30, 2026 (Monthly Statement of
the Public Debt, FiscalData), the securities the Bloomberg US Treasury Index draws from. Each is scored like
the ladder scorecard (scripts/ladder_scorecard.py): the payment value $100 of it buys, priced with the shadow
prices of the cheapest ladder WInS allows (0% on idle cash). Scores above 100 are securities WInS does not list
that would have funded the ladder more cheaply; the summary gives the ladder's cost with every one available.

Bond and low-risk funds: every US-listed ETF whose name marks it as a bond, bill, cash or income fund (Nasdaq
ETF screener), less leveraged, inverse and stock-income funds.
  Pass 1, quantitative: at least 36 months of prices and a price of $3; drop the top 20% by 3-year volatility,
  the worst 20% by drawdown, and funds with a stock beta above 0.5 (a bond fund should not move with stocks);
  quantitative index = 0.5 z(12-month income return) + 0.5 z(3-year Sharpe ratio), within each category;
  pass = the risk filter and the top 75% of the category.
  Pass 2, fit for Laura's safe money (1-5 each): credit quality (by category); match to the January 2033
  decision (term funds by maturity year, others by rate sensitivity against the 6.2 years to Dec 2032);
  diversification (3-year correlation with US stocks); concentration (emerging-market debt, where China and
  Taiwan sit, scores low). Gate: credit quality 1 (high yield, emerging markets). Fit score = average;
  final score = 0.5 z(fit) + 0.5 z(quant index), over funds passing pass 1 and the gate.
"""
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yaml

from lgm.asof import CURVE_DATE, DATA_END
from lgm.curve import bootstrap
from lgm.data import yahoo
from lgm.data.treasury import par_curve
from lgm.instruments import TreasuryBond, ibonds_fund, wins_treasury_bonds
from lgm.ladder import build_matrix, payment_schedule, solve

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ladder_scorecard import FUNDS, shadow_prices  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "reports"
MSPD = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/debt/mspd/mspd_table_3_market"
        "?filter=record_date:eq:2026-09-30&page[size]=1000")
SCREENER = "https://api.nasdaq.com/api/screener/etf?tableonly=true&limit=10000&download=true"
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

INCLUDE = (r"(?:treasur|t-bill|\bbill|bond|fixed income|municipal|\bmuni|corporate|aggregate|mortgage|\bmbs\b|"
           r"ibonds|bulletshares|floating rate|high yield|\btips\b|inflation|government|ultra-short|short-term|"
           r"money market|\bcash\b|\bclo\b|\bloan|securitized|core plus|total return)")
EXCLUDE = (r"(?:\b[23]x\b|-[123]x|ultrashort|ultra short(?! (term|duration))|ultrapro|inverse|\bbear\b|\bbull\b|daily|"
           r"leveraged|equity|stock|dividend|covered call|premium income|buywrite|option|bitcoin|crypto|ether|"
           r"gold|silver|commodit|real estate|reit|preferred|convertible|currency|volatility|hedge|long/short|"
           r"tail risk|managed futures|autocall|buffer|defined outcome|\btarget (date|retirement)|nasdaq|s&p 500|"
           r"\bqqq\b|growth|innovation|technology|healthcare|energy)")
CATEGORIES = [   # (category, name pattern, credit quality 1-5), first match wins
    ("Emerging-market debt", r"emerging|\bem\b|china|asia", 1),
    ("High yield", r"high yield|high-yield|junk|fallen angel|\bloan", 1),
    ("International developed", r"international|ex-us|ex us|world|global (?!x)", 2),
    ("Floating rate and AAA CLO", r"floating|\bclo\b", 3),
    ("Inflation-linked", r"\btips\b|inflation", 5),
    ("Municipal", r"municipal|\bmuni|tax-exempt|tax exempt", 3),
    ("T-bill and cash", r"t-bill|\bbill|money market|\bcash\b|0-3 month|0-1 year|ultra-short|ultra short", 5),
    ("Term Treasury (iBonds)", r"ibonds.*treasury|treasury.*20[2-4]\d|bulletshares.*treasury", 5),
    ("Term corporate", r"ibonds|bulletshares|20[2-4]\d", 3),
    ("Treasury", r"treasur|government|govt", 5),
    ("Mortgage and agency", r"mortgage|\bmbs\b|agency|securitized|gnma", 4),
    ("Investment-grade corporate", r"corporate|credit|investment grade", 3),
    ("Aggregate and core", r"aggregate|core|total|broad|bond|fixed income|income", 4),
]


def _get_json(url: str, path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    r = requests.get(url, headers=H, timeout=60)
    r.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(r.text)
    return r.json()


def treasury_universe() -> tuple[pd.DataFrame, dict]:
    data = _get_json(MSPD, RAW / "treasury" / "mspd_market_2026-09-30.json")["data"]
    wins = {(b.maturity, round(b.coupon, 5)) for b in wins_treasury_bonds(2026, 2048)}
    bonds = []
    for r in data:
        if r["security_class1_desc"] not in ("Notes", "Bonds") or "null" in (r["maturity_date"], r["interest_rate_pct"]):
            continue
        mat = dt.date.fromisoformat(r["maturity_date"])
        c = float(r["interest_rate_pct"]) / 100
        cusip = r["security_class2_desc"]
        bonds.append((TreasuryBond(cusip, c, mat, cusip), r["security_class1_desc"][:-1], float(r["outstanding_amt"]) if r["outstanding_amt"] != "null" else np.nan,
                      f"{r['security_class1_desc'][:-1]} {c:.3%} {mat:%b %d, %Y}"))
    zc = bootstrap(par_curve(CURVE_DATE))
    acct = yaml.safe_load((ROOT / "config" / "wins_account.yaml").read_text())["ladder"]
    pays = payment_schedule(amount=50_000 * acct["scale"])
    wins_universe = wins_treasury_bonds(2026, 2048) + [ibonds_fund(t) for t in FUNDS]
    A, p, _, _ = build_matrix(wins_universe, pays, zc, 0.0)
    y, cost = shadow_prices(A, p, np.array([a for _, a in pays]))
    seen, live = set(), []
    for b, _, _, _ in bonds:
        if b.maturity > zc.date and b.cusip not in seen:
            seen.add(b.cusip)
            live.append(b)
    Ab, pb, labels, _ = build_matrix(live, pays, zc, 0.0)
    amt = pd.Series({}, dtype=float)
    for b, _, a, _ in bonds:
        amt[b.cusip] = np.nansum([amt.get(b.cusip, 0.0), a])
    kind = {b.cusip: (k, amt[b.cusip], desc) for b, k, _, desc in bonds}
    df = pd.DataFrame({"security": [kind[l][2] for l in labels], "cusip": labels, "type": [kind[l][0] for l in labels],
                       "coupon": [b.coupon for b in live], "maturity": [b.maturity for b in live],
                       "outstanding_bn": [kind[l][1] / 1000 for l in labels],
                       "listed_in_wins": [(b.maturity, round(b.coupon, 5)) in wins for b in live],
                       "value_per_100": 100 * (y @ Ab) / pb})
    df["value_rank"] = df["value_per_100"].round(2).rank(ascending=False, method="min").astype(int)
    df = df.sort_values(["value_per_100", "maturity"], ascending=[False, True])
    full = solve(live + [ibonds_fund(t) for t in FUNDS], pays, zc, 0.0)
    best_by_year = (df[df["maturity"].map(lambda d: 2032 <= d.year <= 2041)]
                    .groupby(df["maturity"].map(lambda d: d.year))["value_per_100"].max().round(2).to_dict())
    return df, {"securities": int(len(df)), "listed_in_wins": int(df["listed_in_wins"].sum()),
                "ladder_cost_wins": round(cost, 2), "ladder_cost_all_treasuries": round(full.cost, 2),
                "saving_if_all_listed": round(cost - full.cost, 2), "best_score_by_maturity_year": best_by_year,
                "above_100": int((df["value_per_100"] > 100.005).sum())}


def category(name: str) -> tuple[str, int]:
    for cat, pat, credit in CATEGORIES:
        if re.search(pat, name, re.I):
            return cat, credit
    return "Other", 3


def fund_universe() -> pd.DataFrame:
    rows = _get_json(SCREENER, RAW / "nasdaq_etf_screener_2026-11-03.json")["data"]
    rows = rows.get("data", rows)["rows"]
    df = pd.DataFrame(rows)[["symbol", "companyName"]].rename(columns={"companyName": "name"})
    keep = df["name"].str.contains(INCLUDE, case=False, regex=True) & ~df["name"].str.contains(EXCLUDE, case=False, regex=True)
    df = df[keep & df["symbol"].str.fullmatch(r"[A-Z]{2,5}")].drop_duplicates("symbol").copy()
    df[["category", "credit_quality"]] = [category(n) for n in df["name"]]
    return df.reset_index(drop=True)


def month_end_5y() -> pd.Series:
    frames = [pd.read_csv(RAW / f"treasury_par_{y}.csv", usecols=["Date", "5 Yr"]) for y in range(2014, 2027)]
    s = pd.concat(frames)
    s["Date"] = pd.to_datetime(s["Date"])
    return s.set_index("Date")["5 Yr"].sort_index().resample("ME").last() / 100


def fund_metrics(df: pd.DataFrame) -> pd.DataFrame:
    y5 = month_end_5y().diff()
    vti = yahoo.history("VTI", interval="1mo")["adjclose"].resample("ME").last().pct_change()
    out = []
    for sym in df["symbol"]:
        try:
            cached = yahoo._path(sym, "1mo").exists()
            h = yahoo.history(sym, start="2015-01-01", interval="1mo")
            if not cached:
                time.sleep(0.25)
        except Exception:
            out.append({"symbol": sym})
            continue
        h = h.resample("ME").last().loc[:DATA_END]
        adj, px = h["adjclose"], h["close"]
        r = adj.pct_change().dropna()
        rec = {"symbol": sym, "months": int(len(r)), "last_price": float(px.iloc[-1]) if len(px) else np.nan}
        if len(r) >= 13:
            rec["income_12m"] = float((adj.iloc[-1] / adj.iloc[-13]) / (px.iloc[-1] / px.iloc[-13]) - 1)
        if len(r) >= 36:
            l36 = r.iloc[-36:]
            vol = float(l36.std() * np.sqrt(12))
            ret3 = float((1 + l36).prod() ** (1 / 3) - 1)
            p60 = adj.iloc[-61:]
            m = pd.concat([l36, vti, y5], axis=1, join="inner").dropna()
            m.columns = ["f", "s", "dy"]
            rec.update(vol3=vol, ret3=ret3, sharpe3=(ret3 - 0.04) / vol if vol > 0 else np.nan,
                       maxdd=float((p60 / p60.cummax() - 1).min()),
                       stock_beta=float(np.cov(m["f"], m["s"])[0, 1] / m["s"].var()),
                       stock_corr=float(m["f"].corr(m["s"])),
                       rate_duration=float(-np.cov(m["f"], m["dy"])[0, 1] / m["dy"].var()))
        out.append(rec)
    return df.merge(pd.DataFrame(out), on="symbol", how="left")


def zs(s, by):
    g = s.groupby(by)
    sd = g.transform("std")
    return ((s - g.transform("mean")) / sd.where(sd > 0)).fillna(0.0)


def rank_funds(d: pd.DataFrame) -> pd.DataFrame:
    d["pass_data"] = (d["months"] >= 36) & (d["last_price"] >= 3) & d["vol3"].notna()
    ok = d["pass_data"]
    vcut, dcut = d.loc[ok, "vol3"].quantile(0.80), d.loc[ok, "maxdd"].quantile(0.20)
    d["pass_risk"] = ok & (d["vol3"] <= vcut) & (d["maxdd"] >= dcut) & (d["stock_beta"] <= 0.5)
    e = d[ok]
    d.loc[ok, "quant_index"] = 0.5 * zs(e["income_12m"].fillna(0), e["category"]) + 0.5 * zs(e["sharpe3"], e["category"])
    d.loc[ok, "quant_cat_pct"] = d.loc[ok].groupby("category")["quant_index"].rank(pct=True)
    d["pass_quant"] = d["pass_risk"] & (d["quant_cat_pct"] > 0.25)
    years = (dt.date(2032, 12, 15) - dt.date.fromisoformat(str(CURVE_DATE))).days / 365.25
    term = d["name"].str.extract(r"(20[2-4]\d)")[0].astype(float)
    gap = np.where(term.notna(), (term - 2032).abs() * 1.0, (d["rate_duration"] - years).abs())
    d["date_match"] = np.select([pd.Series(gap) <= 0.5, pd.Series(gap) <= 1.5, pd.Series(gap) <= 3, pd.Series(gap) <= 5],
                                [5, 4, 3, 2], 1).astype(float)
    d.loc[d["rate_duration"].isna() & term.isna(), "date_match"] = np.nan
    d["diversification"] = np.select([d["stock_corr"] <= 0.1, d["stock_corr"] <= 0.3, d["stock_corr"] <= 0.5,
                                      d["stock_corr"] <= 0.7], [5, 4, 3, 2], 1).astype(float)
    d.loc[d["stock_corr"].isna(), "diversification"] = np.nan
    d["concentration"] = np.where(d["category"] == "Emerging-market debt", 1.0,
                                  np.where(d["category"] == "International developed", 4.0, 5.0))
    dims = ["credit_quality", "date_match", "diversification", "concentration"]
    d["fit_score"] = d[dims].astype(float).mean(axis=1)
    d["accepted"] = d["credit_quality"] > 1
    a = d["accepted"] & d["pass_quant"] & d["fit_score"].notna()
    zf = lambda c: (d.loc[a, c] - d.loc[a, c].mean()) / d.loc[a, c].std()
    d.loc[a, "final_score"] = 0.5 * zf("fit_score") + 0.5 * zf("quant_index")
    d.loc[a, "final_rank"] = d.loc[a, "final_score"].rank(ascending=False, method="min")
    d.loc[a, "category_rank"] = d.loc[a].groupby("category")["final_score"].rank(ascending=False, method="min")
    d.attrs.update(vol_cut=float(vcut), dd_cut=float(dcut))
    return d.sort_values(["final_rank", "fit_score"], ascending=[True, False])


def main():
    tdf, tsum = treasury_universe()
    tdf.round(4).to_csv(OUT / "treasury_universe.csv", index=False)
    funds = rank_funds(fund_metrics(fund_universe()))
    cols = ["final_rank", "category_rank", "symbol", "name", "category", "months", "last_price", "income_12m", "sharpe3",
            "ret3", "vol3", "maxdd", "stock_beta", "stock_corr", "rate_duration", "pass_data", "pass_risk", "quant_index",
            "quant_cat_pct", "pass_quant", "credit_quality", "date_match", "diversification", "concentration",
            "fit_score", "accepted", "final_score"]
    funds[cols].round(4).to_csv(OUT / "bond_funds_universe.csv", index=False)
    held = funds.set_index("symbol").reindex(["IBTM", "IBTO", "IBTP", "IBTQ", "IBTR"])[["final_rank", "category_rank", "fit_score", "quant_index"]]
    summary = {"treasuries": tsum, "funds": {
        "universe": int(len(funds)), "pass_data": int(funds["pass_data"].sum()), "pass_risk": int(funds["pass_risk"].sum()),
        "pass_quant": int(funds["pass_quant"].sum()), "final_ranked": int(funds["final_rank"].notna().sum()),
        "categories": funds["category"].value_counts().to_dict(),
        "risk_cuts": {"vol3_max": round(funds.attrs.get("vol_cut", np.nan), 4), "maxdd_min": round(funds.attrs.get("dd_cut", np.nan), 4)},
        "our_funds": json.loads(held.round(3).to_json(orient="index"))}}
    (OUT / "bond_universe_summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps(summary, indent=1, default=str))
    print(funds[funds["final_rank"].notna()].head(12)[["final_rank", "symbol", "name", "category", "fit_score", "quant_index"]]
          .round(2).to_string(index=False))


if __name__ == "__main__":
    main()
