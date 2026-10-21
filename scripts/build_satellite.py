"""Build the stock satellite and score core + satellite with the Monte Carlo.

Usage: python scripts/build_satellite.py [n_scenarios] [--rescreen]
  1. Quant screen of the S&P 500 (IVV holdings)          -> reports/satellite_quant_screen.csv   (--rescreen)
  2. Sector-balanced shortlist                            -> reports/satellite_shortlist.csv      (--rescreen)
  3. Nasdaq evidence for the shortlist                    -> reports/satellite_evidence.csv       (--rescreen)
  4. Qualitative model and selection                      -> reports/satellite_qualitative.csv, satellite_selected.csv
  5. HRP weights; satellite inside Black-Litterman        -> reports/satellite_weights.csv, satellite_bl.csv
  6. Monte Carlo: satellite share x beliefs x commissions -> reports/satellite_scoring.csv
  7. WInS whole-share orders at the Oct 20, 2026 close    -> reports/satellite_wins_orders.csv
Without --rescreen, steps 1-3 are read from reports/ (they depend on prices cached at screen time).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from lgm import engine
from lgm.data import nasdaq, yahoo
from lgm.growth import qualitative, satellite
from lgm.growth.core import build_core
from lgm.growth.lookthrough import market_weights_and_exposures
from lgm.growth.portfolio import basket_returns, carve, satellite_weights, whole_shares, with_satellite
from lgm.growth.scoring import esg_params, score
from lgm.growth.universe import CORE

ROOT = Path(__file__).resolve().parents[1]
OUT, CFG = ROOT / "reports", ROOT / "config"
SHARE_CLASS_DUPLICATES = {"GOOG": "GOOGL", "FOX": "FOXA", "NWS": "NWSA"}
PRICE_DATE = "2026-10-20"
SHARES = (0.0, 0.10, 0.20, 0.30)


def screen_and_shortlist():
    u = satellite.universe()
    px = satellite.prices(u["yahoo"].tolist() + ["VTI"])
    d = satellite.quant_screen(u, satellite.metrics(px.drop(columns=["VTI"]), px["VTI"]))
    d.to_csv(OUT / "satellite_quant_screen.csv")
    short = satellite.shortlist(d)
    short.to_csv(OUT / "satellite_shortlist.csv")
    names = [t for t in short["ticker"] if t not in SHARE_CLASS_DUPLICATES]
    ev = pd.DataFrame.from_dict({t: nasdaq.evidence(t) for t in names}, orient="index")
    ev.to_csv(OUT / "satellite_evidence.csv")


def select(qcfg: dict) -> pd.DataFrame:
    screen = pd.read_csv(OUT / "satellite_quant_screen.csv", index_col=0)
    ev = pd.read_csv(OUT / "satellite_evidence.csv", index_col=0)
    df = qualitative.score(screen, ev, pd.read_csv(CFG / "qualitative_judgments.csv"), qcfg)
    sel = qualitative.select(df, qcfg["selection"]["target_names"], qcfg["selection"]["max_sector_share"])
    df.to_csv(OUT / "satellite_qualitative.csv")
    sel.to_csv(OUT / "satellite_selected.csv")
    print(f"qualitative model: {int(df['accepted'].sum())} of {len(df)} accepted, {len(sel)} selected")
    return sel


def wins_orders(w: pd.Series, sel: pd.DataFrame, budgets: dict[str, float], cov: pd.DataFrame) -> pd.DataFrame:
    px = pd.Series({t: float(yahoo.history(t, start="2026-10-01", end=PRICE_DATE, interval="1d", refresh=True)
                         .loc[PRICE_DATE, "close"]) for t in w.index})
    rows, summary = [], []
    for label, b in budgets.items():
        n = whole_shares(w, px, b)
        held = n * px
        w_real = held / held.sum()
        err = w_real - w
        te = float(np.sqrt(err @ cov.loc[w.index, w.index].values @ err) * np.sqrt(12))
        trades = int((n > 0).sum())
        summary.append({"budget": label, "dollars": b, "names_held": trades, "invested": round(held.sum(), 2),
                        "cash_left": round(b - held.sum(), 2), "commissions": 25 * trades,
                        "commission_pct": round(25 * trades / b, 4), "max_weight_error": round(float(err.abs().max()), 4),
                        "tracking_error_vs_target": round(te, 4)})
        for t in w.index:
            rows.append({"budget": label, "ticker": t, "sector": sel.loc[t, "sector"], "price": round(px[t], 2),
                         "target_weight": round(w[t], 4), "shares": int(n[t]), "dollars": round(held[t], 2),
                         "weight": round(w_real[t], 4)})
    pd.DataFrame(rows).to_csv(OUT / "satellite_wins_orders.csv", index=False)
    return pd.DataFrame(summary)


def main(n: int = 20_000, rescreen: bool = False):
    qcfg = yaml.safe_load((CFG / "qualitative.yaml").read_text())
    ccfg = yaml.safe_load((CFG / "cma.yaml").read_text())
    imp = qcfg["implementation"]
    if rescreen:
        screen_and_shortlist()
    sel = select(qcfg)
    tickers = sel.index.tolist()

    # 5. HRP weights and the satellite inside Black-Litterman
    w_sat = satellite_weights(tickers, months=imp["hrp_lookback_months"])
    sat = basket_returns(w_sat)
    core = build_core()
    r = with_satellite(core, sat, ccfg["satellite_view"])
    tech = sel["sector"].isin(satellite.TECH).astype(float)
    pd.DataFrame({"sector": sel["sector"], "hrp_weight": w_sat.round(5)}).sort_values("hrp_weight", ascending=False) \
        .to_csv(OUT / "satellite_weights.csv")
    K = len(CORE)
    rf, var = ccfg["cash_long_run"], r["var"]
    names = [g.etf for g in CORE] + ["SATELLITE"]
    pd.DataFrame({"asset": names, "w_mkt": r["w_mkt"], "vol": np.sqrt(var), "pi_excess": r["pi"],
                  "bl_excess": r["mu"], "bl_geo_total": r["mu"] + rf - 0.5 * var}).round(5) \
        .to_csv(OUT / "satellite_bl.csv", index=False)
    w_core = core["w_bl"]
    fund = carve(w_core, 1.0) - np.r_[w_core, 0.0]
    edge = float(r["mu"] @ fund)                          # posterior edge over the ETFs it replaces
    print("satellite: style benchmark " + ", ".join(f"{k} {v:.1%}" for k, v in r["style"].items()))
    print(f"satellite: vol {np.sqrt(var[K]):.3f}, beta {r['beta_vs_market']:.2f}, tracking error vs style benchmark "
          f"{r['tracking_error']:.3f}; stock-selection alpha {r['alpha_prior']:.4f} -> posterior {r['alpha_post']:.4f}"
          f" ({r['alpha_spillover']:+.4f} from the style views); arithmetic edge over its funding ETFs {edge:.4f}")

    # Look-through: the carve-out must not add tech/communication or China/Taiwan exposure
    mw = market_weights_and_exposures(CORE)
    mkt_tech = float(core["w_mkt"] @ mw["tech"])
    for s in SHARES:
        w = carve(w_core, s)
        t_share = float(w[:K] @ mw["tech"] + w[K] * (w_sat @ tech))
        ct = float(w[:K] @ mw["china_taiwan"])
        print(f"  satellite {s:.0%}: look-through tech/comm {t_share:.3f} (market {mkt_tech:.3f}), China+Taiwan {ct:.4f}")
        if t_share > mkt_tech or ct > float(core["w_mkt"] @ mw["china_taiwan"]) + 1e-9:
            raise SystemExit(f"satellite at {s:.0%} breaks the look-through limits")

    # 6. Monte Carlo
    sat_kw = {"extra_tickets": len(tickers) - 1, "annual_cost": 2 * imp["annual_replacements"] * engine.COMMISSION_ETF}
    er = np.r_[[g.expense_ratio for g in CORE], 0.0]
    cands = {f"Core + {s:.0%} satellite" if s else "BL core only": carve(w_core, s) for s in SHARES}
    geo_eq = r["pi"] + rf - 0.5 * var
    geo_bl = r["mu"] + rf - 0.5 * var
    geo_hoped = geo_bl.copy()
    added = r["alpha_prior"] - r["alpha_post"] - r["alpha_spillover"]
    geo_hoped[K] += added
    beliefs = {"Equilibrium (no alpha)": geo_eq, "Black-Litterman posterior": geo_bl,
               "Satellite alpha as hoped (+1.0%)": geo_hoped}
    kw = {k: (sat_kw if "satellite" in k else {}) for k in cands}
    rows = []
    for bname, geo in beliefs.items():
        p = esg_params(r["cal"], geo)
        for k, v in score(cands, {k: er for k in cands}, p, n=n, with_2031=False, engine_kw=kw).items():
            rows.append({"beliefs": bname, "commissions": "$25 (WInS)", "candidate": k, **v})
        if bname == "Black-Litterman posterior":
            free = {k: {**kw[k], "commissions": False} for k in cands}
            for k, v in score(cands, {k: er for k in cands}, p, n=n, with_2031=False, engine_kw=free).items():
                rows.append({"beliefs": bname, "commissions": "none", "candidate": k, **v})
    df = pd.DataFrame(rows)
    base = df[df["candidate"] == "BL core only"].set_index(["beliefs", "commissions"])["median"]
    df["median_vs_core"] = df["median"] - df.set_index(["beliefs", "commissions"]).index.map(base)
    df.round(4).to_csv(OUT / "satellite_scoring.csv", index=False)

    # Break-even alpha for the chosen share, from the posterior and "as hoped" runs (linear in alpha)
    pick = f"Core + {imp['share_of_equity']:.0%} satellite"
    g = df[(df["candidate"] == pick) & (df["commissions"] == "$25 (WInS)")].set_index("beliefs")["median_vs_core"]
    slope = (g["Satellite alpha as hoped (+1.0%)"] - g["Black-Litterman posterior"]) / added
    extra_needed = -g["Black-Litterman posterior"] / slope
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print(df[["beliefs", "commissions", "candidate", "funded", "p5", "median", "p95", "cvar5", "median_vs_core"]]
              .round(0).to_string(index=False))
    print(f"{pick}: each +1pp of satellite alpha moves the median facility by ${slope / 100:,.0f};"
          f" with $25 commissions it needs {extra_needed:+.4f} a year of alpha beyond the posterior to break even")

    # 7. WInS whole-share orders
    sat_cov = long_cov(tickers)
    budgets = {"WInS mirror (20% of $60k equity)": 12_000.0, "Plan, Jan 2028 (20% of ~$90k equity)": 18_000.0}
    print(wins_orders(w_sat, sel, budgets, sat_cov).to_string(index=False))


def long_cov(tickers: list[str], months: int = 60, end: str = "2026-09-30") -> pd.DataFrame:
    from lgm.growth.portfolio import long_prices
    return long_prices(tickers).pct_change().loc[:end].iloc[-months:].cov()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(int(args[0]) if args else 20_000, rescreen="--rescreen" in sys.argv)
