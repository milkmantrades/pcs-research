#!/usr/bin/env python3
"""Weekly SPXW put credit spread sim, Monday ~10:00 ET entry, hold to settle.

Structures:
  atr100_w50 : short put @ round5(prev_close - 1.0*ATRw), wing K-50
  atr100_w25 : same short, wing K-25
  atr0786_w50: short put @ round5(prev_close - 0.786*ATRw), wing K-50
  ctrl_w50   : short put @ round5(prev_close*(1-0.0274)), wing K-50  [no vol scaling]

Fills: sell short leg at BID, buy wing at ASK (last quote <= 10:00).
Settle: cash at Friday SPX close. Commission $2.64/spread. $100 multiplier.
"""
import sqlite3
import pandas as pd
import numpy as np

DIR = "/root/spy/atr_options_mispricing"
COMM = 2.64
MULT = 100.0


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
    wk = pd.read_csv(f"{DIR}/spx_weekly_levels.csv", parse_dates=["date"]).set_index("date")
    daily = pd.read_csv("/root/spy/gex/SPX_eod.csv", parse_dates=["date"])
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
        df.to_csv(f"{DIR}/trades_{sname}.csv", index=False)

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
        print(f"\n--- {label} ---")
        print(f"n={len(df)}  win={(df['pnl'] > 0).mean():.1%}  "
              f"avg credit={df['credit'].mean():.2f} pts  "
              f"avg dist={df['dist_pct'].mean():.2%}")
        print(f"total P&L=${df['pnl'].sum():,.0f}  ${df['pnl'].sum() / yrs:,.0f}/yr  "
              f"PF={pf:.2f}  maxDD=${-dd:,.0f}  avg/trade=${df['pnl'].mean():,.0f}")
        for tag, sub in [("2025+", df[df["week_end"] >= "2025-01-01"]),
                         ("2026", df[df["week_end"] >= "2026-01-01"])]:
            if len(sub):
                gg = sub.loc[sub["pnl"] > 0, "pnl"].sum()
                ll = -sub.loc[sub["pnl"] < 0, "pnl"].sum()
                print(f"  {tag}: n={len(sub)} win={(sub['pnl'] > 0).mean():.1%} "
                      f"P&L=${sub['pnl'].sum():,.0f} PF={gg / ll if ll > 0 else np.inf:.2f}")
        yr = df.groupby(df["week_end"].dt.year)["pnl"].agg(["count", "sum"])
        print(yr.to_string())

    for sname, df in all_trades.items():
        report(df, sname)

    # losers detail for primary
    p = all_trades["atr100_w50"]
    losers = p[p["pnl"] < 0]
    print(f"\n=== atr100_w50 losers ({len(losers)}) ===")
    with pd.option_context("display.width", 200):
        print(losers[["entry", "short_k", "credit", "settle", "pnl"]].to_string(index=False))


if __name__ == "__main__":
    main()
