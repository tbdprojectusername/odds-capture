#!/usr/bin/env python3
"""MOV-HOLD-2 weekly grader.

For signals whose event has started (>=6h ago): freeze the close (last quote
before start), compute realized CLV vs Pinnacle close (primary) and retail
consensus close (secondary). Settlement (win/loss) comes from
results/results.csv when present (columns: signal_key, winner_key,
method[optional]); rows without a result stay status=pending_settlement.

Also appends settled fights to reference/fights_log.csv (source=capture) so
prior-fight counts stay current, and rewrites DASHBOARD.md.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from score_signals import load_capture, bfo_pairs, consensus_at, pinnacle_at


def cluster_ci(d: pd.DataFrame, col: str, cluster: str = "event_start"):
    z = d[[cluster, col]].dropna()
    n = len(z)
    if n == 0:
        return (np.nan, np.nan, np.nan)
    mu = z[col].mean()
    s = (z[col] - mu).groupby(z[cluster]).sum().to_numpy()
    G = len(s)
    if G <= 1:
        return (float(mu), np.nan, np.nan)
    se = np.sqrt((G / (G - 1)) * np.sum(s * s) / n ** 2)
    return (float(mu), float(mu - 1.96 * se), float(mu + 1.96 * se))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent.parent / "data")
    ap.add_argument("--movement-dir", type=Path, default=Path(__file__).resolve().parent)
    args = ap.parse_args()
    md = args.movement_dir
    now = pd.Timestamp(datetime.now(timezone.utc))

    ledger_p = md / "ledger/signals.csv"
    if not ledger_p.exists():
        print("no signals yet"); return
    led = pd.read_csv(ledger_p)
    led["event_start"] = pd.to_datetime(led.event_start, utc=True, format="mixed")
    graded_p = md / "ledger/graded.csv"
    graded = pd.read_csv(graded_p) if graded_p.exists() else pd.DataFrame(columns=["signal_key"])
    done = set(graded.signal_key) if len(graded) else set()

    results_p = md / "results/results.csv"
    results = pd.read_csv(results_p) if results_p.exists() else pd.DataFrame(columns=["signal_key", "winner_key"])
    rmap = dict(zip(results.signal_key, results.winner_key))

    bfo, pin = load_capture(args.data_dir)
    z = bfo_pairs(bfo)

    new_rows = []
    for _, r in led.iterrows():
        if r.signal_key in done or pd.isna(r.event_start):
            continue
        if str(r.tier) not in ("A", "B"):
            continue
        if now < r.event_start + pd.Timedelta(hours=6):
            continue
        pair = r.signal_key.rsplit("|", 1)[0]
        f1 = sorted(pair.split("|"))[0]
        sel_is_f1 = r.selected_fighter == f1

        close_cons = consensus_at(z, pair, t_max=r.event_start)
        close_pin = pinnacle_at(pin, pair, t_max=r.event_start)
        q_sel_close_cons = q_sel_close_pin = np.nan
        if close_cons is not None:
            q_sel_close_cons = close_cons["q1"] if sel_is_f1 else 1 - close_cons["q1"]
        if close_pin is not None:
            q_sel_close_pin = close_pin["q1"] if sel_is_f1 else 1 - close_pin["q1"]
        clv_cons = 100 * (q_sel_close_cons - r.entry_q_sel) if np.isfinite(q_sel_close_cons) else np.nan
        clv_pin = 100 * (q_sel_close_pin - r.entry_q_sel) if np.isfinite(q_sel_close_pin) else np.nan

        winner = rmap.get(r.signal_key)
        # V8 F1: ROI exists only for real paper fills. Signal CLV is always graded;
        # a synthetic fill at the minimum price is never invented.
        filled = bool(r.get("paper_filled", False))
        sel_won = np.nan
        if winner is None or (isinstance(winner, float) and np.isnan(winner)):
            status, unit = "pending_settlement", np.nan
        elif str(winner) in ("draw", "nc"):
            status, unit = ("void", 0.0) if filled else ("void_unfilled", np.nan)
        else:
            sel_won = bool(str(winner) == str(r.selected_fighter))
            if not filled:
                status, unit = "settled_unfilled", np.nan
            else:
                price = float(r.paper_fill_dec)
                unit = (price - 1) if sel_won else -1.0
                status = "settled"
        new_rows.append({
            "signal_key": r.signal_key, "graded_at": str(now), "tier": r.tier,
            "selected_side": r.selected_side, "counts_prospective": r.counts_prospective,
            "event_start": str(r.event_start),
            "clv_pp_vs_pinnacle_close": round(clv_pin, 3) if np.isfinite(clv_pin) else np.nan,
            "clv_pp_vs_consensus_close": round(clv_cons, 3) if np.isfinite(clv_cons) else np.nan,
            # V8 F13: a close is only as good as its age; record snapshot staleness.
            "close_pinnacle_t": str(close_pin["t"]) if close_pin is not None else "",
            "close_pinnacle_gap_min": round((r.event_start - close_pin["t"]).total_seconds() / 60, 1)
                                      if close_pin is not None else np.nan,
            "close_consensus_t": str(close_cons["t"]) if close_cons is not None else "",
            "close_consensus_gap_min": round((r.event_start - close_cons["t"]).total_seconds() / 60, 1)
                                       if close_cons is not None else np.nan,
            "paper_filled": filled,
            # V8-recheck R2: carry the remediation cohort boundary into grades.
            "pre_remediation": bool(r.get("pre_remediation", False)),
            "roi_cohort_eligible": bool(r.get("roi_cohort_eligible", False)),
            "selected_won": sel_won,   # fight outcome, independent of paper fill
            "status": status, "unit_return": unit,
            "stake_fraction": r.stake_fraction,
        })
    if new_rows:
        graded = pd.concat([graded, pd.DataFrame(new_rows)], ignore_index=True)
        (md / "ledger").mkdir(exist_ok=True)
        graded.to_csv(graded_p, index=False)

    # append settled fights to fights_log so priors stay current
    if len(results):
        logp = md / "reference/fights_log.csv"
        flog = pd.read_csv(logp, parse_dates=["event_date"])
        have = set(zip(flog.name_key, flog.event_date.astype(str)))
        adds = []
        settled = led[led.signal_key.isin(results.signal_key)]
        for _, r in settled.iterrows():
            pair = r.signal_key.rsplit("|", 1)[0]
            d = pd.to_datetime(r.event_start).tz_localize(None).normalize()
            for k in pair.split("|"):
                if (k, str(d)) not in have:
                    adds.append({"name": k, "dob": np.nan, "event_date": d,
                                 "name_key": k, "source": "capture"})
        if adds:
            pd.concat([flog, pd.DataFrame(adds)], ignore_index=True).to_csv(logp, index=False)

    # Dashboard rendering lives in morning_brief.py (run it after this script).
    print(json.dumps({"graded_new": len(new_rows), "graded_total": len(graded)}, indent=1))


if __name__ == "__main__":
    main()
