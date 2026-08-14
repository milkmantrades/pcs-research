#!/usr/bin/env python3
"""Touch-stop analysis: close the spread when price reaches the -1 ATR level.

Pipeline (run stages with flags; all stages are resumable):
  --touches   compute first-touch minutes per trade per stop depth from ES 1-min
              (daily calibration factor = last RTH ES close / SPX close)
  --pull      pull SPXW exit quotes for a 10-minute window from each touch minute
              into the `stopq` table (requires local ThetaTerminal v3 on :25503)
  --sim       apply the stop to trades_variant_w1618.csv (+ gap-skip), write
              trades_w1618_gapskip_stop10_corrected.csv, print depth sweep

!! AUDIT FLAG (Codex, 2026-08-14, docs/ATR_PCS_DIRECTION_CODEX_OPINION.md) !!
The published results selected the first exit quote AT-OR-AFTER the touch-bar
timestamp. ES 1-min bars are stamped at interval START, so the bar's low is only
observable at minute-end -- the same-stamp quote precedes trigger observability
(~1-minute lookahead). --causal shifts exit selection to strictly AFTER the
touch minute (Codex's minimal correction: combined PF 1.47 -> 1.20, backfill
turns negative). The same-day basis calibration is also non-causal (prior-day
basis changes 13 touch classifications). A clean rerun needs native SPX intraday
prices. Treat non-causal outputs as upper bounds.

ES data path is site-specific; see ES_PATH below.
"""
import argparse
import csv
import io
import sqlite3
import numpy as np
import pandas as pd
import requests

DIR = "data"
ES_PATH = "/srv/ftp/ossicones/futures-data/ES_full_1min_continuous_ratio_adjusted_through_2026-07-10.txt"
BASE = "http://127.0.0.1:25503/v3"
COMM = 2.64
FIBS = [1.0, 1.118, 1.236, 1.382, 1.5]
SEAM = "2020-05-01"


def load_es_rth():
    es = pd.read_csv(ES_PATH, header=None, names=["ts", "o", "h", "l", "c", "v"],
                     parse_dates=["ts"])
    es = es[es.ts >= "2012-05-01"]
    es["d"] = es.ts.dt.normalize()
    tod = es.ts.dt.time
    rth = es[(tod >= pd.Timestamp("09:30").time())
             & (tod <= pd.Timestamp("16:00").time())].copy()
    spx = pd.read_csv(f"{DIR}/spx_eod_full.csv", parse_dates=["date"]).set_index("date")
    cal = (rth.groupby("d")["c"].last() / spx["close"]).dropna().rename("k")
    rth = rth.merge(cal, left_on="d", right_index=True, how="left")
    rth["spx_low"] = rth.l / rth.k
    return rth.set_index("ts").sort_index(), spx


def compute_touches():
    rth, spx = load_es_rth()
    full = pd.read_csv(f"{DIR}/spx_weekly_levels_full.csv", parse_dates=["date"]).set_index("date")
    canon = pd.read_csv(f"{DIR}/spx_weekly_levels.csv", parse_dates=["date"]).set_index("date")
    wk = pd.concat([full[(full.index >= "2012-06-01") & (full.index < SEAM)],
                    canon[canon.index >= SEAM]])
    tr = pd.read_csv(f"{DIR}/trades_variant_w1618.csv", parse_dates=["week_end", "entry"])
    tr = tr.merge(wk[["prev_close", "atr_prev"]], left_on="week_end", right_index=True)
    ddates = spx.index
    tr["exp"] = tr.week_end.map(
        lambda we: ddates[(ddates > we - pd.Timedelta(days=7)) & (ddates <= we)].max())
    rows = []
    for t in tr.itertuples():
        seg = rth.loc[t.entry + pd.Timedelta(hours=10, minutes=1):
                      t.exp + pd.Timedelta(hours=16)]
        for f in FIBS:
            level = t.prev_close - f * t.atr_prev
            if level <= t.wing_k:
                continue
            hit = seg[seg.spx_low <= level]
            if len(hit):
                rows.append({"entry": t.entry.date(), "exp": t.exp.date(), "fib": f,
                             "short_k": t.short_k, "wing_k": t.wing_k,
                             "stop_ts": hit.index[0]})
    st = pd.DataFrame(rows)
    st.to_csv(f"{DIR}/stop_depth_touches.csv", index=False)
    print(st.groupby("fib").size().rename("touched").to_string())


def pull_exit_quotes():
    st = pd.read_csv(f"{DIR}/stop_depth_touches.csv", parse_dates=["stop_ts"])
    con = sqlite3.connect(f"{DIR}/level_quotes.sqlite")
    con.execute("""CREATE TABLE IF NOT EXISTS stopq(
        entry_date TEXT, expiration TEXT, strike REAL, right TEXT, ts TEXT,
        bid REAL, ask REAL, PRIMARY KEY(entry_date, expiration, strike, right, ts))""")
    have = set()
    for e, k, ts in con.execute("SELECT entry_date, strike, ts FROM stopq"):
        have.add((e, float(k), pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M")))
    n_req = 0
    for t in st.itertuples():
        day = t.stop_ts.strftime("%Y-%m-%d")
        t0, t1 = t.stop_ts.strftime("%H:%M"), (t.stop_ts + pd.Timedelta(minutes=10)).strftime("%H:%M")
        for k in (t.short_k, t.wing_k):
            if any((str(t.entry), float(k),
                    (t.stop_ts + pd.Timedelta(minutes=m)).strftime("%Y-%m-%d %H:%M")) in have
                   for m in range(3)):
                continue
            r = requests.get(f"{BASE}/option/history/quote", params={
                "symbol": "SPXW", "expiration": str(t.exp), "strike": k, "right": "P",
                "start_date": day, "end_date": day, "interval": "1m",
                "start_time": t0, "end_time": t1}, timeout=120)
            n_req += 1
            rows = list(csv.DictReader(io.StringIO(r.text))) if r.ok else []
            recs = [(str(t.entry), str(t.exp), k, "P", x["timestamp"],
                     float(x["bid"]), float(x["ask"])) for x in rows if x.get("bid")]
            con.executemany("INSERT OR REPLACE INTO stopq VALUES(?,?,?,?,?,?,?)", recs)
            con.commit()
            for x in recs:
                have.add((x[0], float(x[2]), pd.Timestamp(x[4]).strftime("%Y-%m-%d %H:%M")))
    print(f"pulled {n_req} contract-windows")


def sim(causal=False):
    con = sqlite3.connect(f"{DIR}/level_quotes.sqlite")
    sq = pd.read_sql_query("SELECT * FROM stopq", con)
    sq["ts"] = pd.to_datetime(sq.ts)
    sq = sq.sort_values("ts")
    st = pd.read_csv(f"{DIR}/stop_depth_touches.csv", parse_dates=["stop_ts"])
    tr = pd.read_csv(f"{DIR}/trades_variant_w1618.csv", parse_dates=["week_end", "entry"])
    tr["entry_d"] = tr.entry.dt.strftime("%Y-%m-%d")
    tr = tr[~tr.gap_below_trigger]

    def exit_quote(entry_d, k, ts):
        lo = ts + pd.Timedelta(minutes=1) if causal else ts
        q = sq[(sq.entry_date == entry_d) & (sq.strike == float(k))
               & (sq.ts >= lo) & (sq.ts <= ts + pd.Timedelta(minutes=10))]
        return q.iloc[0] if len(q) else None

    def line(df, col, tag):
        g = df.loc[df[col] > 0, col].sum()
        l = -df.loc[df[col] < 0, col].sum()
        eq = df[col].cumsum()
        dd = -(eq - eq.cummax()).min()
        return (f"  {tag:<12s} n={len(df):3d}  win={(df[col] > 0).mean():5.1%}  "
                f"PF={g / l if l > 0 else np.inf:5.2f}  P&L=${df[col].sum():>8,.0f}  "
                f"maxDD=${dd:>7,.0f}")

    print(f"w1618 + gap-skip, exit selection: {'CAUSAL (strictly after touch minute)' if causal else 'as published (same minute -- see audit flag)'}")
    for f in FIBS + [None]:
        stf = st[st.fib == f].set_index("entry") if f else None
        pnl, stopped = [], []
        for t in tr.itertuples():
            p, s_ = t.pnl, False
            if f is not None and t.entry_d in stf.index:
                s = stf.loc[t.entry_d]
                sh = exit_quote(t.entry_d, t.short_k, s.stop_ts)
                wg = exit_quote(t.entry_d, t.wing_k, s.stop_ts)
                if sh is not None and wg is not None:
                    p = (t.credit - (sh.ask - wg.bid)) * 100 - 2 * COMM
                    s_ = True
            pnl.append(p)
            stopped.append(s_)
        d = tr.assign(px=pnl, stopped=stopped)
        if f == 1.0 and not causal:
            d.to_csv(f"{DIR}/trades_w1618_gapskip_stop10_corrected.csv", index=False)
        tag = f"stop -{f}" if f else "no stop"
        for pname, mask in [("backfill", d.week_end < SEAM),
                            ("modern", d.week_end >= SEAM),
                            ("combined", pd.Series(True, index=d.index))]:
            print(line(d[mask], "px", tag if pname == "backfill" else "") + f"  [{pname}]")
        print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--touches", action="store_true")
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--causal", action="store_true",
                    help="exit at first quote strictly AFTER the touch minute (Codex correction)")
    a = ap.parse_args()
    if a.touches:
        compute_touches()
    if a.pull:
        pull_exit_quotes()
    if a.sim or not (a.touches or a.pull):
        sim(causal=a.causal)
