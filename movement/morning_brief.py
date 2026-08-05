#!/usr/bin/env python3
"""Daily morning brief: refresh DASHBOARD.md and emit a digest for the alert issue.

Run after grade_ledger.py. Rewrites the dashboard every run; writes
state/new_brief.json only when there is something to say (new signals in the
last 24h, actionability flips, freshly graded results, real-bet settlements,
or events starting within 48h that carry open bets).
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from score_signals import load_capture, bfo_pairs, consensus_at, pinnacle_at, dec_to_amer


def live_best(z, pin, signal_key, selected_fighter):
    pair = signal_key.rsplit("|", 1)[0]
    f1 = sorted(pair.split("|"))[0]
    sel_is_f1 = selected_fighter == f1
    best, book = np.nan, ""
    c = consensus_at(z, pair)
    if c is not None:
        best = c["best_dec1"] if sel_is_f1 else c["best_dec2"]
        book = c["best_dec1_book"] if sel_is_f1 else c["best_dec2_book"]
    p = pinnacle_at(pin, pair)
    if p is not None:
        d = p["dec1"] if sel_is_f1 else p["dec2"]
        if pd.isna(best) or d > best:
            best, book = d, "Pinnacle"
    return best, book


def fmt_money(x, ccy="CAD"):
    return f"{ccy} {x:,.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent.parent / "data")
    ap.add_argument("--movement-dir", type=Path, default=Path(__file__).resolve().parent)
    args = ap.parse_args()
    md = args.movement_dir
    now = pd.Timestamp(datetime.now(timezone.utc))

    pol = json.loads((md / "specs/mov_hold_2_policy_spec.json").read_text(encoding="utf-8"))
    policy_id = pol.get("policy_id", "MOV-HOLD-?")
    led = pd.read_csv(md / "ledger/signals.csv")
    led["event_start"] = pd.to_datetime(led.event_start, utc=True, format="mixed")
    led["scored_at"] = pd.to_datetime(led.scored_at, utc=True, format="mixed")
    # American columns are regenerated from decimals for display — CSV round-trips
    # coerce "+240" to 240.0 and drop signs.
    for dc, ac in [("best_dec", "best_amer"), ("min_acceptable_dec", "min_acceptable_amer"),
                   ("est_board_close_dec", "est_board_close_amer"),
                   ("entry_consensus_dec", "entry_consensus_amer")]:
        if dc in led:
            led[ac] = pd.to_numeric(led[dc], errors="coerce").map(
                lambda d: dec_to_amer(d) if pd.notna(d) else "")
    graded_p = md / "ledger/graded.csv"
    graded = pd.read_csv(graded_p) if graded_p.exists() else pd.DataFrame(columns=["signal_key", "status"])
    real_p = md / "ledger/real_bets.csv"
    real = pd.read_csv(real_p) if real_p.exists() else pd.DataFrame()

    bfo, pin = load_capture(args.data_dir)
    z = bfo_pairs(bfo)

    open_led = led[led.tier.isin(["A", "B"]) & (led.event_start > now)].copy()
    nows, books, flips = [], [], {}
    state_p = md / "state/brief_state.json"
    prev = json.loads(state_p.read_text()) if state_p.exists() else {"actionable": {}, "last_brief": "1970-01-01T00:00:00Z"}
    for _, r in open_led.iterrows():
        b, bk = live_best(z, pin, r.signal_key, r.selected_fighter)
        nows.append(b); books.append(bk)
        ok = bool(pd.notna(b) and b >= r.min_acceptable_dec)
        prev_ok = prev["actionable"].get(r.signal_key)
        if prev_ok is not None and prev_ok != ok:
            flips[r.signal_key] = (r.selected_fighter, ok)
        prev["actionable"][r.signal_key] = ok
    open_led["now_dec"] = nows
    open_led["now_amer"] = [dec_to_amer(x) if pd.notna(x) else "" for x in nows]
    open_led["now_book"] = books
    open_led["clears_min"] = open_led.now_dec >= open_led.min_acceptable_dec

    gmap = graded.set_index("signal_key").to_dict("index") if len(graded) else {}

    # ---------------- dashboard ----------------
    L = [f"# {policy_id} dashboard", "",
         f"Updated {now:%Y-%m-%d %H:%M} UTC · policy `{policy_id}` · paper bankroll $10,000 · "
         f"signals {len(led[led.tier.isin(['A','B'])])} (A {len(led[led.tier.eq('A')])} / B {len(led[led.tier.eq('B')])}) · "
         f"graded {len(graded)}", ""]

    if len(real):
        L += ["## Real bets", "", "| Fighter | Tier | Fill | Stake | To win | Line now | Proj. close | Status |",
              "|---|---|---|---|---|---|---|---|"]
        pnl_all = 0.0; pnl_proto = 0.0; any_settled = False
        for _, rb in real.iterrows():
            sig = led[led.signal_key.eq(rb.signal_key)]
            proj = sig.est_board_close_amer.iloc[0] if len(sig) else ""
            g = gmap.get(rb.signal_key, {})
            status = rb.status
            live_row = open_led[open_led.signal_key.eq(rb.signal_key)]
            now_a = live_row.now_amer.iloc[0] if len(live_row) else ""
            # real settlement follows the fight result (selected_won), independent
            # of paper-fill status
            if g.get("status") in ("settled", "settled_unfilled") and pd.notna(g.get("selected_won", np.nan)):
                won = bool(g["selected_won"])
                pnl = rb.to_win if won else -rb.stake
                pnl_all += pnl; any_settled = True
                if bool(rb.get("protocol_eligible", False)):
                    pnl_proto += pnl
                status = f"{'WON' if won else 'LOST'} {fmt_money(pnl, rb.currency)}"
            elif g.get("status") in ("void", "void_unfilled"):
                status = "VOID"
            flag = "" if bool(rb.get("protocol_eligible", False)) else " †"
            L.append(f"| {rb.fighter}{flag} | {rb.tier} | {int(rb.price_amer)} | {fmt_money(rb.stake, rb.currency)} | "
                     f"{fmt_money(rb.to_win, rb.currency)} | {now_a} | {proj} | {status} |")
        if any_settled:
            # V8-recheck R5: never label combined discretionary cash as system performance.
            L.append(f"\n**Protocol-eligible real P&L: {fmt_money(pnl_proto)}** · "
                     f"all discretionary cash P&L (incl. exceptions): {fmt_money(pnl_all)}")
        if (~real.get("protocol_eligible", pd.Series(dtype=bool)).astype(bool)).any():
            L.append("\n† exception or unconfirmed fill — excluded from protocol P&L "
                     "(see ledger/real_bets.csv exception_reason).")
        if (real.price_source != "user_confirmed").any():
            L.append("\n\\* fill price assumed from capture — correct in `ledger/real_bets.csv` if different.")
        L.append("")

    real_unit = float(pol.get("real_bets_stage0", {}).get("real_unit_usd", 0))
    for tier, label in [("A", "Open positions — Tier A"),
                        ("B", "Open positions — Tier B (evidence cohort, paper only)")]:
        t = open_led[open_led.tier.eq(tier)].sort_values("event_start")
        if not len(t):
            continue
        L += [f"## {label}", "",
              "| Bet | Side | Event | Entry | Now | Min | Proj. close | Pred CLV | **Real (Stage 0)** | Paper Kelly | Clears min |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for _, r in t.iterrows():
            real = f"**${real_unit:,.0f}**" if (tier == "A" and real_unit > 0) else "$0 (paper)"
            L.append(f"| {r.selected_fighter} | {r.selected_side} | {r.event_start:%b %d} | {r.best_amer} | "
                     f"{r.now_amer} ({r.now_book}) | {r.min_acceptable_amer} | {r.est_board_close_amer} | "
                     f"{r.pred_clv_pp:+.1f}pp | {real} | ${r.stake_usd:,.0f} | {'✅' if r.clears_min else '❌ PASS'} |")
        L.append("")
    L.append(f"Real Stage-0 unit: ${real_unit:,.0f} flat per A-signal at min price or better "
             "(your actual fills are logged as placed; paper Kelly is the shadow-evidence sizing). ")
    L.append("")

    if len(graded):
        g = graded[graded.get("counts_prospective", pd.Series(dtype=bool)).astype(bool)] if "counts_prospective" in graded else graded
        if len(g):
            # V8-recheck R2: ROI only from the remediation-eligible cohort; CLV for
            # pre-remediation rows is descriptive and labelled as such.
            L += ["## Prospective performance (counted signals)", ""]
            elig_col = g.get("roi_cohort_eligible", pd.Series(False, index=g.index)).fillna(False).astype(bool)
            pre_col = g.get("pre_remediation", pd.Series(False, index=g.index)).fillna(False).astype(bool)
            for (tier, side), gg in g.groupby(["tier", "selected_side"]):
                clv = gg.clv_pp_vs_pinnacle_close.mean()
                el = gg[elig_col.reindex(gg.index).fillna(False)]
                settled = el[el.status.eq("settled") & el.unit_return.notna()]
                roi = settled.unit_return.mean() if len(settled) else np.nan
                pre_n = int(pre_col.reindex(gg.index).fillna(False).sum())
                L.append(f"- Tier {tier} / {side}: n={len(gg)} (pre-remediation {pre_n}), "
                         f"CLV vs Pinnacle close {clv:+.2f}pp, ROI-eligible settled {len(settled)}"
                         + ("" if pd.isna(roi) else f", flat ROI {roi:+.1%}"))
            L.append("\nROI counts only `roi_cohort_eligible` fills (scored ≥ remediation_ts); "
                     "pre-remediation rows contribute CLV description only.\n")

    upcoming = open_led.groupby(open_led.event_start.dt.date).agg(
        signals=("signal_key", "size"), staked=("stake_usd", "sum")).reset_index()
    if len(upcoming):
        L += ["## Upcoming", ""]
        for _, u in upcoming.iterrows():
            L.append(f"- **{u.event_start}**: {u.signals} open signals, ${u.staked:,.0f} paper staked")
        L.append("")
    L.append("Pass/fail bars: PREREG.md · staking: STAKING.md · this file is bot-written; edits will be overwritten.")
    (md / "DASHBOARD.md").write_text("\n".join(L), encoding="utf-8")

    # ---------------- digest ----------------
    last_brief = pd.Timestamp(prev.get("last_brief", "1970-01-01T00:00:00Z"))
    new_sigs = led[(led.scored_at > now - pd.Timedelta(hours=24)) & led.tier.isin(["A", "B"])]
    newly_graded = graded[pd.to_datetime(graded.get("graded_at", pd.Series(dtype=str)), utc=True,
                                         format="mixed", errors="coerce") > last_brief] if len(graded) else graded
    soon = open_led[open_led.event_start <= now + pd.Timedelta(hours=48)]
    sections = []
    if len(new_sigs):
        sections.append("**New signals (24h):** " + "; ".join(
            f"[{r.tier}] {r.selected_fighter} ({r.selected_side}) min {r.min_acceptable_amer}, "
            f"now {open_led[open_led.signal_key.eq(r.signal_key)].now_amer.iloc[0] if len(open_led[open_led.signal_key.eq(r.signal_key)]) else '?'}"
            for _, r in new_sigs.iterrows()))
    if flips:
        sections.append("**Actionability changes:** " + "; ".join(
            f"{f} {'is now BETTABLE' if ok else 'dropped below minimum — PASS'}" for f, ok in flips.values()))
    if len(newly_graded):
        parts = []
        for _, gr in newly_graded.iterrows():
            fighter = led[led.signal_key.eq(gr.signal_key)].selected_fighter
            nm = fighter.iloc[0] if len(fighter) else gr.signal_key
            clv = gr.get("clv_pp_vs_pinnacle_close")
            parts.append(f"{nm}: CLV {clv:+.2f}pp, {gr.status}")
        sections.append("**Graded since last brief:** " + "; ".join(parts))
    if len(soon):
        sections.append("**Events within 48h:** " + "; ".join(
            f"{r.selected_fighter} ({r.event_start:%a %H:%M} UTC)" for _, r in soon.iterrows()))
    brief_p = md / "state/new_brief.json"
    if sections:
        brief_p.write_text(json.dumps({"date": f"{now:%Y-%m-%d}", "sections": sections}, indent=1), encoding="utf-8")
    elif brief_p.exists():
        brief_p.unlink()

    prev["last_brief"] = str(now)
    state_p.write_text(json.dumps(prev, indent=1), encoding="utf-8")
    print(json.dumps({"dashboard": "written", "digest_sections": len(sections)}, indent=1))


if __name__ == "__main__":
    main()
