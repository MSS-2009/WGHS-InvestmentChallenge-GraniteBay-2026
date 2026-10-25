# Agent brief r8-reinvest — how certain is the ladder when cash earns what rates actually pay?

**Read first:** `docs/loop/COMMON.md` (standing rules: they apply in full), then `docs/MODEL.md`
"How certain is 'certain'?" and the "Caveats" bullet that ends "the Monte Carlo does not simulate that
reinvestment rate", then `src/lgm/ladder.py` (`solve`, `premium`, `build_matrix`, `idle_cash_days`)
and `Scenarios.df` / `Scenarios.zero_cc` in `src/lgm/esg.py`.
**Your worktree:** branch `r8-reinvest`, based on `improve`. Already created for you; you are in it.
`PY` = `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python`; always run
with `PYTHONPATH=<your worktree>/src`. Never run a command in the main checkout (COMMON rule 12).

## 0. What is settled, and the question
The reserve ladder is the cheapest cash-flow-matched portfolio from `ladder.solve`, which assumes every
coupon, maturity and fund distribution received before a payment is reinvested at a fixed 3% until the
payment is due. `ladder.premium(curve, 0.03)` is the engine's `kappa0` (1.8% over zero-coupon value);
at 0% the cheapest ladder costs 3.7% over, and pricing for 0% lowers the median facility by $7.8k
(`reports/report_numbers.json`, `stress.reserve_certain_at_0pct_reinvestment`). Nothing simulates the
rate cash really earns. **Question:** if the ladder bought for 3% is held to 2042 and its idle cash
earns the simulated short rate instead, how often, and by how much, does it miss a payment? And what
would it cost to make it certain at a stated confidence? The model and its defaults stay as they are:
this is a study.

## 1. Tasks (commit after each)
1. **Measure first.** Time one `simulate` of 2,000 scenarios to January 2042 (`dc.replace` the
   headline `esg_params(...)` from `scripts/report_numbers.py` with `months=` the engine month of
   January 2042, from `lgm.asof.month_of`). Multiply out 20,000 scenarios and estimate peak memory
   (COMMON rule 11: keep it under about 2 GB; chunk scenarios if needed). Write the numbers in your
   findings doc. If 20,000 to 2042 does not fit, use fewer and say how many.
2. **Script `scripts/reinvest_risk.py`.**
   - Build the ladder exactly as `ladder.premium(curve, 0.03)` does on the headline curve (the Oct 20
     curve `report_numbers.py` uses): same universe, same payments. Get each held instrument's dated
     cash flows and the LP's holdings, so you have one deterministic schedule of cash arriving
     (date, dollars) and the ten $50,000 payments.
   - Check the schedule against the LP before using it: rolling cash forward at a flat 3% must fund
     every payment with a final surplus of about zero (print the surplus), and at 0% it must fall short
     by roughly what `premium(curve, 0.0) - premium(curve, 0.03)` implies. If either check fails,
     stop and report `blocked`.
   - Hold the schedule from January 2027 (the lock) to the last payment. Each month, cash on hand
     earns that path's 1-month rate, `r = -log(sc.df(m, 1/12)) * 12`, applied for the month, after
     the reinvestment rule. Rules, each a row of output:
     (a) flat 3% (must reproduce zero shortfall), (b) flat 0%, (c) simulated 1-month rate floored at
     0, (d) simulated rate minus 0.50 points (a deposit spread), floored at 0.
   - Per rule, over paths: share of paths missing any payment; mean and 95th / 99th percentile of the
     total shortfall in dollars; the largest single-payment shortfall at the 99th percentile; the extra
     cash needed at the lock (January 2027 dollars, discounted at the path's own rates or, if simpler
     and stated, at 3%) so that 95% and 99% of paths miss nothing; and, for (c), the 1st / 50th / 99th
     percentile of the average short rate earned 2027-2042, so the reader can see what drives it.
   - Write `reports/reinvest_risk.csv` (one row per rule) and print it.
3. **Test `tests/test_reinvest_risk.py`:** a two-payment toy schedule where hand arithmetic gives the
   shortfall at 0% and at 3%; the script's roll-forward function reproduces both to the cent.
4. **Findings `docs/loop/r8_reinvest_findings.md`:** the measurement from task 1, the two checks from
   task 2 with their printed numbers, the table, and at most five sentences on what it means for the
   "How certain is 'certain'?" paragraph. Every number from the script (COMMON rule 5). Say plainly if
   the result goes against the expectation that 3% is cautious (rule 8).

## You own
`scripts/reinvest_risk.py`, `reports/reinvest_risk.csv`, `tests/test_reinvest_risk.py`,
`docs/loop/r8_reinvest_findings.md`. Nothing else. Do not add the script to `run_all.py`.

## Acceptance criteria
- [ ] Task 1's timing and memory numbers are in the findings doc, measured, not estimated by eye.
- [ ] Rule (a) gives zero shortfall on every path; the two schedule checks are printed and pass.
- [ ] Tests pass; final pytest line pasted verbatim.
- [ ] `PYTHONPATH=<wt>/src PY scripts/run_all.py` leaves every pre-existing report byte-identical
      (`git status --short reports/` shows only `reinvest_risk.csv`).
- [ ] Every figure in the findings doc is printed by the script.

## Not yours to decide
Whether MODEL.md changes, whether the engine's `kappa0` or the WInS ladder changes, and whether the
script joins run_all. Report what you found; reporting `blocked` with partial results beats guessing.
