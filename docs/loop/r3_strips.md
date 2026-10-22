# Agent brief r3-strips: a reserve that is certain without assuming any reinvestment rate

**Read first, in order:** `docs/loop/COMMON.md` (standing rules, in full; rules 6 and 11 matter most
here), `docs/MODEL.md` ("How certain is 'certain'?"), `src/lgm/ladder.py`, `src/lgm/instruments.py`,
`src/lgm/curve.py`, `scripts/wins_ladder_check.py`.
**Your worktree:** branch `r3-strips`, based on `improve`. Already created; you are in it.
Run everything as `PYTHONPATH=$WT/src PY ...`. This thread previously worked on the scenario
generator (rounds 1-2, both merged); this is a new topic.

## 0. Context
The ten $50,000 payments (each Jan 1, 2033-2042) are "locked" with a linear-program ladder of the
instruments the competition account (WInS) allows: five Treasury bonds and the iShares iBonds
Treasury ETFs. Coupons and maturities arrive before the payments, so the ladder is certain only if
that cash is reinvested at 3% or more. At 0% reinvestment the cheapest ladder costs 3.7% over
zero-coupon value instead of 1.8%, which lowers the median facility by $7.8k. The client has asked
us to drop the competition's restrictions and look at the real-world answer.

## 1. The question
In the real Treasury market, Treasury STRIPS (zero-coupon principal and coupon strips) mature on
Feb 15, May 15, Aug 15 and Nov 15. A Nov 15 strip held to a Jan 1 payment idles for about six weeks.
Plain Treasury notes and bonds maturing in mid- to late December also exist. What does a reserve
that needs **no reinvestment assumption** cost, built from real instruments, against the WInS
ladder at 3% and at 0%?

## 2. Task 1: prices (research)
Find real quotes for Treasury STRIPS maturing Nov 2032 through Nov 2041 (ideally both principal and
coupon strips), and for any Treasury notes or bonds maturing between Nov 15 and Dec 31 of 2032-2041,
on or near Oct 20, 2026 (the model's curve date; say which date you got). Candidate sources:
TreasuryDirect, the Wall Street Journal's Treasury STRIPS table, FINRA TRACE / FINRA Fixed Income
data, broker quote pages. Save every raw file under `data/raw/strips/` with URL, date and SHA-256 in
`data/raw/strips/SOURCES.md`, and cross-check at least three quotes against a second source or
against the model's own zero curve (state the gap in basis points). If no real quotes can be
obtained, stop and report `blocked`. Do not substitute curve-implied prices and call them quotes.
A curve-implied STRIPS ladder is allowed only as a clearly labelled comparison. Commit.

## 3. Task 2: the instruments and the ladder (additive)
- Add a zero-coupon instrument type to `src/lgm/instruments.py` (and anything `ladder.py` needs to
  price and schedule it), plus a loader for your quotes. Existing instruments and the WInS universe
  must not change.
- Solve the cheapest ladder that meets every payment at **0% reinvestment**, from (a) STRIPS only,
  (b) STRIPS plus the December-maturing notes and bonds, (c) the WInS universe (existing), and report
  each at 0% and at 3%. Report cost, cost over zero-coupon value, idle cash-days, and the holdings.
- Tests in `tests/test_strips.py`: a zero-coupon instrument's flows and price; an LP on a synthetic
  curve where the answer is known. Commit.

## 4. Task 3: what it is worth (`scripts/strips_reserve.py`)
Write `reports/strips_reserve.csv` (one row per universe x reinvestment rate) and the effect on the
headline median facility if the IPS used the certain-at-0% STRIPS ladder: price it through
`EngineConfig.kappa0` the same way `scripts/report_numbers.py` prices its 0% stress (read how it does
that, and reuse it). Commit.

## 5. Findings `docs/loop/r3_strips_findings.md`
Quotes, sources, the per-universe table, and a recommendation. Note any practical issues (bid-ask on
STRIPS, minimum sizes, taxes on the imputed interest of zero-coupon bonds for a taxable owner): say
what you found, with a source, or say that you did not check it.

## Verify / acceptance
- [ ] real quotes on disk with URL, date, SHA-256, and three cross-checks (or `blocked`)
- [ ] zero-coupon instrument and ladders (a)-(c) at 0% and 3%, tested
- [ ] `scripts/strips_reserve.py`, `reports/strips_reserve.csv`, and the headline effect
- [ ] `docs/loop/r3_strips_findings.md`
- [ ] `PYTHONPATH=$WT/src PY -m pytest -q` passes; `scripts/run_all.py` leaves every pre-existing `reports/` file byte-identical
- [ ] one commit per task

## Files you own
`src/lgm/instruments.py` and `src/lgm/ladder.py` (additive only), `src/lgm/data/strips.py`,
`data/raw/strips/`, `scripts/strips_reserve.py`, `tests/test_strips.py`, `reports/strips_reserve.csv`,
`docs/loop/r3_strips_findings.md`. Do not edit `esg.py`, `backtest.py` or `engine.py` (other workers own them).

## Not yours to decide
Whether the IPS switches instruments.

## Budget
About 2 hours. Research that hits a wall after a real attempt: report `blocked` with what you tried.
