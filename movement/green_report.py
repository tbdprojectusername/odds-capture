#!/usr/bin/env python3
"""Read-only GREEN aggregator for MOV-HOLD-2.2 (V8-recheck R7).

Enforces every binding criterion from PREREG_REMEDIATION_2026-08-05c.md
mechanically and emits the exact row keys it used, so any reviewer can rerun
and diff. Writes GREEN_REPORT.md + green_report.json next to the ledgers.
Never modifies any ledger.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

CLOSE_GAP_PRIMARY_MIN = 60.0     # minutes; ≤60 eligible, ≤30 high quality
MIN_N = 60
MIN_EVENTS = 30
MIN_CLV_PP = 1.5
MIN_EXEC_RATE = 0.60
MIN_CLOSE_COVERAGE = 0.60


def cluster_ci(vals: pd.Series, clusters: pd.Series):
    n = len(vals)
    mu = vals.mean()
    sums = (vals - mu).groupby(clusters).sum().to_numpy()
    G = len(sums)
    if G <= 1:
        return mu, np.nan, np.nan, G
    se = math.sqrt((G / (G - 1)) * np.sum(sums ** 2) / n ** 2)
    return mu, mu - 1.96 * se, mu + 1.96 * se, G


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--movement-dir", type=Path, default=Path(__file__).resolve().parent)
    args = ap.parse_args()
    md = args.movement_dir
    now = pd.Timestamp(datetime.now(timezone.utc))
    pol = json.loads((md / "specs/mov_hold_2_policy_spec.json").read_text(encoding="utf-8"))
    rem_ts = pd.Timestamp(pol["remediation"]["remediation_ts"])

    led = pd.read_csv(md / "ledger/signals.csv")
    graded_p = md / "ledger/graded.csv"
    graded = pd.read_csv(graded_p) if graded_p.exists() else pd.DataFrame()
    out = {"generated": str(now), "policy_id": pol.get("policy_id"),
           "remediation_ts": str(rem_ts), "verdict": "NOT_GREEN", "checks": {}, "rows_used": []}

    if not len(graded):
        out["checks"]["graded_rows"] = "none yet"
        _write(md, out, [])
        return

    m = graded.merge(
        led[["signal_key", "selected_fighter", "selected_side", "scored_at", "open_source",
             "open_n_books", "clears_min_at_scoring"]],
        on="signal_key", how="left", suffixes=("", "_led"))
    m["scored_at"] = pd.to_datetime(m.scored_at, utc=True, format="mixed")

    # ---- the promotion cohort, filter by filter (each count reported) ----
    filt = {}
    z = m.copy();                             filt["graded"] = len(z)
    z = z[z.tier.eq("A")];                    filt["tier_A"] = len(z)
    z = z[z.selected_side.eq("favorite")];    filt["favorites"] = len(z)
    z = z[z.counts_prospective.astype(bool)]; filt["counts_prospective"] = len(z)
    z = z[z.scored_at >= rem_ts];             filt["post_remediation"] = len(z)
    z = z[z.paper_filled.astype(bool)];       filt["paper_filled"] = len(z)
    z = z[z.roi_cohort_eligible.astype(bool)]; filt["roi_cohort_eligible"] = len(z)
    close_ok = pd.to_numeric(z.close_pinnacle_gap_min, errors="coerce") <= CLOSE_GAP_PRIMARY_MIN
    close_cov = float(close_ok.mean()) if len(z) else 0.0
    z_el = z[close_ok.fillna(False)];         filt["eligible_close_le60m"] = len(z_el)
    out["checks"]["funnel"] = filt

    clv = pd.to_numeric(z_el.clv_pp_vs_pinnacle_close, errors="coerce").dropna()
    z_clv = z_el.loc[clv.index]
    events = z_clv.event_start.nunique()
    mu, lo, hi, G = cluster_ci(clv, z_clv.event_start) if len(z_clv) else (np.nan,) * 4

    # executable-at-scoring over the whole counted post-remediation A-favorite set
    base = m[m.tier.eq("A") & m.selected_side.eq("favorite") &
             m.counts_prospective.astype(bool) & (m.scored_at >= rem_ts)]
    exec_rate = float(base.clears_min_at_scoring.astype(bool).mean()) if len(base) else np.nan

    checks = {
        "n_eligible": (len(z_clv), f">= {MIN_N}", len(z_clv) >= MIN_N),
        "event_clusters": (int(events), f">= {MIN_EVENTS}", events >= MIN_EVENTS),
        "clv_mean_pp": (round(float(mu), 3) if np.isfinite(mu) else None, f">= {MIN_CLV_PP}",
                        bool(np.isfinite(mu) and mu >= MIN_CLV_PP)),
        "clv_ci_lower": (round(float(lo), 3) if np.isfinite(lo) else None, "> 0",
                         bool(np.isfinite(lo) and lo > 0)),
        "exec_at_scoring_rate": (round(exec_rate, 3) if np.isfinite(exec_rate) else None,
                                 f">= {MIN_EXEC_RATE}", bool(np.isfinite(exec_rate) and exec_rate >= MIN_EXEC_RATE)),
        "close_coverage": (round(close_cov, 3), f">= {MIN_CLOSE_COVERAGE}", close_cov >= MIN_CLOSE_COVERAGE),
        "ops_30day_clean": (None, "manual attestation + incident log", False),
    }
    out["checks"]["criteria"] = {k: {"value": v[0], "bar": v[1], "pass": v[2]} for k, v in checks.items()}

    # source strata (report-only; pooling gate lives in the addendum)
    strata = z_el.groupby("open_source").agg(
        n=("signal_key", "size"),
        clv=("clv_pp_vs_pinnacle_close", "mean")).reset_index()
    out["checks"]["open_source_strata"] = strata.to_dict("records")
    out["rows_used"] = sorted(z_clv.signal_key.tolist())
    out["verdict"] = "GREEN" if all(v[2] for v in checks.values()) else "NOT_GREEN"
    _write(md, out, z_clv.signal_key.tolist())


def _write(md: Path, out: dict, rows):
    (md / "green_report.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    lines = [f"# GREEN report — {out.get('policy_id')}", "",
             f"Generated {out['generated']} · verdict: **{out['verdict']}**", ""]
    fun = out.get("checks", {}).get("funnel")
    if fun:
        lines += ["Funnel: " + " → ".join(f"{k} {v}" for k, v in fun.items()), ""]
    crit = out.get("checks", {}).get("criteria")
    if crit:
        lines += ["| Criterion | Value | Bar | Pass |", "|---|---|---|---|"]
        for k, c in crit.items():
            lines.append(f"| {k} | {c['value']} | {c['bar']} | {'✅' if c['pass'] else '❌'} |")
        lines.append("")
    strata = out.get("checks", {}).get("open_source_strata")
    if strata:
        lines.append("Open-source strata (pooling gated by transport test, addendum): " +
                     "; ".join(f"{s['open_source']}: n={s['n']}, CLV {s['clv']:+.2f}pp" for s in strata))
    lines += ["", f"Rows used ({len(rows)}): see green_report.json `rows_used`.",
              "", "Read-only report; criteria frozen in PREREG_REMEDIATION_2026-08-05c.md."]
    (md / "GREEN_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"verdict": out["verdict"], "rows": len(rows)}, indent=1))


if __name__ == "__main__":
    main()
