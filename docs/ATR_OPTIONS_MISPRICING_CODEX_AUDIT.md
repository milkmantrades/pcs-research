# Codex audit — Weekly SPX ATR-level options mispricing and put-spread sleeve

**Audit date:** 2026-08-12  
**Scope:** `ATR_LEVELS_OPTIONS_MISPRICING_FINDINGS.md`, the five named Python programs,
`level_quotes.sqlite`, saved result CSVs, `gex/SPX_eod.csv`, `gex/VIX_eod.csv`, and
`spy.db`/`ind_1w`. All option reruns below use the banked quotes; no historical option data
was re-pulled.

## Bottom line

The 10:00 ET **50-wide strategy result is reproducible**: 321 trades, 15 losses, 95.33%
wins, PF 2.086, +$40,169.56, $5,814.80 max drawdown, and no negative calendar year. The
75-wide and 100-wide PFs also reproduce.

Several stronger claims do not survive the audit:

- **High — executable digital mispricing:** the −1 ATR put result is +3.10 percentage points
  at independent-leg mids, but the requested seller-side 5-point vertical is negative on
  average. On the positive-credit subset it implies 4.82% versus 5.94% realized. The claim
  that the tight digital is overpriced after executable friction is **refuted**.
- **High — control attribution:** the 2.74%-distance control averages 9.76% midpoint implied
  probability versus 7.68% for ATR on paired weeks. It is a nearer-delta, higher-risk rule,
  so it does not establish that ATR adds edge beyond selling a roughly 7% implied-probability
  put. Banked approximations still favor ATR, but the sparse, ATR-centered quote grid cannot
  produce a clean independent delta-matched control.
- **High — tail and sizing text:** there were four capped 50-point payouts, not “no
  full-width loss.” They account for 46.1% of gross losing dollars. Actual per-lot max risk
  reached $4,992.64; $4,741 is the *average* max risk, not the structural cap.
- **Medium — quote-time fragility:** the 50-wide result stays profitable at 09:58 and 10:02,
  but PF moves from 2.09 to about 2.29 and total P&L moves by roughly 17%. Five nonpositive
  10:00 credits become positive at the adjacent snapshots.
- **Medium — selection/year stability:** the full-sample paired gap is positive, but the
  ten-cell simultaneous lower bound crosses zero. The “positive in all seven years” pattern
  is thin: one additional event flips 2021 and 2023, and only 23.5% of within-year bootstrap
  samples retain all seven positive signs.

The recent read remains favorable: the saved 50-wide trades reproduce 2025+ at 79 trades,
96.2% wins, PF 3.19, and +$15,892; 2026 YTD has 29 wins in 29 trades and +$9,988.44.

## 1. Point-in-time integrity — QUALIFIED

**No traded-week leakage was found.** `physical_probs.py:67-75` resamples daily SPX bars to
`W-FRI`, computes weekly true range, applies Wilder-style `ewm(alpha=1/14,
adjust=False)`, and then shifts ATR and close by one week. A direct reconstruction matched
every saved weekly OHLC and previous close exactly; maximum ATR difference was
`5.7e-14` from floating-point arithmetic. This also matches the repo convention in
`indicators.py:156-198`.

The three consumers agree on the same boundary logic:

- `pull_level_quotes.py:61-70`
- `pull_control_quotes.py:34-43`
- `mispricing_map.py:41-51`
- `sim_put_spread.py:55-70`

Each selects daily dates in `(prev_end, W-FRI label]`, takes the first as entry and the last
as expiration/settlement. Across the 328 banked weeks this yields 295 Monday entries and 33
Tuesday entries after Monday holidays; it yields 315 Friday expirations and 13 Thursday
expirations when Friday was closed. Good Friday and year-end holiday bins are handled
correctly. No complete week in the sample was discarded by the `len(days) < 3` rule.

There are three qualifications:

1. `spx_weekly_levels.csv` has 329 rows because `physical_probs.py` includes the still-open
   `W-FRI 2026-08-14` bin, containing only the 2026-08-10 and 2026-08-11 sessions. The option
   consumers reject it because it has fewer than three sessions, but the physical-probability
   table counts its 2026-08-11 close as a weekly close. Excluding it gives 328 completed SPX
   weeks. At −1 ATR the corrected full-sample close-below rate is 16/328 = **4.878%** rather
   than 16/329 = 4.863%; 2025+ is 4/84 = **4.762%** rather than 4/85 = 4.706%. Rounded
   findings do not change. The analogous +1 ATR rates become 7.317% full sample and 10.714%
   for 2025+.
2. “327 weeks matched” is not a common denominator. The bank has 328 entry weeks; the map
   ranges from 293 to 327 observations by cell, and the primary −1 ATR put cell has **n=326**.
   The 50-wide strategy has n=321 after armability filters. The published start date is also
   off by one week: the bank and saved trades begin with entry 2020-04-27 and expiration
   2020-05-01, not entry 2020-05-04.
3. `spy.db/ind_1w` correctly contains 1,366 lagged weekly SPY rows, but ends at the completed
   week timestamped 2026-04-12. It is not current through the audit date. The long-history
   statistic is reproducible; its 2025+ slice is less current than the SPX slice.

The SPX file begins in December 2019. Using a classical 14-week SMA seed instead of Pandas'
first-observation EWM seed changes the May 2020 ATR by 2.41 SPX points (1.31%) and changes
five rounded −1 ATR strikes in 2020. This is initialization sensitivity, not lookahead, and
decays below 0.2 point by December 2020.

## 2. Settlement realism — CONFIRMED

The strategy uses `gex/SPX_eod.csv` expiration-day close in `sim_put_spread.py:69-84`.
[Cboe's SPX Weeklys specifications](https://www.cboe.com/tradable_products/sp_500/spx_weekly_options/specifications)
identify root `SPXW` as PM-settled, cash-settled, and European. The
[Cboe SPX fact sheet](https://cdn.cboe.com/resources/spx/spx-fact-sheet.pdf) states that the
SPXW exercise value uses the last reported component-stock prices on expiration day.

I joined the 321 primary expirations to Cboe's weekly, month-end, and standard-expiration
[settlement-value archive](https://www.cboe.com/index_settlement_values/weeklys_settlement_values/):

- 308/321 dates have an SPXW row in the current web archive.
- 306 match the local SPX close exactly.
- 2020-10-02 differs by +0.02 point and 2020-10-09 by −0.01 point. Neither is near either
  strike, so no outcome or P&L changes.
- The 13 unmatched dates are early third Fridays from 2020-05 through 2021-08. The archive
  does not display an SPXW PM row for those dates, although Cboe's
  [SPXpm pilot history](https://cdn.cboe.com/resources/options/regulation/pm_settlement_pilot/spx/SPXpm%20Interim%20Pilot%20Report%20and%20XSP%20-%20Q42021.pdf)
  documents third-Friday PM-settled SPXW well before the study period. Their contract rule
  makes the SPX close the correct value.

The pull requests explicitly use `symbol=SPXW` in `pull_level_quotes.py:109-113` and
`pull_control_quotes.py:56-60`; standard AM-settled `SPX` contracts are not requested. Third
Friday alone does not imply AM settlement because PM-settled SPXW third-Friday contracts
coexist with standard SPX AM contracts. One reproducibility weakness remains: the SQLite
schema at `pull_level_quotes.py:88-94` does not store the requested root, so provenance is in
the acquisition code rather than self-contained in the database.

## 3. Quote handling and fill honesty — QUALIFIED

The implemented mechanics are correct:

- `mispricing_map.py:20-30` and `sim_put_spread.py:26-34` select the last quote at or before
  10:00.
- Every one of 11,989 banked contract-days has exactly seven rows, 09:56 through 10:02, so
  the baseline always selects the timestamped 10:00 row rather than an older row.
- `sim_put_spread.py:73-84` sells the short put at bid, buys the wing at ask, skips a
  nonpositive short bid or spread credit, settles intrinsic value, applies the $100
  multiplier, and subtracts $2.64 once per spread.

At 10:00 there are no negative or crossed individual quotes. There are 50 zero bids and 35
zero asks across the full selected quote bank; 35 are locked zero/zero quotes. Across primary
50-wide trades, both the short bid size and wing ask size are at least one contract. The
reported short-leg depth is exact: median 89 and tenth percentile 10.

For the 50-wide primary rule, 328 eligible calendar weeks become 321 trades:

| exclusion | count | outcome check |
|---|---:|---|
| short bid `<= 0` | 1 | expired above the short strike |
| spread credit `<= 0` | 5 | four expired above the short; 2026-06-05 settled 1.26 points below it |
| missing 50-point wing | 1 | expired above the short strike |

The exclusions do not hide a severe loss. They are nevertheless snapshot-sensitive: only
two weeks are excluded at 09:58 and 10:02.

| quote cutoff | n | losses | avg credit | PF | P&L | max DD | negative years |
|---|---:|---:|---:|---:|---:|---:|---:|
| 09:58 | 326 | 15 | 2.783 | 2.287 | $46,880.36 | $4,610.28 | 0 |
| **10:00** | **321** | **15** | **2.613** | **2.086** | **$40,169.56** | **$5,814.80** | **0** |
| 10:02 | 326 | 15 | 2.793 | 2.295 | $47,215.36 | $4,927.44 | 0 |

Thus profitability and the all-positive-year result survive adjacent minutes, but reported
PF and P&L are materially snapshot-dependent. The weakest baseline year is 2024 at only
+$423.36; it is +$2,760.72 at 09:58 and +$1,960.72 at 10:02.

2020 was not uniformly stale or unusable. For primary legs, the median short/wing spreads
were 0.20/0.15 point, but maxima reached 6.20/3.90 points and maximum midpoint-to-fill cost
was 5.05 points. From 09:56 to 10:00, only 8.1% of short prices and 14.0% of wing prices were
unchanged; sizes changed in every primary contract. The larger issue is occasional width,
not timestamp staleness.

## 4. Strike rounding — CONFIRMED

`round(x/5)*5` is used consistently in `pull_level_quotes.py:47-48`,
`mispricing_map.py:16-17`, and `sim_put_spread.py:22-23`. None of the 3,280 raw level/side
observations is an exact `.5` tie after division by five, so Python banker's rounding never
changes a strike relative to ordinary nearest-five rounding. For the primary downside cell,
rounded strike minus raw level averages +0.137 point and ranges from −2.491 to +2.465. There
is no material systematic rounding effect.

The digital is centered on the interval, not on `K`. For puts, a K/K−5 vertical corresponds
to an average distribution threshold near K−2.5, and `mispricing_map.py:69-73` correctly uses
that midpoint. The findings phrase “against the same K” is inaccurate. Using settlement
strictly below K instead changes one primary event—2026-06-05—and raises realized frequency
from 4.601% to 4.908%, reducing the midpoint gap from +3.104 to +2.798 points. The midpoint
implementation is the better apples-to-apples comparison.

## 5. Digital construction — REFUTED at executable prices

At mids, `(mid(K) - mid(K-5))/5` is the standard finite-width put-digital approximation and
the saved primary numbers reproduce:

- n=326
- midpoint implied = **7.706%**
- midpoint-threshold realized = **4.601%**
- gap = **+3.104 percentage points**

The requested executable seller-side calculation does not preserve the gap:

- mean `(bid(K) - ask(K-5))/5` = **−3.052%**
- gap versus 4.601% realized = **−7.653 points**
- restricting to the 202 weeks with positive 5-point credit gives executable implied
  **4.817%**, realized **5.941%**, gap **−1.124 points**, PF **0.702**, and −$1,668.28.

The negative raw average is not a probability; it records that independent-leg spread
crossing cost often exceeds the five-point vertical's value. It directly answers whether
the midpoint mispricing can be sold in that tight structure: it cannot in this sample.

The midpoint surface also has quote-noise violations:

- 29/327 put weeks and 20/323 call weeks have at least one adjacent level where implied
  probability increases with distance.
- Across 3,205 map observations, 13 midpoint digitals are below zero and one is above one.
  The primary cell contains two negatives (−12% and −5%).
- The largest adjacent violation is +43 points for puts and +168 points for calls, caused by
  wide independent-leg markets.

The code path allows these observations: `mispricing_map.py:62-69` rejects a missing leg and
a short quote with both bid and ask zero, but it does not validate the partner quote, bound
the resulting digital to [0, 1], or enforce cross-strike monotonicity.

This noise does not by itself erase the *midpoint* result. On 294 put weeks with all five
digitals available, bounded, and monotone, −1 ATR is 7.296% implied versus 4.422% realized,
a +2.874-point gap. An isotonic repair gives a similar result. The failure is specifically
the conversion from midpoint indication to executable 5-point sale.

For calls, the “do not sell” instruction is robust: seller-side call vertical values make
the gaps still more negative. The stronger statement that calls are cheaply *buyable* is a
midpoint artifact. At +1 ATR, midpoint implied is 6.159% versus 8.191% realized, but the
buyer-side cost `(ask(K)-bid(K+5))/5` is 11.15%, 2.96 points *above* realized. Buyer-side
cost exceeds realized frequency at all five call levels. The data supports “do not sell
calls,” not an executable long-call claim.

## 6. Selection effects and frequency uncertainty — QUALIFIED

For the 321 strategy trades, 15/321 = 4.673%. A 95% exact binomial interval is
**[2.639%, 7.590%]** and Wilson is [2.852%, 7.566%]. The 7.706% midpoint-implied benchmark
sits just above those upper limits. A lower-tail binomial test at 7.706% gives p=0.021; a
Poisson-binomial calculation with the available week-specific implied values gives p=0.0208
for 15 or fewer events.

The paired −1 ATR map gap has a 95% week bootstrap interval of **[+0.675, +5.302] points**;
a four-week block bootstrap gives [+0.844, +5.202]. The full-sample cell is therefore not
dependent on a single losing week.

Selection across the ten reported level/side cells matters to the strength of that statement.
On the 291 weeks shared by all ten cells, −1 ATR puts remain the largest gap at +3.162 points,
but the 95% one-sided simultaneous lower bound is **−2.643 points**. The selected-cell claim
is positive descriptively, but not isolated from the ten-cell scan by this sample.

| year | n | implied | realized events | realized | gap |
|---|---:|---:|---:|---:|---:|
| 2020 | 35 | 7.10% | 1 | 2.86% | +4.24 pt |
| 2021 | 53 | 7.33% | 3 | 5.66% | +1.67 pt |
| 2022 | 51 | 10.34% | 4 | 7.84% | +2.50 pt |
| 2023 | 51 | 4.79% | 2 | 3.92% | +0.87 pt |
| 2024 | 52 | 7.07% | 2 | 3.85% | +3.22 pt |
| 2025 | 52 | 8.60% | 3 | 5.77% | +2.83 pt |
| 2026 YTD | 32 | 9.02% | 0 | 0.00% | +9.02 pt |

One additional realized event makes 2021 and 2023 negative. Every annual within-year
bootstrap interval crosses zero except 2026, and the chance that all seven resampled annual
gaps remain positive is 23.5%. “Positive every year” is true for the observed point estimates
but thin as a stability statement.

Losers are not materially serially clustered: there is one adjacent pair (2022-06-06 and
2022-06-13), lag-one loss correlation is 0.021, loss-after-loss frequency is 6.7%, and
loss-after-win frequency is 4.6%.

## 7. Generic VRP / delta control — QUALIFIED; attribution not established

The published fixed 2.74% result reproduces exactly: n=315, 19 losses, average credit 3.429,
PF 1.616, +$34,987.40, $16,046.24 max drawdown, with 2022 at −$5,418.64 and 2024 at
−$776.36. ATR wins the stated comparison.

That comparison is not delta-fair. On 327 paired digital weeks:

- ATR mean distance is 3.187% and midpoint implied probability is 7.682%.
- Fixed-control mean distance is 2.740% and midpoint implied probability is **9.755%**.
- The fixed rule therefore sells a materially nearer effective delta and collects 3.43
  points versus 2.61.

I built the closest fixed-distance approximation available without new pulls. Selecting the
banked, executable 50-wide candidate nearest a fixed 3.35%-of-close strike makes aggregate
midpoint implied probability 7.77%, close to ATR. It produces n=319, 5.02% realized,
2.69-point average credit, PF **1.54**, +$26,477, and $13,157 max drawdown. ATR remains
better in that approximation.

This is not a clean final control. The bank only explicitly pulls K, K−5, K−25, and K−50
around the five ATR bases and the 2.74% control. The 3.35% target misses its desired strike by
19 SPX points on average, and its candidate universe is itself ATR-centered. A weekly
implied-probability selector from the same bank mechanically chooses the ATR strike on a
large share of weeks. Exact credit/delta matching needs a fuller strike chain or targeted
quotes at the independently defined control strikes.

**Correct conclusion:** ATR scaling beats the particular 2.74% naive control and the banked
fixed-distance approximation. This dataset does **not** establish that the edge is ATR-specific
rather than the payoff from selling a roughly 7% implied-probability put. The sentence “the
vol scaling is the edge” is too strong.

## 8. Width sweep — QUALIFIED

The banked-quote rerun is:

| width | n | losses | PF | total P&L | max DD | avg max risk | avg P&L / avg max risk | negative years |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 202 | 12 | 0.702 | −$1,668.28 | $2,405.00 | $478.56 | −1.73% | 5 |
| 25 | 313 | 14 | 1.741 | +$17,239.68 | $4,214.28 | $2,361.11 | 2.33% | 1 |
| **50** | **321** | **15** | **2.086** | **+$40,169.56** | **$5,814.80** | **$4,741.38** | **2.64%** | **0** |
| 75 | 325 | 16 | 2.374 | +$60,749.00 | $6,982.44 | $7,153.15 | 2.61% | 0 |
| 100 | 321 | 16 | 2.503 | +$75,089.56 | $9,292.64 | $9,580.79 | 2.44% | 0 |

The PF ordering is not driven by differing samples. On the 198 dates tradable at all widths,
PF is 0.687 / 1.642 / 2.110 / 2.426 / 2.606 for 5/25/50/75/100. However, structural-risk
efficiency peaks slightly at **50**, not 75: 3.523% versus 3.487% on the common sample and
2.639% versus 2.613% on each width's full sample. Seventy-five only “peaks” if observed max
drawdown is used as the risk denominator, which is not the contractual risk cap.

The n differences also have a different cause from the suggested one:

- 5-wide drops 124 weeks for nonpositive credit, not for missing deep wings.
- 25-wide drops 14 for nonpositive credit and one zero short bid.
- 50-wide drops five for nonpositive credit, one zero short bid, and one missing wing.
- 75-wide has two missing wings, in 2023 and 2024, plus one zero short bid.
- 100-wide has five missing wings, all in 2022, plus one zero bid and one nonpositive credit.

The saved pull code does not explicitly acquire K−75 or K−100
(`pull_level_quotes.py:73-80`); those wings are available only when another ATR/control grid
point happened to bank the strike. The 75/100 sweep has no checked-in source program or
trade CSV, a reproducibility gap, although its economics can be reconstructed from SQLite.

Finally, “no full-width loss” is false. Four 50-wide trades settled below the long wing and
paid the full 50 points: 2020-10-30, 2022-01-21, 2024-09-06, and 2025-04-04. A positive entry
credit means net P&L is not −$5,000, but each is the maximum loss for its entered spread.
Average max risk is $4,741; the largest entered max risk is **$4,992.64**, so a new trade must
be sized to nearly $5,000 per lot.

## 9. End-to-end reconciliation — CONFIRMED

All quotes below are the exact 10:00 database row. Credit is `short bid − wing ask`; P&L is
`(credit − payout) × 100 − 2.64`.

| entry → expiration | level arithmetic → strikes | short bid/ask (size) | wing bid/ask (size) | credit | settlement | payout | P&L |
|---|---|---:|---:|---:|---:|---:|---:|
| 2020-04-27 → 2020-05-01 | 2836.74 − 186.4613 = 2650.2787 → 2650/2600 | 1.90/2.05 (300 bid) | 0.95/1.05 (256 ask) | 0.85 | 2830.71 | 0.00 | +$82.36 |
| 2020-05-26 → 2020-05-29 | 2955.45 − 174.7324 = 2780.7176 → 2780/2730 | 0.45/0.50 (47) | 0.20/0.30 (210) | 0.15 | 3044.31 | 0.00 | +$12.36 |
| 2021-03-29 → 2021-04-01 | 3974.54 − 122.3586 = 3852.1814 → 3850/3800 | 5.80/6.10 (272) | 3.00/3.30 (842) | 2.50 | 4019.87 | 0.00 | +$247.36 |
| 2024-04-15 → 2024-04-19 | 5123.41 − 109.8853 = 5013.5247 → 5015/4965 | 4.00/4.20 (244) | 2.30/2.40 (100) | 1.60 | 4967.23 | 47.77 | **−$4,619.64** |
| 2025-03-31 → 2025-04-04 | 5580.94 − 172.6554 = 5408.2846 → 5410/5360 | 29.70/29.90 (5) | 19.30/19.50 (30) | 10.20 | 5074.08 | 50.00 | **−$3,982.64** |

The second row is a Tuesday entry after Memorial Day. The third is the Good Friday holiday
week, correctly expiring and settling Thursday 2021-04-01 even though the resample label is
Friday 2021-04-02. The fourth is the reported worst P&L. The fifth demonstrates a capped
full-width payout. The sampled Cboe SPXW values match the local settlements.

## Economic read

### Loss anatomy

The loss profile is mostly drift-through in frequency, with a meaningful capped tail in
dollars:

- Loser entry VIX median/mean is 22.28/22.22 versus 18.66/20.18 for winners. Only 3/15 loser
  entries have VIX at least 25, the same 20% proportion as winners. Entry VIX alone is not a
  clean gate.
- Maximum VIX during the week is more diagnostic: median 28.97 for losers versus 21.54 for
  winners.
- First strike touch occurs Friday in 6 losses, Tuesday in 4, Wednesday in 3, and Thursday in
  2. First daily close below the short is Thursday or Friday in 11/15. Fourteen of 15 weekly
  losses are intraday/grind-dominant in an overnight-versus-intraday log-return decomposition.
  The 2025-03-31 tariff-shock week is the one clear gap-dominant case.
- Four capped payouts produce $17,050.56 of $37,002.60 gross losing P&L, or 46.1%. The sleeve
  is therefore not a pure crash-only loser by count, but tail weeks dominate loss severity.

The only adjacent losing pair is June 2022. Other losses are dispersed from 2020-10-26
through 2025-10-06.

### Feb-2018 / 2008 implication

The SPY weekly analog closed 7.16 and 9.44 SPY points below its lagged −1 ATR level in the two
February 2018 selloff weeks—roughly 72 and 94 SPX points at the usual 10:1 scale. A 50-wide
SPX spread would have capped in both; a 75-wide would have paid about 72 points in the first
and capped in the second. The week ending 2008-10-12 closed 12.99 SPY points below its lower
ATR level, roughly 130 SPX points, capping both widths.

Those episodes imply that the extra 25 points of a 75-wide spread become extra loss, not
extra protection, in the most relevant omitted regimes. In-sample, moving from 50 to 75 adds
about 0.88 point of average credit but about $2,412 of average contractual risk per lot. That
is unattractive for the first probe despite the higher headline PF.

### Call side

The call midpoint gaps are negative and seller-side execution makes them more negative, so
the instruction not to sell the call wing is confirmed. A buy-side crossing treatment flips
all five gaps positive—cost above realized frequency—so the banked snapshot does not support
calling the upside “cheap to buy.” A separate long-call study would need wider structures or
less punitive execution than crossing a five-point vertical one leg at a time.

## Probe deployment decision

**Yes—deploy only at probe size, using the 50-wide spread.** The executable 50-wide P&L is
positive at all three nearby snapshots, has no negative year, and is strongest in 2025+.
Fifty-wide has slightly better return per contractual dollar than 75-wide and materially less
omitted-regime tail exposure. Size each entry to its actual maximum loss and assume up to
approximately **$5,000 per lot**, not $4,740. Require a positive natural spread credit and
record the exact multileg fill. Treat the rationale as a profitable, operationally honest
weekly put-spread candidate; do not describe the evidence as proof of an executable 5-point
digital mispricing or as proof that ATR scaling beats a true delta-matched rule.
