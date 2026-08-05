"""Build fighters_static.csv + fights_log.csv reference tables for the cloud scorer,
then run the staleness parity test on 2026 H1 fights.

Reference design (documented in PREREG):
- fights_log.csv: one row per fighter-appearance in the odds frame (the `prior`
  definition matches the training frame exactly: prior fights WITH complete odds).
  Live features computed from it: prior count, days_since_last_fight, ufcage,
  division (last bout's), plus DOB carried per fighter.
- fighters_static.csv: per fighter, the 7 decayed-average stats + reach from their
  most recent training_data row (= values as of their last completed fight;
  exactly one fight stale for the *next* fight, by construction).
"""
import unicodedata
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path("C:/Users/cmtub/OneDrive/Documents/Betting Models/betting-models")
OUTD = Path(__file__).parent / "reference"
OUTD.mkdir(exist_ok=True)

def nrm(x):
    s = unicodedata.normalize("NFKD", str(x))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return " ".join("".join(c if c.isalnum() else " " for c in s).split())

STAT_BASES = ["win_ratio_dec_avg", "sig_str_land_per_min_dec_avg", "sig_str_def_dec_avg",
              "td_land_per_min_dec_avg", "td_def_dec_avg", "sub_att_per_min_dec_avg",
              "ko_sub_per_win_dec_avg"]

# ---------- fights_log from the odds frame ----------
oc = pd.read_parquet(REPO / "codex_data_v7/fights_openclose.parquet")
oc["event_date"] = pd.to_datetime(oc.event_date)
log = pd.concat([
    oc[["f1_name", "f1_dob", "event_date"]].rename(columns={"f1_name": "name", "f1_dob": "dob"}),
    oc[["f2_name", "f2_dob", "event_date"]].rename(columns={"f2_name": "name", "f2_dob": "dob"}),
], ignore_index=True)
log["name_key"] = log.name.map(nrm)
log["source"] = "odds_frame"

# division per bout from ufcstats competitions
import re
def division_name(x):
    s = str(x).replace("UFC ", "").replace("Interim ", "")
    s = re.sub(r"\s+Title Bout$", "", s); s = re.sub(r"\s+Bout$", "", s)
    return s.strip() or "Unknown"
comp = pd.read_csv(REPO / "mma-ai/data/raw/ufcstats/competitions.csv",
                   usecols=["player1", "player2", "weightclass", "event_date"])
comp["event_date"] = pd.to_datetime(comp.event_date)
comp["division"] = comp.weightclass.map(division_name)
cl = pd.concat([
    comp[["player1", "event_date", "division"]].rename(columns={"player1": "name"}),
    comp[["player2", "event_date", "division"]].rename(columns={"player2": "name"}),
], ignore_index=True)
cl["name_key"] = cl.name.map(nrm)
last_div = cl.sort_values("event_date").groupby("name_key").division.last()

log = log.sort_values("event_date")
log.to_csv(OUTD / "fights_log.csv", index=False)
print(f"fights_log: {len(log)} rows, {log.name_key.nunique()} fighters")

# ---------- fighters_static from training_data (latest row per fighter) ----------
use = (["fight_id", "event_date", "fighter1_name", "fighter2_name", "reach", "reach_opp"]
       + STAT_BASES + [b.replace("_dec_avg", "_opp_dec_avg") for b in STAT_BASES])
td = pd.read_csv(REPO / "mma-ai/data/training_data.csv", usecols=use, low_memory=False)
td["event_date"] = pd.to_datetime(td.event_date)
a = td[["event_date", "fighter1_name", "reach"] + STAT_BASES].rename(
    columns={"fighter1_name": "name"})
bmap = {b.replace("_dec_avg", "_opp_dec_avg"): b for b in STAT_BASES}
b = td[["event_date", "fighter2_name", "reach_opp"] + list(bmap)].rename(
    columns={"fighter2_name": "name", "reach_opp": "reach", **bmap})
allrows = pd.concat([a, b], ignore_index=True)
allrows["name_key"] = allrows.name.map(nrm)
allrows = allrows.sort_values("event_date")
static = allrows.groupby("name_key").last().reset_index().rename(columns={"event_date": "as_of_fight_date"})
static["division_last"] = static.name_key.map(last_div)
dob = log.dropna(subset=["dob"]).sort_values("event_date").groupby("name_key").dob.last()
static["dob"] = static.name_key.map(dob)
static.to_csv(OUTD / "fighters_static.csv", index=False)
print(f"fighters_static: {len(static)} fighters | stat completeness: "
      f"{static[STAT_BASES[0]].notna().mean():.1%}")

# ---------- STALENESS PARITY TEST on 2026 fights ----------
# For each 2026 fight, rebuild fighter features using only information available
# the day before (previous appearance's stats), keep odds features identical, score
# with the MOV-MKT-1 spec, and compare gate decisions to the shipped ledger.
import json
from scipy.special import expit, logit
SPEC = json.load(open("C:/Users/cmtub/Documents/Codex/2026-08-05/you/outputs/mma_movement_hold_v1/mov_mkt_1_model_spec.json"))

def head_score(head, feat_row, division):
    co = dict(zip(head["transformed_features"], head["coefficients"]))
    z = head["intercept"]
    for f in head["numeric_features"]:
        x = feat_row.get(f, np.nan)
        if pd.isna(x): x = head["numeric_medians"][f]
        xs = (x - head["numeric_means_after_impute"][f]) / head["numeric_scales"][f]
        z += co.get("num__" + f, 0.0) * xs
    z += co.get(f"cat__division_{division}", 0.0)
    return z

frame = pd.read_pickle(Path(__file__).parent / "frame_rebuilt.pkl")
f26 = frame[frame.year == 2026].copy()
led26 = pd.read_csv("C:/Users/cmtub/Documents/Codex/2026-08-05/you/outputs/mma_movement_hold_v1/mov_hold_2026_all_fights.csv")

# as-of-day-before stats per fighter: last allrows entry strictly before event
allrows_sorted = allrows.sort_values("event_date")
def stats_asof(nk, before):
    g = allrows_sorted[(allrows_sorted.name_key == nk) & (allrows_sorted.event_date < before)]
    if g.empty: return None
    return g.iloc[-1]

STAT_DIFF_MAP = {  # model feature -> static base
    "win_ratio_dec_avg_diff_fav": "win_ratio_dec_avg",
    "sig_str_land_per_min_dec_avg_diff_fav": "sig_str_land_per_min_dec_avg",
    "sig_str_def_dec_avg_diff_fav": "sig_str_def_dec_avg",
    "td_land_per_min_dec_avg_diff_fav": "td_land_per_min_dec_avg",
    "td_def_dec_avg_diff_fav": "td_def_dec_avg",
    "sub_att_per_min_dec_avg_diff_fav": "sub_att_per_min_dec_avg",
    "ko_sub_per_win_dec_avg_diff_fav": "ko_sub_per_win_dec_avg",
}
logs = log.sort_values("event_date")
def log_feats(nk, before):
    g = logs[(logs.name_key == nk) & (logs.event_date < before)]
    if g.empty: return 0, np.nan, np.nan
    return len(g), (before - g.event_date.iloc[-1]).days, (before - g.event_date.iloc[0]).days / 365.25

rows = []
for _, r in f26.iterrows():
    k1, k2 = nrm(r.f1_name), nrm(r.f2_name)
    ed = r.event_date
    s1, s2 = stats_asof(k1, ed), stats_asof(k2, ed)
    n1, dsl1, age1u = log_feats(k1, ed)
    n2, dsl2, age2u = log_feats(k2, ed)
    fs = int(r.fav_sign)
    feat = {
        "z_open_fav": r.z_open_fav, "z_open_fav_sq": r.z_open_fav_sq,
        "open_vig": r.open_vig, "open_lead_days": r.open_lead_days,
        "age_diff_fav": r.age_diff_fav,   # DOBs are static: identical live
        "prior_diff_fav": fs * (n1 - n2), "prior_sum": n1 + n2,
        "debut_mismatch": int((n1 == 0) ^ (n2 == 0)),
        "card_position_pct": np.nan,      # unknown live -> imputed
        "days_since_last_fight_diff_fav": fs * (dsl1 - dsl2) if pd.notna(dsl1) and pd.notna(dsl2) else np.nan,
        "reach_diff_fav": fs * (s1.reach - s2.reach) if s1 is not None and s2 is not None and pd.notna(s1.reach) and pd.notna(s2.reach) else np.nan,
        "ufcage_diff_fav": fs * (age1u - age2u) if pd.notna(age1u) and pd.notna(age2u) else np.nan,
    }
    for f, b in STAT_DIFF_MAP.items():
        v1 = s1[b] if s1 is not None else np.nan
        v2 = s2[b] if s2 is not None else np.nan
        feat[f] = fs * (v1 - v2) if pd.notna(v1) and pd.notna(v2) else np.nan
    div = last_div.get(k1, "Unknown")
    delta = head_score(SPEC["movement_head"], feat, div)
    steam_z = head_score(SPEC["direction_head"], feat, div)
    p_steam = 1 / (1 + np.exp(-steam_z))
    qopen = r.qfav_opening
    pred_qclose = expit(np.log(qopen/(1-qopen)) + delta)
    b1, b3 = SPEC["market_calibrator"]["coefficients"]
    zz = np.log(np.clip(pred_qclose, 1e-4, 1-1e-4) / (1 - np.clip(pred_qclose, 1e-4, 1-1e-4)))
    p_mkt = 1 / (1 + np.exp(-(b1*zz + b3*zz**3)))
    rows.append({"fight_id": r.fight_id, "pred_delta_live": delta, "p_steam_live": p_steam,
                 "pred_qclose_live": pred_qclose, "p_mkt_live": p_mkt})
live = pd.DataFrame(rows).merge(led26, on="fight_id")

# reconstruct live-side selection + gates
Ofav = np.where(live.selected_side.eq("favorite"), live.selected_odds, np.nan)
fr = frame.set_index("fight_id").loc[live.fight_id]
Ofav = np.where(fr.fav_sign.eq(1), fr.f1_opening_odds, fr.f2_opening_odds)
Odog = np.where(fr.fav_sign.eq(1), fr.f2_opening_odds, fr.f1_opening_odds)
ev_f = live.p_mkt_live * Ofav - 1
ev_d = (1 - live.p_mkt_live) * Odog - 1
live["sel_fav_live"] = ev_f >= ev_d
live["ev_live"] = np.maximum(ev_f, ev_d)
live["steam_sel_live"] = np.where(live.sel_fav_live, live.p_steam_live, 1 - live.p_steam_live)
live["clv_live"] = 100 * np.where(live.sel_fav_live, live.pred_qclose_live - fr.qfav_opening.to_numpy(),
                                  fr.qfav_opening.to_numpy() - live.pred_qclose_live)
live["qual_live"] = (live.ev_live >= .01) & (live.steam_sel_live >= .75) & (live.clv_live >= 2.0)
live["qual_ship"] = (live.selected_ev >= .01) & (live.selected_steam_prob >= .75) & (live.pred_clv_pp >= 2.0)

agree = (live.qual_live == live.qual_ship).mean()
both = ((live.qual_live) & (live.qual_ship)).sum()
only_live = ((live.qual_live) & (~live.qual_ship)).sum()
only_ship = ((~live.qual_live) & (live.qual_ship)).sum()
print(f"\n=== STALENESS PARITY (227 fights, 2026 H1) ===")
print(f"decision agreement: {agree:.1%} | both qualify: {both} | live-only: {only_live} | shipped-only: {only_ship}")
print(f"p_steam corr: {live.p_steam_live.corr(live.prob_fav_steams):.4f} | mean abs diff: {(live.p_steam_live - live.prob_fav_steams).abs().mean():.4f}")
print(f"p_mkt mean abs diff: {(live.p_mkt_live - np.where(live.sel_fav_live, live.selected_p_market, 1-live.selected_p_market)).__abs__().mean():.4f}")
print(f"pred CLV mean abs diff: {(live.clv_live - np.where(live.sel_fav_live == live.selected_side.eq('favorite'), live.pred_clv_pp, -live.pred_clv_pp)).abs().mean():.3f}pp")
disag = live[live.qual_live != live.qual_ship]
if len(disag):
    print("\ndisagreements:")
    print(disag[["fight_id","f1_name","f2_name","ev_live","selected_ev","steam_sel_live","selected_steam_prob","clv_live","pred_clv_pp"]].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
live.to_csv(Path(__file__).parent / "parity_2026.csv", index=False)
