#!/usr/bin/env python3
"""Pull control strikes: puts at fixed 2.74% below prev weekly close + wings."""
import csv
import io
import sqlite3
import time
from collections import deque

import pandas as pd
import requests

BASE = "http://127.0.0.1:25503/v3"
DIR = "/root/spy/atr_options_mispricing"
PCT = 0.0274


def round5(x):
    return round(x / 5.0) * 5.0


def main():
    wk = pd.read_csv(f"{DIR}/spx_weekly_levels.csv", parse_dates=["date"]).set_index("date")
    daily = pd.read_csv("/root/spy/gex/SPX_eod.csv", parse_dates=["date"])
    ddates = daily["date"]
    exps = set(pd.read_csv(io.StringIO(requests.get(
        f"{BASE}/option/list/expirations", params={"symbol": "SPXW"},
        timeout=30).text))["expiration"])

    con = sqlite3.connect(f"{DIR}/level_quotes.sqlite")
    done = {tuple(r[:4]) for r in con.execute(
        "SELECT entry_date, expiration, strike, right FROM qdone")}

    plan = []
    prev_end = None
    for wend, row in wk.iterrows():
        days = ddates[(ddates > (prev_end or wend - pd.Timedelta(days=7)))
                      & (ddates <= wend)]
        prev_end = wend
        if len(days) < 3:
            continue
        entry = days.iloc[0].strftime("%Y-%m-%d")
        settle = days.iloc[-1].strftime("%Y-%m-%d")
        if settle not in exps:
            continue
        k = round5(row["prev_close"] * (1 - PCT))
        for kk in (k, k - 5, k - 25, k - 50):
            if (entry, settle, float(kk), "P") not in done:
                plan.append((entry, settle, kk, "P"))
    print(f"{len(plan)} to pull", flush=True)

    dq = deque(plan)
    n_ok, t0 = 0, time.time()
    while dq:
        entry, exp, k, right = dq.popleft()
        try:
            r = requests.get(f"{BASE}/option/history/quote", params={
                "symbol": "SPXW", "expiration": exp, "strike": k,
                "right": right, "start_date": entry, "end_date": entry,
                "interval": "1m", "start_time": "09:56", "end_time": "10:02",
            }, timeout=120)
            r.raise_for_status()
            rows = list(csv.DictReader(io.StringIO(r.text)))
            recs = []
            for x in rows:
                try:
                    recs.append((entry, exp, k, right, x.get("timestamp") or "",
                                 float(x["bid"]), float(x["ask"]),
                                 int(x["bid_size"]), int(x["ask_size"])))
                except (KeyError, ValueError):
                    continue
            con.executemany("INSERT OR REPLACE INTO q VALUES(?,?,?,?,?,?,?,?,?)", recs)
            con.execute("INSERT OR REPLACE INTO qdone VALUES(?,?,?,?,?)",
                        (entry, exp, k, right, "ok" if recs else "empty"))
            con.commit()
            n_ok += 1
        except Exception as e:
            if "472" in str(e):
                con.execute("INSERT OR REPLACE INTO qdone VALUES(?,?,?,?,?)",
                            (entry, exp, k, right, "nodata"))
                con.commit()
            else:
                print(f"FAIL {entry} {exp} {k}{right}: {e}", flush=True)
                time.sleep(2)
    print(f"DONE {n_ok} in {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
