"""Does USD/TWD mean-revert over Laura's horizon, or is the model's random walk right?

Usage: python scripts/fx_horizon.py [n_null]
The model's USD/TWD is a random walk, so its 74-month spread grows with the square root of time. Over
2000-2026 (the H.10 series the model calibrates on) the 74-month change spread is half that, which
looks like mean reversion. This tests it: variance ratios at 12, 36 and 74 months against a random
walk built by resampling the same months' changes (same length, same fat tails, so the small-sample
downward bias of overlapping ratios is in the null too), on 2000-2026 and on FRED's longer copy of
the same H.10 rate (DEXTAUS, from Oct 1983; identical month-ends after 2000). Writes
reports/fx_horizon.csv with the model's spread alongside.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from lgm.calibrate import usd_twd_monthly
from lgm.data import fred
from lgm.esg import simulate
from lgm.growth.core import build_core
from lgm.growth.scoring import esg_params

OUT = Path(__file__).resolve().parents[1] / "reports" / "fx_horizon.csv"
HORIZONS = (12, 36, 74)


def variance_ratio(x: np.ndarray, h: int) -> float:
    r1 = np.diff(x)
    mu = r1.mean()
    return float(((x[h:] - x[:-h] - h * mu) ** 2).mean() / (h * ((r1 - mu) ** 2).mean()))


def main(n_null: int = 4000):
    long = fred.fetch(["DEXTAUS"], "dextaus")["DEXTAUS"].dropna().resample("ME").last()
    h10 = usd_twd_monthly()
    both = pd.concat([np.log(long).rename("fred"), np.log(h10).rename("h10")], axis=1).dropna()
    assert (both.fred - both.h10).abs().max() < 1e-6, "FRED DEXTAUS and the H.10 page disagree"
    core = build_core()
    sc = simulate(esg_params(core["cal"], core["table"]["bl_geo_total"].values), n=20_000, seed=11)
    rng = np.random.default_rng(0)
    rows = []
    for label, s in (("H.10 2000-2026", np.log(h10)), ("DEXTAUS 1983-2026", np.log(long))):
        x = s.values
        dx = np.diff(x)
        for h in HORIZONS:
            null = np.array([variance_ratio(np.r_[0, np.cumsum(rng.choice(dx, len(dx)))], h) for _ in range(n_null)])
            vr = variance_ratio(x, h)
            ch = x[h:] - x[:-h]
            m = sc.fx_log[:, h] - sc.fx_log[:, 0]
            rows.append({"sample": label, "start": str(s.index[0].date()), "months": len(x), "horizon_m": h,
                         "variance_ratio": vr, "rw_null_median": float(np.median(null)),
                         "p_mean_reversion": float((null <= vr).mean()), "hist_sd": float(ch.std()),
                         "hist_p5": float(np.quantile(ch, .05)), "hist_p95": float(np.quantile(ch, .95)),
                         "model_sd": float(m.std()), "model_p5": float(np.quantile(m, .05)),
                         "model_p95": float(np.quantile(m, .95))})
            r = rows[-1]
            print(f"{label:18s} h={h:2d}: VR {vr:.2f} (random walk median {r['rw_null_median']:.2f}, "
                  f"p {r['p_mean_reversion']:.2f}); change sd history {r['hist_sd']:.3f}, model {r['model_sd']:.3f}")
    pd.DataFrame(rows).round(4).to_csv(OUT, index=False)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4000)
