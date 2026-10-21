# Validation of the former CS team's numbers

Every figure in the two documents the CS team left behind — the model rebuild guide ("Init plan") and
"Laura Gao case v2: specific instruments for each plan" (Plans v2) — was checked against primary sources
or reproduced independently with this codebase. Checked Oct 21, 2026.

**Verdict:** the guide's arithmetic is exact, and the team's simulation results reproduce within 0–5%.
Eight discrepancies in the documents and three errors about WInS itself were found; none changes a
strategy conclusion.

## 1. Primary-source data

| Item | Document value | Primary source | Result |
| --- | --- | --- | --- |
| Treasury par yields, Oct 16 (5/7/10/20-yr) | 4.89 / 4.98 / 5.09 / 5.47 | Treasury daily par yield CSV | Exact |
| Treasury 2-yr, Oct 16 (guide Step 6) | 4.74 | Treasury | Exact |
| Treasury curve, Oct 20 (Plans v2 basis) | used for all pricing | Treasury | Loaded directly |
| Five Treasury bonds: CUSIP, coupon, maturity | 912810PU6 5.000% May-37 ... 912810QT8 3.125% Nov-41 | TreasuryDirect securities API | All five exact |
| ETF closes, Oct 20 (VTI, VEA, VWO, VGIT, IBTM-IBTR) | 377.09, 69.78, 58.25, 57.03, 21.89, 23.16, 24.27, 23.89, 23.70 | Yahoo Finance | All within $0.01 |
| iBonds expense ratio | 0.07% | iShares (IBTR page) | Exact |
| IBTR launch date | Mar 25, 2026 | iShares | Exact |

## 2. Guide, Steps 1-7 (deterministic and spreadsheet Monte Carlo)

All 23 published figures reproduce to the dollar (`tests/test_guide_steps.py`), including the Step 4
curve lock of $298,927 from Treasury's official Oct 16 curve, the 29% facility drop in Step 3, the
Step 6 floor of $117,594, and the Step 7 simulation ranges (60/40: 96.5% funded, $16k / $210k / $507k;
all-stock 86%; lock-and-balance $140k / $200k / $290k; random-rate reserve $388k-$442k).

## 3. Model outputs (reproduced with the rebuilt engine)

Facility money in Jan 2033, $ thousands. Rebuilt engine: 20,000 scenarios, the team's documented
inputs (stocks 6.06%/yr net, 16.5% volatility, rates unchanged on average), fat tails (Student-t, 5 df).

| Plan | Funded: theirs / ours | 5th pct | Median | 95th pct | 2031 floor | 2031 80% range |
| --- | --- | --- | --- | --- | --- | --- |
| S1 all equity | 86.8% / 86.8% | 0 / 0 | 212.8 / 221.0 | 759.3 / 780.8 | — | — |
| S2 static 60/40 | 96.4% / 97.0% | 16.2 / 20.3 | 208.0 / 216.6 | 508.3 / 528.7 | 0 / 0 | 120.7-332.4 / 82.7-313.9 |
| S8 hybrid | 100% / 100% | 94.2 / 97.6 | 194.9 / 199.8 | 355.3 / 368.2 | 124.3 / 119.7 | 191.9-230.2 / 183.3-222.6 |
| S6 lock, stock surplus | 100% / 100% | 106.2 / 107.9 | 197.7 / 200.0 | 365.5 / 370.5 | 0 / 0 | 150.2-261.7 / 148.3-270.2 |
| S9 lock, 60/40, floor | 100% / 100% | 137.9 / 142.7 | 193.5 / 196.5 | 273.2 / 275.3 | 114.6 / 114.8 | 181.4-208.6 / 179.8-208.4 |

Other model claims:

| Claim | Theirs | Ours |
| --- | --- | --- |
| Zero-coupon cost of the ladder, Oct 16 (guide 4C) | $295,584 | $295,559 |
| Real-instrument ladder, Oct 16 (guide 4C) | $300,769 | $300,396 (LP, 3% reinvestment) |
| Real-instrument ladder, Oct 20 (Plans v2) | $300.1k | $299,717 |
| Rates 0.75 pts lower at the lock: lock-and-balance median | $192k -> $159k (-17%) | $196.5k -> $160.5k (-18%) |
| Fat tails change results by | < $5k | < $5k (Gaussian vs t5) |
| Facility buys less in Taiwan terms | ~25% | 21% at 4%/yr building costs; 25% needs ~5%/yr |
| Plans v2 nine-instrument ladder funds ten payments | yes | yes: coupons 2027-32 pay the 2033 payment; $4k-$16k surplus each year |

## 4. Discrepancies found

1. **Plans v2 bond prices** are 0.6-0.7 points above prices from Treasury's curve (yields 5-9 bp lower).
   Conservative (overstates ladder cost ~0.7%), not reproducible from published data. Use WInS quotes.
2. **Plans v2 Jan 2033 ladder ($411.8k)** vs $404.6k on an unchanged curve (+1.8%); consistent with
   their double-counted fund fee (their own footnote) plus the bond-price gap above.
3. **Fund fee counted twice** in Plans v2's internal ladder cost (~$2k) — their footnote; fixed here.
4. **Taiwan "25% less"** needs ~5%/yr building-cost growth; the team's stated range is 3-6%.
5. **"10-year yield spiked to ~5.33%" (week of Oct 12-16)** — a search-result claim used in our
   exemplar's grader notes; Treasury closes peaked at 5.21% (Oct 13). Corrected in the exemplar.
6. **IBTR assets** — exemplar IPS said ~$11 million (July 2026); iShares shows $111.4 million (Oct 19).
   Corrected.
7. **Oct 19 7-year yield** — exemplar documents interpolated 5.02%; Treasury published 5.04%. The lock
   cost becomes $297,228 (was $297,325); the rate fall that breaches $300,000 is 0.097 pts. Corrected.
8. **Background check recommends TIPS** for the reserve; TIPS are not permitted. Ignored.

## 5. Checked inside WInS (Session Rules tab, quote pages and bond list, Oct 21, 2026)

| Item | Plans v2 | WInS | Result |
| --- | --- | --- | --- |
| Starting cash | $300,000 | $300,000 | Confirmed |
| Trade cap | 200 | 200 | Confirmed |
| Commissions | $25 per ETF, $10 per bond | $25 per stock/ETF, $10 per bond | Confirmed |
| Trading window | to Nov 6 | Sep 28 09:30 - Nov 6 16:00 ET | Confirmed |
| Minimum stock price | $5 | **$3.00** | Wrong in Plans v2 |
| Government bonds | US, UK, DE, FR, IT, NL | **US Treasury bonds only** (the screen lists other markets, but session rules allow US only) | Wrong in Plans v2 |
| Bond types | notes and bonds | **42 original-issue T-bonds only** (no T-notes); nothing maturing Mar 2031 - Jan 2036 | New constraint |
| UST 5.000% May-2037 (912810PU6) | used for the Jan 2038 payment | **Not listed in WInS**; nearest is 4.750% Feb-2037 (912810PT9) | Replace |
| Other four Plans v2 bonds | used | Listed | Confirmed |
| ETFs: VTI, VEA, VWO, VGIT, IBTL-IBTR, TLT, TLH, SGOV, VT, ACWI | used | Listed; Oct 20 prices match | Confirmed |
| Not stated in Plans v2 | — | No fractional shares; no day trading; 0% interest on cash; ~40 exchanges incl. Taiwan (TW) and Hong Kong | New constraints |

The WInS bond list is saved in `data/wins/treasury_bonds.csv` and the ladder optimiser only uses it.
The cheapest WInS-feasible ladder for a Jan 2027 purchase on the Oct 20 curve costs $299,717
(`ladder.solve`), identical to the optimum with the unlisted bond, because the optimiser never needed it.

## Reproduce

```
python -m pytest                      # 32 tests, includes every guide figure
python scripts/validate_plans_v2.py   # section 3 table -> reports/plans_v2_validation.csv
```
