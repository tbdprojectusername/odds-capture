#!/usr/bin/env python3
"""Automatic settlement: pull UFC results from the public UFCStats mirror and
fill movement/results/results.csv for started signals.

Source: https://raw.githubusercontent.com/Greco1899/scrape_ufc_stats/main
(ufc_fight_results.csv: EVENT/BOUT/OUTCOME with fighter1-perspective W/L;
ufc_event_details.csv: EVENT/DATE). Known quirk: EVENT values carry a
trailing space in results but not in event details — strip everything.

Append-only: existing rows in results.csv are never modified.
"""
from __future__ import annotations

import argparse
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

BASE = "https://raw.githubusercontent.com/Greco1899/scrape_ufc_stats/main"


def nrm(x: object) -> str:
    s = unicodedata.normalize("NFKD", str(x))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return " ".join("".join(c if c.isalnum() else " " for c in s).split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--movement-dir", type=Path, default=Path(__file__).resolve().parent)
    args = ap.parse_args()
    md = args.movement_dir
    now = pd.Timestamp(datetime.now(timezone.utc))

    led = pd.read_csv(md / "ledger/signals.csv")
    led["event_start"] = pd.to_datetime(led.event_start, utc=True, format="mixed")
    res_p = md / "results/results.csv"
    res = pd.read_csv(res_p) if res_p.exists() else pd.DataFrame(
        columns=["signal_key", "winner_key", "method", "source", "fetched_at"])
    have = set(res.signal_key)

    pending = led[led.tier.isin(["A", "B"]) & (led.event_start + pd.Timedelta(hours=6) < now)
                  & ~led.signal_key.isin(have)]
    if not len(pending):
        print("no pending settlements"); return

    fights = pd.read_csv(f"{BASE}/ufc_fight_results.csv")
    events = pd.read_csv(f"{BASE}/ufc_event_details.csv")
    events["EVENT"] = events.EVENT.str.strip()
    events["date"] = pd.to_datetime(events.DATE, format="mixed", errors="coerce")
    fights["EVENT"] = fights.EVENT.str.strip()
    fights = fights.merge(events[["EVENT", "date"]], on="EVENT", how="left")
    parts = fights.BOUT.str.split(r"\s+vs\.?\s+", regex=True, n=1, expand=True)
    fights["k1"], fights["k2"] = parts[0].map(nrm), parts[1].map(nrm)

    new_rows = []
    for _, r in pending.iterrows():
        pair = set(r.signal_key.rsplit("|", 1)[0].split("|"))
        ev_date = r.event_start.tz_localize(None).normalize()
        cand = fights[(fights.k1.isin(pair)) & (fights.k2.isin(pair)) &
                      (fights.date.notna()) &
                      ((fights.date - ev_date).abs() <= pd.Timedelta(days=3))]
        if not len(cand):
            print(f"no mirror result yet: {r.signal_key}"); continue
        f = cand.iloc[0]
        out = str(f.OUTCOME).strip().upper()
        if out == "W/L":
            winner = f.k1
        elif out == "L/W":
            winner = f.k2
        elif "D" in out.split("/"):
            winner = "draw"
        else:
            winner = "nc"
        new_rows.append({"signal_key": r.signal_key, "winner_key": winner,
                         "method": str(f.METHOD).strip(), "source": "ufcstats_public_mirror",
                         "fetched_at": str(now)})
        print(f"settled: {r.signal_key} -> {winner} ({str(f.METHOD).strip()})")
    if new_rows:
        (md / "results").mkdir(exist_ok=True)
        pd.concat([res, pd.DataFrame(new_rows)], ignore_index=True).to_csv(res_p, index=False)
    print(f"appended {len(new_rows)} results")


if __name__ == "__main__":
    main()
