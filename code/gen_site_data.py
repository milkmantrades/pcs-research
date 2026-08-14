#!/usr/bin/env python3
"""Generate the embedded DATA JSON for site/atr-premium-selling.html."""
import json
import sqlite3
import pandas as pd
import numpy as np

DIR = "/root/spy/atr_options_mispricing"
COMM = 2.64
MULT = 100.0
FIBS = {"trigger": 0.236, "0382": 0.382, "0618": 0.618, "0786": 0.786, "100": 1.0}
LEVEL_LABELS = {"trigger": "±0.236 trigger", "0382": "±0.382 (GG)",
                "0618": "±0.618", "0786": "±0.786", "100": "±1.0 full ATR"}


def round5(x):
    return round(x / 5.0) * 5.0


def load_quotes():
    con = sqlite3.connect(f"{DIR}/level_quotes.sqlite")
    q = pd.read_sql_query("SELECT * FROM q", con)
    con.close()
    q["ts"] = pd.to_datetime(q["ts"])
    q = q[q["ts"].dt.time <= pd.Timestamp("10:00:00").time()]
    return q.sort_values("ts").groupby(
        ["entry_date", "expiration", "strike", "right"]).last()


def weeks_list(wk, ddates):
    out, prev = [], None
    for wend, row in wk.iterrows():
        days = ddates[(ddates > (prev or wend - pd.Timedelta(days=7)))
                      & (ddates <= wend)]
        prev = wend
        if len(days) < 3:
            continue
        out.append((wend, days.iloc[0].strftime("%Y-%m-%d"), days.iloc[-1], row))
    return out


def sim(quotes, weeks, dclose, strike_fn, width):
    trades = []
    for wend, entry, sd, row in weeks:
        exp = sd.strftime("%Y-%m-%d")
        settle = dclose.loc[sd]
        k = strike_fn(row)
        kw = k - width
        try:
            s = quotes.loc[(entry, exp, float(k), "P")]
            w = quotes.loc[(entry, exp, float(kw), "P")]
        except KeyError:
            continue
        if s["bid"] <= 0:
            continue
        credit = (s["bid"] + s["ask"]) / 2.0 - (w["bid"] + w["ask"]) / 2.0
        if credit <= 0:
            continue
        payout = max(0.0, k - settle) - max(0.0, kw - settle)
        pnl = (credit - payout) * MULT - COMM
        trades.append({"we": wend.strftime("%Y-%m-%d"), "entry": entry,
                       "k": k, "kw": kw, "credit": round(credit, 2),
                       "settle": round(settle, 2), "pnl": round(pnl, 2),
                       "risk": round((width - credit) * MULT, 2)})
    return pd.DataFrame(trades)


def summarize(d):
    yrs = (pd.to_datetime(d.we.iloc[-1]) - pd.to_datetime(d.we.iloc[0])).days / 365.25
    g = d.loc[d.pnl > 0, "pnl"].sum()
    l = -d.loc[d.pnl < 0, "pnl"].sum()
    eq = d.pnl.cumsum()
    dd = float(-(eq - eq.cummax()).min())
    yearly = d.groupby(pd.to_datetime(d.we).dt.year).pnl.sum()
    return {"n": int(len(d)), "win": round(float((d.pnl > 0).mean()), 4),
            "pf": round(float(g / l) if l > 0 else None, 2),
            "total": round(float(d.pnl.sum()), 2),
            "peryr": round(float(d.pnl.sum() / yrs), 0),
            "dd": round(dd, 2),
            "avg_credit": round(float(d.credit.mean()), 2),
            "avg_risk": round(float(d.risk.mean()), 0),
            "max_risk": round(float(d.risk.max()), 2),
            "neg_years": int((yearly < 0).sum()),
            "yearly": {str(k): round(float(v), 2) for k, v in yearly.items()}}


def main():
    wk = pd.read_csv(f"{DIR}/spx_weekly_levels.csv", parse_dates=["date"]).set_index("date")
    daily = pd.read_csv("/root/spy/gex/SPX_eod.csv", parse_dates=["date"])
    ddates = daily["date"]
    dclose = daily.set_index("date")["close"]
    daily2 = daily.set_index("date")
    daily2["ema21"] = daily2["close"].ewm(span=21, adjust=False).mean()
    quotes = load_quotes()
    weeks = weeks_list(wk, ddates)

    atr_k = lambda row: round5(row["prev_close"] - 1.0 * row["atr_prev"])
    ctrl_k = lambda row: round5(row["prev_close"] * (1 - 0.0274))

    widths = {}
    for w in (5, 25, 50, 75, 100):
        d = sim(quotes, weeks, dclose, atr_k, w)
        widths[str(w)] = summarize(d)
        if w == 50:
            primary = d
        if w == 75:
            w75 = d
    ctrl = sim(quotes, weeks, dclose, ctrl_k, 50)

    # equity curves (date, cumulative)
    def curve(d):
        return [[r.we, round(float(c), 2)] for r, c in
                zip(d.itertuples(), d.pnl.cumsum())]

    # EMA regime split for primary
    prim = primary.copy()
    prim["entry_dt"] = pd.to_datetime(prim.entry)
    def above(e):
        ref = ddates[ddates < e].iloc[-1]
        return bool(daily2.loc[ref, "close"] > daily2.loc[ref, "ema21"])
    prim["above"] = prim.entry_dt.map(above)

    # mispricing map aggregates
    ivp = pd.read_csv(f"{DIR}/implied_vs_physical.csv", parse_dates=["week_end"])
    mm = []
    for side in ("dn", "up"):
        for lvl in FIBS:
            d = ivp[(ivp.side == side) & (ivp.level == lvl)]
            mm.append({"side": side, "level": lvl, "label": LEVEL_LABELS[lvl],
                       "n": int(len(d)),
                       "implied": round(float(d.implied.mean()), 4),
                       "realized": round(float(d.realized.mean()), 4)})
    # yearly gap for -1 ATR puts
    d1 = ivp[(ivp.side == "dn") & (ivp.level == "100")].copy()
    d1["year"] = d1.week_end.dt.year
    ygap = [{"year": int(y), "n": int(len(g)),
             "implied": round(float(g.implied.mean()), 4),
             "realized": round(float(g.realized.mean()), 4)}
            for y, g in d1.groupby("year")]

    # physical probabilities
    spy = pd.read_csv(f"{DIR}/physical_spy.csv")
    spx = pd.read_csv(f"{DIR}/physical_spx.csv")
    phys = []
    for _, r in spy.iterrows():
        sx = spx[spx.level == r.level].iloc[0]
        phys.append({"level": r.level, "label": LEVEL_LABELS[r.level],
                     "spy_full_below": round(r.full_close_below, 3),
                     "spx_below": round(sx.full_close_below, 3),
                     "spx25_below": round(sx["2025p_close_below"], 3),
                     "spy_full_above": round(r.full_close_above, 3),
                     "spx_above": round(sx.full_close_above, 3),
                     "spx25_above": round(sx["2025p_close_above"], 3)})

    losers = primary[primary.pnl < 0][["entry", "k", "kw", "credit", "settle", "pnl"]]

    data = {
        "asof": "2026-08-12",
        "sample": {"start": prim.we.min(), "end": prim.we.max()},
        "primary": summarize(primary),
        "ctrl": summarize(ctrl),
        "widths": widths,
        "curves": {"atr50": curve(primary), "ctrl50": curve(ctrl),
                   "atr75": curve(w75)},
        "regime": {
            "above": summarize(prim[prim.above].drop(columns=["entry_dt", "above"])),
            "below": summarize(prim[~prim.above].drop(columns=["entry_dt", "above"]))},
        "map": mm,
        "ygap": ygap,
        "phys": phys,
        "losers": losers.to_dict("records"),
    }
    out = f"{DIR}/site_data.json"
    with open(out, "w") as f:
        json.dump(data, f)
    print(f"wrote {out}")
    print(json.dumps(data["primary"], indent=1))


if __name__ == "__main__":
    main()
