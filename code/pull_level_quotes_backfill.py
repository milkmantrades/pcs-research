#!/usr/bin/env python3
"""Backfill Monday ~10:00 ET SPXW quotes at weekly ATR-level strikes, 2012-06 -> 2020-04.

Pro-tier extension of pull_level_quotes.py. Levels from spx_weekly_levels_full.csv
(spliced Yahoo 2011->2019-11 + gex/SPX_eod.csv). Same DB + schema; qdone dedups.
"""
import csv
import io
import sqlite3
import subprocess
import sys
import time

import pandas as pd
import requests

BASE = "http://127.0.0.1:25503/v3"
DB = "/root/spy/atr_options_mispricing/level_quotes.sqlite"
FIBS = {"trigger": 0.236, "0382": 0.382, "0618": 0.618, "0786": 0.786, "100": 1.0}
START, END = "2012-06-01", "2020-05-01"


def api_ok():
    try:
        r = requests.get(f"{BASE}/option/list/expirations",
                         params={"symbol": "SPXW"}, timeout=10)
        return r.ok and r.text.startswith("symbol")
    except Exception:
        return False


def heal(reason):
    print(f"HEAL ({reason})", flush=True)
    subprocess.run(["pkill", "-9", "-f", "lib/2026"], check=False)
    subprocess.run(["pkill", "-9", "-f", "ThetaTerminalv3"], check=False)
    time.sleep(8)
    subprocess.Popen(["bash", "/root/spy/theta/start_theta.sh"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for i in range(60):
        time.sleep(10)
        if api_ok():
            print(f"HEAL ok after {(i + 1) * 10}s", flush=True)
            return True
    return False


def round5(x):
    return round(x / 5.0) * 5.0


def build_plan():
    wk = pd.read_csv("/root/spy/atr_options_mispricing/spx_weekly_levels_full.csv",
                     parse_dates=["date"]).set_index("date")
    wk = wk[(wk.index >= START) & (wk.index < END)]
    daily = pd.read_csv("/root/spy/atr_options_mispricing/spx_eod_full.csv",
                        parse_dates=["date"])
    ddates = daily["date"]
    exps = set(pd.read_csv(io.StringIO(requests.get(
        f"{BASE}/option/list/expirations", params={"symbol": "SPXW"},
        timeout=30).text))["expiration"])

    plan = []  # (entry_date, expiration, strike, right, week_end)
    prev_end = None
    n_skip = 0
    for wend, row in wk.iterrows():
        days = ddates[(ddates > (prev_end or wend - pd.Timedelta(days=7)))
                      & (ddates <= wend)]
        prev_end = wend
        if len(days) < 3:
            continue
        entry = days.iloc[0].strftime("%Y-%m-%d")
        settle = days.iloc[-1].strftime("%Y-%m-%d")
        if settle not in exps:
            print(f"SKIP week {wend.date()}: no SPXW expiration {settle}")
            n_skip += 1
            continue
        strikes = set()
        for fib in FIBS.values():
            kd = round5(row["prev_close"] - fib * row["atr_prev"])
            ku = round5(row["prev_close"] + fib * row["atr_prev"])
            for k in (kd, kd - 5, kd - 25, kd - 50):
                strikes.add((k, "P"))
            for k in (ku, ku + 5, ku + 25, ku + 50):
                strikes.add((k, "C"))
        for k, right in sorted(strikes):
            plan.append((entry, settle, k, right, wend.strftime("%Y-%m-%d")))
    print(f"{n_skip} weeks skipped (no SPXW Friday expiration)", flush=True)
    return plan


def main():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS q(
        entry_date TEXT, expiration TEXT, strike REAL, right TEXT, ts TEXT,
        bid REAL, ask REAL, bsz INTEGER, asz INTEGER,
        PRIMARY KEY(entry_date, expiration, strike, right, ts))""")
    con.execute("""CREATE TABLE IF NOT EXISTS qdone(
        entry_date TEXT, expiration TEXT, strike REAL, right TEXT, status TEXT,
        PRIMARY KEY(entry_date, expiration, strike, right))""")
    done = {tuple(r[:4]) for r in con.execute(
        "SELECT entry_date, expiration, strike, right FROM qdone")}

    plan = build_plan()
    work = [p for p in plan
            if (p[0], p[1], float(p[2]), p[3]) not in done]
    print(f"{len(plan)} planned, {len(work)} to pull ({len(done)} done)", flush=True)

    streak, n_ok, t0 = 0, 0, time.time()
    from collections import deque
    dq = deque((*w, 0) for w in work)
    while dq:
        entry, exp, k, right, wend, att = dq.popleft()
        try:
            r = requests.get(f"{BASE}/option/history/quote", params={
                "symbol": "SPXW", "expiration": exp, "strike": k,
                "right": right, "start_date": entry, "end_date": entry,
                "interval": "1m", "start_time": "09:56", "end_time": "10:02",
            }, timeout=120)
            r.raise_for_status()
            if r.text.startswith("We have upgraded"):
                raise RuntimeError("param error: " + r.text[:120])
            rows = list(csv.DictReader(io.StringIO(r.text)))
            recs = []
            for x in rows:
                ts = x.get("timestamp") or ""
                try:
                    recs.append((entry, exp, k, right, ts, float(x["bid"]),
                                 float(x["ask"]), int(x["bid_size"]),
                                 int(x["ask_size"])))
                except (KeyError, ValueError):
                    continue
            con.executemany("INSERT OR REPLACE INTO q VALUES(?,?,?,?,?,?,?,?,?)",
                            recs)
            con.execute("INSERT OR REPLACE INTO qdone VALUES(?,?,?,?,?)",
                        (entry, exp, k, right, "ok" if recs else "empty"))
            con.commit()
            n_ok += 1
            streak = 0
            if n_ok % 200 == 0:
                print(f"{n_ok} ok, {n_ok / (time.time() - t0) * 60:.1f}/min",
                      flush=True)
        except Exception as e:
            if "472" in str(e):
                con.execute("INSERT OR REPLACE INTO qdone VALUES(?,?,?,?,?)",
                            (entry, exp, k, right, "nodata"))
                con.commit()
                continue
            print(f"FAIL {entry} {exp} {k}{right}: {e}", flush=True)
            streak += 1
            if att + 1 < 4:
                dq.append((entry, exp, k, right, wend, att + 1))
            else:
                con.execute("INSERT OR REPLACE INTO qdone VALUES(?,?,?,?,?)",
                            (entry, exp, k, right, "fail"))
                con.commit()
            if streak >= 3:
                if not heal(f"streak={streak}"):
                    sys.exit(2)
                streak = 0
            else:
                time.sleep(2)
    print(f"DONE {n_ok} in {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
