# Guide for AI agents working in this repo

This is a completed-but-open research study of a weekly SPX put-credit-spread strategy
(short put at the Saty −1 ATR weekly level). It is NOT a production trading system.
Read this file before touching anything.

## Source of truth, in order

1. `docs/ATR_LEVELS_OPTIONS_MISPRICING_FINDINGS.md` — every study section INCLUDING the
   corrections. Later sections amend earlier ones; read the whole file before quoting a number.
2. `docs/ATR_PCS_DIRECTION_CODEX_OPINION.md` — independent audit (2026-08-14). Its stop-fill
   lookahead finding invalidates the headline numbers of every `*_stop*` trade file.
3. `README.md` — the public narrative.
4. Code docstrings.

If a number in one place disagrees with a later correction, the later correction wins.

## The two candidate strategies

- **B (audit-clean, preferred)**: sell only when the Monday implied digital at the strike
  is below its trailing 52-week median; hold to settlement. `code/sim_calm_filter.py`.
- **A (numbers stale)**: ATR-scaled wing + gap-skip + touch stop. The stop simulation has a
  ~1-minute observability lookahead (ES bars are stamped at interval START). Rerun with
  `code/sim_stop_analysis.py --sim --causal` for the corrected lower-bound numbers.

## Data ground rules

- `data/level_quotes.sqlite` is ABSENT on purpose: raw ThetaData quotes cannot be
  redistributed. Rebuild it with your own ThetaData subscription (Pro tier for pre-2020):
  start a local ThetaTerminal v3 on port 25503, then run `code/pull_level_quotes.py`,
  `pull_level_quotes_backfill.py`, `pull_control_quotes*.py`, `pull_deep_wing_quotes.py`.
  All pulls are resumable (a `qdone` table dedups). Place/point the DB at
  `data/level_quotes.sqlite`.
- The ES 1-minute file used for stop timing (FirstRate) is licensed and external; its path
  is a site-specific constant in `sim_stop_analysis.py`.
- Everything in `data/` is derived output and safe to regenerate.

## Conventions (do not silently change these)

- Fills are HONEST: sell at bid, buy at ask. $2.64 commission per spread, $100 multiplier.
- Levels: previous weekly close − fib × prior-week Wilder ATR(14) (`.shift(1)` — the ATR
  window never touches the traded week). Strikes rounded to nearest 5.
- Weeks are W-FRI resampled; entry = first trading day ~10:00 ET; settle = Friday SPX close.
- Timestamps are US/Eastern.
- SEAM = 2020-05-01: weeks before it use `spx_weekly_levels_full.csv` (long-warmup ATR),
  weeks after use the canonical `spx_weekly_levels.csv` (matches the originally published
  sample). Only 6 of 329 overlapping weeks differ in strike; do not "fix" this seam.

## Path quirk

`sim_put_spread.py`, `sim_put_spread_backfill.py`, and `sim_variants.py` are the original
research scripts and carry hardcoded `/root/spy/...` paths (historical artifacts, kept
verbatim). The newer `sim_calm_filter.py`, `sim_stop_analysis.py`, and `sim_long_calls.py`
run from the repo root against `data/`.

## If you extend this research

- Every new expression needs a mechanics-matched baseline control before you believe it.
  Example: `sim_long_calls.py` — raw long calls "made" $100k+ per era until a delta-matched
  futures control showed it was all market beta.
- Report backfill (2012→2020-04) and modern (2020-05→) eras separately, always. The edge is
  regime-dependent; combined-only numbers mislead.
- P&L = frequency × payoff. Report trades/yr and $/yr, not just PF.
- The same 14 years have been examined many times in this study. Prefer new evidence
  (other indices, other tenors, forward paper trades) over more variants on this dataset.
- Known open items: causal stop rerun on native SPX intraday data; NDX/RUT cross-index
  replication (frozen rules, no per-index tuning); monthly-tenor variant.

## Sanity anchors (regenerate to verify your environment)

- `sim_calm_filter.py`: B on w1618 combined ≈ PF 2.07, ~97% win, maxDD ≈ $4,080.
- `sim_stop_analysis.py --sim`: stop −1.0 combined PF 1.47 (published), `--causal` ≈ 1.20.
- `sim_long_calls.py`: alpha negative at every level except +1.0 ATR modern (noise).
