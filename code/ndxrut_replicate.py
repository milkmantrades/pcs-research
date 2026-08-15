#!/usr/bin/env python3
"""NDX/RUT cross-index replication of the frozen PCS expressions.

Frozen rules (NO per-index tuning):
  levels: prev weekly close - fib x prior-week Wilder ATR(14), fibs 1.0/1.236/1.618/1.786
  strikes: snap each level to the NEAREST LISTED strike for that week's expiration
  implied digital: (mid(K) - mid(K_below)) / (K - K_below), K_below = adjacent listed strike
  entry Monday ~10:00 ET, short at bid / wing at ask, $2.64 commission, hold to settle
  expressions: hold (short -1.0 / wing -1.618), calm filter (implied < trailing 52wk median,
  shifted, min 26 obs), ladder (calm -> -1.0/-1.618; med..p75 -> -1.236/-1.786; >p75 sit out)

Roots: prefer PM-settled weekly root (NDXP/RUTW); else base root (NDX/RUT) EXCEPT
third-Friday weeks (AM-settled under base roots) which are skipped -- mirrors the
63 skipped SPX weeks. Settlement approximated by Friday index close (Yahoo).

Stages: --pull (resumable) then --sim.
"""
import argparse
import csv
import io
import sqlite3
import time

import numpy as np
import pandas as pd
import requests

BASE = "http://127.0.0.1:25503/v3"
DIR = "/root/spy/atr_options_mispricing"
DB = f"{DIR}/ndxrut_quotes.sqlite"
COMM = 2.64
MULT = 100.0
START = "2012-06-01"
SEAM = "2020-05-01"

IDX = {
    "NDX": dict(daily=f"{DIR}/ndx_eod_full.csv", pm_root="NDXP", base_root="NDX"),
    "RUT": dict(daily=f"{DIR}/rut_eod_full.csv", pm_root="RUTW", base_root="RUT"),
}
FIBS = [1.0, 1.236, 1.618, 1.786]


def wilder_atr(df, period=14):
    tr = pd.concat([df["high"] - df["low"],
                    (df["high"] - df["close"].shift(1)).abs(),
                    (df["low"] - df["close"].shift(1)).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def weekly_levels(daily_csv):
    d = pd.read_csv(daily_csv, parse_dates=["date"]).set_index("date")
    wk = d.resample("W-FRI").agg(open=("open", "first"), high=("high", "max"),
                                 low=("low", "min"), close=("close", "last")).dropna()
    wk["atr_prev"] = wilder_atr(wk, 14).shift(1)
    wk["prev_close"] = wk["close"].shift(1)
    return wk.dropna(), d


def expirations(sym):
    r = requests.get(f"{BASE}/option/list/expirations", params={"symbol": sym}, timeout=30)
    return set(pd.read_csv(io.StringIO(r.text))["expiration"])


_strike_cache = {}
def strikes(sym, exp):
    key = (sym, exp)
    if key not in _strike_cache:
        r = requests.get(f"{BASE}/option/list/strikes",
                         params={"symbol": sym, "expiration": exp}, timeout=30)
        if r.ok and r.text.startswith("symbol"):
            _strike_cache[key] = np.sort(pd.read_csv(io.StringIO(r.text))["strike"].values)
        else:
            _strike_cache[key] = np.array([])
    return _strike_cache[key]


def snap(ks, level):
    if len(ks) == 0:
        return None
    return float(ks[np.argmin(np.abs(ks - level))])


def below(ks, k):
    lower = ks[ks < k]
    return float(lower.max()) if len(lower) else None


def is_third_friday(d):
    return d.weekday() == 4 and 15 <= d.day <= 21


def build_plan():
    plan = []
    for idx, cfg in IDX.items():
        wk, daily = weekly_levels(cfg["daily"])
        wk = wk[wk.index >= START]
        pm_exps = expirations(cfg["pm_root"])
        base_exps = expirations(cfg["base_root"])
        ddates = daily.index
        prev_end = None
        n_skip = 0
        for wend, row in wk.iterrows():
            days = ddates[(ddates > (prev_end or wend - pd.Timedelta(days=7))) & (ddates <= wend)]
            prev_end = wend
            if len(days) < 3:
                continue
            entry = days[0].strftime("%Y-%m-%d")
            sday = days[-1]
            settle = sday.strftime("%Y-%m-%d")
            if settle in pm_exps:
                root = cfg["pm_root"]
            elif settle in base_exps and not is_third_friday(sday):
                root = cfg["base_root"]
            else:
                n_skip += 1
                continue
            ks = strikes(root, settle)
            if len(ks) < 3:
                n_skip += 1
                continue
            want = set()
            k10 = snap(ks, row["prev_close"] - 1.0 * row["atr_prev"])
            for fib in FIBS:
                k = snap(ks, row["prev_close"] - fib * row["atr_prev"])
                if k is not None:
                    want.add(k)
            kb = below(ks, k10) if k10 is not None else None
            if kb is not None:
                want.add(kb)
            for k in sorted(want):
                plan.append((idx, root, entry, settle, k, wend.strftime("%Y-%m-%d")))
        print(f"{idx}: planned weeks minus skips ({n_skip} skipped)", flush=True)
    return plan


def pull():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS q(
        idx TEXT, root TEXT, entry_date TEXT, expiration TEXT, strike REAL, ts TEXT,
        bid REAL, ask REAL, PRIMARY KEY(idx, entry_date, expiration, strike, ts))""")
    con.execute("""CREATE TABLE IF NOT EXISTS qdone(
        idx TEXT, entry_date TEXT, expiration TEXT, strike REAL, status TEXT,
        PRIMARY KEY(idx, entry_date, expiration, strike))""")
    done = {tuple(r) for r in con.execute("SELECT idx, entry_date, expiration, strike FROM qdone")}
    plan = build_plan()
    work = [p for p in plan if (p[0], p[2], p[3], float(p[4])) not in done]
    print(f"{len(plan)} planned, {len(work)} to pull", flush=True)
    n_ok, t0 = 0, time.time()
    for idx, root, entry, exp, k, wend in work:
        try:
            r = requests.get(f"{BASE}/option/history/quote", params={
                "symbol": root, "expiration": exp, "strike": k, "right": "P",
                "start_date": entry, "end_date": entry, "interval": "1m",
                "start_time": "09:56", "end_time": "10:02"}, timeout=120)
            r.raise_for_status()
            rows = list(csv.DictReader(io.StringIO(r.text)))
            recs = [(idx, root, entry, exp, k, x["timestamp"], float(x["bid"]), float(x["ask"]))
                    for x in rows if x.get("bid")]
            con.executemany("INSERT OR REPLACE INTO q VALUES(?,?,?,?,?,?,?,?)", recs)
            con.execute("INSERT OR REPLACE INTO qdone VALUES(?,?,?,?,?)",
                        (idx, entry, exp, k, "ok" if recs else "empty"))
            con.commit()
            n_ok += 1
            if n_ok % 500 == 0:
                print(f"{n_ok} ok, {n_ok / (time.time() - t0) * 60:.0f}/min", flush=True)
        except Exception as e:
            if "472" in str(e):
                con.execute("INSERT OR REPLACE INTO qdone VALUES(?,?,?,?,?)",
                            (idx, entry, exp, k, "nodata"))
                con.commit()
                continue
            print(f"FAIL {idx} {entry} {k}: {e}", flush=True)
            time.sleep(3)
    print(f"PULL DONE {n_ok} in {(time.time() - t0) / 60:.1f} min", flush=True)


def sim():
    con = sqlite3.connect(DB)
    q = pd.read_sql_query("SELECT * FROM q", con)
    q["ts"] = pd.to_datetime(q.ts)
    q = q[q.ts.dt.time <= pd.Timestamp("10:00:00").time()]
    q["mid"] = (q.bid + q.ask) / 2
    q = q.sort_values("ts").groupby(["idx", "entry_date", "strike"]).last().reset_index()

    for idx, cfg in IDX.items():
        wk, daily = weekly_levels(cfg["daily"])
        wk = wk[wk.index >= START]
        pm_exps = expirations(cfg["pm_root"])
        base_exps = expirations(cfg["base_root"])
        ddates = daily.index
        dclose = daily["close"]
        qq = q[q.idx == idx]
        prev_end = None
        rows = []
        for wend, row in wk.iterrows():
            days = ddates[(ddates > (prev_end or wend - pd.Timedelta(days=7))) & (ddates <= wend)]
            prev_end = wend
            if len(days) < 3:
                continue
            entry = days[0].strftime("%Y-%m-%d")
            sday = days[-1]
            settle_d = sday.strftime("%Y-%m-%d")
            if settle_d in pm_exps:
                root = cfg["pm_root"]
            elif settle_d in base_exps and not is_third_friday(sday):
                root = cfg["base_root"]
            else:
                continue
            ks = strikes(root, settle_d)
            if len(ks) < 3:
                continue
            settle = dclose.loc[sday]
            wq = qq[qq.entry_date == entry].set_index("strike")

            def get(k):
                try:
                    return wq.loc[k]
                except KeyError:
                    return None

            k10 = snap(ks, row["prev_close"] - 1.0 * row["atr_prev"])
            kb = below(ks, k10) if k10 is not None else None
            imp = np.nan
            if k10 is not None and kb is not None:
                a, b = get(k10), get(kb)
                if a is not None and b is not None and (k10 - kb) > 0:
                    imp = (a["mid"] - b["mid"]) / (k10 - kb)

            def spread(fs, fw):
                k = snap(ks, row["prev_close"] - fs * row["atr_prev"])
                kw = snap(ks, row["prev_close"] - fw * row["atr_prev"])
                if k is None or kw is None or kw >= k:
                    return None
                s, w = get(k), get(kw)
                if s is None or w is None or s["bid"] <= 0:
                    return None
                credit = s["bid"] - w["ask"]
                if credit <= 0:
                    return None
                payout = max(0.0, k - settle) - max(0.0, kw - settle)
                return dict(short_k=k, wing_k=kw, credit=credit,
                            pnl=(credit - payout) * MULT - COMM)

            rows.append(dict(week_end=wend, entry=entry, implied=imp,
                             t10=spread(1.0, 1.618), t1236=spread(1.236, 1.786)))

        df = pd.DataFrame(rows)
        df["med52"] = df.implied.rolling(52, min_periods=26).median().shift(1)
        df["p75"] = df.implied.rolling(52, min_periods=26).quantile(0.75).shift(1)
        out = []
        for r_ in df.itertuples():
            for tag, tr_ in [("t10", r_.t10), ("t1236", r_.t1236)]:
                if tr_ is not None:
                    out.append(dict(week_end=r_.week_end, entry=r_.entry, struct=tag,
                                    implied=r_.implied, med52=r_.med52, p75=r_.p75, **tr_))
        t = pd.DataFrame(out)
        t.to_csv(f"{DIR}/trades_replication_{idx.lower()}.csv", index=False)

        def rep(s, tag, era):
            if len(s) < 5:
                print(f"  {tag:<26s} n={len(s)} (thin)  [{era}]")
                return
            g = s.loc[s.pnl > 0, "pnl"].sum()
            l = -s.loc[s.pnl < 0, "pnl"].sum()
            eq = s.sort_values("week_end").pnl.cumsum()
            dd = -(eq - eq.cummax()).min()
            print(f"  {tag:<26s} n={len(s):3d}  win={(s.pnl > 0).mean():5.1%}  "
                  f"PF={g / l if l > 0 else np.inf:5.2f}  P&L=${s.pnl.sum():>9,.0f}  "
                  f"maxDD=${dd:>8,.0f}  [{era}]")

        h = t[t.struct == "t10"]
        calm = h[h.implied < h.med52]
        d12 = t[t.struct == "t1236"]
        mild = d12[(d12.implied >= d12.med52) & (d12.implied < d12.p75)]
        ladder = pd.concat([calm, mild])
        print(f"\n===== {idx} replication (frozen rules) =====")
        for era, lo, hi in [("backfill", "2012-01-01", SEAM), ("modern", SEAM, "2100-01-01")]:
            m = lambda d: d[(d.week_end >= lo) & (d.week_end < hi)]
            rep(m(h), "hold -1.0/-1.618", era)
            rep(m(calm), "B: calm filter", era)
            rep(m(ladder), "ladder (calm+mild)", era)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--sim", action="store_true")
    a = ap.parse_args()
    if a.pull:
        pull()
    if a.sim or not a.pull:
        sim()
