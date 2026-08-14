# Codex Consult — PCS (ATR Put Credit Spread): Direction After the 2012 Backfill

**Date:** 2026-08-14. Requested by Pedro. Working dir `/root/spy`. You have full shell;
run Python against the banked data and re-derive anything you doubt. Write your opinion to
`/root/spy/ATR_PCS_DIRECTION_CODEX_OPINION.md` (that file appearing = done signal).

## What happened since your 2026-08-12 audit

You audited the original study (`ATR_OPTIONS_MISPRICING_CODEX_AUDIT.md`) and confirmed the
2020-05→2026 sleeve (short SPXW put @ −1.0 weekly ATR, wing K−50, Monday ~10:00, hold to
settle: PF 2.09, 95.3% win, maxDD $5,815). Verdict then: probe-deploy at 50-wide.

Today Pedro upgraded ThetaData to Pro (options floor 2012-06-01) after public criticism that
the backtest started right after the COVID crash. We backfilled 2012-06→2020-04 (same code,
honest bid/ask fills) and ran variants. Read, in order:

1. `ATR_LEVELS_OPTIONS_MISPRICING_FINDINGS.md` — sections added today:
   "Pro-tier backfill", "Variant sweep", "Touch-stop test", "Stop-depth sweep + correction",
   "Richness conditioning". These contain all headline numbers.
2. `atr_options_mispricing/sim_variants.py`, `sim_put_spread_backfill.py` — sim code
3. Data: `atr_options_mispricing/level_quotes.sqlite` (q, qdone, stopq tables; ~24k
   contract-days now), `spx_eod_full.csv` + `spx_weekly_levels_full.csv` (spliced Yahoo
   2011→2019-11 + Cboe), `trades_variant_*.csv`, `trades_w1618_gapskip_stop10_corrected.csv`,
   `stop_depth_touches.csv`, `implied_digital_atr100.csv`.
   ES 1-min (stop timing): `/srv/ftp/ossicones/futures-data/ES_full_1min_continuous_ratio_adjusted_through_2026-07-10.txt`.
   ThetaTerminal live on `http://127.0.0.1:25503/v3` (Pro) if you need spot pulls; be gentle.

## Headline results (verify freely)

- Original rules 2012-06→2020-04: PF 0.91, −$5,512/339 trades, maxDD $25,373 (4.4× the
  modern-era DD). 2018 = −$24,172 (8 losers). COVID Jan–Apr 2020 = only −$1,400/16 trades
  (fat crash credits cushioned). Fixed-2.74% control BEAT ATR pre-2020 (PF 1.12 vs 0.91).
- ATR-scaled wing (−1.618) improves modern era (PF 2.49, $11.5k/yr on ~$9.2k width risk),
  does nothing for backfill.
- Gap-skip (skip if Monday opens below −0.236 ATR put trigger): improves all 6
  structure×era cells, costs ~2 trades/yr. COVID: skipped all 5 crash Mondays.
- Touch stop (close at −1 ATR touch; ES-timed, real exit quotes): flips backfill positive,
  cuts 14-yr maxDD to ~$7-12k at every depth 1.0–1.5; exact depth not identifiable
  (23-82 stopped trades per depth; −1.118's backfill PF 1.40 is an isolated spike).
  Corrected canonical config (wing −1.618 + gap-skip + stop −1.0):
  backfill PF 1.05/+$1,758/DD $9,019; modern PF 1.76/+$35,225/DD $4,299; ~$2,600/yr combined.
- Richness conditioning INVERTED: Monday implied digital at the strike is ~equal across eras
  (7.9% vs 7.6%); implied ≥7.5% weeks are the pre-2020 LOSERS (PF 0.75) — implied level is a
  conditional-risk gauge, not richness. Walk-forward calm filter (implied < trailing 52-wk
  median, no fitted constant) on the −1.618-wing structure, hold to settle, no stop/gap-skip:
  combined PF 2.07, 97.4% win, maxDD $4,080, but only ~$1,181/yr (keeps 48% of weeks,
  ~26% of dollars).
- Mispricing map (from the original study, still standing): upside calls persistently cheap
  at mid (but buyer-side crossing kills simple long-call reading).

## Pedro's constraints and stated preferences

- Simplicity is a core value: "every added line in the trading rules needs to truly earn
  its keep." The original's beauty was one rule.
- Rescue-over-rigor repo policy: PARK not CLOSE; forward/paper evidence is the arbiter;
  no preregistration ceremony. But obviously-overfit configs still don't deploy.
- Retail/prop scale (1–5 lots). SPX or SPY/XSP execution. This strategy was published
  publicly on his site and X, including today's mea-culpa thread (backfill disclosed).
- Two candidate philosophies on the table:
  (A) Trade all + defend: wing −1.618, gap-skip, stop −1.0 → ~$2,600/yr, DD ~$9k, 3 rules.
  (B) Calm-only + hold: wing −1.618, implied < trailing median → ~$1,200/yr, DD ~$4k,
      2 rules, zero intraweek management.

## What we want from you

1. **Adversarial pass on today's additions** (lighter than a full audit): any correctness
   or bias landmine in the backfill splice, ES-timed stop simulation (daily basis
   calibration uses same-day close — acceptable measurement noise or a real problem?),
   stop exit fills, or the walk-forward calm filter? Flag anything that would embarrass us.
2. **The in-sample rescue question, honestly**: gap-skip and stop were chosen after seeing
   the backfill losers. Calm filter came from an inverted hypothesis, same session. How
   much should the combined-era numbers be haircut? Is (A) an overfit Frankenstein or a
   defensible mechanical design? Would you demand a fresh holdout (e.g., NDX/RUT
   replication, which is one pipeline run away on this Pro subscription) before any deploy?
3. **Direction ranking**: given Pedro's simplicity constraint and scale, rank what to do
   next among (or beyond): deploy A at probe size / deploy B at probe size / paper both /
   NDX-RUT cross-index replication first / monthly-tenor variant / fair-value richness
   model (implied minus vol-conditional physical) / long cheap calls test / stop here and
   let the paper sleeve vote. Pick ONE primary recommendation and defend it in a paragraph.
4. **Anything we haven't thought of** that materially changes the picture — one page max.

Be blunt. Pedro decides; your job is the strongest possible independent read.
