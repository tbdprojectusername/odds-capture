#!/usr/bin/env python3
"""MOV-HOLD-2 prospective scorer.

Runs after each odds poll. Detects newly quoted UFC moneylines, freezes their
open, scores the frozen MOV-MKT-2 movement model, applies the pre-registered
gates, and appends signals to an append-only ledger. Pure pandas/numpy — the
frozen spec JSON carries every coefficient, median and scale.

Design rules (see PREREG.md — changes there first, code second):
- A pair+event scores exactly once (state file). No rescoring on line moves,
  no chasing, no rebets.
- Model features use the frozen OPEN (first two-sided sighting). The EV gate
  and minimum price are evaluated at the ENTRY quote (latest consensus at
  scoring time) — that is the price a bettor can actually get.
- A signal only counts toward the prospective cohorts if discovery_lag_h <= 168
  and the event is >= 24h away; late discoveries are logged but flagged.
"""
from __future__ import annotations

import argparse
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

RETAIL_BOOKS = ["BetWay", "Caesars", "BetRivers", "FanDuel", "Unibet"]
EXCHANGES = {"Kalshi", "Polymarket"}

STAT_DIFF_MAP = {
    "win_ratio_dec_avg_diff_fav": "win_ratio_dec_avg",
    "sig_str_land_per_min_dec_avg_diff_fav": "sig_str_land_per_min_dec_avg",
    "sig_str_def_dec_avg_diff_fav": "sig_str_def_dec_avg",
    "td_land_per_min_dec_avg_diff_fav": "td_land_per_min_dec_avg",
    "td_def_dec_avg_diff_fav": "td_def_dec_avg",
    "sub_att_per_min_dec_avg_diff_fav": "sub_att_per_min_dec_avg",
    "ko_sub_per_win_dec_avg_diff_fav": "ko_sub_per_win_dec_avg",
}


def nrm(x: object) -> str:
    s = unicodedata.normalize("NFKD", str(x))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return " ".join("".join(c if c.isalnum() else " " for c in s).split())


def amer_to_dec(a: float) -> float:
    a = float(a)
    return 1 + a / 100 if a > 0 else 1 + 100 / (-a)


def dec_to_amer(d: float) -> str:
    if not np.isfinite(d) or d <= 1:
        return ""
    return f"+{round((d - 1) * 100)}" if d >= 2 else str(round(-100 / (d - 1)))


def load_capture(data_dir: Path):
    bfo = pd.concat([pd.read_csv(p) for p in sorted(data_dir.glob("bfo_*.csv"))[-2:]],
                    ignore_index=True)
    bfo = bfo[bfo.row_kind.eq("moneyline") & bfo.american.notna()].copy()
    bfo["t"] = pd.to_datetime(bfo.poll_time, utc=True, format="mixed")
    bfo["sel_key"] = bfo.selection.map(nrm)
    pin = pd.concat([pd.read_csv(p) for p in sorted(data_dir.glob("pinnacle_*.csv"))[-2:]],
                    ignore_index=True)
    pin = pin[pin.bet_type.eq("ml") & pin.period.eq(0) & pin.american.notna()].copy()
    pin["t"] = pd.to_datetime(pin.poll_time, utc=True, format="mixed")
    pin["home_key"], pin["away_key"] = pin.home.map(nrm), pin.away.map(nrm)
    pin["pair"] = np.where(pin.home_key < pin.away_key,
                           pin.home_key + "|" + pin.away_key,
                           pin.away_key + "|" + pin.home_key)
    return bfo, pin


def bfo_pairs(bfo: pd.DataFrame) -> pd.DataFrame:
    """Two-sided retail quotes per (event_slug, matchup_id, poll, book)."""
    z = bfo[bfo.book.isin(RETAIL_BOOKS)].copy()
    keys = ["t", "event_slug", "matchup_id", "book"]
    z["n_sides"] = z.groupby(keys).sel_key.transform("nunique")
    z = z[z.n_sides.eq(2)].copy()
    z["dec"] = z.american.map(amer_to_dec)
    z["raw"] = 1 / z.dec
    z["pair"] = z.groupby(keys).sel_key.transform(lambda s: "|".join(sorted(s.unique())))
    return z


def consensus_at(z: pd.DataFrame, pair: str, t_max=None, t_min=None):
    """Mean two-sided no-vig q for the alphabetically-first fighter + mean raw
    decimal per side across retail books at the latest poll <= t_max."""
    g = z[z.pair.eq(pair)]
    if t_max is not None:
        g = g[g.t.le(t_max)]
    if t_min is not None:
        g = g[g.t.ge(t_min)]
    if g.empty:
        return None
    t_use = g.t.max()
    g = g[g.t.eq(t_use)]
    f1 = sorted(pair.split("|"))[0]
    per_book = []
    for book, gb in g.groupby("book"):
        s = gb.groupby("sel_key").agg(raw=("raw", "mean"), dec=("dec", "mean"))
        if len(s) != 2 or f1 not in s.index:
            continue
        tot = s.raw.sum()
        per_book.append({"book": book, "q1": s.loc[f1].raw / tot, "vig": tot - 1,
                         "dec1": s.loc[f1].dec, "dec2": s.dec.drop(f1).iloc[0]})
    if not per_book:
        return None
    pb = pd.DataFrame(per_book)
    return {"t": t_use, "q1": pb.q1.mean(), "vig": pb.vig.mean(),
            "dec1": pb.dec1.mean(), "dec2": pb.dec2.mean(), "n_books": len(pb),
            "best_dec1": pb.dec1.max(), "best_dec1_book": pb.loc[pb.dec1.idxmax(), "book"],
            "best_dec2": pb.dec2.max(), "best_dec2_book": pb.loc[pb.dec2.idxmax(), "book"]}


def pinnacle_at(pin: pd.DataFrame, pair: str, t_max=None):
    g = pin[pin.pair.eq(pair)]
    if t_max is not None:
        g = g[g.t.le(t_max)]
    if g.empty:
        return None
    t_use = g.t.max()
    g = g[g.t.eq(t_use)]
    f1 = sorted(pair.split("|"))[0]
    g = g.assign(sel_key=np.where(g.side.eq("home"), g.home_key, g.away_key),
                 dec=g.american.map(amer_to_dec))
    s = g.groupby("sel_key").dec.mean()
    if len(s) != 2 or f1 not in s.index:
        return None
    raw = 1 / s
    return {"t": t_use, "q1": raw.loc[f1] / raw.sum(), "vig": raw.sum() - 1,
            "dec1": s.loc[f1], "dec2": s.drop(f1).iloc[0],
            "start": g.start_time.iloc[0]}


def head_score(head: dict, feat: dict, division: str) -> float:
    co = dict(zip(head["transformed_features"], head["coefficients"]))
    z = head["intercept"]
    for f in head["numeric_features"]:
        x = feat.get(f, np.nan)
        if pd.isna(x):
            x = head["numeric_medians"][f]
        z += co.get("num__" + f, 0.0) * (
            (float(x) - head["numeric_means_after_impute"][f]) / head["numeric_scales"][f])
    z += co.get(f"cat__division_{division}", 0.0)
    return float(z)


def cliplogit(q):
    q = np.clip(q, 1e-4, 1 - 1e-4)
    return float(np.log(q / (1 - q)))


def fighter_features(key: str, asof: pd.Timestamp, log: pd.DataFrame, static: pd.DataFrame):
    g = log[(log.name_key.eq(key)) & (log.event_date < asof)]
    n = len(g)
    dsl = (asof - g.event_date.max()).days if n else np.nan
    ufc = (asof - g.event_date.min()).days / 365.25 if n else np.nan
    row = static[static.name_key.eq(key)]
    st = row.iloc[0] if len(row) else None
    dob = pd.to_datetime(st.dob) if st is not None and pd.notna(st.dob) else pd.NaT
    if pd.notna(dob) and dob.tzinfo is None:
        dob = dob.tz_localize("UTC")
    age = (asof - dob).days / 365.25 if pd.notna(dob) else np.nan
    return {"n": n, "dsl": dsl, "ufc": ufc, "st": st, "age": age,
            "matched": st is not None, "division": st.division_last if st is not None else "Unknown"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent.parent / "data")
    ap.add_argument("--movement-dir", type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument("--now", default=None, help="override 'now' for tests (ISO)")
    args = ap.parse_args()
    md = args.movement_dir
    now = pd.Timestamp(args.now) if args.now else pd.Timestamp(datetime.now(timezone.utc))
    if now.tzinfo is None:
        now = now.tz_localize("UTC")

    spec = json.loads((md / "specs/mov_mkt_2_model_spec.json").read_text(encoding="utf-8"))
    pol = json.loads((md / "specs/mov_hold_2_policy_spec.json").read_text(encoding="utf-8"))
    ga, gb = pol["tiers"]["A"], pol["tiers"]["B"]
    exec_floor = pol["execution"]["min_executable_ev"]

    static = pd.read_csv(md / "reference/fighters_static.csv")
    log = pd.read_csv(md / "reference/fights_log.csv", parse_dates=["event_date"])
    log["event_date"] = pd.to_datetime(log.event_date).dt.tz_localize("UTC")
    women = set(pd.read_csv(md / "reference/women_keys.csv").name_key)
    # V8 F7/F12: append-only reviewed bout classification (signal_key, domain).
    # Unmatched fighters fail CLOSED until a human classifies the bout as men's.
    domp = md / "reference/bout_domain.csv"
    domains = (pd.read_csv(domp).set_index("signal_key").domain.to_dict()
               if domp.exists() else {})
    static_keys = set(static.name_key)

    bfo, pin = load_capture(args.data_dir)
    z = bfo_pairs(bfo)

    state_p = md / "state/first_seen.csv"
    state = pd.read_csv(state_p, parse_dates=["first_seen", "start_time"]) if state_p.exists() else \
        pd.DataFrame(columns=["signal_key", "pair", "first_seen", "start_time", "open_q1",
                              "open_vig", "open_dec1", "open_dec2", "open_n_books", "open_source"])
    ledger_p = md / "ledger/signals.csv"
    ledger = pd.read_csv(ledger_p) if ledger_p.exists() else pd.DataFrame()
    seen_keys = set(state.signal_key) if len(state) else set()
    scored_keys = set(ledger.signal_key) if len(ledger) else set()

    # -------- discover pairs + starts (Pinnacle is the start-time authority) -------
    starts = (pin.dropna(subset=["start_time"]).groupby("pair").start_time.max())
    all_pairs = sorted(set(z.pair.unique()) | set(pin.pair.unique()))
    new_state = []
    for pair in all_pairs:
        st_raw = starts.get(pair)
        start = pd.to_datetime(st_raw, utc=True) if st_raw is not None else pd.NaT
        skey = f"{pair}|{start.date()}" if pd.notna(start) else f"{pair}|unknown"
        if skey in seen_keys or f"{pair}|unknown" in seen_keys and pd.isna(start):
            continue
        # first two-sided sighting: earliest retail-book poll, else earliest Pinnacle poll
        gz = z[z.pair.eq(pair)]
        first_retail = gz.t.min() if len(gz) else pd.NaT
        gp = pin[pin.pair.eq(pair)]
        first_pin = gp.t.min() if len(gp) else pd.NaT
        first_seen = min([t for t in [first_retail, first_pin] if pd.notna(t)], default=pd.NaT)
        if pd.isna(first_seen):
            continue
        cons = consensus_at(z, pair, t_max=first_seen + pd.Timedelta(minutes=15))
        src = "retail_consensus"
        if cons is None:
            p0 = pinnacle_at(pin, pair, t_max=first_seen + pd.Timedelta(minutes=15))
            if p0 is None:
                continue
            cons = {"q1": p0["q1"], "vig": p0["vig"], "dec1": p0["dec1"], "dec2": p0["dec2"],
                    "n_books": 1}
            src = "pinnacle"
        # resolve upgrades of previously-unknown starts
        if pd.notna(start) and f"{pair}|unknown" in seen_keys:
            state.loc[state.signal_key.eq(f"{pair}|unknown"), ["signal_key", "start_time"]] = [skey, start]
            seen_keys.discard(f"{pair}|unknown"); seen_keys.add(skey)
            continue
        new_state.append({"signal_key": skey, "pair": pair, "first_seen": first_seen,
                          "start_time": start, "open_q1": cons["q1"], "open_vig": cons["vig"],
                          "open_dec1": cons["dec1"], "open_dec2": cons["dec2"],
                          "open_n_books": cons["n_books"], "open_source": src})
        seen_keys.add(skey)
    if new_state:
        add = pd.DataFrame(new_state)
        state = add if state.empty else pd.concat([state, add], ignore_index=True)
    (md / "state").mkdir(exist_ok=True)
    state.to_csv(state_p, index=False)

    # ----------------- score unscored pairs with known future starts -----------------
    new_signals = []
    for _, srow in state.iterrows():
        skey = srow.signal_key
        if skey in scored_keys or pd.isna(srow.start_time):
            continue
        start = pd.to_datetime(srow.start_time, utc=True)
        pair = srow.pair
        f1_key, f2_key = sorted(pair.split("|"))
        # Domain guard: the model is trained on men's UFC bouts only. Women's
        # bouts are out-of-distribution (reference has no stats; imputation
        # fabricates debut profiles) and are excluded, matching the backtest.
        if f1_key in women or f2_key in women:
            new_signals.append({"signal_key": skey, "scored_at": str(now),
                                "event_start": str(start), "f1": f1_key, "f2": f2_key,
                                "tier": "excluded_womens", "counts_prospective": False,
                                "model_id": spec["model_id"], "policy_id": pol["policy_id"]})
            scored_keys.add(skey)
            continue
        # V8 F7: identity history cannot establish domain for unmatched fighters —
        # a debutante absent from women_keys would otherwise score as a male debut.
        # Fail closed until the bout is explicitly classified men's.
        if (f1_key not in static_keys or f2_key not in static_keys) and domains.get(skey) != "mens":
            new_signals.append({"signal_key": skey, "scored_at": str(now),
                                "event_start": str(start), "f1": f1_key, "f2": f2_key,
                                "tier": "excluded_unverified_domain", "counts_prospective": False,
                                "model_id": spec["model_id"], "policy_id": pol["policy_id"]})
            scored_keys.add(skey)
            continue
        # entry quote: latest consensus now (this is what you can bet)
        entry = consensus_at(z, pair)
        p_now = pinnacle_at(pin, pair)
        if entry is None and p_now is None:
            continue
        if entry is None:
            entry = {"q1": p_now["q1"], "vig": p_now["vig"], "dec1": p_now["dec1"],
                     "dec2": p_now["dec2"], "n_books": 1, "best_dec1": p_now["dec1"],
                     "best_dec1_book": "Pinnacle", "best_dec2": p_now["dec2"],
                     "best_dec2_book": "Pinnacle", "t": p_now["t"]}
        elif p_now is not None:
            if p_now["dec1"] > entry["best_dec1"]:
                entry["best_dec1"], entry["best_dec1_book"] = p_now["dec1"], "Pinnacle"
            if p_now["dec2"] > entry["best_dec2"]:
                entry["best_dec2"], entry["best_dec2_book"] = p_now["dec2"], "Pinnacle"

        # ---- frozen-open model features (favorite orientation from OPEN) ----
        q1_open = float(srow.open_q1)
        fav_is_f1 = q1_open >= 0.5
        qfav_open = q1_open if fav_is_f1 else 1 - q1_open
        fav_key, dog_key = (f1_key, f2_key) if fav_is_f1 else (f2_key, f1_key)
        ff = fighter_features(fav_key, start, log, static)
        fd = fighter_features(dog_key, start, log, static)
        zof = cliplogit(qfav_open)
        feat = {
            "z_open_fav": zof, "z_open_fav_sq": zof ** 2,
            "open_vig": float(srow.open_vig),
            "open_lead_days": (start - pd.to_datetime(srow.first_seen, utc=True)).total_seconds() / 86400,
            "age_diff_fav": ff["age"] - fd["age"] if pd.notna(ff["age"]) and pd.notna(fd["age"]) else np.nan,
            "prior_diff_fav": ff["n"] - fd["n"], "prior_sum": ff["n"] + fd["n"],
            "debut_mismatch": int((ff["n"] == 0) ^ (fd["n"] == 0)),
            "card_position_pct": np.nan,
            "days_since_last_fight_diff_fav": ff["dsl"] - fd["dsl"] if pd.notna(ff["dsl"]) and pd.notna(fd["dsl"]) else np.nan,
            "ufcage_diff_fav": ff["ufc"] - fd["ufc"] if pd.notna(ff["ufc"]) and pd.notna(fd["ufc"]) else np.nan,
        }
        sf, sd = ff["st"], fd["st"]
        feat["reach_diff_fav"] = (sf.reach - sd.reach) if sf is not None and sd is not None and pd.notna(sf.reach) and pd.notna(sd.reach) else np.nan
        for f, b in STAT_DIFF_MAP.items():
            v1 = sf[b] if sf is not None else np.nan
            v2 = sd[b] if sd is not None else np.nan
            feat[f] = (v1 - v2) if pd.notna(v1) and pd.notna(v2) else np.nan
        division = ff["division"] if ff["division"] != "Unknown" else fd["division"]

        delta = head_score(spec["movement_head"], feat, division)
        p_steam_fav = 1 / (1 + np.exp(-head_score(spec["direction_head"], feat, division)))
        pred_qclose_fav = 1 / (1 + np.exp(-(zof + delta)))
        b1, b3 = spec["market_calibrator"]["coefficients"]
        zc = cliplogit(pred_qclose_fav)
        p_mkt_fav = 1 / (1 + np.exp(-(b1 * zc + b3 * zc ** 3)))

        # ---- entry prices oriented to fav/dog ----
        e_dec1, e_dec2 = float(entry["dec1"]), float(entry["dec2"])
        O_fav, O_dog = (e_dec1, e_dec2) if fav_is_f1 else (e_dec2, e_dec1)
        best_fav, best_fav_bk = (entry["best_dec1"], entry["best_dec1_book"]) if fav_is_f1 else (entry["best_dec2"], entry["best_dec2_book"])
        best_dog, best_dog_bk = (entry["best_dec2"], entry["best_dec2_book"]) if fav_is_f1 else (entry["best_dec1"], entry["best_dec1_book"])
        ev_fav = p_mkt_fav * O_fav - 1
        ev_dog = (1 - p_mkt_fav) * O_dog - 1
        sel_fav = ev_fav >= ev_dog
        sel = {
            "side": "favorite" if sel_fav else "underdog",
            "fighter_key": fav_key if sel_fav else dog_key,
            "p": p_mkt_fav if sel_fav else 1 - p_mkt_fav,
            "ev": ev_fav if sel_fav else ev_dog,
            "odds": O_fav if sel_fav else O_dog,
            "best": best_fav if sel_fav else best_dog,
            "best_bk": best_fav_bk if sel_fav else best_dog_bk,
            "steam": p_steam_fav if sel_fav else 1 - p_steam_fav,
            "pred_clv_pp": 100 * ((pred_qclose_fav - qfav_open) if sel_fav else (qfav_open - pred_qclose_fav)),
        }
        tier = ""
        if sel["ev"] >= ga["min_ev"] and sel["steam"] >= ga["min_steam"] and sel["pred_clv_pp"] >= ga["min_pred_clv_pp"]:
            tier = "A"
        elif sel["ev"] >= gb["min_ev"] and sel["steam"] >= gb["min_steam"] and sel["pred_clv_pp"] >= gb["min_pred_clv_pp"]:
            tier = "B"
        # V8 F10: also tag the tier under OPEN-quote EV (the audited gate basis),
        # holding model outputs and side selection fixed.
        o_dec1, o_dec2 = float(srow.open_dec1), float(srow.open_dec2)
        Of_o, Od_o = (o_dec1, o_dec2) if fav_is_f1 else (o_dec2, o_dec1)
        ev_open = (p_mkt_fav * Of_o - 1) if sel_fav else ((1 - p_mkt_fav) * Od_o - 1)
        open_tier = ""
        if ev_open >= ga["min_ev"] and sel["steam"] >= ga["min_steam"] and sel["pred_clv_pp"] >= ga["min_pred_clv_pp"]:
            open_tier = "A"
        elif ev_open >= gb["min_ev"] and sel["steam"] >= gb["min_steam"] and sel["pred_clv_pp"] >= gb["min_pred_clv_pp"]:
            open_tier = "B"
        min_price = (1 + exec_floor) / sel["p"]
        lag_h = (now - pd.to_datetime(srow.first_seen, utc=True)).total_seconds() / 3600
        hours_to_start = (start - now).total_seconds() / 3600
        counts = bool(tier) and lag_h <= 168 and hours_to_start >= 24
        clears_min = bool(sel["best"] >= min_price)
        actionable = bool(tier == "A" and clears_min and counts)
        # V8 F1: a threshold is not a fill. Paper execution exists only when the
        # captured best price clears the floor; size and grade only real fills.
        paper_filled = bool(tier in ("A", "B") and counts and clears_min)
        paper_fill_dec = float(sel["best"]) if paper_filled else np.nan
        kelly = (max((sel["p"] * paper_fill_dec - 1) / (paper_fill_dec - 1), 0.0)
                 if paper_filled else 0.0)
        stake = min(pol["sizing"]["kelly_fraction"] * kelly, pol["sizing"]["per_bet_cap"])
        if not counts or tier != "A" or not paper_filled:
            stake = 0.0   # A-tier Kelly stakes only; B-tier gets its flat unit below
        # entry no-vig q of selected side for CLV grading
        q1_entry = float(entry["q1"]) if "q1" in entry else q1_open
        qfav_entry = q1_entry if fav_is_f1 else 1 - q1_entry
        q_sel_entry = qfav_entry if sel_fav else 1 - qfav_entry

        new_signals.append({
            "signal_key": skey, "scored_at": str(now), "event_start": str(start),
            "f1": f1_key, "f2": f2_key, "selected_fighter": sel["fighter_key"],
            "selected_side": sel["side"], "tier": tier if tier else "none",
            "counts_prospective": counts, "discovery_lag_h": round(lag_h, 1),
            "open_q_sel": round(qfav_open if sel_fav else 1 - qfav_open, 5),
            "entry_q_sel": round(q_sel_entry, 5),
            "entry_consensus_dec": round(sel["odds"], 4),
            "entry_consensus_amer": dec_to_amer(sel["odds"]),
            "best_dec": round(float(sel["best"]), 4),
            "best_amer": dec_to_amer(float(sel["best"])), "best_book": sel["best_bk"],
            "min_acceptable_dec": round(min_price, 4),
            "min_acceptable_amer": dec_to_amer(min_price),
            "actionable_now": actionable,
            "clears_min_at_scoring": clears_min,
            "paper_filled": paper_filled,
            "paper_fill_dec": round(paper_fill_dec, 4) if np.isfinite(paper_fill_dec) else np.nan,
            "paper_fill_book": sel["best_bk"] if paper_filled else "",
            "paper_fill_time": str(now) if paper_filled else "",
            "p_market": round(sel["p"], 5), "ev_entry": round(sel["ev"], 5),
            "ev_open": round(float(ev_open), 5), "open_gate_tier": open_tier if open_tier else "none",
            "steam_prob": round(sel["steam"], 5), "pred_clv_pp": round(sel["pred_clv_pp"], 3),
            # projected close of the SELECTED side: fair (no-vig) and an
            # approximate board price re-applying the opening hold. Display only —
            # selection uses gates + entry EV, never these.
            "pred_close_q_sel": round(pred_qclose_fav if sel_fav else 1 - pred_qclose_fav, 5),
            "pred_fair_close_dec": round(1 / (pred_qclose_fav if sel_fav else 1 - pred_qclose_fav), 4),
            "est_board_close_dec": round(1 / min((pred_qclose_fav if sel_fav else 1 - pred_qclose_fav)
                                                 * (1 + float(srow.open_vig)), 0.999), 4),
            "stake_fraction": round(stake, 6),
            "open_n_books": int(srow.open_n_books), "open_source": srow.open_source,
            "fighters_matched": bool(ff["matched"] and fd["matched"]),
            "division_used": division,
            "model_id": spec["model_id"], "policy_id": pol["policy_id"],
        })
        scored_keys.add(skey)

    # ---- staking allocation (amendment 2026-08-05b) ----
    # Bespoke MOV-HOLD staking: quarter-Kelly at the takeable price, 5% per-bet
    # cap, NO event cap (card outcomes ~independent). Only guard: total A-tier
    # stake open at once <= open_exposure_ceiling; an over-ceiling batch scales
    # proportionally. Placed stakes never resize. B-tier: flat paper unit.
    bank = float(pol["sizing"].get("paper_bankroll_usd", 10000))
    b_unit = float(pol["sizing"].get("b_tier_unit_fraction", 0.005))
    ceiling = float(pol["sizing"].get("open_exposure_ceiling", 0.25))
    if new_signals:
        ns = pd.DataFrame(new_signals)
        prior_open = 0.0
        if len(ledger) and "stake_fraction" in ledger:
            old = ledger[ledger.get("tier", pd.Series(dtype=str)).eq("A")].copy()
            if len(old):
                unstarted = pd.to_datetime(old.event_start, utc=True, format="mixed") > now
                prior_open = float(old.loc[unstarted, "stake_fraction"].fillna(0).sum())
        amask = ns.tier.eq("A") & ns.counts_prospective & ns.paper_filled.fillna(False)
        bmask = ns.tier.eq("B") & ns.counts_prospective & ns.paper_filled.fillna(False)
        want = ns.loc[amask, "stake_fraction"].astype(float)
        budget = max(ceiling - prior_open, 0.0)
        if want.sum() > budget and want.sum() > 0:
            ns.loc[amask, "stake_fraction"] = (want * budget / want.sum()).round(6)
        ns["stake_usd"] = np.where(amask, (ns.stake_fraction.astype(float) * bank).round(2),
                          np.where(bmask, round(b_unit * bank, 2), 0.0))
        new_signals = ns.to_dict("records")

    (md / "ledger").mkdir(exist_ok=True)
    if new_signals:
        add = pd.DataFrame(new_signals)
        ledger = add if ledger.empty else pd.concat([ledger, add], ignore_index=True)
        # American columns are display strings; regenerate from decimals on every
        # write so CSV round-trips can never strip the "+" sign.
        for dc, ac in [("entry_consensus_dec", "entry_consensus_amer"),
                       ("best_dec", "best_amer"),
                       ("min_acceptable_dec", "min_acceptable_amer"),
                       ("pred_fair_close_dec", "pred_fair_close_amer"),
                       ("est_board_close_dec", "est_board_close_amer")]:
            if dc in ledger:
                ledger[ac] = pd.to_numeric(ledger[dc], errors="coerce").map(
                    lambda d: dec_to_amer(d) if pd.notna(d) else "")
        ledger.to_csv(ledger_p, index=False)
    alerts = [s for s in new_signals if s["tier"] in ("A", "B") and s["counts_prospective"]]
    (md / "state/new_alerts.json").write_text(json.dumps(alerts, indent=1), encoding="utf-8")
    print(json.dumps({"pairs_tracked": len(state), "newly_scored": len(new_signals),
                      "alerts": [{k: a.get(k) for k in ("tier", "selected_fighter", "selected_side",
                                                        "min_acceptable_amer", "min_acceptable_dec",
                                                        "best_amer", "best_book", "actionable_now",
                                                        "stake_usd", "event_start")} for a in alerts]}, indent=1))


if __name__ == "__main__":
    main()
