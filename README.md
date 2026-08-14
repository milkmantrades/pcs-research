# PCS Research — Weekly SPX Put Credit Spread at the −1 ATR Level

Research code and data for a weekly SPX options strategy built on Saty Mahajan's ATR
Levels framework. Sell a Friday-expiry SPXW put credit spread at the weekly −1 ATR
level, Monday ~10:00 ET, hold to cash settlement.

**Status: research candidate. Nothing here is deployed or investment advice.**
The full history of what worked, what failed, and what an independent audit corrected
is in `docs/` — read it before trusting any number in this repo.

## The story so far

1. Original study (May 2020 → Aug 2026 sample): PF 2.09, 95.3% win, no losing year.
2. Public critique: the sample started right after the COVID crash (data-vendor floor).
3. Backfill to June 2012 (ThetaData Pro): the same rules were NOT profitable pre-2020
   (PF 0.91, max drawdown 4.4× larger). 2018 — not COVID — was the worst stretch.
4. Rescue variants tested: ATR-scaled wing, gap-skip filter, touch stop. An independent
   Codex audit then found a 1-minute lookahead in the stop simulation — the stopped
   configs' numbers are stale pending an armable rerun (`docs/ATR_PCS_DIRECTION_CODEX_OPINION.md`).
5. The surviving audit-clean expression ("B"): trade only when the Monday implied
   digital at the strike is below its trailing 52-week median, hold to settle, no
   intraweek management. 2012–2026: PF 2.07, 97.4% win of 302 trades, maxDD $4,080,
   ~$1,181/yr per 1-lot. Pre-2020 roughly flat; post-2020 PF 3.58.

## Repo layout

- `code/` — data pulls (ThetaData v3 terminal on `localhost:25503`), physical
  probabilities, mispricing map, and all strategy simulations. Honest fills throughout:
  sell at bid, buy at ask, $2.64 commission per spread.
- `data/` — derived datasets: weekly ATR levels, spliced SPX daily OHLC, per-trade
  results for every variant, implied digital series, stop touch times, implied-vs-physical
  map. These are transformations, not raw vendor data.
- `docs/` — findings report (all study sections, including corrections) and both
  independent Codex audits.
- `charts/` — equity-curve charts from the public write-up.

## What is deliberately NOT here

`level_quotes.sqlite` (~27MB of raw SPXW 1-minute NBBO quotes) is excluded: raw vendor
market data cannot be redistributed under ThetaData's license. To rebuild it, run the
`pull_*.py` scripts against your own ThetaData subscription (options history to 2012-06
requires the Pro tier); the scripts are resumable and re-create the database exactly.
The ES 1-minute file used for stop timing (FirstRate) is likewise licensed and excluded.

## Known limitations

- Stop-based variants: exit timing had a 1-minute observability bug (see audit); treat
  all `*_stop*` trade files as upper bounds until the causal rerun lands.
- Sample floor is 2012-06 (SPXW weekly history). No 2008, no Feb-2018-style single-week
  gap beyond what 2018 Q4 provides. 63 pre-2016 weeks have no Friday SPXW expiration.
- Every filter beyond the base rule was chosen after seeing historical results. Forward
  paper performance is the arbiter, not these backtests.

## Credit

ATR Levels framework by Saty Mahajan. Critique that triggered the backfill:
@Ragnar_roundt, @anawan1, and others on X.
