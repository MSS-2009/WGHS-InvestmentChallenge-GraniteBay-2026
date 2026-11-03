"""CSV inputs for the Google Sheets workbook (Stock Universe Ranking and Black-Litterman).

Usage: python scripts/sheet_exports.py
Writes reports/sheets/*.csv: only the measured inputs, in the workbook's column order. The workbook reads them
with IMPORTDATA from this repository and computes every score, pass and rank itself with formulas, so the
sheet and the Python scripts can be checked against each other.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REP = ROOT / "reports"
OUT = REP / "sheets"


def stocks_pass1():
    p1 = pd.read_csv(REP / "universe_pass1_quant.csv").sort_values("quant_rank")
    p1 = p1.rename(columns={"ticker": "Ticker", "name": "Company", "sector": "Sector", "months": "Months of data",
                            "last_price": "Price ($)", "mom12_1": "12-1 month momentum", "sharpe3": "3-yr Sharpe ratio",
                            "vol3": "3-yr volatility", "maxdd5": "5-yr max drawdown", "beta3": "Beta (3-yr)"})
    p1[["Ticker", "Company", "Sector", "Months of data", "Price ($)", "12-1 month momentum", "3-yr Sharpe ratio",
        "3-yr volatility", "5-yr max drawdown", "Beta (3-yr)"]].to_csv(OUT / "stocks_pass1.csv", index=False)


def stocks_pass2():
    p2 = pd.read_csv(REP / "universe_pass2_qual.csv")
    p2["excluded"] = p2["reject_reason"].fillna("").str.extract(r"excluded activity: ([^;]+)")[0].fillna("")
    out = pd.DataFrame({
        "Ticker": p2["ticker"], "Company": p2["name"].str.replace(",", "", regex=False), "Sector": p2["sector"],
        "Innovation and creativity": p2["innovation_creativity"], "Societal utility": p2["societal_utility"],
        "People and inclusion": p2["people_inclusion"], "Trust and integrity": p2["trust_integrity"],
        "Access education and creators": p2["access_education_creators"],
        "Management (ROE and margin trend)": p2["management_capital_allocation"],
        "Competitive position (margins vs peers)": p2["moat_position"],
        "Risk flags (volatility and drawdown)": p2["risk_flags"], "Financial quality": p2["financial_quality"],
        "Growth": p2["growth_innovation"], "Sentiment and momentum": p2["sentiment_momentum"],
        "Excluded activity": p2["excluded"], "Analyst rating": p2["analyst_rating"].fillna(""),
        "Revenue growth (3-yr a year)": p2["rev_cagr_3y"],
        "Operating margin (4-yr avg)": p2["op_margin_avg4"] / 100, "Return on equity": p2["roe"] / 100,
        "Values keyword hits": p2[[c for c in p2.columns if c.endswith("_hits")]].sum(axis=1),
    })
    out.to_csv(OUT / "stocks_pass2.csv", index=False)


def bonds():
    d = pd.read_csv(REP / "bond_funds_universe.csv")
    out = pd.DataFrame({
        "Symbol": d["symbol"], "Fund": d["name"].str.slice(0, 60), "Category": d["category"],
        "Credit quality (1-5)": d["credit_quality"], "Months of data": d["months"], "Price ($)": d["last_price"],
        "12-month income return": d["income_12m"], "3-yr Sharpe ratio": d["sharpe3"], "3-yr volatility": d["vol3"],
        "Max drawdown (5-yr)": d["maxdd"], "Stock beta": d["stock_beta"], "Correlation with US stocks": d["stock_corr"],
        "Rate sensitivity (years)": d["rate_duration"], "Matches 2033 date (1-5)": d["date_match"],
        "Diversification (1-5)": d["diversification"], "Concentration (1-5)": d["concentration"],
    })
    out.to_csv(OUT / "bond_funds.csv", index=False)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bonds()
    stocks_pass1()
    if (REP / "universe_pass2_qual.csv").exists():
        stocks_pass2()
    for f in sorted(OUT.glob("*.csv")):
        print(f.name, sum(1 for _ in f.open()) - 1, "rows")


if __name__ == "__main__":
    main()
