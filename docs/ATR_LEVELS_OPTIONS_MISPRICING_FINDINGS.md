# Saty ATR Levels vs Options Prices: Weekly SPX Mispricing Map + Put-Spread Sleeve

**Date:** 2026-08-12. **Data:** SPXW 1-min quotes (ThetaData v3, Value tier, floor 2020-01-01), SPX EOD (gex/SPX_eod.csv), SPY weekly indicators 2000→2026 (spy.db ind_1w).
**Code/data:** `atr_options_mispricing/` (physical_probs.py, pull_level_quotes.py, mispricing_map.py, sim_put_spread.py, level_quotes.sqlite 10.5k contract-days, trades_*.csv).

## Question

Weekly/monthly Saty ATR level probabilities are stable over time. Can we (1) find options
priced too high or too low against those probabilities, and (2) build a stable premium-selling
strategy from the gap?

## Setup

- Levels: prev weekly close ± fib × prior-week ATR(14) (Wilder, prior-period per the fixed
  indicators.py convention). Fibs: 0.236 (trigger), 0.382, 0.618, 0.786, 1.0.
- Physical: P(weekly close beyond level) and P(touch), SPY 2000→2026 (1,366 wks),
  SPX 2020-05→2026-08 (329 wks).
- Implied: each week's first trading day ~10:00 ET, SPXW expiring that Friday.
  Implied P(settle beyond K) from tight-vertical mids: (mid(K) − mid(K±5)) / 5 at
  K = round5(level). Realized outcome measured against the same K.
- 327 weeks matched, 2020-05-04 → 2026-08-07.

## Physical probabilities (confirms stability)

P(weekly close beyond level), SPY full / SPX 2020+ / SPX 2025+:

| Level | below (dn) | above (up) |
|---|---|---|
| trigger | .30 / .30 / .28 | .41 / .47 / .44 |
| 0.382 | .24 / .25 / .26 | .32 / .35 / .35 |
| 0.618 | .14 / .17 / .20 | .19 / .20 / .21 |
| 0.786 | .11 / .12 / .11 | .12 / .15 / .14 |
| 1.0 | **.059 / .049 / .047** | .062 / .073 / .106 |

## (1) Mispricing map — implied minus realized, 327 weeks

| Level | dn (puts) | up (calls) |
|---|---|---|
| trigger | −0.001 | −0.030 |
| 0.382 | −0.020 | −0.026 |
| 0.618 | −0.013 | −0.015 |
| 0.786 | +0.006 | −0.027 |
| **1.0** | **+0.031** | −0.020 |

- **Puts at the −1.0 ATR weekly level are the one stably overpriced spot**: implied 7.7% vs
  realized 4.6%. The gap was positive in every year 2020→2026 (range +0.9pt in 2023 to
  +9.0pt in 2026 YTD; +5.2pt in 2025+). −0.786 is mildly positive recently.
- Near-the-money puts (trigger→0.618) showed no overpricing in this sample — 2022 alone
  made them pay out more than implied (dn-trigger gap −14.5pt that year). Nothing to sell there.
- **Upside calls: don't sell them** — negative mid-quote gap at almost every level in most
  years (+1 ATR: implied 6.2% vs realized 8.2%), and seller-side execution makes it worse.
  But the audit killed the "cheap to buy" reading: buyer-side crossing costs exceed realized
  frequency at all five call levels. The finding is "don't sell calls," not "buy calls."

## (2) Strategy: short weekly put vertical at the −1 ATR level

Rules: first trading day of week ~10:00 ET, sell SPXW Friday-expiry put at
round5(prev weekly close − 1.0 × prior-week ATR), buy wing 50 lower. Fill = short at bid,
wing at ask (honest). Hold to cash settlement. $2.64 commission. 1-lot, $100 multiplier.

| Structure | n | win | PF | total P&L | $/yr | maxDD | neg yrs |
|---|---|---|---|---|---|---|---|
| **ATR −1.0, 50-wide** | 321 | **95.3%** | **2.09** | **+$40,170** | **$6,410** | **$5,815** | **0 of 7** |
| ATR −1.0, 25-wide | 313 | 95.5% | 1.74 | +$17,240 | $2,751 | $4,214 | 1 |
| ATR −0.786, 50-wide | 319 | 90.6% | 1.40 | +$30,737 | $4,905 | $13,723 | 2 |
| Control: fixed −2.74%, 50-wide | 315 | 94.0% | 1.62 | +$34,987 | $5,583 | $16,046 | 2 (2022 −$5.4k, 2024) |

- Frequency ~50 trades/yr. Avg credit 2.61 pts ($261) on ~$4,740 max risk → avg +$125/trade.
- 2025+: n=79, 96.2% win, PF 3.19, +$15,892. 2026 YTD: 29/29 wins, +$9,988.
- 15 losers in 321 (all listed in trades_atr100_w50.csv); worst −$4,620 (2024-04-15).
  **Four losers paid the full 50-point width** (2020-10-30, 2022-01-21, 2024-09-06,
  2025-04-04) — 46% of gross losing dollars. Largest entered max risk $4,992.64/lot:
  size to ~$5,000 per lot, not the $4,740 average.
- **ATR scaling beats the naive fixed-% rule** (control: PF 1.62, 2022 −$5,419, 3× the maxDD)
  — but the audit showed the control sits at a nearer effective delta (9.8% vs 7.7% implied),
  so this comparison does not isolate ATR-specific edge from "sell a ~7% implied-prob put
  weekly." A delta-matched banked approximation still favored ATR (PF 1.54 vs 2.09); a clean
  attribution needs fuller strike chains.
- Sensitivity: min-credit floors (0.5/1.0/1.5 pts) don't improve PF or DD; base rule stands
  untouched. Entry bid depth: median 89 contracts, p10 = 10 — 1-lot armable at signal time.

## Caveats

- Sample = 2020→2026 (Value-tier floor). Contains the 2022 bear, Apr-2025 tariff shock, and
  2020 COVID aftermath, but no 2008/Feb-2018-style single-week gap. Structural max loss is
  width − credit, up to ~$5,000/lot observed; size to that, not to the observed DD (per
  risk-cap-vs-vehicle rule).
- Implied probs use quote mids at one minute of the week; strategy P&L uses honest bid/ask
  fills, so the sleeve result does not depend on the mid convention.
- SPXW PM settlement approximated by SPX closing print (same value in practice).

## Codex audit (2026-08-12, gpt-5.6-sol xhigh) — `ATR_OPTIONS_MISPRICING_CODEX_AUDIT.md`

Strategy result reproduced exactly (PF 2.086, 0 negative years); point-in-time integrity,
settlement (306/308 exact Cboe matches), strike rounding, and 5-trade hand reconciliation all
CONFIRMED. Deploy verdict: **probe size, 50-wide**. Corrections it forced (applied above):

- Tight 5-point digital NOT sellable at executable prices — the +3.1pt gap exists at mids
  only; seller-side crossing turns it negative. The 50-wide sleeve result is unaffected (it
  uses honest fills), but the "executable digital mispricing" framing is dead.
- Four full-width losers (not zero); size to ~$5,000/lot.
- Width sweep: structural-risk efficiency peaks at 50, not 75 (75 only wins if observed DD is
  the denominator). Feb-2018/2008 analogs: the extra 25 points of a 75-wide become extra loss,
  not protection. First probe should be 50-wide.
- Snapshot sensitivity: PF 2.09 (10:00) vs ~2.29 (09:58 / 10:02); profitable and 0 negative
  years at all three.
- "Positive gap every year" is thin: one extra realized event flips 2021/2023; simultaneous
  10-cell lower bound crosses zero. But the trade-level read holds: realized 4.67% vs implied
  7.7%, binomial p = 0.021; paired-gap bootstrap CI [+0.68, +5.30] pts.
- Loss anatomy: 14/15 losers are intraday grind-through (not overnight gaps); week-max VIX
  (median 29 in losers vs 21.5 in winners) is more diagnostic than entry VIX. Tail weeks are
  46% of loss dollars.

## Pro-tier backfill: 2012-06 → 2020-04 (2026-08-14)

Pedro upgraded ThetaData to Pro (options history floor 2012-06-01). Pulled the same
Monday-10:00 SPXW level strikes for 413 additional weeks (63 skipped — no SPXW Friday
expiration, mostly pre-2016 third-Friday weeks). Levels from spliced SPX daily
(Yahoo 2011→2019-11, matches Cboe file to the penny on 30 overlap days; `spx_eod_full.csv`,
`spx_weekly_levels_full.csv`). Same honest fills, same sim code
(`sim_put_spread_backfill.py`, `trades_*_backfill.csv`, +11,081 contract-days in DB).

| Structure, 2012-06→2020-04 | n | win | PF | total P&L | maxDD |
|---|---|---|---|---|---|
| ATR −1.0, 50-wide | 339 | 93.5% | **0.91** | **−$5,512** | **$25,373** |
| ATR −1.0, 25-wide | 333 | 93.1% | 0.99 | −$232 | $15,659 |
| ATR −0.786, 50-wide | 344 | 89.2% | 1.00 | −$286 | $25,473 |
| Control fixed −2.74%, 50-wide | 331 | 94.6% | 1.12 | +$5,705 | $23,530 |

- **The 2020-05→2026 result does not extend backward.** Backfill PF 0.91 vs 2.09;
  22 losers in 339 (8 in 2018 alone, −$24,172 that year). MaxDD $25,373 = 4.4× the
  published $5,815. Negative years: 2014, 2018, 2020-partial.
- **The COVID crash itself was NOT the worst stretch**: Jan–Apr 2020 = 16 trades,
  2 losers (wks of 2020-02-24 −$3,143, 2020-03-16 −$3,333), −$1,400 net. Crash-sized
  credits (18.6 / 16.7 pts vs 1.96 avg) cushioned the strikes ATR lag left too close.
  2018 (ATR lag at Volmageddon + Q4, 8 losers) was the expensive regime.
- **ATR-scaling advantage flips sign pre-2020**: control beats ATR (PF 1.12 vs 0.91).
  The "vol scaling is the differential edge" read is a 2020+ phenomenon.
- Structural read: avg credit 1.96 pts backfill vs 2.61 pts 2020+; the −1ATR
  implied-overpricing gap looks like a post-COVID feature, not a permanent one.
- Settlement spot checks vs known SPX closes exact (2016-01-08 = 1922.03,
  2018-12-21 = 2416.62). Pre-2019-12 settles use Yahoo ^GSPC close.
- Verdict framing per recalibration: the 2020-05→2026 sample (PF 2.09, 2026 YTD 29/29)
  remains true and recent-window-weighted; the backfill shows regime dependence.
  Deploy/kill decision is Pedro's. Candidate follow-ups: mispricing-map recompute on
  backfill years (was the −1ATR gap ever positive pre-2020?), VIX-floor entry gate.

## Variant sweep (2026-08-14): ATR-scaled wings, deeper short, entry-regime filters

Pulled deep fibs (−1.236/−1.618/−1.786 ATR, +1,090 contract-days) and ran three
structures × {VIX grid, gap-skip} × {backfill 2012-20, modern 2020-26}
(`sim_variants.py`, `trades_variant_*.csv`). VIX = Monday open, spliced Yahoo+Cboe.
Gap-skip = skip when Monday SPX open < weekly put trigger (prev_close − 0.236 ATR).

PF by cell (backfill / modern / combined; n combined):

| Structure | no filter | + gap-skip |
|---|---|---|
| w50 (short −1.0, wing K−50) | 0.91 / 2.09 / 1.36 (660) | **1.02 / 2.24 / 1.45** (630) |
| w1618 (short −1.0, wing −1.618 ATR) | 0.91 / 2.49 / 1.67 (658) | 0.94 / 2.91 / 1.77 (625) |
| v1236 (short −1.236, wing −1.786 ATR) | 0.71 / 2.79 / 1.56 (638) | 0.84 / **4.43** / 1.88 (607) |

- **ATR-scaled wings don't fix pre-2020** (backfill PF ≈ unchanged 0.91) but improve the
  modern era: w1618 PF 2.49, +$72,049, $11,497/yr — on ~$9.2k avg structural risk/lot
  (avg width 92 pts modern), so per-risk efficiency ≈ the 50-wide. Width auto-scales with
  vol (34 pts avg backfill, 92 modern).
- **Deeper short (v1236) is worse pre-2020** (PF 0.71 — credits avg 1.09 pts, commission
  drag) and better post-2020 (PF 2.79, 98.4% win). Modern + gap-skip: PF 4.43, 99.0% win,
  maxDD $6,321 — but that cell has only 3 losers left; small-n.
- **Gap-skip is the one monotone improver**: better PF in all 6 structure×period cells,
  flips base backfill positive (0.91→1.02), costs ~4.5% of trades. Skipped weeks lose
  ~5× base rate (3/9 backfill skips were losers). Mechanically sensible: don't sell the
  level after price has already gapped through the trigger. Each cell's gain rests on
  2–4 avoided losers.
- **VIX gate is non-monotone pre-2020**: both tails positive (vix<15 PF 1.10 n=193;
  vix>20 PF 1.02 n=44) with the 15–25 band holding the losses; modern is fine everywhere.
  No clean threshold; treat as descriptive, not a gate.

## Touch-stop test (2026-08-14): close spread when price reaches −1 ATR

Stop timing from ES 1-min (daily-calibrated to SPX close; measurement approximation —
live signal is SPX itself). 97 of 660 trades (14.7%) touched post-entry. Exit = first
quote ≤10 min after touch (overnight touches → next open), buy short at ask / sell wing
at bid, second $2.64 commission. 286/286 exit quotes found (`stop_touches.csv`,
`trades_variant_*_stop.csv`, stopq table).

| w1618, PF / P&L / maxDD | hold to settle | with stop | stop + gap-skip |
|---|---|---|---|
| backfill 12-20 | 0.91 / −$4,761 / $20,678 | 1.11 / +$3,976 / $6,851 | 1.13 / +$4,001 / $6,776 |
| modern 20-26 | 2.49 / +$72,049 / $9,173 | 1.75 / +$41,715 / $5,204 | 1.90 / +$38,600 / $4,299 |
| combined | 1.67 / +$67,288 / $20,678 | 1.50 / +$45,691 / $6,851 | 1.58 / +$42,600 / $6,776 |

- **The stop is a regime-robustness transformer**: flips the broken pre-2020 era positive
  (w50: −$5,512 → +$3,650) and cuts combined maxDD 67-73% ($25.4k → $6.8k on w50), at the
  cost of ~40% of modern-era P&L (w1618 $11.5k/yr → $6.7k/yr).
- Anatomy (w1618): of 97 stopped, 38 would have lost holding (−$100,964 → −$33,966 stopped;
  saves $67k) and 59 would have recovered (+$33,399 → −$55,197; whipsaw cost $89k modern-weighted).
  Win rate drops 94% → 86-88% (whipsaws become ~−$850 avg losses instead of full-width).
- P&L-per-maxDD-dollar roughly doubles across the full 14 yrs (0.23 → 0.47/yr per $DD, w1618).
- Both eras positive with the stop — the only configuration tested so far with that property.
- Caveats: stop exactly at the short-strike level is the tightest choice (max whipsaw);
  deeper stops (mid-way to wing) untested. ES-basis timing noise ±few points. Gap-through
  opens still exit at the gapped price — stop caps typical loss, not overnight tail.

## Stop-depth sweep + correction (2026-08-14, w1618 + gap-skip)

Recomputed touch list from the w1618 trade list itself (102 fib-1.0 touches vs 97 from
the earlier w50-derived list) — **corrected stop −1.0 numbers**: backfill PF 1.05/+$1,758/
DD $9,019 (was 1.13/+$4,001/$6,776); modern PF 1.76/+$35,225 (was 1.90/+$38,600). 2018
(−$2,238) and COVID (+$5,036, 0 stops) figures unchanged. Stop results carry ~±$2-4k
sensitivity to touch-list derivation. Canonical trades:
`trades_w1618_gapskip_stop10_corrected.csv`; sweep data `stop_depth_touches.csv`.

Sweep (stop at −f × ATR, combined 2012→2026 PF / backfill PF): 1.0 → 1.47/1.05;
1.118 → 1.77/1.40; 1.236 → 1.68/1.16; 1.382 → 1.85/1.05; 1.5 → 1.88/1.13; none → 1.77/0.94.

- **The stop's benefit is robust across depths** (all five cut 14-yr DD from $18.5k to
  $7-12k and lift backfill above water); the exact depth is NOT identifiable — each row
  rides on 23-82 stopped trades and differences are noise-level.
- −1.118's backfill PF 1.40 is an isolated spike (neighbors 1.05/1.16) — parameter
  island, do not select it.
- Thread preview + charts updated to corrected numbers.

## Richness conditioning (2026-08-14): the hypothesis inverted

Computed Monday ~10:00 implied digital P(settle < K) at the −1 ATR strike from K/K−5
mids for 658/660 weeks (`implied_digital_atr100.csv`).

- **Implied level is nearly identical across eras** (mean 7.9% backfill vs 7.6% modern) —
  the market charged the same; realized frequency is what differed. A fixed richness
  threshold cannot sit out the pre-2020 era.
- **"Sell when implied is high" is backwards**: implied ≥ 7.5% weeks lose pre-2020
  (PF 0.75, −$12,126 of the era's losses) — high implied ≈ high true conditional risk,
  not overpricing. The implied digital is a risk gauge, not a richness signal.
- **Calm filter works walk-forward** (sell iff implied < trailing 52-wk median, no fitted
  constant, PIT at every step), w1618 hold-to-settle: combined PF 2.07, 97.4% win,
  maxDD $4,080, but only ~$1,181/yr — keeps 48% of weeks and ~26% of the dollars.
  Backfill ≈ breakeven (−$857), modern PF 3.58/DD $2,709.
- Two coherent philosophies now on the table: (A) trade everything + defend
  (wing/gap-skip/stop, ~$2,600/yr, DD $9k, 3 rules) vs (B) trade only calm weeks,
  hold to settle (wing + calm filter, ~$1,200/yr, DD $4k, 2 rules, no intraweek
  management). The modern-era dollars live in risky weeks; only (A) collects them.
- True fair-value richness (implied minus a vol-conditional physical estimate) untested —
  needs a conditional breach model; parked.

## Cheap-calls buy-side test (2026-08-14): profitable raw, but it's all beta

Long calls at all five up-levels (naked + 25/50-wide debit verticals), honest ask/bid fills,
hold to settle, 2012-06→2026, ~650 weeks per level (no new pulls — mirrored call strikes were
in both pull plans). Raw results look spectacular (naked +0.236 ATR: +$73,581 backfill,
+$119,614 modern; every level PF > 1 in both eras). **Delta-matched futures control**
(delta proxied by the traded K/K+5 digital, applied to the same weeks' SPX moves):

- Alpha = call P&L minus beta control is NEGATIVE at every level in both eras except
  +1.0 ATR modern (+$6,710, t = 0.3 — noise). Worst: +0.236 ATR modern −$114,812
  (−$353/trade, t = −2.3). A delta-matched futures position beat the calls everywhere.
- Read: the mid-quote cheapness is real but roughly cancels the crossing cost — net, a
  weekly OTM call is a fair-priced-to-expensive way to hold beta. The 2012-2026 bull
  market made the raw P&L; the option added nothing.
- Consistent with and extends the 08-12 audit's "calls not buyable" verdict (which covered
  only the 5-wide digital). PARK buy-side; "don't sell calls" still stands.
- Pairing rationale also weak: the put sleeve doesn't lose in melt-ups, so long calls
  hedge nothing the book actually has.

## Codex direction consult (2026-08-14, gpt-5.6-sol xhigh) — `ATR_PCS_DIRECTION_CODEX_OPINION.md`

**Verdict: NDX/RUT cross-index replication first, with the stop repaired; do not deploy A
on current numbers; B (calm filter) is clean and can paper immediately.** Key findings:

- **CRITICAL — stop fills not armable**: ES 1-min bars are stamped at interval START, so a
  bar's low is only observable at minute-end, while the exit used the option quote AT that
  same stamp — exit sometimes precedes the trigger's observability. Minimal correction
  (first quote strictly after the touch minute): config A falls from PF 1.47/+$36,984/DD
  $9,019 to **PF 1.20/+$18,974/DD $12,492** combined; backfill flips negative
  (**PF 0.92, −$2,847**); 3 of 5 stop depths become backfill-negative. A's "both eras
  positive" claim is dead pending an armable rerun (native SPX intraday timing + strictly
  subsequent quotes).
- **HIGH — same-day ES/SPX basis calibration is lookahead**: causal (prior-session) basis
  changes 13 touch classifications and 68 touch times. Not harmless noise.
- Gap-skip nearly redundant once the corrected stop exists (adds ~$145 same-minute; costs
  ~$2,475 under causal fills) — drop unless forward fills earn it.
- **B (calm filter) reproduces exactly and is causal** (shifted trailing median, 26-obs
  warmup); hygiene: 4 nonpositive digitals auto-"calm" — excluding them PF 2.01, same DD.
  For sizing, budget half the profit rate and twice the DD.
- Fixed-50 + calm/hold flagged as the scale-appropriate expression: PF 1.63, +$9,844,
  DD $4,080, max risk ~$5k/lot (vs −1.618 wing recently ~$11-15k/lot structural).
- MEDIUM — stop/calm generation code not checked in; write one end-to-end runner before
  publishing another statistic. Splice itself verified clean.
- Thread preview marked HOLD (banner) — posts 10-12 stale pending rerun.

## Ladder candidate (2026-08-15): calm / mildly-hot / very-hot tiers

Pedro's question: instead of skipping elevated-implied weeks, step the short strike down.
Tested with existing data (`sim_ladder.py`, no new pulls):

- Naive version (all hot weeks → short −1.236/wing −1.786) FAILS pre-2020: PF 0.68,
  −$10,396 — worse than the −1.0 structure in the same weeks (PF 0.78). Stale-ATR weeks
  mismeasure every strike equally; crash onsets outrun any reachable strike.
- **Graded version works in both eras**: implied < trailing 52wk median → sell −1.0/−1.618;
  median → 75th pct → sell −1.236/−1.786; > 75th pct → sit out.
  Mildly-hot tier: backfill PF 1.54 (+$2,072, DD $2,090), modern PF 7.96 (98.9% win of 87,
  +$15,028). Roughly doubles strategy B's dollars (~$33k vs $15.7k over 14 yrs).
- **Bias acknowledgment**: this is the Nth look at the same 14 years; the p75 boundary was
  chosen after seeing the split, and the modern mild-hot cell has 1 loser in 87 trades.
  Frozen as "ladder v1" (median + p75, one step, no further knobs); judged by NDX/RUT
  replication and forward tracking, not by more variants on this dataset.

## SPY benchmark (2026-08-15): equal capital, honest framing

Buy-and-hold SPY (dividends incl.) vs strategy B from the first calm trade (2013-04-05).
Capital = largest single-trade risk ($14,955, the only implementable equal-capital basis —
capital = first-trade risk of $1,940 goes negative at the 2018 trough, DD 210%).
SPY: 6.27x, 14.7%/yr CAGR, −33.7% maxDD. Strategy B: 2.05x, 5.5%/yr (≈6.6% with T-bills
on idle cash), maxDD 27% of capital. **SPY wins raw return decisively** — B is a low-beta
income sleeve, not an equity substitute; never present it as beating buy-and-hold.
Chart: `chart4_spy_vs_calm.png`; SPY series `spy_adjclose_2012_2026.csv`.

## NDX/RUT cross-index replication (2026-08-15) — the decision gate

Frozen rules, zero per-index tuning (`ndxrut_replicate.py`, `trades_replication_{ndx,rut}.csv`,
`ndxrut_quotes.sqlite`, 5,542 quotes, 0 failed pulls). Same level convention; strikes snapped
to each expiration's listed chain; implied digital from adjacent listed strikes; PM-settled
roots preferred (NDXP 2018+/RUTW 2016+, base roots for earlier weeklies); third-Friday
AM-settled weeks skipped (NDX 153 / RUT 147 skips). Honest fills, hold to settle.

| PF (backfill / modern) | NDX | RUT |
|---|---|---|
| hold −1.0/−1.618 | 0.97 / 2.79 (+$194,310) | 0.66 / 2.10 (+$24,829) |
| B: calm filter | **1.41 / 7.61** (+$2,447 / +$47,501) | 0.50 / 1.02 (≈$0) |
| ladder (calm+mild) | **2.06 / 8.75** (+$8,662 / +$81,812) | 0.35 / 1.91 |

- **NDX: clean transfer.** Same signature as SPX (flat-to-dead pre-2020, strong after), and
  the calm filter + ladder rescue the backfill era on an index they were never fitted to —
  the mild-tier finding replicates. Dollar figures are ~4-5× SPX per lot (index scale);
  PF is the comparable number. NDX maxDD large on unfiltered hold ($33-40k/lot) — filters
  cut it to $5-10k.
- **RUT: the filter does not transfer.** Modern-era raw structure works (hold PF 2.10) but
  the calm filter removes the profitable weeks (modern PF 1.02) and everything is negative
  pre-2020. The implied-digital gauge appears unreliable on RUT (wider relative spreads /
  coarser adjacent-strike digitals on a ~2,000 index), or small-cap put flow simply differs.
- Read: the edge and its calm-week conditioning are a **large-cap index phenomenon**
  (SPX + NDX), not universal premium selling. Partial confirmation — better than
  SPX-only, not a clean sweep. Modern NDX PF 7.61/8.75 rest on 1-2 losers; the meaningful
  replication signal is the backfill flipping positive (PF 1.41/2.06) out-of-family.
- Per the Codex gate: transfer is mixed → B advances to paper/probe on SPX (NDX optional
  second sleeve); RUT is out. Deploy decision Pedro's.

## Next

- Monthly variant (same pipeline, monthly ATR levels + monthly expirations) — queued.
- Buy-side test of the cheap call wings.
- Early-management overlays (exit at 50% credit, touch-based defense) — only if Pedro wants;
  hold-to-settle already clears the bar.
- Paper/probe deployment decision is Pedro's. Mechanics fit the existing bilbo paper-trader
  ThetaData snapshot flow (same endpoints, Value tier suffices).
