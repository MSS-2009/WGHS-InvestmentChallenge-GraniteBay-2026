"""What each of the October 22, 2026 changes did to the IPS headline (a waterfall).

Usage: python scripts/round6_waterfall.py [n_scenarios]
Starts from the morning's model (round 5 merged) and switches the round-6 changes on one at a time,
in the order they were made, re-running the headline IPS (Black-Litterman core and beliefs, WInS
commissions, 20,000 scenarios, seed 11) after each. The last row is today's headline. Writes
reports/round6_waterfall.csv.
"""
import copy
import dataclasses as dc
import sys
from pathlib import Path

import pandas as pd
import yaml

from lgm import engine
from lgm.calibrate import calibrate_assets
from lgm.esg import simulate
from lgm.growth.core import CFG, build_core
from lgm.growth.scoring import esg_params
from lgm.growth.universe import CORE
from lgm.profiles import _cal
from lgm.strategies import IPS

OUT = Path(__file__).resolve().parents[1] / "reports" / "round6_waterfall.csv"
JPM_2026 = {"us": 0.067, "intl_dev": 0.075, "em": 0.078}      # the edition config/cma.yaml carried this morning
STEPS = [
    ("Morning model (round 5 merged)", {}),
    ("Commissions compounded", {"compound": True}),
    ("Sale tickets in January 2033", {"settle": True}),
    ("Taiwan cost growth correlated with USD/TWD", {"twfx": True}),
    ("Rate persistence bias-corrected (Kendall)", {"kendall": True}),
    ("J.P. Morgan 2027 assumptions", {"jpm2027": True}),
    ("Equity correlations shrunk toward their average", {"shrink_mean": True}),
    ("EMXC and MCHI volatility include 2008", {"vol_proxies": True}),
    ("Black-Litterman market level anchored to the consensus", {"anchor": True}),
]


def headline(on: dict, n: int) -> dict:
    cfg = yaml.safe_load(CFG.read_text())
    cfg["anchor_market_to_consensus"] = on.get("anchor", False)
    if not on.get("jpm2027", False):
        firms = copy.deepcopy(cfg["firms"])
        firms.pop("J.P. Morgan 2027")
        firms["J.P. Morgan 2026"] = JPM_2026
        cfg["firms"] = firms
    cal = calibrate_assets([g.history for g in CORE], equity_shrink_target="mean" if on.get("shrink_mean") else "zero",
                           vol_proxies=None if on.get("vol_proxies") else {})
    r = build_core(cfg=cfg, cal=cal)
    p = esg_params(r["cal"], r["table"]["bl_geo_total"].values, phi=None if on.get("kendall") else _cal().phi)
    if not on.get("twfx"):
        p = dc.replace(p, tw_cost_fx_corr=0.0)
    sc = simulate(p, n=n, seed=11)
    cfg_e = engine.EngineConfig(eq_er=tuple(g.expense_ratio for g in CORE), compound_costs=on.get("compound", False),
                                sell_at_settlement=on.get("settle", False))
    return engine.summarize(engine.run(dc.replace(IPS, region_weights=tuple(r["w_bl"])), sc, cfg_e))


def main(n: int = 20_000):
    on, rows, prev = {}, [], None
    for label, switch in STEPS:
        on.update(switch)
        s = headline(on, n)
        row = {"step": label, **{k: s[k] for k in ("median", "p5", "cvar5", "real_median")}}
        for k in ("median", "p5", "cvar5", "real_median"):
            row[f"{k}_change"] = 0.0 if prev is None else s[k] - prev[k]
        rows.append(row)
        prev = s
        print(f"{label:58s} median {s['median']:,.0f} ({row['median_change']:+,.0f})  p5 {s['p5']:,.0f} "
              f"({row['p5_change']:+,.0f})  real median {s['real_median']:,.0f} ({row['real_median_change']:+,.0f})")
    pd.DataFrame(rows).round(1).to_csv(OUT, index=False)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20_000)
