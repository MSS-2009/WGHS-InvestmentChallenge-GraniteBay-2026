"""Fund scorecard: every equity fund the WInS account has held, scored and ranked on our three models.

Usage: python scripts/fund_scorecard.py
Writes reports/fund_scorecard.csv. Look-through data: config/fund_lookthrough.yaml.

1. Quantitative index: the return-quality score of our S&P 500 screen (src/lgm/growth/satellite.py),
   0.5 z(12-1 month momentum) + 0.5 z(3-year Sharpe ratio), on each fund's total returns to DATA_END.
2. Black-Litterman index: how far the custom BL model's views move a fund's expected return away from
   what its market risk alone implies (posterior minus equilibrium excess return), less the fund's
   fee. The market portfolio scores zero, so the index is purely relative. ESGV and VSGX are not BL
   assets: returns-based style analysis (60 months, weights >= 0 summing to 1) maps each onto the
   nine core funds and it takes their weighted BL figures.
3. Qualitative index: the qualitative model's two fund limits (config/qualitative.yaml,
   no_lookthrough_overweight): -0.5 z(tech/communication share) - 0.5 z(China+Taiwan share).
Each index is shown on a scale where the average fund scores 50 and one standard deviation is 10
points; the overall score is the average of the three. The scorecard ranks funds; it does not set
weights (the BL model does).
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import minimize

from lgm.asof import DATA_END
from lgm.growth.core import build_core
from lgm.growth.satellite import metrics, prices
from lgm.growth.universe import CORE

ROOT = Path(__file__).resolve().parents[1]
LOOK = yaml.safe_load((ROOT / "config" / "fund_lookthrough.yaml").read_text())["funds"]


def z(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std()


def style_weights(y: pd.Series, X: pd.DataFrame) -> tuple[np.ndarray, float]:
    """Sharpe (1992) returns-based style analysis; returns the weights and the residual variance."""
    k = X.shape[1]
    res = minimize(lambda w: float(((y.values - X.values @ w) ** 2).sum()), np.full(k, 1 / k),
                   bounds=[(0, 1)] * k, constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}], method="SLSQP")
    resid = y.values - X.values @ res.x
    return res.x, float(resid.var(ddof=1))


def main():
    funds = list(LOOK)
    core = [g.etf for g in CORE]
    hist = [g.history for g in CORE]
    px = prices(sorted(set(funds + hist + ["ACWI"])), start="2015-01-01").loc[:DATA_END]
    met = metrics(px[funds], px["ACWI"])

    r = build_core()
    t = r["table"].set_index("etf")
    mu, pi = t.loc[core, "bl_excess"].values, t.loc[core, "pi_excess"].values
    rets = px[hist].pct_change().iloc[-60:]
    bl_ret, eq_ret, mapped = {}, {}, {}
    for f in funds:
        if f in core:
            bl_ret[f], eq_ret[f] = t.loc[f, "bl_excess"], t.loc[f, "pi_excess"]
        else:
            w, rv = style_weights(px[f].pct_change().iloc[-60:], rets)
            bl_ret[f], eq_ret[f] = float(w @ mu), float(w @ pi)
            mapped[f] = dict(zip(core, w.round(3))) | {"r2": 1 - rv / px[f].pct_change().iloc[-60:].var()}

    df = pd.DataFrame(index=funds)
    df["held"] = [LOOK[f]["held"] for f in funds]
    df["mom12_1"], df["sharpe3"], df["ret3"], df["vol3"], df["maxdd5"] = (met.loc[funds, c] for c in
                                                                           ("mom12_1", "sharpe3", "ret3", "vol3", "maxdd5"))
    df["bl_excess"], df["equilibrium_excess"] = pd.Series(bl_ret), pd.Series(eq_ret)
    df["expense_ratio"] = [LOOK[f]["expense_ratio"] for f in funds]
    df["bl_alpha_net"] = df["bl_excess"] - df["equilibrium_excess"] - df["expense_ratio"]
    df["w_bl"] = [t.loc[f, "w_bl"] if f in core else 0.0 for f in funds]
    df["w_mkt"] = [t.loc[f, "w_mkt"] if f in core else np.nan for f in funds]
    df["tech_comm"] = [LOOK[f]["tech_comm"] / 100 for f in funds]
    df["china_taiwan"] = [LOOK[f]["china_taiwan"] / 100 for f in funds]

    df["quant_index"] = 50 + 10 * z(0.5 * z(df["mom12_1"]) + 0.5 * z(df["sharpe3"]))
    df["bl_index"] = 50 + 10 * z(df["bl_alpha_net"])
    df["qual_index"] = 50 + 10 * z(-0.5 * z(df["tech_comm"]) - 0.5 * z(df["china_taiwan"]))
    df["overall"] = df[["quant_index", "bl_index", "qual_index"]].mean(axis=1)
    for c in ("quant_index", "bl_index", "qual_index", "overall"):
        df[c.replace("_index", "") + "_rank"] = df[c].rank(ascending=False).astype(int)
    df = df.sort_values("overall", ascending=False)
    df.index.name = "fund"
    df.round(4).to_csv(ROOT / "reports" / "fund_scorecard.csv")

    show = df[["quant_index", "quant_rank", "bl_index", "bl_rank", "qual_index", "qual_rank", "overall", "overall_rank",
               "bl_alpha_net", "w_bl", "w_mkt", "tech_comm", "china_taiwan"]]
    print(f"Fund scorecard ({len(df)} funds, returns to {DATA_END})")
    print(show.round(3).to_string())
    for f, w in mapped.items():
        print(f"{f} style weights on the core funds (R2 {w.pop('r2'):.2f}): "
              + ", ".join(f"{k} {v:.0%}" for k, v in w.items() if v >= 0.005))


if __name__ == "__main__":
    main()
