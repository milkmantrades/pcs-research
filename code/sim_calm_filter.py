#!/usr/bin/env python3
"""Strategy B: calm-filter put credit spread (the audit-clean expression).

Signal: Monday ~10:00 ET implied digital P(settle < K) at the -1 ATR strike,
computed from K / K-5 put mids: (mid(K) - mid(K-5)) / 5.
Rule:   sell the spread ONLY when the implied digital is below the trailing
        52-week median of prior readings (shifted -- current week excluded;
        minimum 26 observations). No stop, no gap rule; hold to settlement.

Outputs implied_digital_atr100.csv and prints era stats for the fixed-50 and
-1.618-ATR-wing structures. Trade legs/fills come from the trades_variant_*.csv
files produced by sim_variants.py.

Known hygiene (Codex audit 2026-08-14): a handful of nonpositive implied
digitals are quote-noise; they auto-classify as "calm". Excluding them changes
PF 2.07 -> 2.01 on the w1618 structure, same maxDD. Reject non-monotone
digitals in any live implementation.
"""
import sqlite3
import numpy as np
import pandas as pd

DIR = "data"
SEAM = "2020-05-01"


def load_quote_mids():
    con = sqlite3.connect(f"{DIR}/level_quotes.sqlite")
    q = pd.read_sql_query("SELECT * FROM q WHERE right='P'", con)
    con.close()
    q["ts"] = pd.to_datetime(q.ts)
    q = q[q.ts.dt.time <= pd.Timestamp("10:00:00").time()]
    q["mid"] = (q.bid + q.ask) / 2
    return (q.sort_values("ts")
             .groupby(["entry_date", "expiration", "strike"]).last().reset_index())


def implied_digitals():
    """Implied digital per week at the -1 ATR strike (from the w50 trade list)."""
    qq = load_quote_mids()
    tr = pd.read_csv(f"{DIR}/trades_variant_w50.csv", parse_dates=["week_end", "entry"])
    tr["entry_d"] = tr.entry.dt.strftime("%Y-%m-%d")
    rows = []
    for t in tr.itertuples():
        a = qq[(qq.entry_date == t.entry_d) & (qq.strike == float(t.short_k))]
        b = qq[(qq.entry_date == t.entry_d) & (qq.strike == float(t.short_k) - 5)]
        if len(a) and len(b):
            rows.append({"entry_d": t.entry_d, "week_end": t.week_end,
                         "implied": (a.mid.iloc[0] - b.mid.iloc[0]) / 5.0})
    imp = pd.DataFrame(rows).sort_values("week_end")
    imp["med52"] = imp.implied.rolling(52, min_periods=26).median().shift(1)
    imp.to_csv(f"{DIR}/implied_digital_atr100.csv", index=False)
    return imp


def report(df, col, tag, era):
    g = df.loc[df[col] > 0, col].sum()
    l = -df.loc[df[col] < 0, col].sum()
    eq = df[col].cumsum()
    dd = -(eq - eq.cummax()).min()
    yrs = max((df.week_end.max() - df.week_end.min()).days / 365.25, 0.1)
    print(f"  {tag:<11s} n={len(df):3d}  win={(df[col] > 0).mean():5.1%}  "
          f"PF={g / l if l > 0 else np.inf:5.2f}  P&L=${df[col].sum():>8,.0f}  "
          f"${df[col].sum() / yrs:>6,.0f}/yr  maxDD=${dd:>7,.0f}  [{era}]")


def main():
    imp = implied_digitals()
    for fname, label in [("trades_variant_w50.csv", "w50 (fixed 50-wide)"),
                         ("trades_variant_w1618.csv", "w1618 (-1.618 ATR wing)")]:
        tr = pd.read_csv(f"{DIR}/{fname}", parse_dates=["week_end", "entry"])
        tr["entry_d"] = tr.entry.dt.strftime("%Y-%m-%d")
        d = tr.merge(imp[["entry_d", "implied", "med52"]], on="entry_d").dropna(subset=["med52"])
        d["calm"] = d.implied < d.med52
        print(f"===== {label}: sell iff implied < trailing 52wk median =====")
        for era, mask in [("backfill", d.week_end < SEAM),
                          ("modern", d.week_end >= SEAM),
                          ("combined", pd.Series(True, index=d.index))]:
            report(d[mask], "pnl", "unfiltered", era)
            report(d[mask & d.calm], "pnl", "calm only", era)
        print()


if __name__ == "__main__":
    main()
