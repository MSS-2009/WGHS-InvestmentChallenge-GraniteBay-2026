"""Does the ladder's premium over zero-coupon value hold when rates move?

Usage: python scripts/ladder_premium.py [n_scenarios]
The engine prices a locked payment at its zero-coupon value plus a fixed premium (`kappa0`, 1.8%, the
LP's on today's curve, scaled down with the ladder's remaining time). This re-solves the cheapest
WInS ladder (`ladder.premium`, cash awaiting a payment at 3%) on 61 simulated curves spread across the
5-year rate's range at each lock date, fits premium = a + b x (5-year rate - today's), and scores the
strategies with that slope (`EngineConfig.kappa_rate_slope`) and with the fitted Jan 2027 level.
Today's WInS instruments are used at every date, so the 2031 fit is rougher (bonds age out, new ones
are not added). Jan 2033 is omitted because the first scheduled payment is due at settlement, so there
is no remaining ladder to price. Writes reports/ladder_premium.csv.
"""
import dataclasses as dc
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from lgm import engine, ladder
from lgm.asof import START
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.strategies import IPS, S1, S2, S6, S9

OUT = Path(__file__).resolve().parents[1] / "reports" / "ladder_premium.csv"


def month_date(m: int) -> dt.date:
    return dt.date(START.year + (START.month - 1 + m) // 12, (START.month - 1 + m) % 12 + 1, 1)


def main(n: int = 20_000):
    core = build_core()
    p = esg_params(core["cal"], core["table"]["bl_geo_total"].values)
    sc = simulate(p, n=n, seed=11)
    ref = float(sc.zero_cc(0, 5.0)[0, 0])
    cfg0 = engine.EngineConfig()
    rows, fits = [], {}
    for name, m in (("Jan 2027", engine.M_2027), ("Jan 2028", engine.M_2028), ("Jan 2031", engine.M_2031)):
        z5 = sc.zero_cc(m, 5.0)[:, 0]
        idx = np.argsort(z5)[np.linspace(0, n - 1, 61).astype(int)]
        prem = np.array([ladder.premium(sc.curve(i, m, month_date(m))) for i in idx])
        b, a = np.polyfit(z5[idx] - ref, prem, 1)
        fits[name] = (a, b)
        rows.append({"kind": "fit", "date": name, "engine_kappa": engine.kappa(m, cfg0), "lp_at_today_rate": a,
                     "slope": b, "resid_sd": float((prem - a - b * (z5[idx] - ref)).std()),
                     "lp_min": prem.min(), "lp_max": prem.max(), "z5_p5": np.quantile(z5, .05), "z5_p95": np.quantile(z5, .95)})
        r = rows[-1]
        print(f"{name}: engine {r['engine_kappa']:.4f}; LP {a:.4f} + {b:.2f} x (5y - {ref:.2%}), resid sd {r['resid_sd']:.4f}, "
              f"range {r['lp_min']:.4f}..{r['lp_max']:.4f}")
    slope = float(np.mean([fits["Jan 2027"][1], fits["Jan 2028"][1]]))   # the lock dates that carry the money
    w = tuple(np.asarray(core["w_bl"]) / np.sum(core["w_bl"]))
    er = tuple(g.expense_ratio for g in CORE)
    variants = {"constant (engine)": {}, "rate slope": {"kappa_rate_slope": slope, "kappa_rate_ref": ref},
                "rate slope, Jan 2027 LP level": {"kappa_rate_slope": slope, "kappa_rate_ref": ref,
                                                  "kappa0": float(fits["Jan 2027"][0])}}
    base = {}
    for v, kw in variants.items():
        for st in (IPS, S1, S2, S6, S9):
            s = engine.summarize(engine.run(dc.replace(st, region_weights=w), sc, engine.EngineConfig(eq_er=er, **kw)))
            b0 = base.setdefault(st.name, s)
            rows.append({"kind": "score", "variant": v, "slope": kw.get("kappa_rate_slope", 0.0),
                         "kappa0": kw.get("kappa0", cfg0.kappa0), "strategy": st.name, "median": s["median"],
                         "p5": s["p5"], "cvar5": s["cvar5"], "median_vs_engine": s["median"] - b0["median"],
                         "p5_vs_engine": s["p5"] - b0["p5"], "cvar5_vs_engine": s["cvar5"] - b0["cvar5"]})
            r = rows[-1]
            print(f"{v:30s} {st.name[:36]:36s} median {r['median_vs_engine']:+,.0f}  p5 {r['p5_vs_engine']:+,.0f}  "
                  f"cvar5 {r['cvar5_vs_engine']:+,.0f}")
    pd.DataFrame(rows).round(5).to_csv(OUT, index=False)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20_000)
