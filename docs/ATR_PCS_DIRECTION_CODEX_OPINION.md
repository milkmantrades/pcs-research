# Independent direction opinion — ATR put-credit-spread sleeve

**Date:** 2026-08-14  
**Bottom line:** Do **NDX/RUT cross-index replication first**, with A's stop repaired to use native-index timing and the first *strictly subsequent* executable option quote. Do not put SPX money behind A as currently reported. B is the cleaner candidate and can paper immediately, but the cheapest high-value next fact is whether either frozen expression transfers to another index without rescue tuning.

## Adversarial findings

1. **Critical — A's stop fills are not armable.** `stop_depth_touches.csv` identifies a breach from a FirstRate ES one-minute bar and `stopq` prices the exit with the option quote carrying that same minute stamp. FirstRate bars are [stamped at the interval start](https://tools.firstratedata.com/), so the bar low is only known after that minute; [ThetaData's interval quote](https://docs.thetadata.us/operations/option_history_quote.html) is the quote at the timestamp. The exit therefore sometimes precedes the information that triggers it. I reproduced `trades_w1618_gapskip_stop10_corrected.csv` exactly, then used the first quote strictly after the touch minute. A changes from **PF 1.47 / +$36,984 / $9,019 DD** to **PF 1.20 / +$18,974 / $12,492 DD** combined. Backfill changes from **PF 1.05 / +$1,758** to **PF 0.92 / -$2,847**. Three of five stop depths become backfill-negative. Rerun from SPX tick/one-second prices and raw/tick option NBBO, exiting strictly after trigger observability and checking size for the intended 1–5 lots.

2. **High — same-day ES/SPX close calibration is real lookahead, not harmless noise.** A reconstruction using additive daily basis matched 101/102 saved -1.0 touch classifications. Replacing the future same-day closing basis with the last known prior-session basis changed 13 touch classifications and changed 68 common touch times. That is material beside a backfill profit of only $1,758. Native SPX intraday history eliminates the issue; until that rerun, do not describe the stop as ES-timed “measurement noise.” Ratio-adjusted continuous ES is also the wrong instrument for precise multi-year cash-index crossing without a causal basis series.

3. **Medium — stop and calm-filter generation code is absent.** `sim_variants.py` and `sim_put_spread_backfill.py` reproduce the entry/settlement studies, but neither generates `stop_depth_touches.csv`, `stopq`, the corrected stop trades, or the rolling-median filter. The artifacts are internally reconstructable, but the published additions are not end-to-end reproducible. Check in one runner with the time convention, basis formula, overnight rule, quote-selection rule, commissions, and minimum quote sizes explicit before another public statistic.

4. **Low/clean — the backfill splice itself did not produce a numerical landmine.** `spx_eod_full.csv` has no duplicates, nulls, or invalid OHLC rows; the Cboe portion is identical to `gex/SPX_eod.csv`; and I regenerated `spx_weekly_levels_full.csv` to floating-point tolerance. The 2011 start supplies ample ATR warmup before June 2012. The raw Yahoo splice-building script/cache is not retained, so the claimed 30-day Yahoo/Cboe overlap is a provenance gap, not a detected bias.

5. **Qualified clean — B is causal and its headline reproduces exactly.** The actual rule is current implied digital below the **shifted** median of the prior 52 available observations, starting after 26 observations. It gives 302 trades, PF 2.069, +$15,746.73, $4,079.63 DD; backfill -$856.99 and modern PF 3.576. It is not lookahead. Four implied digitals are nonpositive quote-noise artifacts and are automatically labeled “calm”; excluding them still gives PF 2.01 and the same DD, so this is hygiene rather than invalidation. Document the 26-observation warmup and reject/repair non-monotone digitals live.

## Rescue/selection read

A is mechanically intelligible, not a 20-parameter monstrosity, but the evidence has not earned the package. The wing, gap rule, and stop were all selected after seeing the failures, and the gap rule is nearly redundant once the corrected stop is present: on the reported same-minute basis it adds only **$145** combined and reduces all-history DD by **$75**; under strictly later fills it costs about **$2,475** and improves DD by only about **$596**. Drop it unless forward fills establish a benefit. The -1.618 wing improves modern dollars largely by taking more width risk, not by improving pre-2020 behavior.

For A, use the armable rerun above rather than applying a subjective discount: it is already a **49% P&L haircut and 39% DD increase**, before fixing ES basis. For B, the historical figures are valid but same-session selected; for sizing I would budget **half the observed profit rate and twice observed DD**, not because the expression should be killed, but because the backfill is still slightly negative and only eight losses determine PF. Yes, given the cheap pipeline and the public/reputational context, I would require fresh cross-index evidence before live SPX-risk deployment. Paper trading is not blocked.

## Direction ranking

1. **NDX/RUT replication first** — freeze A and B, prohibit index-specific retuning, and use causal native-index stop timing.
2. **Paper both / let the sleeves vote** — especially collect trigger-to-fill slippage and size; paper can run while replication runs.
3. **Deploy B at probe size** only after the above; XSP/SPY-sized risk is preferable to one SPX lot.
4. **Fair-value richness model** — scientifically better than raw implied level, but only if it remains a simple PIT score.
5. **Long cheap calls test** — a separate opportunity; use buyer-side crossing and wider structures.
6. **Monthly-tenor variant** — useful diversification, lower decision value than transfer/fill evidence now.
7. **Deploy A at probe size** — last until the stop rerun is armable.

One additional scale point materially changes the choice: current -1.618-wing trades have recently averaged roughly **$11,000 structural risk and reached about $15,000 per SPX lot**; neither a stop nor a $4,000 observed DD caps overnight loss. The already-banked **fixed-50 + calm/hold** expression is worth carrying into the replication as the simplicity/risk control: PF 1.63, +$9,844, $4,080 DD, backfill +$723, and maximum risk about $5,000. It earns less, but it fits Pedro's scale and simplicity constraint far better than using a three-times-larger wing to manufacture more dollars.

## Primary recommendation

Run the NDX/RUT replication now and make it the decision gate. It directly answers whether the rescued behavior is an SPX-era artifact, costs little relative to waiting for a long forward sample, and prevents more same-dataset variants from obscuring the choice. Freeze B and a causally repaired A before the run; include fixed-50 calm as the risk-control comparator, not as another optimization grid. In parallel, paper both to measure actual stop latency and spread execution. If transfer is mixed but B's paper fills behave, B—not A—is the only expression I would advance to a tiny XSP/SPY probe.
