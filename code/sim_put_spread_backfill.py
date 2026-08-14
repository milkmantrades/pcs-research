#!/usr/bin/env python3
"""Weekly SPXW put credit spread sim over the Pro-tier backfill, 2012-06 -> 2020-04.

Same rules as sim_put_spread.py (Monday ~10:00 ET entry, hold to settle,
short at bid / wing at ask, $2.64 commission). Levels from
spx_weekly_levels_full.csv (spliced Yahoo + Cboe EOD); settle = Friday SPX close
from spx_eod_full.csv. Trades written to trades_*_backfill.csv.
"""
import sqlite3
import pandas as pd
import numpy as np

DIR = "/root/spy/atr_options_mispricing"
COMM = 2.64
MULT = 100.0
START, END = "2012-06-01", "2020-05-01"


def round5(x):
    return round(x / 5.0) * 5.0


def load_quotes():
    con = sqlite3.connect(f"{DIR}/level_quotes.sqlite")
    q = pd.read_sql_query("SELECT * FROM q", con)
    con.close()
    q["ts"] = pd.to_datetime(q["ts"])
    q = q[q["ts"].dt.time <= pd.Timestamp("10:00:00").time()]
    q = q.sort_values("ts").groupby(
        ["entry_date", "expiration", "strike", "right"]).last()
    return q


def main():
    wk = pd.read_csv(f"{DIR}/spx_weekly_levels_full.csv",
                     parse_dates=["date"]).set_index("date")
    wk = wk[(wk.index >= START) & (wk.index < END)]
    daily = pd.read_csv(f"{DIR}/spx_eod_full.csv", parse_dates=["date"])
    ddates = daily["date"]
    dclose = daily.set_index("date")["close"]
    quotes = load_quotes()

    def short_k(row, structure):
        if structure.startswith("atr100"):
            return round5(row["prev_close"] - 1.0 * row["atr_prev"])
        if structure.startswith("atr0786"):
            return round5(row["prev_close"] - 0.786 * row["atr_prev"])
        return round5(row["prev_close"] * (1 - 0.0274))

    structures = {
        "atr100_w50": 50, "atr100_w25": 25, "atr0786_w50": 50, "ctrl_w50": 50}

    all_trades = {}
    prev_end = None
    weeks = []
    for wend, row in wk.iterrows():
        days = ddates[(ddates > (prev_end or wend - pd.Timedelta(days=7)))
                      & (ddates <= wend)]
        prev_end = wend
        if len(days) < 3:
            continue
        weeks.append((wend, days.iloc[0].strftime("%Y-%m-%d"),
                      days.iloc[-1], row))

    for sname, width in structures.items():
        trades = []
        for wend, entry, settle_day, row in weeks:
            exp = settle_day.strftime("%Y-%m-%d")
            settle = dclose.loc[settle_day]
            k = short_k(row, sname)
            kw = k - width
            try:
                s = quotes.loc[(entry, exp, float(k), "P")]
                w = quotes.loc[(entry, exp, float(kw), "P")]
            except KeyError:
                continue
            if s["bid"] <= 0:
                continue
            credit = s["bid"] - w["ask"]
            if credit <= 0:
                continue
            payout = max(0.0, k - settle) - max(0.0, kw - settle)
            pnl = (credit - payout) * MULT - COMM
            trades.append({
                "week_end": wend, "entry": entry, "exp": exp, "short_k": k,
                "wing_k": kw, "credit": credit, "settle": settle,
                "payout": payout, "pnl": pnl,
                "bid_size": s["bsz"], "dist_pct": (row["prev_close"] - k) / row["prev_close"],
            })
        df = pd.DataFrame(trades)
        all_trades[sname] = df
        df.to_csv(f"{DIR}/trades_{sname}_backfill.csv", index=False)

    def report(df, label):
        if not len(df):
            print(f"{label}: no trades")
            return
        eq = df["pnl"].cumsum()
        dd = (eq - eq.cummax()).min()
        yrs = (df["week_end"].max() - df["week_end"].min()).days / 365.25
        g = df.loc[df["pnl"] > 0, "pnl"].sum()
        l = -df.loc[df["pnl"] < 0, "pnl"].sum()
        pf = g / l if l > 0 else np.inf
        print(f"\n--- {label} (backfill {START} -> {END}) ---")
        print(f"n={len(df)}  win={(df['pnl'] > 0).mean():.1%}  "
              f"avg credit={df['credit'].mean():.2f} pts  "
              f"avg dist={df['dist_pct'].mean():.2%}")
        print(f"total P&L=${df['pnl'].sum():,.0f}  ${df['pnl'].sum() / yrs:,.0f}/yr  "
              f"PF={pf:.2f}  maxDD=${-dd:,.0f}  avg/trade=${df['pnl'].mean():,.0f}")
        yr = df.groupby(df["week_end"].dt.year)["pnl"].agg(["count", "sum"])
        yr["win"] = df.groupby(df["week_end"].dt.year)["pnl"].apply(
            lambda s: (s > 0).mean())
        print(yr.to_string())

    for sname, df in all_trades.items():
        report(df, sname)

    p = all_trades["atr100_w50"]
    if len(p):
        losers = p[p["pnl"] < 0]
        print(f"\n=== atr100_w50 backfill losers ({len(losers)}) ===")
        with pd.option_context("display.width", 200):
            print(losers[["entry", "short_k", "credit", "settle", "pnl"]]
                  .to_string(index=False))


if __name__ == "__main__":
    main()
