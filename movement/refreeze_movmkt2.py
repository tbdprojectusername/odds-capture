"""MOV-MKT-2 refreeze: band-correction validation on nested pre-2026 folds only,
then final fit on all data through 2026-07-25.

Pre-committed rule (from the plan the user approved): the heavy-favorite band
intercept correction ships only if it improves nested pre-2026 fold metrics.
Gates are NOT re-searched. Output: movement spec JSON with heads, calibrator,
band offsets (possibly zero), plus metadata.
"""
import importlib.util, json, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit, logit
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, mean_absolute_error, r2_score

SEED = 8052026
BANDS = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

BASE = Path("C:/Users/cmtub/Documents/Codex/2026-08-05/you/outputs/mma_odds_movement_v1/run_analysis.py")
spec_l = importlib.util.spec_from_file_location("mov1_base", BASE)
base = importlib.util.module_from_spec(spec_l); spec_l.loader.exec_module(base)

HOLD = Path("C:/Users/cmtub/Documents/Codex/2026-08-05/you/outputs/mma_movement_hold_v1/run_movement_hold.py")
spec_h = importlib.util.spec_from_file_location("movhold", HOLD)
mh = importlib.util.module_from_spec(spec_h); spec_h.loader.exec_module(mh)

_pkl = Path(__file__).parent / "frame_rebuilt.pkl"
if _pkl.exists():
    df = pd.read_pickle(_pkl)
else:
    # rebuild from raw data (~70s); requires pyarrow
    df, _, _ = base.load_frame(Path(r"C:\Users\cmtub\OneDrive\Documents\Betting Models\betting-models"))
    df.to_pickle(_pkl)
price = ["z_open_fav", "z_open_fav_sq", "open_vig", "open_lead_days"]
stats = price + ["age_diff_fav", "prior_diff_fav", "prior_sum", "debut_mismatch",
                 "card_position_pct"] + [c + "_fav" for c in base.STAT_COLS]

def band_of(q):
    return pd.cut(q, BANDS, labels=False, include_lowest=True)

def band_offsets(tr, pm):
    r = tr.target_delta_logit - pm.predict(tr)
    b = band_of(tr.qfav_opening)
    off = r.groupby(b).mean()
    return {int(k): float(v) for k, v in off.items()}

def apply_off(d, pred, offs):
    b = band_of(d.qfav_opening)
    return pred + b.map(lambda x: offs.get(int(x), 0.0) if pd.notna(x) else 0.0).to_numpy(float)

# ---------- nested validation of the correction (2018-2025 folds) ----------
rows = []
d_all = df[df.year.between(2014, 2025)].copy()
preds_plain, preds_corr, ys, folds_col = [], [], [], []
for vy in range(2018, 2026):
    tr, va = d_all[d_all.year < vy], d_all[d_all.year == vy]
    am = mh.light_tune(base, tr, stats, ["division"], "mag", int(tr.year.min()))
    pm = base.make_pipe(stats, ["division"], "mag", am).fit(tr, tr.target_delta_logit)
    offs = band_offsets(tr, pm)
    p0 = pm.predict(va)
    p1 = apply_off(va, p0, offs)
    preds_plain.append(p0); preds_corr.append(p1); ys.append(va.target_delta_logit.to_numpy())
    folds_col.append(np.full(len(va), vy))
    rows.append({"fold": vy, "r2_plain": r2_score(va.target_delta_logit, p0),
                 "r2_corrected": r2_score(va.target_delta_logit, p1),
                 "mae_plain": mean_absolute_error(va.target_delta_logit, p0),
                 "mae_corrected": mean_absolute_error(va.target_delta_logit, p1),
                 "off_band3": offs.get(3, np.nan), "off_band4": offs.get(4, np.nan)})
res = pd.DataFrame(rows)
y = np.concatenate(ys); P0 = np.concatenate(preds_plain); P1 = np.concatenate(preds_corr)
pooled_r2_plain, pooled_r2_corr = r2_score(y, P0), r2_score(y, P1)
pooled_mae_plain, pooled_mae_corr = mean_absolute_error(y, P0), mean_absolute_error(y, P1)
print(res.to_string(index=False, float_format=lambda x: f"{x:+.5f}"))
print(f"\npooled nested R2: plain {pooled_r2_plain:.5f} -> corrected {pooled_r2_corr:.5f}")
print(f"pooled nested MAE: plain {pooled_mae_plain:.5f} -> corrected {pooled_mae_corr:.5f}")
USE_CORRECTION = (pooled_r2_corr > pooled_r2_plain) and (pooled_mae_corr <= pooled_mae_plain + 1e-6)
print("DECISION: correction", "INCLUDED" if USE_CORRECTION else "DROPPED")

# effect on the frozen-gate qualifier set (report-only; gates unchanged)
# (uses fold 2018-2025 direction/calibration pipeline exactly as shipped)

# ---------- final refit through 2026-07-25 ----------
train = df[(df.year >= 2014) & (df.event_date <= "2026-07-25")].copy()
print(f"\nfinal training rows: {len(train)} (max date {train.event_date.max().date()})")
am = mh.light_tune(base, train, stats, ["division"], "mag", 2014)
ad = mh.light_tune(base, train, stats, ["division"], "dir", 2014)
pm = base.make_pipe(stats, ["division"], "mag", am).fit(train, train.target_delta_logit)
pd_ = base.make_pipe(stats, ["division"], "dir", ad).fit(train, train.target_dir)
cal = mh.fit_market_calibrator(train)
offs = band_offsets(train, pm) if USE_CORRECTION else {}

spec = {
    "model_id": "MOV-MKT-2",
    "frozen_through": "2026-07-25",
    "derived_from": "MOV-MKT-1 (audited 2026-08-05); same features, same gates; expanding-window refit",
    "independence_assertion": "No picks-model prediction, residual, edge, EV, pick, or staking output is a feature.",
    "selected_feature_spec": "MOV_MKT_STATS",
    "numeric_features": stats,
    "categorical_features": ["division"],
    "movement_target": "logit(q_favorite_close)-logit(q_favorite_open)",
    "movement_head": base.extract_head(pm, stats, ["division"], "ridge", am),
    "direction_head": base.extract_head(pd_, stats, ["division"], "logistic", ad),
    "market_calibrator": {"form": "logit(p_side)=b1*logit(q_side)+b3*logit(q_side)^3; intercept fixed zero",
                          "coefficients": cal.coef_.ravel().tolist()},
    "band_correction": {"enabled": bool(USE_CORRECTION),
                        "validation": {"pooled_nested_r2_plain": pooled_r2_plain,
                                       "pooled_nested_r2_corrected": pooled_r2_corr,
                                       "pooled_nested_mae_plain": pooled_mae_plain,
                                       "pooled_nested_mae_corrected": pooled_mae_corr},
                        "bands_qfav_open": BANDS,
                        "offsets_delta_logit": offs},
    "nested_validation_note": "correction decided on 2018-2025 nested folds only; gates untouched",
}
out = Path(__file__).parent / "mov_mkt_2_model_spec.json"
out.write_text(json.dumps(spec, indent=2, default=float), encoding="utf-8")
h = hashlib.sha256(out.read_bytes()).hexdigest().upper()
print(f"\nwrote {out.name}  sha256={h}")
print(f"alpha_mag={am} C_dir={ad} calibrator={cal.coef_.ravel().tolist()}")
if USE_CORRECTION: print("offsets:", {k: round(v,5) for k,v in offs.items()})
