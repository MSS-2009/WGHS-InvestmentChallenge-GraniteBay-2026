"""What the satellite verdict looks like if its risk is as understated as scripts/satellite_oos.py measures.

Usage: python scripts/satellite_risk_sensitivity.py [n_scenarios]
The basket's monthly returns are rescaled around their mean by the out-of-sample factor (1.0 = as
estimated), then pushed through the same Black-Litterman and Monte Carlo steps as
scripts/build_satellite.py. Two readings of the extra risk:
  with_return  the larger beta also raises the satellite's equilibrium return (CAPM: risk is paid)
  risk_only    the return stays at the unscaled estimate, only the risk grows (the cautious reading)
Writes reports/satellite_risk_sensitivity.csv.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from lgm import engine
from lgm.growth.core import build_core
from lgm.growth.portfolio import basket_returns, satellite_weights, with_satellite
from lgm.growth.scoring import esg_params, score
from lgm.growth.universe import CORE

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_satellite", ROOT / "scripts" / "build_satellite.py")
bs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bs)


def main(n: int = 20_000):
    oos = pd.read_csv(ROOT / "reports" / "satellite_oos.csv")
    factor = float(oos.sel_vol_ratio.mean() / oos.ctrl_vol_ratio_median.mean())
    qcfg = yaml.safe_load((ROOT / "config" / "qualitative.yaml").read_text())
    ccfg = yaml.safe_load((ROOT / "config" / "cma.yaml").read_text())
    imp = qcfg["implementation"]
    sel = pd.read_csv(ROOT / "reports" / "satellite_selected.csv", index_col=0)
    tickers = sel.index.tolist()
    w_sat = satellite_weights(tickers, months=imp["hrp_lookback_months"])
    sat = basket_returns(w_sat)
    core = build_core()
    K, rf = len(CORE), ccfg["cash_long_run"]
    share = imp["share_of_equity"]
    cands = {"BL core only": bs.carve(core["w_bl"], 0.0), "satellite": bs.carve(core["w_bl"], share)}
    er = np.r_[[g.expense_ratio for g in CORE], 0.0]
    sat_kw = {"extra_tickets": len(tickers) - 1, "annual_cost": 2 * imp["annual_replacements"] * engine.COMMISSION_ETF}
    base = with_satellite(core, sat, ccfg["satellite_view"])
    geo_base = base["mu"] + rf - 0.5 * base["var"]
    rows = []
    for scale in (1.0, factor):
        r = with_satellite(core, sat.mean() + scale * (sat - sat.mean()), ccfg["satellite_view"])
        geo = r["mu"] + rf - 0.5 * r["var"]
        readings = {"with_return": geo} if scale == 1.0 else {"with_return": geo, "risk_only": geo_base}
        for reading, g in readings.items():
            p = esg_params(r["cal"], g)
            for comm in (True, False):
                kw = {"BL core only": {"commissions": comm}, "satellite": {**sat_kw, "commissions": comm}}
                res = score(cands, {k: er for k in cands}, p, n=n, with_2031=False, engine_kw=kw)
                c, s = res["BL core only"], res["satellite"]
                rows.append({"risk_scale": round(scale, 3), "reading": reading if scale != 1.0 else "as_estimated",
                             "commissions": "$25 (WInS)" if comm else "none", "satellite_vol": float(np.sqrt(r["var"][K])),
                             "satellite_beta": float(r["beta_vs_market"]),
                             "median_vs_core": s["median"] - c["median"], "p5_vs_core": s["p5"] - c["p5"],
                             "cvar5_vs_core": s["cvar5"] - c["cvar5"]})
                x = rows[-1]
                print(f"scale {scale:.2f} {x['reading']:12s} {x['commissions']:10s} vol {x['satellite_vol']:.3f} beta "
                      f"{x['satellite_beta']:.2f}: median {x['median_vs_core']:+,.0f}  p5 {x['p5_vs_core']:+,.0f}  "
                      f"cvar5 {x['cvar5_vs_core']:+,.0f} (vs core alone, {share:.0%} satellite)")
    pd.DataFrame(rows).round(4).to_csv(ROOT / "reports" / "satellite_risk_sensitivity.csv", index=False)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20_000)
