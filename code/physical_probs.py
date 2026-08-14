#!/usr/bin/env python3
"""Physical probabilities of weekly closes/touches beyond Saty ATR levels.

Two samples:
  1. SPY weekly, 2000->2026 (spy.db ind_1w -- levels precomputed, prior-week ATR).
  2. SPX weekly, 2020->2026 (gex/SPX_eod.csv resampled W-FRI, same convention).

Perspective: position entered during week i (Monday), settled at week i close.
"""
import sqlite3
import pandas as pd
import numpy as np

FIBS = {"trigger": 0.236, "0382": 0.382, "0618": 0.618, "0786": 0.786, "100": 1.0}


def wilder_atr(df, period=14):
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def stats(df, label, windows):
    """df needs: open high low close prev_close atr_prev (prior-week)."""
    rows = []
    for name, fib in FIBS.items():
        up = df["prev_close"] + fib * df["atr_prev"]
        dn = df["prev_close"] - fib * df["atr_prev"]
        rec = {"level": name, "fib": fib}
        for wname, mask in windows.items():
            d = df[mask]
            u, l = up[mask], dn[mask]
            n = len(d)
            rec[f"{wname}_n"] = n
            rec[f"{wname}_close_above"] = (d["close"] > u).mean()
            rec[f"{wname}_close_below"] = (d["close"] < l).mean()
            rec[f"{wname}_touch_above"] = (d["high"] > u).mean()
            rec[f"{wname}_touch_below"] = (d["low"] < l).mean()
        rows.append(rec)
    out = pd.DataFrame(rows)
    print(f"\n===== {label} =====")
    with pd.option_context("display.width", 200, "display.float_format", "{:.3f}".format):
        print(out.to_string(index=False))
    return out


def main():
    # --- SPY long history from ind_1w (atr_14 already prior-period) ---
    conn = sqlite3.connect("/root/spy/spy.db")
    spy = pd.read_sql_query(
        "SELECT timestamp, open, high, low, close, prev_close, atr_14 FROM ind_1w "
        "ORDER BY timestamp", conn, parse_dates=["timestamp"])
    conn.close()
    spy = spy.rename(columns={"atr_14": "atr_prev"}).dropna(
        subset=["prev_close", "atr_prev"])
    spy = spy.set_index("timestamp")
    w_spy = {
        "full": pd.Series(True, index=spy.index),
        "2020p": spy.index >= "2020-01-01",
        "2025p": spy.index >= "2025-01-01",
    }
    s1 = stats(spy, f"SPY weekly {spy.index.min().date()} -> {spy.index.max().date()}", w_spy)

    # --- SPX from EOD, resample to weekly (Fri-anchored) ---
    spx = pd.read_csv("/root/spy/gex/SPX_eod.csv", parse_dates=["date"]).set_index("date")
    wk = spx.resample("W-FRI").agg(
        open=("open", "first"), high=("high", "max"),
        low=("low", "min"), close=("close", "last")).dropna()
    wk["atr_prev"] = wilder_atr(wk, 14).shift(1)
    wk["prev_close"] = wk["close"].shift(1)
    wk = wk.dropna()
    wk = wk[wk.index >= "2020-05-01"]  # 14-week warmup + margin
    w_spx = {
        "full": pd.Series(True, index=wk.index),
        "2025p": wk.index >= "2025-01-01",
    }
    s2 = stats(wk, f"SPX weekly {wk.index.min().date()} -> {wk.index.max().date()}", w_spx)

    s1.to_csv("/root/spy/atr_options_mispricing/physical_spy.csv", index=False)
    s2.to_csv("/root/spy/atr_options_mispricing/physical_spx.csv", index=False)
    wk.to_csv("/root/spy/atr_options_mispricing/spx_weekly_levels.csv")


if __name__ == "__main__":
    main()
