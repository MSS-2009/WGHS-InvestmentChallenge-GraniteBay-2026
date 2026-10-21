"""Monthly simulation of Laura's portfolio under a strategy, across many scenarios.

Timeline (month 0 = Nov 1, 2026, starting from the latest Treasury curve):
  m=2  Jan 2027  +$300,000; lock per rule; invest the rest
  m=14 Jan 2028  +$150,000; complete any lock shortfall first; invest
  m=26, 38, 62   January rebalancing checks
  m=50 Jan 2031  finish the ladder if the rule says so; move the floor into IBTM; quote range
  m=74 Jan 2033  buy any unlocked part of the reserve; what is left is the facility fund
Everything is vectorised over scenarios.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .esg import Scenarios
from .strategies import Strategy

M_2027, M_2028, M_2031, M_2033 = 2, 14, 50, 74
REBAL_MONTHS = (26, 38, 62)
N_PAY, PMT = 10, 50_000.0
IBTM_MATURITY_M = 73.5          # Dec 15, 2032
ER = {"eq": np.array([0.0003, 0.0003, 0.0006]), "VGIT": 0.0003, "IBTM": 0.0007}
VGIT_TAU, VGIT_DUR, VGIT_CONV = 5.5, 5.1, 31.0
COMMISSION_ETF, COMMISSION_BOND = 25.0, 10.0


@dataclass
class EngineConfig:
    kappa0: float = 0.018         # real-instrument ladder cost over zero-coupon value, Jan 2027 ladder
    deposits: tuple = ((M_2027, 300_000.0), (M_2028, 150_000.0))
    commissions: bool = True
    eq_er: tuple = (0.0003, 0.0003, 0.0006)   # expense ratio per equity asset, same order as the ESG
    extra_tickets: int = 0        # more trades per invest event, e.g. 34 when a 35-stock basket is one asset
    extra_ticket_min: float = 10_000.0   # below this, a small top-up stays in the ETFs (no basket trades)
    annual_cost: float = 0.0      # recurring commissions per year (e.g. basket reconstitution)


def pay_tau(m: float) -> np.ndarray:
    """Years from month m to each payment (Jan 1, 2033 + k)."""
    return (M_2033 + 12 * np.arange(N_PAY) - m) / 12.0


def kappa(m: float, cfg: EngineConfig) -> float:
    """Premium scales with the ladder's average remaining time (reinvestment and fee drag)."""
    return cfg.kappa0 * pay_tau(m).clip(0).mean() / pay_tau(M_2027).mean()


@dataclass
class State:
    eq: np.ndarray            # (N, 3) dollars
    vgit: np.ndarray          # (N,) dollars
    ibtm_face: np.ndarray     # (N,) growth-sleeve IBTM, dollars at maturity
    floor_face: np.ndarray    # (N,) floor IBTM, dollars at maturity
    cash: np.ndarray          # (N,)
    locked: np.ndarray        # (N, K) fraction of each payment matched
    costs: np.ndarray         # (N,) commissions paid


def _ibtm_df(sc: Scenarios, m: int) -> np.ndarray:
    tau = max(IBTM_MATURITY_M - m, 0.0) / 12.0
    return sc.df(m, [tau])[:, 0]


def growth_value(s: State, sc: Scenarios, m: int) -> np.ndarray:
    return s.eq.sum(1) + s.vgit + s.ibtm_face * _ibtm_df(sc, m) + s.cash


def _invest(s: State, sc: Scenarios, m: int, st: Strategy, amount: np.ndarray, cfg: EngineConfig):
    """Invest `amount` at the strategy's target mix."""
    w = np.array(st.region_weights)
    s.eq += np.outer(amount * st.equity_share, w)
    bonds = amount * (1 - st.equity_share)
    if st.bond_vehicle == "VGIT":
        s.vgit += bonds
    else:
        s.ibtm_face += bonds / _ibtm_df(sc, m)
    if cfg.commissions:
        s.costs += np.where(amount > 0, COMMISSION_ETF * (len(w) + (st.equity_share < 1)), 0.0)
        s.costs += np.where(amount >= cfg.extra_ticket_min, COMMISSION_ETF * cfg.extra_tickets, 0.0)


def _rebalance(s: State, sc: Scenarios, m: int, st: Strategy, cfg: EngineConfig, force: bool = False):
    df = _ibtm_df(sc, m)
    bonds = s.vgit + s.ibtm_face * df
    total = s.eq.sum(1) + bonds + s.cash
    eq_share = np.divide(s.eq.sum(1), total, out=np.zeros_like(total), where=total > 0)
    region = np.divide(s.eq, s.eq.sum(1, keepdims=True), out=np.zeros_like(s.eq), where=s.eq.sum(1, keepdims=True) > 0)
    drift = np.abs(eq_share - st.equity_share) > st.band
    drift |= (np.abs(region - np.array(st.region_weights)) > 0.05).any(1) & (s.eq.sum(1) > 0)
    do = drift | force
    if not do.any():
        return
    s.eq[do] = 0.0
    s.vgit[do] = 0.0
    s.ibtm_face[do] = 0.0
    s.cash[do] = 0.0
    amount = np.where(do, total, 0.0)
    _invest(s, sc, m, st, amount, cfg)


def _lock(s: State, sc: Scenarios, m: int, target: float, budget: np.ndarray, cfg: EngineConfig) -> np.ndarray:
    """Raise every payment's matched fraction toward `target`, longest payment first, within budget.
    Returns money spent."""
    tau = pay_tau(m)
    unit = PMT * sc.df(m, np.maximum(tau, 0)) * (1 + kappa(m, cfg))          # (N, K) cost of a full payment
    need = np.clip(target - s.locked, 0, None)                              # (N, K)
    spent = np.zeros(sc.n)
    left = budget.copy()
    for k in range(N_PAY - 1, -1, -1):
        cost_k = need[:, k] * unit[:, k]
        frac = np.where(cost_k > 0, np.minimum(1.0, left / np.where(cost_k > 0, cost_k, 1)), 0.0)
        s.locked[:, k] += need[:, k] * frac
        paid = cost_k * frac
        left -= paid
        spent += paid
    if cfg.commissions:
        s.costs += np.where(spent > 0, 5 * COMMISSION_ETF + 5 * COMMISSION_BOND, 0.0)
    return spent


def _liquidate(s: State, sc: Scenarios, m: int, amount: np.ndarray):
    """Sell growth assets pro rata to raise `amount` (capped at what exists)."""
    df = _ibtm_df(sc, m)
    total = s.eq.sum(1) + s.vgit + s.ibtm_face * df + s.cash
    f = np.divide(np.minimum(amount, total), total, out=np.zeros_like(total), where=total > 0)
    s.eq *= (1 - f)[:, None]
    s.vgit *= 1 - f
    s.ibtm_face *= 1 - f
    s.cash *= 1 - f
    return np.minimum(amount, total)


def _step(s: State, sc: Scenarios, m: int, cfg: "EngineConfig"):
    """Advance one month: markets move, fees accrue."""
    s.eq *= np.exp(sc.eq_log[:, m - sc.m0, :]) * (1 - np.asarray(cfg.eq_er) / 12)
    if cfg.commissions and cfg.annual_cost and m >= M_2027:
        s.costs += cfg.annual_cost / 12
    y0 = np.expm1(sc.zero_cc(m, [VGIT_TAU])[:, 0])
    y1 = np.expm1(sc.zero_cc(m + 1, [VGIT_TAU])[:, 0])
    dy = y1 - y0
    s.vgit *= 1 + y0 / 12 - VGIT_DUR * dy + 0.5 * VGIT_CONV * dy ** 2 - ER["VGIT"] / 12
    s.ibtm_face *= 1 - ER["IBTM"] / 12
    s.floor_face *= 1 - ER["IBTM"] / 12
    short = np.expm1(sc.zero_cc(m, [0.25])[:, 0])
    s.cash *= 1 + short / 12


def run(st: Strategy, sc: Scenarios, cfg: EngineConfig | None = None, state: State | None = None,
        snapshot_2031: bool = False) -> dict:
    """Simulate from month sc.m0. With `state`, the events at month sc.m0 are taken as done
    (used to continue a scenario from its January 2031 position)."""
    cfg = cfg or EngineConfig()
    n = sc.n
    K = sc.eq_log.shape[2]
    s = state or State(np.zeros((n, K)), np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n), np.zeros((n, N_PAY)), np.zeros(n))
    out: dict = {}
    deposits = dict(cfg.deposits)
    for m in range(sc.m0, M_2033 + 1):
        if state is not None and m == sc.m0:
            pass
        elif m in deposits:
            cash_in = np.full(n, deposits[m])
            target = st.lock_2027 if m == M_2027 else st.lock_2028
            spent = _lock(s, sc, m, target, cash_in, cfg) if target > 0 else np.zeros(n)
            if m == M_2027:
                out["lock_cost_2027"] = spent + 0.0
            _invest(s, sc, m, st, cash_in - spent, cfg)
            if m == M_2028:
                _rebalance(s, sc, m, st, cfg)
        elif m in REBAL_MONTHS:
            _rebalance(s, sc, m, st, cfg)
        elif m == M_2031:
            if st.lock_2031 > 0:
                tau = pay_tau(m)
                unit = PMT * sc.df(m, tau) * (1 + kappa(m, cfg))
                need_cost = (np.clip(st.lock_2031 - s.locked, 0, None) * unit).sum(1)
                raised = _liquidate(s, sc, m, need_cost)
                _lock(s, sc, m, st.lock_2031, raised, cfg)
            g = growth_value(s, sc, m)
            out["growth_2031"] = g.copy()
            if st.floor_share_2031 > 0:
                moved = _liquidate(s, sc, m, g * st.floor_share_2031)
                s.floor_face += moved / _ibtm_df(sc, m)
                _rebalance(s, sc, m, st, cfg, force=True)
                if cfg.commissions:
                    s.costs += COMMISSION_ETF * 4
            out["floor_2033"] = s.floor_face * (1 - ER["IBTM"] / 12) ** (M_2033 - m)  # value reaching Dec 2032
            out["locked_2031"] = s.locked.mean(1)
            if snapshot_2031:
                out["state_2031"] = State(*(a.copy() for a in (s.eq, s.vgit, s.ibtm_face, s.floor_face, s.cash, s.locked, s.costs)))
        if m == M_2033:
            break
        _step(s, sc, m, cfg)
    # January 2033 settlement
    assets = s.eq.sum(1) + s.vgit + s.ibtm_face + s.floor_face + s.cash - s.costs
    open_cost = ((1 - s.locked) * PMT * sc.df(M_2033, pay_tau(M_2033)) * (1 + kappa(M_2033, cfg))).sum(1)
    funded = assets >= open_cost - 1e-6
    facility = np.maximum(assets - open_cost, 0.0)
    i33, i27 = M_2033 - sc.m0, max(M_2027 - sc.m0, 0)   # nested runs measure from their start
    real = facility * np.exp(sc.fx_log[:, i33] - sc.fx_log[:, i27]) / np.exp(sc.tw_cost_log[:, i33] - sc.tw_cost_log[:, i27])
    out.update({"funded": funded, "facility": facility, "contribution": facility * st.contribution_share,
                "facility_real_tw2027": real, "assets_2033": assets, "open_cost_2033": open_cost,
                "shortfall": np.maximum(open_cost - assets, 0.0), "locked_2033": s.locked.mean(1)})
    out.setdefault("floor_2033", np.zeros(n))
    out.setdefault("growth_2031", np.zeros(n))
    out.setdefault("lock_cost_2027", np.zeros(n))
    return out


def summarize(res: dict[str, np.ndarray]) -> dict[str, float]:
    f = res["facility"]
    p = lambda q: float(np.percentile(f, q))
    tail = f[f <= np.percentile(f, 5)]
    return {"funded": float(res["funded"].mean()), "p5": p(5), "p10": p(10), "median": p(50),
            "p90": p(90), "p95": p(95), "cvar5": float(tail.mean()) if tail.size else 0.0,
            "real_median": float(np.median(res["facility_real_tw2027"]))}


def state_for(snap: State, i: int, n: int) -> State:
    """Scenario i's state repeated n times."""
    rep = lambda a: np.repeat(a[i:i + 1], n, axis=0)
    return State(rep(snap.eq), rep(snap.vgit), rep(snap.ibtm_face), rep(snap.floor_face), rep(snap.cash),
                 rep(snap.locked), rep(snap.costs))


def conditional_2031(st: Strategy, sc: Scenarios, res: dict, params, i: int | None = None,
                     n_inner: int = 4000, seed: int = 99, cfg: EngineConfig | None = None) -> dict:
    """What Laura could tell co-sponsors in January 2031: re-simulate 2031-2033 from one
    scenario's 2031 position. Default: the scenario with the median 2031 growth value."""
    from dataclasses import replace as dc_replace

    from .esg import simulate

    g = res["growth_2031"] + res["floor_2033"] * 0  # rank on growth assets before the floor move
    if i is None:
        i = int(np.argsort(g)[len(g) // 2])
    start = {"beta": sc.beta[i, M_2031 - sc.m0], "infl": sc.infl[i, M_2031 - sc.m0],
             "fx_log": np.full(n_inner, sc.fx_log[i, M_2031 - sc.m0]),
             "tw_cost_log": np.full(n_inner, sc.tw_cost_log[i, M_2031 - sc.m0])}
    p = dc_replace(params, months=M_2033 - M_2031)
    inner = simulate(p, n_inner, seed=seed, start=start, m0=M_2031)
    r = run(st, inner, cfg, state=state_for(res["state_2031"], i, n_inner))
    f = r["facility"]
    return {"scenario": i, "floor": float(res["floor_2033"][i]), "growth_2031": float(res["growth_2031"][i]),
            "p10": float(np.percentile(f, 10)), "median": float(np.median(f)), "p90": float(np.percentile(f, 90)),
            "p5": float(np.percentile(f, 5)), "p95": float(np.percentile(f, 95))}
