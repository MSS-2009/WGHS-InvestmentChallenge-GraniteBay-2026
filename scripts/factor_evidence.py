"""Long-run evidence from the Kenneth French Data Library for the views in config/cma.yaml.

Usage: python scripts/factor_evidence.py
- Large value minus large growth and small minus large: geometric return gaps by period.
- The satellite's screens, long-only among large stocks: CAPM alpha of high profitability (quality),
  12-2 month winners (momentum) and the lowest-variance quintile (low risk).
The satellite's alpha view is the average 1963-2026 long-only alpha, cut by 58% for the decay after
publication that McLean and Pontiff (2016) measure. Writes reports/factor_evidence.json.
"""
import json
from pathlib import Path

import numpy as np

from lgm.data import french

OUT = Path(__file__).resolve().parents[1] / "reports"
PERIODS = [("1927", "2026"), ("1963", "2026"), ("1990", "2026"), ("2007", "2026")]
POST_PUBLICATION_DECAY = 0.58


def geo(r):
    return float(np.expm1(np.log1p(r.dropna()).mean() * 12))


def main():
    ff = french.monthly("F-F_Research_Data_Factors")
    p6 = french.monthly("6_Portfolios_2x3")
    op = french.monthly("6_Portfolios_ME_OP_2x3")
    mom = french.monthly("6_Portfolios_ME_Prior_12_2")
    var = french.monthly("Portfolios_Formed_on_VAR")
    big = p6[["BIG LoBM", "ME2 BM2", "BIG HiBM"]].mean(1)
    small = p6[["SMALL LoBM", "ME1 BM2", "SMALL HiBM"]].mean(1)

    def gap(a, b):
        return {f"{s}-{e}": round(geo(a.loc[s:e]) - geo(b.loc[s:e]), 4) for s, e in PERIODS}

    def alpha(p):
        out = {}
        for s, e in PERIODS[1:]:
            y = (p - ff["RF"]).loc[s:e].dropna()
            x = ff["Mkt-RF"].loc[y.index]
            beta = float(np.cov(y, x)[0, 1] / x.var())
            out[f"{s}-{e}"] = {"alpha": round(float(y.mean() - beta * x.mean()) * 12, 4), "beta": round(beta, 2)}
        return out

    screens = {"high_profitability": alpha(op["BIG HiOP"]), "momentum_winners": alpha(mom["BIG HiPRIOR"]),
               "lowest_variance": alpha(var["Lo 20"])}
    avg = float(np.mean([v["1963-2026"]["alpha"] for v in screens.values()]))
    out = {"data_through": str(ff.index.max().date()),
           "large_value_minus_large_growth": gap(p6["BIG HiBM"], p6["BIG LoBM"]),
           "small_minus_large": gap(small, big),
           "satellite_screens_long_only_capm_alpha": screens,
           "satellite_alpha_view": {"average_1963_2026": round(avg, 4), "post_publication_decay": POST_PUBLICATION_DECAY,
                                    "view": round(avg * (1 - POST_PUBLICATION_DECAY), 4)}}
    (OUT / "factor_evidence.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
