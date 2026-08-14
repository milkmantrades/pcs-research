#!/usr/bin/env python3
"""Implied vs physical probability at weekly ATR-level strikes.

Implied P(settle beyond K) from tight verticals at Monday ~10:00 ET mids:
  below: (midP(K) - midP(K-5)) / 5    above: (midC(K) - midC(K+5)) / 5
Realized: Friday settle close vs the SAME strike K (apples-to-apples).
"""
import sqlite3
import pandas as pd
import numpy as np

DIR = "/root/spy/atr_options_mispricing"
FIBS = {"trigger": 0.236, "0382": 0.382, "0618": 0.618, "0786": 0.786, "100": 1.0}


def round5(x):
    return round(x / 5.0) * 5.0


def load_quotes():
    con = sqlite3.connect(f"{DIR}/level_quotes.sqlite")
    q = pd.read_sql_query("SELECT * FROM q", con)
    con.close()
    q["ts"] = pd.to_datetime(q["ts"])
    # last quote at or before 10:00:00
    q = q[q["ts"].dt.time <= pd.Timestamp("10:00:00").time()]
    q = q.sort_values("ts").groupby(
        ["entry_date", "expiration", "strike", "right"]).last().reset_index()
    q["mid"] = (q["bid"] + q["ask"]) / 2.0
    return q.set_index(["entry_date", "expiration", "strike", "right"])


def main():
    wk = pd.read_csv(f"{DIR}/spx_weekly_levels.csv", parse_dates=["date"]).set_index("date")
    daily = pd.read_csv("/root/spy/gex/SPX_eod.csv", parse_dates=["date"])
    ddates = daily["date"]
    dclose = daily.set_index("date")["close"]
    quotes = load_quotes()

    rows = []
    prev_end = None
    for wend, row in wk.iterrows():
        days = ddates[(ddates > (prev_end or wend - pd.Timedelta(days=7)))
                      & (ddates <= wend)]
        prev_end = wend
        if len(days) < 3:
            continue
        entry = days.iloc[0].strftime("%Y-%m-%d")
        settle_day = days.iloc[-1]
        exp = settle_day.strftime("%Y-%m-%d")
        settle = dclose.loc[settle_day]
        for name, fib in FIBS.items():
            for side in ("dn", "up"):
                if side == "dn":
                    level = row["prev_close"] - fib * row["atr_prev"]
                    k = round5(level)
                    right, k2 = "P", k - 5
                else:
                    level = row["prev_close"] + fib * row["atr_prev"]
                    k = round5(level)
                    right, k2 = "C", k + 5
                try:
                    m1 = quotes.loc[(entry, exp, k, right)]
                    m2 = quotes.loc[(entry, exp, k2, right)]
                except KeyError:
                    continue
                if m1["bid"] <= 0 and m1["ask"] <= 0:
                    continue
                imp = (m1["mid"] - m2["mid"]) / 5.0
                if side == "dn":
                    realized = 1.0 if settle < k - 2.5 else 0.0
                else:
                    realized = 1.0 if settle > k + 2.5 else 0.0
                rows.append({
                    "week_end": wend, "entry": entry, "exp": exp, "level": name,
                    "side": side, "strike": k, "spot_ref": row["prev_close"],
                    "implied": imp, "realized": realized, "settle": settle,
                    "short_mid": m1["mid"], "short_bid": m1["bid"],
                    "short_ask": m1["ask"],
                })

    df = pd.DataFrame(rows)
    df.to_csv(f"{DIR}/implied_vs_physical.csv", index=False)
    df["year"] = pd.to_datetime(df["week_end"]).dt.year

    def agg(d):
        return pd.Series({
            "n": len(d),
            "implied": d["implied"].mean(),
            "realized": d["realized"].mean(),
            "gap": d["implied"].mean() - d["realized"].mean(),
        })

    print("=== implied vs realized, by level/side (full sample) ===")
    full = df.groupby(["side", "level"]).apply(agg, include_groups=False)
    order = [("dn", k) for k in FIBS] + [("up", k) for k in FIBS]
    full = full.reindex(order)
    with pd.option_context("display.float_format", "{:.3f}".format):
        print(full.to_string())

    print("\n=== 2025+ ===")
    rec = df[df["week_end"] >= "2025-01-01"].groupby(
        ["side", "level"]).apply(agg, include_groups=False).reindex(order)
    with pd.option_context("display.float_format", "{:.3f}".format):
        print(rec.to_string())

    print("\n=== gap by year, dn side ===")
    piv = df[df["side"] == "dn"].groupby(["year", "level"]).apply(
        agg, include_groups=False)["gap"].unstack()[list(FIBS)]
    with pd.option_context("display.float_format", "{:.3f}".format):
        print(piv.to_string())

    print("\n=== gap by year, up side ===")
    piv = df[df["side"] == "up"].groupby(["year", "level"]).apply(
        agg, include_groups=False)["gap"].unstack()[list(FIBS)]
    with pd.option_context("display.float_format", "{:.3f}".format):
        print(piv.to_string())


if __name__ == "__main__":
    main()
