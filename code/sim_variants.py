#!/usr/bin/env python3
"""Wing/short ATR variants + entry-regime filters, 2012-06 -> now.

Structures (all Monday ~10:00 SPXW, hold to settle, short@bid wing@ask, $2.64 comm):
  w50   : short -1.0 ATR, wing K-50 (published base)
  w1618 : short -1.0 ATR, wing at -1.618 ATR (ATR-scaled width)
  v1236 : short -1.236 ATR, wing at -1.786 ATR

Filters (independent, applied at entry, point-in-time):
  vix<X : Monday VIX open below X (spliced Yahoo+Cboe VIX)
  vix>X : Monday VIX open above X
  nogap : skip when Monday SPX open < weekly put trigger (prev_close - 0.236*ATR)

Weeks < 2020-05-01 use spx_weekly_levels_full.csv; >= use canonical file.
"""
import sqlite3
import pandas as pd
import numpy as np

DIR = "/root/spy/atr_options_mispricing"
COMM = 2.64
MULT = 100.0
SEAM = "2020-05-01"


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
    full = pd.read_csv(f"{DIR}/spx_weekly_levels_full.csv",
                       parse_dates=["date"]).set_index("date")
    canon = pd.read_csv(f"{DIR}/spx_weekly_levels.csv",
                        parse_dates=["date"]).set_index("date")
    wk = pd.concat([full[(full.index >= "2012-06-01") & (full.index < SEAM)],
                    canon[canon.index >= SEAM]])
    daily = pd.read_csv(f"{DIR}/spx_eod_full.csv", parse_dates=["date"])
    ddates = daily["date"]
    d = daily.set_index("date")
    vy = pd.read_csv("/root/spy/data/VIX_yahoo_daily.csv", parse_dates=["date"])
    vc = pd.read_csv("/root/spy/gex/VIX_eod.csv", parse_dates=["date"])
    vix = pd.concat([vy[vy.date < "2019-12-02"], vc]).set_index("date")["open"]
    quotes = load_quotes()

    structures = {
        "w50":   (1.0, "fix50"),
        "w1618": (1.0, 1.618),
        "v1236": (1.236, 1.786),
    }

    prev_end = None
    weeks = []
    for wend, row in wk.iterrows():
        days = ddates[(ddates > (prev_end or wend - pd.Timedelta(days=7)))
                      & (ddates <= wend)]
        prev_end = wend
        if len(days) < 3:
            continue
        weeks.append((wend, days.iloc[0], days.iloc[-1], row))

    frames = {}
    for sname, (sfib, wing) in structures.items():
        trades = []
        for wend, entry_day, settle_day, row in weeks:
            entry = entry_day.strftime("%Y-%m-%d")
            exp = settle_day.strftime("%Y-%m-%d")
            settle = d["close"].loc[settle_day]
            k = round5(row["prev_close"] - sfib * row["atr_prev"])
            kw = k - 50 if wing == "fix50" else round5(
                row["prev_close"] - wing * row["atr_prev"])
            if kw >= k:
                continue
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
            mon_open = d["open"].loc[entry_day]
            trigger = row["prev_close"] - 0.236 * row["atr_prev"]
            v = vix.get(entry_day, np.nan)
            trades.append({
                "week_end": wend, "entry": entry, "short_k": k, "wing_k": kw,
                "width": k - kw, "credit": credit, "settle": settle, "pnl": pnl,
                "vix": v, "gap_below_trigger": mon_open < trigger,
            })
        frames[sname] = pd.DataFrame(trades)
        frames[sname].to_csv(f"{DIR}/trades_variant_{sname}.csv", index=False)

    def line(df, tag):
        if len(df) < 2:
            return f"  {tag:<28s} n={len(df):3d}  (too few)"
        eq = df["pnl"].cumsum()
        dd = -(eq - eq.cummax()).min()
        yrs = max((df["week_end"].max() - df["week_end"].min()).days / 365.25, 0.1)
        g = df.loc[df["pnl"] > 0, "pnl"].sum()
        l = -df.loc[df["pnl"] < 0, "pnl"].sum()
        pf = g / l if l > 0 else np.inf
        return (f"  {tag:<28s} n={len(df):3d}  win={(df['pnl']>0).mean():5.1%}  "
                f"PF={pf:5.2f}  P&L=${df['pnl'].sum():>9,.0f}  ${df['pnl'].sum()/yrs:>7,.0f}/yr  "
                f"maxDD=${dd:>7,.0f}  cr={df['credit'].mean():4.2f}  w={df['width'].mean():4.0f}")

    filters = [
        ("no filter", lambda t: pd.Series(True, index=t.index)),
        ("vix<15", lambda t: t.vix < 15), ("vix<20", lambda t: t.vix < 20),
        ("vix<25", lambda t: t.vix < 25), ("vix<30", lambda t: t.vix < 30),
        ("vix>20", lambda t: t.vix > 20),
        ("no gap<trigger", lambda t: ~t.gap_below_trigger),
    ]
    periods = [("backfill 12-20", lambda t: t.week_end < SEAM),
               ("modern 20->26", lambda t: t.week_end >= SEAM),
               ("combined", lambda t: pd.Series(True, index=t.index))]

    for sname, df in frames.items():
        sfib, wing = structures[sname]
        print(f"\n===== {sname}: short -{sfib} ATR, wing "
              f"{'K-50' if wing == 'fix50' else f'-{wing} ATR'} =====")
        for pname, pmask in periods:
            print(f" [{pname}]")
            for fname, fmask in filters:
                sub = df[pmask(df) & fmask(df)]
                print(line(sub, fname))
    n_vix_missing = frames["w50"]["vix"].isna().sum()
    print(f"\nVIX missing on {n_vix_missing} entry days (excluded by vix filters, "
          f"kept by no-filter/nogap)")


if __name__ == "__main__":
    main()
