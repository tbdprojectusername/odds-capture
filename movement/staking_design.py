"""Design MOV-HOLD staking from the strategy's own historical bet stream.

Simulates candidate fractional-Kelly variants (no event cap) over the 172
pre-2026 qualifiers and the 23 2026 qualifiers, plus an event-bootstrap
drawdown distribution for the finalists.
"""
import numpy as np
import pandas as pd

OUT = "C:/Users/cmtub/Documents/Codex/2026-08-05/you/outputs/mma_movement_hold_v1"
SEED = 8052026

led = pd.read_csv(f"{OUT}/mov_hold_nested_ledger_all_specs.csv", parse_dates=["event_date"])
led = led[led.movement_spec.eq("MOV_MKT_STATS")]
q_pre = led[(led.selected_ev >= .01) & (led.selected_steam_prob >= .75) & (led.pred_clv_pp >= 2.0)].copy()
q26 = pd.read_csv(f"{OUT}/mov_hold_2026_qualified.csv", parse_dates=["event_date"])

def simulate(d, lam, cap, open_ceiling=None):
    bank = 1.0; peak = 1.0; maxdd = 0.0; staked = 0.0; worst_event = 0.0
    stakes_pct = []
    for (_, _), g in d.sort_values(["event_date", "event_id"]).groupby(["event_date", "event_id"], sort=True):
        f = np.minimum(lam * g.kelly_raw.to_numpy(float), cap)
        if open_ceiling and f.sum() > open_ceiling:
            f *= open_ceiling / f.sum()
        stakes = bank * f
        ev_pnl = float(np.sum(stakes * g.unit_return.to_numpy(float)))
        worst_event = min(worst_event, ev_pnl / bank)
        bank += ev_pnl; staked += stakes.sum()
        peak = max(peak, bank); maxdd = max(maxdd, 1 - bank / peak)
        stakes_pct.extend(f.tolist())
    return {"end": bank, "maxdd": maxdd, "staked": staked,
            "avg_stake_pct": float(np.mean(stakes_pct)) if stakes_pct else 0,
            "max_stake_pct": float(np.max(stakes_pct)) if stakes_pct else 0,
            "worst_event_pct": worst_event}

print("=== Pre-2026 (172 bets, 8 seasons) — no event cap ===")
print(f"{'variant':28s} {'end bank':>9s} {'maxDD':>7s} {'handle/yr':>10s} {'avg bet':>8s} {'max bet':>8s} {'worst evt':>9s}")
variants = []
for lam, cap, label in [
    (.25, .005, "quarter-Kelly, 0.5% cap (old)"),
    (.125, 1.0,  "eighth-Kelly, uncapped"),
    (.25, .03,  "quarter-Kelly, 3% cap"),
    (.25, .04,  "quarter-Kelly, 4% cap"),
    (.25, .05,  "quarter-Kelly, 5% cap"),
    (.25, 1.0,  "quarter-Kelly, uncapped"),
    (.5,  .05,  "half-Kelly, 5% cap"),
    (.5,  1.0,  "half-Kelly, uncapped"),
]:
    r = simulate(q_pre, lam, cap)
    variants.append((label, lam, cap, r))
    print(f"{label:28s} {r['end']:9.3f} {r['maxdd']:6.1%} {r['staked']/8:9.1%} {r['avg_stake_pct']:7.2%} {r['max_stake_pct']:7.2%} {r['worst_event_pct']:8.1%}")

print("\n=== 2026 holdout (23 bets, ~7 months) ===")
for label, lam, cap, _ in variants:
    r = simulate(q26, lam, cap)
    print(f"{label:28s} end {r['end']:.3f}  maxDD {r['maxdd']:.1%}  staked {r['staked']:.1%}  worst evt {r['worst_event_pct']:+.1%}")

# ---- event-bootstrap drawdown risk for finalists (resample 1 season = 40 bets) ----
print("\n=== Forward season risk (event bootstrap, 2000 sims of ~21 events/season) ===")
rng = np.random.default_rng(SEED)
events = [g for _, g in q_pre.groupby(["event_date", "event_id"])]
n_ev_season = int(round(len(events) / 8))
for label, lam, cap, _ in variants:
    if label in ("quarter-Kelly, 0.5% cap (old)",):
        continue
    dds, ends = [], []
    for _ in range(2000):
        idx = rng.integers(0, len(events), n_ev_season)
        bank = 1.0; peak = 1.0; dd = 0.0
        for i in idx:
            g = events[i]
            f = np.minimum(lam * g.kelly_raw.to_numpy(float), cap)
            stakes = bank * f
            bank += float(np.sum(stakes * g.unit_return.to_numpy(float)))
            peak = max(peak, bank); dd = max(dd, 1 - bank / peak)
        dds.append(dd); ends.append(bank)
    dds = np.array(dds); ends = np.array(ends)
    print(f"{label:28s} median end {np.median(ends):.3f} | P(loss yr) {np.mean(ends<1):.0%} | "
          f"maxDD median {np.median(dds):.1%}  p95 {np.quantile(dds,.95):.1%}  p99 {np.quantile(dds,.99):.1%}")
