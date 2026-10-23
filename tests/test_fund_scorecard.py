"""Fund scorecard: style analysis recovers known weights; the committed scorecard is consistent."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _script():
    spec = importlib.util.spec_from_file_location("fund_scorecard", ROOT / "scripts" / "fund_scorecard.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_style_analysis_recovers_known_weights():
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(0.007, 0.045, (60, 4)), columns=list("ABCD"))
    y = X @ np.array([0.6, 0.3, 0.1, 0.0]) + rng.normal(0, 0.002, 60)
    w, rv = _script().style_weights(y, X)
    assert np.allclose(w, [0.6, 0.3, 0.1, 0.0], atol=0.02)
    assert abs(w.sum() - 1) < 1e-6 and (w >= -1e-9).all()
    assert rv < 0.003 ** 2


def test_scorecard_covers_every_fund_held_and_ranks_consistently():
    d = pd.read_csv(ROOT / "reports" / "fund_scorecard.csv", index_col=0)
    look = _script().LOOK
    assert set(d.index) == set(look)
    for c in ("quant_index", "bl_index", "qual_index"):
        assert abs(d[c].mean() - 50) < 1e-2 and abs(d[c].std() - 10) < 1e-2
    assert (d["overall"].rank(ascending=False).astype(int) == d["overall_rank"]).all()
    # the qualitative index never prefers a fund that is worse on both look-through limits
    for a in d.index:
        for b in d.index:
            if d.loc[a, "tech_comm"] > d.loc[b, "tech_comm"] and d.loc[a, "china_taiwan"] >= d.loc[b, "china_taiwan"]:
                assert d.loc[a, "qual_index"] < d.loc[b, "qual_index"]


def test_ladder_scorecard_scores_the_optimal_ladder_at_100():
    d = pd.read_csv(ROOT / "reports" / "ladder_scorecard.csv")
    assert len(d) == 48 and d["value_per_100"].max() <= 100 + 1e-6
    bought = d[d["model_dollars"] > 0.5]
    assert np.allclose(bought["value_per_100"], 100, atol=1e-4)       # LP duality: bought => zero reduced cost
    assert (d.loc[d["model_dollars"] <= 0.5, "value_per_100"] < 100 - 1e-4).all()
    held = d[d["held_in_wins"]]
    assert len(held) == 9 and held["saving_if_removed"].min() >= -1e-6
