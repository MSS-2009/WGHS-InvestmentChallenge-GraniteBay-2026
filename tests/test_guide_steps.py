"""The former CS team's guide, Steps 1-7: every published figure must reproduce."""
import numpy as np
import pytest

from lgm import simple as s
from lgm.data.treasury import par_curve

TOL = 1.5  # dollars; the guide rounds to whole dollars


@pytest.mark.parametrize("rate,expected", [(0.03, 439_305), (0.04, 421_767), (0.045, 413_440),
                                           (0.05, 405_391), (0.055, 397_610)])
def test_step1_reserve(rate, expected):
    assert s.reserve_pv(rate) == pytest.approx(expected, abs=TOL)


def test_step1_row_by_row_at_5pct():
    rows = [50_000, 47_619, 45_351, 43_192, 41_135, 39_176, 37_311, 35_534, 33_842, 32_230]
    for k, v in enumerate(rows):
        assert 50_000 / 1.05 ** k == pytest.approx(v, abs=1)


@pytest.mark.parametrize("g,expected", [(0.04, 562_094), (0.05, 593_471), (0.06, 626_290), (0.07, 660_602)])
def test_step2_portfolio(g, expected):
    assert s.portfolio_2033(g) == pytest.approx(expected, abs=TOL)


def test_step2_split_at_6pct():
    assert 300_000 * 1.06 ** 6 == pytest.approx(425_556, abs=1)
    assert 150_000 * 1.06 ** 5 == pytest.approx(200_734, abs=1)


def test_step3_grid_and_leverage():
    grid = {0.04: [140_327, 148_654, 156_703], 0.05: [171_704, 180_031, 188_080],
            0.06: [204_523, 212_850, 220_898], 0.07: [238_835, 247_162, 255_211]}
    for g, row in grid.items():
        for rate, v in zip([0.04, 0.045, 0.05], row):
            assert s.facility(g, rate) == pytest.approx(v, abs=TOL)
    after_cut = s.portfolio_2033(0.06) * 0.9 - s.reserve_pv(0.045)
    assert after_cut == pytest.approx(150_221, abs=TOL)
    assert after_cut / s.facility(0.06, 0.045) - 1 == pytest.approx(-0.294, abs=0.001)


@pytest.mark.parametrize("rate,expected", [(0.04, 333_328), (0.045, 317_478), (0.05, 302_509)])
def test_step4a_flat_lock(rate, expected):
    assert s.lock_cost_flat(rate) == pytest.approx(expected, abs=TOL)


def test_step4b_curve_lock_official_oct16_curve():
    curve = par_curve("2026-10-16")
    assert s.lock_cost_par_as_zero(curve) == pytest.approx(298_927, abs=2)


@pytest.mark.parametrize("ret,g45,g35,l100,l6040", [
    (-0.02, 57_348, 40_404, 135_588, 156_097),
    (0.06, 199_546, 182_602, 200_734, 196_975),
    (0.10, 283_022, 266_077, 241_577, 220_399)])
def test_step5_scenarios(ret, g45, g35, l100, l6040):
    assert s.strategy_g(ret, 0.045) == pytest.approx(g45, abs=TOL)
    assert s.strategy_g(ret, 0.035) == pytest.approx(g35, abs=TOL)
    assert s.strategy_l(ret, sixty_forty=False) == pytest.approx(l100, abs=TOL)
    assert s.strategy_l(ret, sixty_forty=True) == pytest.approx(l6040, abs=TOL)


def test_step6_floor():
    f = s.floor_2031()
    assert f["growth_2031"] == pytest.approx(178_652, abs=TOL)
    assert f["locked"] == pytest.approx(107_191, abs=TOL)
    assert f["floor"] == pytest.approx(117_594, abs=TOL)
    assert f["rest"] == pytest.approx(80_294, abs=TOL)
    assert f["total"] == pytest.approx(197_888, abs=TOL)


def test_step7_simple_monte_carlo_ranges():
    mc = s.simple_monte_carlo(n=200_000, seed=7)
    pct = lambda a, q: float(np.percentile(a, q))
    assert mc["g_funded"].mean() == pytest.approx(0.965, abs=0.01)
    assert pct(mc["g_facility"], 5) == pytest.approx(16_000, abs=6_000)
    assert pct(mc["g_facility"], 50) == pytest.approx(210_000, abs=6_000)
    assert pct(mc["g_facility"], 95) == pytest.approx(507_000, abs=8_000)
    assert pct(mc["l100"], 5) == pytest.approx(109_000, abs=6_000)
    assert pct(mc["l100"], 50) == pytest.approx(201_000, abs=6_000)
    assert pct(mc["l100"], 95) == pytest.approx(368_000, abs=8_000)
    assert pct(mc["l6040"], 5) == pytest.approx(140_000, abs=6_000)
    assert pct(mc["l6040"], 50) == pytest.approx(200_000, abs=6_000)
    assert pct(mc["l6040"], 95) == pytest.approx(290_000, abs=8_000)


def test_step7_all_stock_row():
    rng = np.random.default_rng(11)
    r = np.exp(np.log(1.06) + 0.165 * rng.standard_normal((200_000, 6))) - 1
    v = (300_000 * (1 + r[:, 0]) + 150_000) * np.prod(1 + r[:, 1:], axis=1)
    res = s.reserve_pv(0.045)
    assert (v >= res).mean() == pytest.approx(0.86, abs=0.01)
    assert float(np.percentile(np.maximum(v - res, 0), 50)) == pytest.approx(215_000, abs=8_000)
    assert float(np.percentile(np.maximum(v - res, 0), 95)) == pytest.approx(771_000, abs=15_000)


def test_step7_random_rate_upgrade():
    mc = s.simple_monte_carlo(n=60_000, seed=3, random_rate=True)
    lo, hi = np.percentile(mc["reserve"], [5, 95])
    assert lo == pytest.approx(388_000, abs=3_000) and hi == pytest.approx(442_000, abs=3_000)
    assert mc["g_funded"].mean() == pytest.approx(0.963, abs=0.01)
