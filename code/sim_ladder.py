#!/usr/bin/env python3
"""Ladder candidate v1: calm / mildly-hot / very-hot tiers.

Tiers by the Monday implied digital at the -1 ATR strike vs its trailing
52-week distribution (both boundaries shifted -- prior weeks only):
  implied < trailing median          -> sell -1.0 ATR / wing -1.618 (strategy B tier)
  median <= implied < trailing p75   -> sell -1.236 ATR / wing -1.786 (step down)
  implied >= trailing p75            -> sit out

BIAS NOTE: the p75 boundary was chosen after seeing the tier split, on the same
14 years examined many times in this study. The modern mildly-hot tier has a
single loser in 87 trades. Treat as a frozen candidate for cross-index
replication and forward tracking, not a validated result.
"""
import numpy as np
import pandas as pd

DIR = "data"
SEAM = "2020-05-01"


def stats(s, tag):
    if len(s) < 5:
        return f"  {tag:<30s} n={len(s)} (thin)"
    g = s.loc[s.pnl > 0, "pnl"].sum()
    l = -s.loc[s.pnl < 0, "pnl"].sum()
    eq = s.pnl.cumsum()
    dd = -(eq - eq.cummax()).min()
    return (f"  {tag:<30s} n={len(s):3d}  win={(s.pnl > 0).mean():5.1%}  "
            f"PF={g / l if l > 0 else np.inf:5.2f}  P&L=${s.pnl.sum():>8,.0f}  "
            f"maxDD=${dd:>7,.0f}")


def main():
    imp = pd.read_csv(f"{DIR}/implied_digital_atr100.csv",
                      parse_dates=["week_end"]).sort_values("week_end")
    if "med52" not in imp:
        imp["med52"] = imp.implied.rolling(52, min_periods=26).median().shift(1)
    imp["p75"] = imp.implied.rolling(52, min_periods=26).quantile(0.75).shift(1)

    def load(fname):
        t = pd.read_csv(f"{DIR}/{fname}", parse_dates=["week_end", "entry"])
        t["entry_d"] = t.entry.dt.strftime("%Y-%m-%d")
        return t.merge(imp[["entry_d", "implied", "med52", "p75"]],
                       on="entry_d").dropna(subset=["med52", "p75"])

    w = load("trades_variant_w1618.csv")   # -1.0 / -1.618
    v = load("trades_variant_v1236.csv")   # -1.236 / -1.786

    calm = w[w.implied < w.med52]
    mild = v[(v.implied >= v.med52) & (v.implied < v.p75)]
    hot_skipped = w[w.implied >= w.p75]

    for era, lo, hi in [("backfill", "2012-01-01", SEAM),
                        ("modern", SEAM, "2027-01-01")]:
        m = lambda d: d[(d.week_end >= lo) & (d.week_end < hi)]
        print(f"[{era}]")
        print(stats(m(calm), "calm tier: -1.0/-1.618"))
        print(stats(m(mild), "mildly-hot tier: -1.236/-1.786"))
        print(f"  {'very-hot tier: SIT OUT':<30s} n={len(m(hot_skipped)):3d}  "
              f"(would-be -1.0 P&L ${m(hot_skipped).pnl.sum():,.0f})")
        both = pd.concat([m(calm), m(mild)])
        print(stats(both, "LADDER total (traded tiers)"))
        print()


if __name__ == "__main__":
    main()
