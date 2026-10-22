# Agent brief r1-policy: is the IPS policy near the best in a wider family?

**Read first, in order:** `docs/loop/COMMON.md` (standing rules; they apply to you in full),
`docs/MODEL.md` (especially "Policy study"), `src/lgm/strategies.py`, `src/lgm/engine.py`,
`scripts/policy_study.py`, `scripts/report_numbers.py`, `src/lgm/backtest.py`.
**Your worktree:** branch `r1-policy`, based on `improve`. It already exists; you are in it.
Call its absolute path `WT`. Run everything as `PYTHONPATH=$WT/src PY ...` (see COMMON.md).

## 0. What is settled
The IPS policy is: lock every payment in Jan 2027/2028 (the $300k deposit is all spent on the ladder,
the rest is completed from the $150k), invest the rest 60/40 (Black-Litterman equity core, IBTM bonds),
rebalance in January when the equity share drifts more than 5 points, move 60% of the growth sleeve
into IBTM in Jan 2031 (a floor), and contribute 85% of the facility in Jan 2033. The existing policy
study only varies the 2031 floor share (0-100%) with everything else fixed. The contribution share is
a client preference: do not optimise it.

## 1. The question
Only hand-picked static policies have been tried. Is the IPS close to the best policy in a wider
family, including simple dynamic rules, by each of several objectives? If a different policy is clearly
better, by how much, and does that survive a fresh seed and real history? "The IPS is within $X of the
best by every objective" is a good answer if true.

## 2. Task 1: dynamic rules in the engine (opt-in)
Add optional fields to `Strategy` (defaults must reproduce today's numbers exactly) and implement them
in `engine.py`:
- **Glide path:** `equity_share_end`. The target equity share moves linearly from `equity_share`
  (Jan 2028) to `equity_share_end` (Jan 2032) at each January rebalance check.
- **Floor timing:** `floor_year` (2029, 2030, 2031 or 2032; default 2031) for the existing floor move.
  The 2031 co-sponsor quote must still be computed in 2031 (`out["growth_2031"]`, `floor_2033`).
- **Ratchet (lock in gains):** at each January check from 2029 to 2032, if the growth sleeve exceeds
  `ratchet_trigger` times a reference (state your reference, e.g. the amount invested in 2028 grown at
  the IBTM yield), move `ratchet_share` of the excess into floor IBTM.
Charge commissions for any new trades exactly the way the engine does now. Tests in
`tests/test_policy_search.py`: defaults reproduce `engine.run` outputs bit-for-bit for S1, S2, S6, S8,
S9 and IPS; each rule does what it says on a hand-checkable case (zero volatility, known rates). Commit.

## 3. Task 2: the search (new script `scripts/policy_search.py`)
Use the headline parameters the way `scripts/report_numbers.py` builds them (Black-Litterman core
weights, $25 commissions, 20,000 scenarios) and **one common scenario set for every policy**.
Grid (trim if the measured cost demands it; say what you trimmed):
- `lock_2027` in {0.5, 0.75, 1.0} (lock_2028 = lock_2031 = 1.0)
- `equity_share` in {0.4, 0.5, 0.6, 0.7, 0.8, 1.0}
- `equity_share_end` in {same as start, start - 0.2, start - 0.4} (floored at 0)
- `floor_share` in {0, 0.2, 0.4, 0.6, 0.8, 1.0} and `floor_year` in {2030, 2031, 2032}
- ratchet off, or (`ratchet_trigger`, `ratchet_share`) in {(1.1, 0.5), (1.2, 0.5), (1.2, 1.0)}
Measure the time of one `engine.run` first and multiply out; keep the total under 20 minutes.
For every policy record: funded share, p5, p10, median, p90, cvar5, certainty equivalents for CRRA
gamma 2, 4, 8 (import `certainty_equivalent` from `scripts/policy_study.py` or copy it exactly), and
the amount secured in 2031 (floor value reaching Dec 2032, median). A policy that funds less than 100%
of scenarios is reported but never ranked. Write `reports/policy_search.csv`. Commit.

## 4. Task 3: are the winners real?
For the IPS and the top 3 policies by each objective (median, p5, cvar5, CE2, CE4, CE8; de-duplicate):
- re-run on a fresh seed (20,000 scenarios) and report the change in each objective;
- run on the 184 historical paths (`backtest.history_paths`, both as-happened and re-centred on the
  BL expected returns, the way `scripts/validate_model.py` does): funded, p5, median, p95, worst;
- the 2031 conditional range (p20/p80 and p10/p90) at the median 2031 scenario.
Write `reports/policy_search_top.csv`, one row per policy per check. Commit.

## 5. Findings doc `docs/loop/r1_policy_findings.md`
For each objective: the best policy, its value, the IPS's value, the gap in dollars, and the IPS's
rank. Then the robustness results per policy. Then a plain recommendation, marked as yours.
Watch for a winner that is best only because it takes more equity risk than the client's stated goals
allow: say what each winner trades away (p5, cvar5, 2031 secured amount, range width).

## Verify
- `PYTHONPATH=$WT/src PY -m pytest -q` passes (paste the last line verbatim).
- `PYTHONPATH=$WT/src PY scripts/run_all.py` leaves every pre-existing `reports/` file byte-identical.

## Acceptance criteria
- [ ] glide path, floor timing and ratchet implemented, opt-in, tested (defaults bit-for-bit)
- [ ] `scripts/policy_search.py` and `reports/policy_search.csv` covering the grid (or a stated trim)
- [ ] `reports/policy_search_top.csv` with fresh-seed, history and 2031-range checks per policy
- [ ] `docs/loop/r1_policy_findings.md` with per-objective gaps and a recommendation
- [ ] tests pass; pre-existing reports byte-identical
- [ ] one commit per task

## Files you own
`src/lgm/strategies.py`, `src/lgm/engine.py`, `scripts/policy_search.py`, `tests/test_policy_search.py`,
`reports/policy_search*.csv`, `docs/loop/r1_policy_findings.md`.
Another worker is editing `src/lgm/esg.py` and `src/lgm/calibrate.py` in parallel and may make one small
additive change in `engine.conditional_2031`. Do not edit `esg.py` or `calibrate.py`.

## Not yours to decide
Which policy the IPS adopts, the contribution share, and the objective that ranks policies. Recommend;
report `question` if you think a decision is needed now.

## Budget
About 2 hours of work and 20 minutes of compute in total. Stop and report at the budget.
