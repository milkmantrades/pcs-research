#!/usr/bin/env python3
"""Cheap-calls buy-side test with a delta-matched beta control.

Long calls at the five up-levels (naked + 25/50-wide debit verticals), buy at
ask / sell wing at bid, hold to settlement. Raw P&L is positive at every level
in both eras -- but the control shows it is bull-market beta, not option edge:
a delta-matched futures position (delta proxied by the traded K/K+5 digital)
beat the calls everywhere except one noise cell (+1.0 ATR modern, t=0.3).

Conclusion (2026-08-14): PARK the buy side. See FINDINGS "Cheap-calls buy-side
test" section.
"""
import sqlite3
import numpy as np
import pandas as pd

DIR = "data"
MULT = 100.0
FIBS = {"trigger": 0.236, "0382": 0.382, "0618": 0.618, "0786": 0.786, "100": 1.0}


def main():
    con = sqlite3.connect(f"{DIR}/level_quotes.sqlite")
    q = pd.read_sql_query("SELECT * FROM q WHERE right='C'", con)
    con.close()
    q["ts"] = pd.to_datetime(q.ts)
    q = q[q.ts.dt.time <= pd.Timestamp("10:00:00").time()]
    q["mid"] = (q.bid + q.ask) / 2
    q = q.sort_values("ts").groupby(["entry_date", "expiration", "strike"]).last()

    full = pd.read_csv(f"{DIR}/spx_weekly_levels_full.csv", parse_dates=["date"]).set_index("date")
    canon = pd.read_csv(f"{DIR}/spx_weekly_levels.csv", parse_dates=["date"]).set_index("date")
    wk = pd.concat([full[(full.index >= "2012-06-01") & (full.index < "2020-05-01")],
                    canon[canon.index >= "2020-05-01"]])
    daily = pd.read_csv(f"{DIR}/spx_eod_full.csv", parse_dates=["date"]).set_index("date")
    ddates = daily.index
    r5 = lambda x: round(x / 5.0) * 5.0

    prev_end = None
    weeks = []
    for wend, row in wk.iterrows():
        days = ddates[(ddates > (prev_end or wend - pd.Timedelta(days=7))) & (ddates <= wend)]
        prev_end = wend
        if len(days) < 3:
            continue
        weeks.append((wend, days[0], days[-1], row))

    print("Naked long call vs delta-matched futures control:")
    for lname, fib in FIBS.items():
        rows = []
        for wend, eday, sday, row in weeks:
            entry, exp = eday.strftime("%Y-%m-%d"), sday.strftime("%Y-%m-%d")
            settle, s0 = daily.loc[sday, "close"], daily.loc[eday, "open"]
            k = r5(row["prev_close"] + fib * row["atr_prev"])
            try:
                a = q.loc[(entry, exp, float(k))]
                b = q.loc[(entry, exp, float(k + 5))]
            except KeyError:
                continue
            if a["ask"] <= 0:
                continue
            digital = max(0.02, min(0.98, (a["mid"] - b["mid"]) / 5))
            pnl_call = (max(0.0, settle - k) - a["ask"]) * MULT - 1.32
            pnl_beta = digital * (settle - s0) * MULT
            rows.append({"week_end": wend, "call": pnl_call, "beta": pnl_beta,
                         "alpha": pnl_call - pnl_beta})
        d = pd.DataFrame(rows)
        for era, lo, hi in [("backfill", "2012-01-01", "2020-05-01"),
                            ("modern", "2020-05-01", "2027-01-01")]:
            s = d[(d.week_end >= lo) & (d.week_end < hi)]
            t = s.alpha.mean() / (s.alpha.std() / np.sqrt(len(s))) if len(s) > 10 else np.nan
            print(f"  +{fib} ATR [{era:8s}] n={len(s):3d}  call=${s.call.sum():>8,.0f}  "
                  f"beta=${s.beta.sum():>8,.0f}  ALPHA=${s.alpha.sum():>8,.0f} (t={t:4.1f})")


if __name__ == "__main__":
    main()
