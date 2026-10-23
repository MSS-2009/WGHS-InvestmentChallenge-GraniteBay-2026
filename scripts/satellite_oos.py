"""Is the stock satellite's risk understated by selection? An out-of-sample test.

Usage: python scripts/satellite_oos.py [n_random]
The satellite's names were picked for low past volatility and drawdown, and its volatility and beta
are then measured over the same history, so both are suspected to be biased low. This re-runs the
quantitative part of the selection at past dates and compares the chosen basket's risk before the
date (what the model would have used) with its risk after it.

At each screen date (quarterly through 2023: the cached prices start in 2018 and the screen needs five
years): the house screen (`satellite.metrics`, `satellite.quant_screen`, `satellite.shortlist`) on
data to that date, then the 35 best return-quality names with at most 7 per sector (the qualitative
judgments cannot be reproduced historically), weighted by HRP on the prior 60 months. In-sample is the
36 months before the date; out-of-sample is every month after it. Control: random 35-name baskets from
the same screen-date universe, weighted the same way, over the same windows, which separates the
selection effect from the market simply getting calmer or rougher. Universe: today's S&P 500, so
names that left the index are missing (survivorship), which flatters every basket alike.
Writes reports/satellite_oos.csv.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from lgm.growth import satellite
from lgm.growth.qualitative import hrp_weights

OUT = Path(__file__).resolve().parents[1] / "reports" / "satellite_oos.csv"
DATES = ["2023-01-31", "2023-04-30", "2023-07-31", "2023-10-31"]
N_NAMES, MAX_PER_SECTOR = 35, 7


def basket_stats(w: pd.Series, r: pd.DataFrame, m: pd.Series) -> tuple[float, float]:
    """Annual volatility and beta to the market of a fixed-weight basket over the months of r."""
    rr = r[w.index].fillna(0) @ w
    mm = m.loc[rr.index]
    return float(rr.std() * np.sqrt(12)), float(np.cov(rr, mm)[0, 1] / mm.var())


def pick(screen: pd.DataFrame) -> list[str]:
    short = satellite.shortlist(screen).sort_values("rq_score", ascending=False)
    chosen, per = [], {}
    for t, row in short.iterrows():
        if per.get(row["sector"], 0) < MAX_PER_SECTOR:
            chosen.append(t)
            per[row["sector"]] = per.get(row["sector"], 0) + 1
        if len(chosen) == N_NAMES:
            break
    return chosen


def main(n_random: int = 300):
    u = satellite.universe()
    cached = [t for t in u["yahoo"] if (satellite.yahoo.RAW / f"{t}_1mo.csv").exists()]
    px = satellite.prices(cached + ["VTI"])               # cached only: no downloads
    mkt = px.pop("VTI")
    ret, mret = px.pct_change(), mkt.pct_change()
    rng = np.random.default_rng(0)
    rows = []
    for d in DATES:
        t = pd.Timestamp(d)
        screen = satellite.quant_screen(u, satellite.metrics(px, mkt, end=d))
        sel = pick(screen)
        pool = screen.index.tolist()                      # every name with enough data at the screen date
        hist60 = ret.loc[:t].iloc[-60:]
        ins, oos = ret.loc[:t].iloc[-36:], ret.loc[t:].iloc[1:]
        def stats(names):
            w = hrp_weights(hist60[names].dropna(axis=1))
            return (*basket_stats(w, ins, mret), *basket_stats(w, oos, mret))
        s = stats(sel)
        ctrl = np.array([stats(list(rng.choice(pool, N_NAMES, replace=False))) for _ in range(n_random)])
        ratio_sel, ratio_ctrl = s[2] / s[0], ctrl[:, 2] / ctrl[:, 0]
        rows.append({"screen_date": d, "oos_months": len(oos), "n_pool": len(pool),
                     "sel_vol_in": s[0], "sel_vol_out": s[2], "sel_beta_in": s[1], "sel_beta_out": s[3],
                     "sel_vol_ratio": ratio_sel, "sel_beta_ratio": s[3] / s[1],
                     "ctrl_vol_in_median": float(np.median(ctrl[:, 0])), "ctrl_vol_out_median": float(np.median(ctrl[:, 2])),
                     "ctrl_vol_ratio_median": float(np.median(ratio_ctrl)),
                     "ctrl_beta_ratio_median": float(np.median(ctrl[:, 3] / ctrl[:, 1])),
                     "sel_vol_ratio_pctile_in_ctrl": float((ratio_ctrl < ratio_sel).mean())})
        x = rows[-1]
        print(f"{d}: selected vol {x['sel_vol_in']:.1%} -> {x['sel_vol_out']:.1%} (x{x['sel_vol_ratio']:.2f}), "
              f"beta {x['sel_beta_in']:.2f} -> {x['sel_beta_out']:.2f} | random baskets vol "
              f"{x['ctrl_vol_in_median']:.1%} -> {x['ctrl_vol_out_median']:.1%} (x{x['ctrl_vol_ratio_median']:.2f}), "
              f"beta x{x['ctrl_beta_ratio_median']:.2f} | selected ratio at {x['sel_vol_ratio_pctile_in_ctrl']:.0%} of random")
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)
    print(f"mean vol ratio: selected {df.sel_vol_ratio.mean():.2f}, random {df.ctrl_vol_ratio_median.mean():.2f}; "
          f"selection effect {df.sel_vol_ratio.mean() / df.ctrl_vol_ratio_median.mean():.2f}x. Wrote {OUT}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 300)
