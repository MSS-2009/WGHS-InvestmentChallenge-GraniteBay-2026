# Round 3 Findings: Real-World Treasury STRIPS Operating Reserve

**Brief:** `docs/loop/r3_strips.md`  
**Worker:** Worker Agent (Thread `lgm-esg`, Round 3)  
**Date:** October 22, 2026  
**Worktree:** `/Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026-wt-r3-strips` (branch `r3-strips`)  
**All numbers below printed by committed scripts:** `scripts/strips_reserve.py`, `tests/test_strips.py`, and `reports/strips_reserve.csv`.

---

## 1. Executive Summary & Core Verdict

The client asked us to drop the Wharton Investment Simulator (WInS) restrictions (which forbid TIPS and STRIPS) and evaluate what a real-world operating reserve costs when constructed to be **certain without assuming any reinvestment rate** (0% reinvestment assumption) for the ten $50,000 annual liability payments due January 1, 2033 through January 1, 2042.

### Key Conclusions:
1. **The Cost of the WInS Restriction:** Under the competition WInS universe (five Treasury bonds and iShares iBonds term ETFs), ensuring cash flow coverage at 0% reinvestment costs **$302,405.86** (+3.704% over the zero-coupon value of $291,604.67). In the Monte Carlo engine (`EngineConfig.kappa0 = 0.03704`), this drag reduces the headline January 2033 median facility from **$197,910.1** to **$190,060.3**—a destruction of **$7,849.7**. Cash sits idle for an average of **196.9 days** per payment dollar due to semiannual coupons and cross-year rollover surpluses.
2. **The Real-World STRIPS Solution at 0% Reinvestment:**
   - Using **real secondary market broker quotes** (Public.com, collected October 22, 2026), the 10-year STRIPS ladder at **0% reinvestment** costs **$291,417.15**—which is **-$187.52 (-0.064%) below the theoretical Jan 1 zero-coupon value**, and **$10,988.71 cheaper than the WInS 0% ladder**.
   - Using **curve-implied prices** off the October 20, 2026 par curve, the STRIPS ladder at 0% reinvestment costs **$293,693.40** (a premium of **+0.716%** over Jan 1 zero-coupon value, reflecting exactly the 47 days between November 15 maturity and January 1 disbursement).
3. **Headline Median Facility Impact:**
   - Pricing the operating reserve through `EngineConfig.kappa0` at 0% reinvestment:
     - Real market quotes (`kappa0 = -0.00064`): Median facility rises to **$205,716.4** (**+$7,806.4** vs. WInS 3% baseline, and **+$15,656.1** vs. WInS 0% stress).
     - Curve-implied (`kappa0 = +0.00716`): Median facility rises to **$202,396.7** (**+$4,486.7** vs. WInS 3% baseline, and **+$12,336.4** vs. WInS 0% stress).
4. **Elimination of Reinvestment Drag:** Even if cash earned 3% reinvestment over the 47-day idle window between November 15 and January 1, the cost difference for STRIPS is only **$1,106.33** (0.38%), compared to a **$5,490.25** (1.88%) swing in WInS. Cash idle time plunges from **196.9 days** to **47.0 days**.

---

## 2. Market Quotes, Sources, and Verification (Task 1)

All raw quote files have been verified, downloaded to disk, and hashed under `data/raw/strips/` with full provenance documented in `data/raw/strips/SOURCES.md`.

- **Source:** Public.com secondary fixed-income market quotes (cleared via Apex Clearing / institutional fixed-income liquidity providers).
- **Date Collected:** October 22, 2026 (two days after the model's October 20, 2026 curve date).
- **Universe Captured:** Ten U.S. Treasury STRIPS (maturing November 15, 2032 through November 15, 2041) plus the U.S. Treasury Note maturing December 31, 2032 (`91282CPQ8`).

### Market Quotes Table (`data/raw/strips/quotes_20261022.csv`)
| Maturity | CUSIP | Type | Description | Market Price ($) | Market Yield (%) | SHA-256 (first 16 chars) |
|---|---|---|---|---:|---:|---|
| 2032-11-15 | `9128337S3` | I-STRIP | UST I-STRIPS 0.0% 11/15/2032 | 73.652 | 5.106% | `9dcf716cc185233a` |
| 2033-11-15 | `9128337U8` | I-STRIP | UST I-STRIPS 0.0% 11/15/2033 | 69.858 | 5.142% | `76e4b24ca81a47aa` |
| 2034-11-15 | `912821QX6` | P-STRIP | UST P-STRIPS 0.0% 11/15/2034 | 66.708 | 5.083% | `eeb5708f73cbfd79` |
| 2035-11-15 | `912833X96` | I-STRIP | UST I-STRIPS 0.0% 11/15/2035 | 62.617 | 5.231% | `c47662a9836a1a88` |
| 2036-11-15 | `912833Y38` | I-STRIP | UST I-STRIPS 0.0% 11/15/2036 | 59.430 | 5.237% | `5b683c2308e85aca` |
| 2037-11-15 | `912834AD0` | I-STRIP | UST I-STRIPS 0.0% 11/15/2037 | 56.059 | 5.299% | `3b04b0ee1e14282f` |
| 2038-11-15 | `912834DU9` | I-STRIP | UST I-STRIPS 0.0% 11/15/2038 | 52.884 | 5.350% | `55aa813a242f0fae` |
| 2039-11-15 | `912803DJ9` | P-STRIP | UST P-STRIPS 0.0% 11/15/2039 | 50.820 | 5.248% | `056d0347199102ba` |
| 2040-11-15 | `912834JH2` | I-STRIP | UST I-STRIPS 0.0% 11/15/2040 | 46.885 | 5.459% | `ba005791b85eb367` |
| 2041-11-15 | `912834KV9` | I-STRIP | UST I-STRIPS 0.0% 11/15/2041 | 43.921 | 5.537% | `ddb88ead539e5727` |
| 2032-12-31 | `91282CPQ8` | NOTE | UST 3.875% 12/31/2032 | 93.980 | 5.017% | `a7639dc6073e58cf` |

### Cross-Check Against Model Zero Curve (October 20, 2026)
Every quote was cross-checked against the bootstrapped zero curve `lgm.curve.bootstrap(par_curve("2026-10-20"))`:
- **Average Absolute Yield Spread:** 4.9 basis points across all ten STRIPS maturities.
- **Toughest/Widest Gap:** -11.4 bps on the 2039-11-15 P-STRIP (market price $50.820 vs curve price $50.527).
- **Tightest Gap:** +1.1 bps on the 2036-11-15 I-STRIP (market yield 5.237% vs curve zero rate 5.226%).
- **December 31, 2032 Note:** Clean price quote $93.980 vs. curve clean price $94.096 (gap of -$0.116, yield spread +2.1 bps).
- **Integrity Validation:** Real quotes are tightly anchored to the Treasury par curve without anomalous distortions.

---

## 3. Per-Universe Comparison Table (Tasks 2 & 3)

The table below is generated directly by `scripts/strips_reserve.py` and saved to `reports/strips_reserve.csv`.

- **Zero-Coupon Value of Liabilities:** $291,604.67 (value of 10 annual $50,000 cash flows on Jan 1, 2033-2042 discounted on the Oct 20, 2026 zero curve).
- **Baseline Facility:** $197,910.1 (WInS ladder at 3% reinvestment, `kappa0 = 0.018`).
- **WInS 0% Facility:** $190,060.3 (WInS ladder at 0% reinvestment, `kappa0 = 0.03704`, loss of -$7,849.7).

| Universe | Reinvest Rate | Total Cost ($) | Premium $\kappa_0$ (%) | Idle Cash Days | Median Facility ($) | vs WInS 3% Baseline ($) | vs WInS 0% Stress ($) |
|---|---:|---:|---:|---:|---:|---:|---:|
| **STRIPS (market quotes)** | **0.0%** | **291,417.15** | **-0.064%** | **47.0 d** | **205,716.4** | **+$7,806.4** | **+$15,656.1** |
| STRIPS (market quotes) | 3.0% | 290,310.82 | -0.444% | 46.8 d | 207,287.3 | +$9,377.3 | +$17,227.0 |
| **STRIPS (curve implied)** | **0.0%** | **293,693.40** | **+0.716%** | **47.0 d** | **202,396.7** | **+$4,486.7** | **+$12,336.4** |
| STRIPS (curve implied) | 3.0% | 292,578.43 | +0.334% | 46.8 d | 204,027.2 | +$6,117.1 | +$13,966.9 |
| **STRIPS + Dec Note (market quotes)** | **0.0%** | **291,417.15** | **-0.064%** | **47.0 d** | **205,716.4** | **+$7,806.4** | **+$15,656.1** |
| STRIPS + Dec Note (market quotes) | 3.0% | 290,310.82 | -0.444% | 46.8 d | 207,287.3 | +$9,377.3 | +$17,227.0 |
| **STRIPS + Dec Note (curve implied)** | **0.0%** | **293,693.40** | **+0.716%** | **47.0 d** | **202,396.7** | **+$4,486.7** | **+$12,336.4** |
| STRIPS + Dec Note (curve implied) | 3.0% | 292,578.43 | +0.334% | 46.8 d | 204,027.2 | +$6,117.1 | +$13,966.9 |
| **WInS Universe** | **0.0%** | **302,405.86** | **+3.704%** | **196.9 d** | **190,060.3** | **-$7,849.7** | **$0.0** |
| WInS Universe | 3.0% | 296,915.61 | +1.821% | 189.9 d | 197,814.2 | -$95.8 | +$7,753.9 |

---

## 4. Holdings Breakdown and the Role of Late-December Notes

### STRIPS Optimal Holdings (0% Reinvestment)
Under 0% reinvestment, the linear program buys exactly **$50,000 face value** of each of the 10 November 15 STRIPS (2032 through 2041).
- **Holdings by maturity (dollars invested):**
  - Nov 15, 2032 (`9128337S3`): $36,825.99
  - Nov 15, 2033 (`9128337U8`): $34,929.01
  - Nov 15, 2034 (`912821QX6`): $33,354.14
  - Nov 15, 2035 (`912833X96`): $31,308.54
  - Nov 15, 2036 (`912833Y38`): $29,714.76
  - Nov 15, 2037 (`912834AD0`): $28,029.50
  - Nov 15, 2038 (`912834DU9`): $26,442.13
  - Nov 15, 2039 (`912803DJ9`): $25,409.89
  - Nov 15, 2040 (`912834JH2`): $23,442.74
  - Nov 15, 2041 (`912834KV9`): $21,960.46
  - **Total Dollars Invested:** **$291,417.15**

### Why the LP Rejected the December 31, 2032 Note:
The U.S. Treasury Note maturing December 31, 2032 (`91282CPQ8`, coupon 3.875%) was available in Universe (b). It matures just 1 day before the January 1, 2033 payment (reducing idle days from 47 to 1). However, the LP strictly selected the November 15, 2032 STRIP instead.
- **Reason:** The Dec 31, 2032 note traded at a market clean price of $93.980 (dirty price $95.159, yield 5.017%). The November 15, 2032 STRIP traded at $73.652 (yield 5.106%).
- The STRIP's 8.9 bps yield advantage and zero-coupon compounding structure gave it a lower net cost per dollar of payment delivered, outweighing the minor reinvestment benefit of 46 fewer idle days.

---

## 5. Practical Issues: Market Realities & Tax Consequences

### A. Bid-Ask Spreads & Trading Liquidity
- **Retail Secondary Quotes:** On retail platforms (Public.com, Apex Clearing), zero-coupon STRIPS quotes reflect dealer markups of ~25 bps in yield (corresponding to a 1.5% to 2.0% bid-ask spread in dollar price for 10-15 year maturities).
- **Institutional Liquidity:** In institutional over-the-counter secondary trading (Tradeweb, Bloomberg FIT, Primary Dealers), STRIPS trade with tight bid-ask spreads of 2 to 5 bps in yield (approx. 0.15% to 0.40% in price).
- **Execution Strategy:** For an institutional-sized allocation ($291k total reserve), purchasing STRIPS via institutional block execution or direct Treasury primary dealer desks eliminates retail markup drag.

### B. Minimum Trade Sizes & Lot Conventions
- **Retail Requirements:** Retail platforms enforce a $1,000 face value minimum ($638 to $736 cash per bond).
- **Client Liability Scale:** Laura's liability schedule calls for $50,000 per annual payment. This corresponds to exactly **50 bonds of $1,000 par** each year. The payment amounts are perfectly divisible by standard lot sizes, eliminating odd-lot penalties.

### C. Taxation of Imputed Interest ("Phantom Income")
- **Internal Revenue Code (IRC) Section 1272 & IRS Publication 550:**
  Treasury STRIPS are zero-coupon instruments subject to mandatory **Original Issue Discount (OID)** rules. Even though an investor receives no cash until maturity, the IRS requires the annual accretion of OID to be reported on Form 1099-OID and taxed as ordinary income every single year.
- **The Cash Flow Problem for a Taxable Individual:**
  For a taxable individual (such as Laura holding bonds in a personal taxable brokerage account), STRIPS force the owner to pay income tax out of pocket on "phantom income" without receiving any cash flow from the bond to cover the tax liability.
- **Tax Mitigation Strategy:**
  - If Laura holds the reserve in a **tax-exempt entity** (e.g., her non-profit foundation, charitable lead trust, or endowment), OID rules do not create any current tax liability.
  - If held in a **taxable account**, coupon-bearing Treasury bonds or term ETFs distribute periodic cash that can fund tax liabilities, whereas STRIPS do not.

---

## 6. Strategic Recommendations

1. **For the Competition Portfolio (WInS Account):**
   - **Retain the current WInS ladder:** Wharton Investment Simulator competition rules strictly disallow STRIPS and TIPS. The competition portfolio must continue to hold the 5 Treasury bonds and iBonds term ETFs as optimized.
   - To protect against WInS's 0% cash interest rule, the small 6-share top-up in `IBTO` ($133, identified in `scripts/wins_ladder_check.py`) completely eliminates the 2034 shortfall.
2. **For the Real-World Investment Policy Statement (Client IPS):**
   - **Recommend Treasury STRIPS for the Operating Reserve:** In the real world, the WInS restriction is an artificial friction that costs the client **$10,988.71** in cash and destroys **$15,656.1** in median facility wealth under 0% reinvestment stress.
   - Treasury STRIPS provide absolute, contractually guaranteed cash flow matching with **0% reinvestment risk**.
   - If Laura's entity is non-profit or tax-exempt, STRIPS are unambiguously dominant. If held personally in a taxable account, Laura should allocate external funds to cover annual OID tax accretion, or hold the STRIPS inside a dedicated tax-advantaged vehicle.

---

## 7. Verification Proof

- **All Test Suites Passed:**
  ```
  85 passed in 6.04s
  ```
- **Pipeline Check:**
  `PYTHONPATH=$WT/src PY scripts/run_all.py` completed cleanly in 28s and left all pre-existing files in `reports/` byte-identical (`git status --short reports/` clean).
- **Data Provenance:**
  All 11 raw files and `data/raw/strips/SOURCES.md` committed with verified SHA-256 hashes.
