# MOV-HOLD-1 — independent adversarial audit

Auditor: Claude (Fable 5), 2026-08-05. Audited package: `C:\Users\cmtub\Documents\Codex\2026-08-05\you\outputs\mma_movement_hold_v1` (+ sibling `mma_odds_movement_v1`), raw data from the betting-models repo. Originals untouched; all reruns in a scratch copy. Full artifact hash manifest: `artifact_hashes_before.txt` (all six reference SHA-256 hashes match the handoff).

---

## 1. Executive verdict: `prospective-shadow-ready`

The package is what it claims to be, with two disciplined qualifications. Everything reproduces exactly from raw data; I found no temporal leakage, no odds-math error, no outcome contamination, and no evidence that 2026 outcomes chose the gate numbers. The incremental-CLV claim not only survives stronger controls than the package's own audit — it strengthens under them. The incremental-ROI claim remains unresolved, exactly as the package states.

The two qualifications:

1. **"2026 was untouched" is overstated as written.** The gates and staking were mechanically selected from pre-2026 data only (verified by exact re-execution), but the artifact record shows the 2026 window was scored by at least two earlier same-morning variants of the movement model before the shipped version was frozen, and the wider research program (audit rounds V5–V7) has repeatedly analyzed the same 2026 window. 2026 is a *soft* holdout with reduced evidentiary weight, not a virgin one.
2. **The profitable tail of the 2026 ledger is execution-unverifiable.** 9 of 23 bets — carrying 61.7% of the flat P&L, including all four underdogs — have openers that either have no archive-tick backing at all or disagree with the first archive tick by 4.6–12.3 probability points. No named-book capture overlaps any holdout bet (captures begin 2026-07-26; last holdout event 2026-07-18).

Deployment as a shadow strategy with prospective named-book logging is justified. Live promotion is not, and would not be even if the statistics were stronger, until executable-price evidence exists.

---

## 2. Findings table

| # | Sev | Finding | Evidence | Metric impact | Corrective action |
|---|-----|---------|----------|---------------|-------------------|
| F1 | **P1** | "Untouched 2026" claim overstated: 2026 was scored under ≥2 prior same-day model variants before the shipped freeze | `codex_data_v7/mov_mkt_1_holdout_2026.csv` (11:22, includes realized `y_mag`; earlier spec `MOV-MKT-1-OPEN 2026-08-05-p1`, 2026 R² 0.080) and sibling MOV-OPEN-1 holdout (11:05, R² 0.131) both predate the shipped run (11:38–11:45, R² 0.104); repo carries V5–V7 audit history over the same window | Gate/staking numbers themselves are clean (mechanical pre-2026 selection, verified by bit-exact re-run); the contamination is at the design/feature-set level. Downgrade the strength of all "untouched 2026" language; treat 2026 R²/ROI as soft-holdout evidence | Rename the claim "gates and sizing frozen without using 2026"; future holdouts: freeze the *code* hash before the holdout period is ever scored by any family member |
| F2 | **P1** | Post-selection optimism in the reported pre-2026 CI | Selection-aware event bootstrap re-running the entire registry + `choose_policy` procedure: the same gates are re-chosen in only 69/200 replicates; mean winner's-curse optimism +1.4pp | Debiased pre-2026 flat ROI ≈ **+7.4%** (reported +8.8%); CI lower bound ≈ +0.9% (reported +2.3%). CLV unaffected (stable across the entire gate surface) | Report the debiased figure alongside the naive one; keep using CLV as the primary promotion metric |
| F3 | **P2** | Composite-opener executability: unverifiable exactly where the P&L is | 4 qualifiers (incl. both biggest winners, Pericic +1.70u, Young +1.30u — both dogs) have zero archive ticks; 5 more mismatch the first tick by 4.6–12.3pp (Luna row was a 9-day-notice replacement fight); 61.7% of 2026 flat P&L sits on these rows; no named-book capture overlaps the holdout | Tick-backed clean subset (n=14, all favorites): ROI +14.9% [−1.7%, +31.4%], CLV +5.23pp [+3.45, +7.01] — the signal survives on the verifiable subset, the windfall doesn't | Keep shadow-only; prospective qualification must require a live named-book quote (Pinnacle/BFO panel is already capturing) |
| F4 | **P2** | 2026 underdog windfall is unsupported by pre-2026 evidence | Pre-2026 treated dogs: n=6, negative excess unit return (treated-dog regression coef −0.88 ± 0.30); 2026 dogs: 4 bets = 56.8% of P&L, all execution-unverifiable (F3) | The dog sleeve's 2026 contribution should be treated as luck | Shadow the dog sleeve separately; do not let 4 bets promote a 96.5%-favorite strategy's dog leg |
| F5 | **P2** | Incremental ROI unresolved (package's own conclusion — confirmed and sharpened) | Regression baseline (open prob, EV, side, lead, year FE, event-clustered): pre-2026 excess ROI +5.8pp [−4.0, +15.4]; LOO-cell baseline +5.0pp [−2.1, +12.1]; 2026 frozen-regression counterfactual +15.3pp [−7.6, +38.1] | The +23.6% 2026 headline is not evidence of incremental skill; direction is consistently positive but nowhere resolved | Keep `shadow_only_incremental_roi_not_resolved`; resolve via prospective CLV first (it resolves ~10× faster) |
| F6 | **P2** | Magnitude head over-predicts steam for heavy favorites — the very group it concentrates in | Nested residual means: −0.038 (q .6–.7), −0.083 (q .8–.9), −0.118 (q .9–1.0) logits; year-level R² swings −0.02…+0.13 | Predicted CLV is optimistic at the short end; partially absorbed by the EV gate; realized CLV stays positive anyway | Consider a per-band intercept correction at next scheduled refit (not mid-shadow) |
| F7 | P3 | Shipped `mov_hold_1_policy_spec.json` + strategy report were hand-edited after the run | Keys `initial_policy_gate_status`, `incremental_audit` and the rewritten verdict line are not produced by any shipped script; a re-run regenerates the pre-edit content | None on numbers (all values match); provenance hygiene only | Make `audit_movement_hold.py` write the status back itself (see patch note) |
| F8 | P3 | Portability defects | `build_2026_bet_table.py` hard-codes the repo path (acknowledged in handoff); `--out` with a relative path breaks sibling-module discovery; silent cache reuse of `mov_mkt_nested_predictions.csv`; `requirements.txt` pins (pandas 3.0.5/np 2.5.1/sklearn 1.9.0) unavailable locally — reproduction was nonetheless bit-exact under pandas 2.3.1/np 2.3.2/sklearn 1.7.1 | None observed | `patches/portability.patch` |
| F9 | P3 | Multiplicity family narrower than the true search | BH applied to 145 gate cells per metric within the chosen spec; outside the family: 2 feature specs (picked by nested R²), 16 staking variants (picked by log-growth), the `choose_policy` filter design itself, prior same-day variants (F1), and the pre-package movement-research history | Covered quantitatively by F2's procedure-level bootstrap | Report effective DOF honestly (see §6); prefer procedure-level bootstrap over per-cell BH in future |
| F10 | P3 | Minor spec divergences worth knowing | `light_tune` grids differ from base `tune_penalty` (mag grid drops α=0.01; dir grid caps C at 1); `open_lead_days` missing for 13.5% of rows (median-imputed); `card_position_pct` scraped post-event (announced order can shift day-of; std. coef −0.07, low materiality) | Negligible | Document |

No P0 findings. Specifically checked and cleared: no picks-model field enters any feature (asserted in code and verified in the frozen spec's feature list); closing odds appear only in targets/labels/CLV/calibration; per-fold pipelines (imputer, scaler, one-hot, penalty tuning, market calibrator) are fit strictly on training years; folds are calendar-aligned with no same-event straddling (`fold == event_year` for all 3,007 rows); no duplicate fight_ids; all merges `validate="one_to_one"` with event-date assertions; drawn/NC fights (0 in 2026 scored set) return stake.

---

## 3. Claim reconciliation

All 41 reported aggregates recomputed independently from the supplied ledgers: **41/41 PASS** (machine-readable table: `claim_reconciliation.csv`). Headline rows:

| Claim | Reported | Recomputed | Δ |
|---|---|---|---|
| Nested pre-2026 rows / R² / dir-acc | 3,007 / 0.0656 / 60.23% | 3,007 / 0.06558 / 60.23% | ✓ |
| 2026 rows / R² / dir-acc | 227 / 0.1038 / 63.88% | 227 / 0.10382 / 63.88% | ✓ |
| Pre-2026 qualifiers / ROI / CI | 172 / +8.8% / [+2.3, +15.3] | 172 / +8.80% / [+2.27, +15.33] | ✓ |
| Pre-2026 CLV / CI | +3.13 / [+2.44, +3.82] | +3.130 / [+2.436, +3.824] | ✓ |
| 2026 funnel | 227→112→75→23 | 227→112→75→23 | ✓ |
| 2026 ROI / CI | +23.6% / [+1.2, +46.1] | +23.63% / [+1.20, +46.07] | ✓ |
| 2026 CLV / CI | +6.22 / [+2.96, +9.49] | +6.223 / [+2.957, +9.489] | ✓ |
| Kelly ledger (end bank / staked / maxDD) | 1.027739895 / 10.1251% / 0.1759% | identical to 1e-9 | ✓ |
| Incremental audit (4 excess figures + CIs) | as reported | identical to 1e-3 | ✓ |
| Favorite share / dog P&L share | 96.5% / 56.8% | 96.51% / 56.84% | ✓ |

**Deterministic reproduction:** full re-run from raw data (no cache) in a scratch tree reproduced every artifact — 6,014 nested prediction rows, the 145-cell registry, the 16-row staking registry, both frozen spec JSONs, the 172- and 23-bet ledgers, stakes, and the incremental audit — with zero numeric differences beyond 1e-14 float noise, despite major dependency-version skew. The only differences: the hand-edited fields of F7 and the `--out` quirk of F8. Settlement integrity was additionally spot-verified externally: the ledger's two most consequential results (Gaethje TKO Topuria as a graded −1u favorite loss; Mitchell submitting Luna as a graded −1u dog loss) match public records.

---

## 4. Field-level temporal / leakage matrix

Every model and policy input, its source, and when it becomes knowable. "Entry time" is the validated-opener timestamp (first archive tick where available; archive open column otherwise).

| Field | Source table.field | Knowable at | Joined as-of | Post-open info? | Outcome/close proxy? |
|---|---|---|---|---|---|
| `z_open_fav`, `z_open_fav_sq` | `fights_openclose.f1/f2_opening_odds` → two-sided no-vig | line open | fight row (1:1, fight_id) | No | No |
| `open_vig` | same, `u1+u2−1` at open | line open | fight row | No | No |
| `open_lead_days` | `bfo_ticks` first paired tick vs event_date | line open | fight row (matchup-pair windowed to next occurrence, window `(prev_event+1d, event+1d]`) | No | No |
| `age_diff_fav` | `f1_dob/f2_dob` vs event_date | signing | fight row | No | No |
| `prior_diff_fav`, `prior_sum`, `debut_mismatch` | `f1_prior/f2_prior` (as-of prior-UFC-fight counts) | pre-fight | fight row | No | No |
| `card_position_pct` | ufcstats `competitions.csv` scrape order per event_url | announced pre-event (scraped post-event — F10 caveat) | (pair, event_date) 1:1 | Nominally no; day-of reorders possible | No |
| 10 × `*_dec_avg_diff_fav` etc. | `mma-ai/training_data.csv` (decayed averages of *prior* fights, McInerney anti-leakage pipeline) | pre-fight | fight_id 1:1 + event-date equality assertion | No (spot-verified: both-debut fights 90% null, veterans 100% populated) | No |
| `division` | competitions weightclass | signing | (pair, event_date) | No | No |
| **Target** `target_delta_logit` | logit(qfav_close) − logit(qfav_open) | post-close | label only | — | is the label |
| **Label** `target_dir` | sign of above | post-close | label only | — | is the label |
| `qfav_closing` | closing odds | post-close | labels, realized CLV, and **calibrator training target within training folds only** | — | by design |
| `result` | fight settlement (1=f1, 0=f2, 2/3=draw/NC) | post-fight | outcome grading + calibrator target (training folds only) | — | by design |
| Picks-model fields (`p_model_f1`, `model_gap_fav`, `p_fwd`, `p_rev`, `m1`, `b2_pred_fav`) | walkforward_model_preds | — | present in the frame, **excluded from every MOV-HOLD feature list; excluded set asserted in code; confirmed absent from frozen spec** | — | — |

Fold hygiene (verified on artifacts, not just code): expanding-window folds 2018–2025, `fold == event_year` for all rows; tuning (`light_tune`) validates only inside the training years; imputers/scalers/encoders/calibrator refit per fold; final 2026 scoring uses a single model fit on 2014–2025. The 2026 rows cannot affect feature construction (all features are per-fight, past-only), tuning, calibration, gates, BH, or sizing — mechanically true in code and confirmed by re-execution. Rematches/renames: normalized-name pair keys windowed to the next occurrence; 1:1 merge validators would have thrown on duplicate joins (none did; 0 duplicate fight_ids).

Odds/target math (all verified to ≤1e-14 against raw odds): decimal odds (BFO archive is decimal — confirmed, min 1.037); no-vig `q1=(1/O1)/((1/O1)+(1/O2))`; favorite orientation by `q1_opening ≥ .5` with exact sign inversion for dogs; CLV in points = `100·(qfav_close−qfav_open)·side`; unit returns win `O−1`, loss −1, draw/NC 0; Kelly `max((pO−1)/(O−1),0)`; per-bet cap then proportional event-cap scaling (re-simulated: ending bankroll matches to 1e-9); min acceptable price `= 1.01/p` (23/23 rows) with the correct "rescore on any other price" framing; the `estimated_raw_close_decimal` is display-only and enters no selection.

---

## 5. Calibration and residual diagnostics

**Market calibrator** (logit-cubic, no intercept, both sides duplicated): coefficients b1=1.0364, b3=0.0609. Exact symmetry `p(1−q)=1−p(q)` verified to 2e-16. Side-duplication affects no reported quantity (no SEs are drawn from that fit). The cubic term is inert, not overfit: walk-forward log loss cubic 0.60573 vs linear 0.60581 vs raw close-q 0.60686. The correction it encodes is the favorite side of the favorite–longshot bias: +1.4pp at q=0.70, +3.2pp at q=0.80, +4.9pp at q=0.90.

**Is the strategy just that calibration?** No — this was the audit's central question and the cleanest result. Rebuilding each fold's calibrator and applying it to the *opening* price (no movement model): only **1.7%** of the 172 qualifiers clear the 1% EV gate statically; only 8.1% have static EV ≥ 0; mean static EV is **−2.3%** (the vig eats the calibration boost). The movement forecast contributes the whole +6.0pp EV increment that creates qualification. The favorite-longshot correction shapes *where* the strategy hunts (heavy favorites); the movement model decides *whether* a bet exists.

**Direction head** (C=0.01, heavily shrunk): AUC 0.638; well calibrated in the actionable region (predicted 0.772 vs observed 0.785 in the (0.75, 0.80] bin; 0.833 vs 0.795 above). 7.1% of rows reach the 75% gate.

**Magnitude head**: R² 0.066 nested / 0.104 in 2026 (2026 sits inside the fold range — fold R² spans −0.02 to +0.13; 2019 was negative). Residual SD ~0.30 logits, roughly homoskedastic across price bands, with the F6 short-favorite over-prediction bias. Head coherence: pred-CLV sign agrees with the direction head in 99.2% of EV-qualified rows (corr 0.53) — combining them into selected-side predicted CLV is internally consistent.

**Kelly basis** (calibrated projected-close probability as settlement probability): on every evaluated sample the concern runs the *safe* direction — qualifier win rates exceed `p_market` (pre-2026: 86.7% vs 81.7%; 2026: 87.0% vs 78.4%), nested recalibration slope 1.047/intercept +0.03 (≈ideal), and `p_market` beats the open on Brier everywhere. No overbetting channel is visible at quarter-Kelly with 0.5%/1% caps (pre-2026 sim maxDD 2.3%). The residual caveat is F2/luck: those win-rate gaps are also the sample fortune that produced the ROI headlines.

---

## 6. Policy search and multiplicity

Reconstructed search: 2 feature specs (nested-R² pick) × 150 gate cells (145 with n≥40 survive) × 16 staking variants, plus the `choose_policy` filter battery (n≥150, strictness floors, clustered-CI>0, BH<10% on both metrics, positive 2021–23 *and* 2024–25 subperiods) and the strictness-first sort. Findings:

- **Exactly one cell passed all filters** — (75%, 2.0pp, 1%). The strictness sort was vacuous; the filter battery *is* the selection. The cell ranks 10th of 145 by raw ROI (it was not the ROI max; unadjusted p=0.0083, BH 0.035).
- The EV floor landed at 1% because the n≥150 rule eliminated stricter EV cells (n=172 at 1%; below 150 at 2%+): the gate sits at the *corner of the searched grid* on steam and CLV, and at the sample-size boundary on EV.
- **Gate-sensitivity** (including beyond-grid neighbors): the ROI surface is a noisy plateau — steam 0.65–0.80 × CLV 1.0–3.0 gives +4.7% to +10.5% with overlapping CIs, several neighbors' CIs crossing zero; favorite share climbs 79%→100% across it. **CLV is the stable surface** (+2.7 to +3.9pp everywhere, all clustered CIs > 0).
- **LOYO**: dropping any single year keeps ROI in +7.6%…+11.1% and CLV in +2.87…+3.41. **LOEO**: max single-event influence 0.75pp of ROI. Nothing hinges on one year or card.
- **Effective research DOF and debiasing (F2)**: a 200-replicate event bootstrap that re-runs the whole registry + `choose_policy` re-picks the same gates only 34.5% of the time; mean optimism of the chosen cell +1.4pp ROI → **debiased pre-2026 flat ROI ≈ +7.4%, lower bound ≈ +0.9%**. Beyond-package DOF (F1's earlier variants; years of movement research incl. a B2-lite benchmark) argue for further humility on ROI — but cannot plausibly manufacture the CLV result, which is p≈1e-18 scale and gate-insensitive.
- **Staking selection verified**: (λ=0.25, 0.5% bet cap, 1% event cap) is the argmax of log-growth among eligible variants in the registry; frozen values match.

---

## 7. Incremental value and concentration (stronger controls)

Package baseline replicated exactly, then strengthened. Pre-specified design: EV-qualified universe (n=753), treatment = steam+CLV gates, controls = logit(open prob of selected side), continuous selected EV, side, lead time, year FE; event-clustered SEs; for 2026, a counterfactual regression frozen on the 2021–25 EV universe.

| Test | Excess CLV (pp) | Excess ROI |
|---|---|---|
| Package cell baseline (replicated) | +1.27 [+0.64, +1.89] | +2.0% [−4.5%, +8.6%] |
| Cell baseline, qualifiers excluded (their cells included the treated rows — diluted) | **+2.12 [+1.45, +2.79]** | +5.0% [−2.1%, +12.1%] |
| Regression baseline, pooled | **+1.85 [+0.93, +2.77]** (z=3.95) | +5.8% [−4.0%, +15.4%] |
| Regression, favorites only | +1.70 [+0.89, +2.51] | +10.4% [+1.4%, +19.4%] (post-hoc cut — do not promote on it) |
| Regression, dogs only (6 treated) | +3.2 ± 4.7 (uninformative) | **−0.88 ± 0.30** (treated dogs lost) |
| 2026 vs frozen regression counterfactual | **+5.20 [+2.35, +8.05]** | +15.3% [−7.6%, +38.1%] |

Baseline-cell thinness confirmed (min cell n=3, median 10) — the quintile design is too coarse, and the regression baseline is the right instrument; it agrees with and strengthens the package's conclusion: **incremental CLV is real; incremental ROI is directionally positive and unresolved.**

Concentration: 2026 leave-one-bet-out ROI spans +17.0%…+29.3%; dropping the single biggest winner keeps +17.0%; event-bootstrap percentile CI [+4.4%, +48.5%], P(ROI≤0)=0.6% — the raw 2026 ROI is not one bet, but per F4 the dog sleeve (56.8% of P&L from 4 unverifiable bets, against negative pre-2026 dog evidence) must be treated as luck. The favorites-only, tick-backed core (n=14) still shows ROI +14.9% [−1.7%, +31.4%] and CLV +5.23 [+3.45, +7.01].

---

## 8. Execution and slippage

- **Named-book verification: impossible for this ledger.** Pinnacle capture begins 2026-07-26, per-book BFO panel 2026-07-27; the last holdout event is 2026-07-18. Zero overlap — every holdout price is a composite archive open. This alone caps the verdict at shadow.
- **Tick backing:** 19/23 qualifiers have archive tick paths; median open-vs-first-tick mismatch 0.0pp (good), but see F3 for the 9 problem rows.
- **Empirical slippage scale** (from the live per-book panel at line birth, 30 matchups, ≥3 books): cross-book no-vig spread averages 2.19pp (max 6.1pp); best book is on average 1.06pp *better* than consensus on the favorite. So consensus-open paper prices sit inside a ±1–3pp executable band — and pre-2026 mean CLV (+3.1pp) exceeds it, 2026 (+6.2pp) comfortably so.
- **Synthetic slippage with re-qualification** (haircut on the decimal margin, EV gate re-applied): pre-2026 ROI +8.8%→+7.5%/+6.9%/+6.3% at 1%/2%/3%; 2026 +23.6%→+23.3%/+22.9%/+22.5% (no bet falls out; 2026 EVs were large). The edge does not depend on flawless execution.
- **Latency:** only ~16% of the eventual selected-side move happens in the line's first 6h pre-2026 (~26% in 24h); in 2026 the first-day move was actually slightly negative. Same-day-but-not-instant entry historically retains ≳74% of the CLV. "Immediate at opener" is the right rule but not a knife's edge.
- One structural note: lead times run 5.7–139.6 days (median 10.1); the 139-day opener (Topuria–Gaethje) and the 9-day replacement (Luna) illustrate that "the opener" is a heterogeneous object — early superfight lines and short-notice replacement lines have very different liquidity. Prospective logging will measure this properly.

---

## 9. Corrective patches

`patches/portability.patch` (kept apart from the hash-referenced originals): resolve `--out` before deriving the sibling-module root; add `--repo/--out` arguments to `build_2026_bet_table.py`; add `--force-rebuild` to bypass the silent nested-predictions cache; recommendation to make `audit_movement_hold.py` write the revised status into the policy spec instead of hand-editing (F7).

---

## 10. Promotion recommendation

**Recommended status: `prospective-shadow-ready` — confirm the package's own `shadow_only_incremental_roi_not_resolved`, with the F1 language correction.** Do not promote to live on this evidence, and do not cite the 2026 ROI as validated edge.

Exact prerequisites for the next status (live-eligible review):

1. **Prospective, named-book, pre-registered signals.** Every future qualifier logged at signal time against an executable quote (Pinnacle and/or a named BFO-panel book), with the obtainable price, timestamp, and the frozen minimum-price rule applied. The capture infrastructure for this is already live. No retuning of model, gates, or sizing during the run; any refit restarts the clock.
2. **Resolve incremental CLV prospectively first.** At the observed qualification rate (~23 bets/6.5 months) and pre-2026 excess-CLV effect size (~+1.3–2.1pp, clustered SD ≈ 4pp), ~60–100 prospective bets give adequate power — roughly 18–30 months. Incremental *ROI* at ±5pp resolution needs several hundred bets; treat CLV as the promotion metric and ROI as a monitored, capped byproduct.
3. **Dog sleeve stays quarantined** (shadow-logged, zero stake or token stake) until it has its own prospective evidence; pre-2026 treated dogs were net losers and the 2026 dog P&L is unverifiable (F3/F4).
4. **Execution ledger requirements:** record book, price, limit, and fill; compare signal price vs best-available and vs Pinnacle; a bet that cannot be matched to an executable quote at ≥ the minimum acceptable price does not count as a strategy bet.
5. **Risk frame:** keep quarter-Kelly with the 0.5%/1% caps (verified maxDD profile); recheck the F6 short-favorite bias at the first scheduled refit.

### What would change the verdict

- *Downgrade to research-only* if prospective named-book quotes systematically fail to match qualifying openers (consensus-open unavailability), or prospective CLV attenuates toward zero (would indicate the historical signal was an artifact of the composite archive's open definition).
- *Upgrade path* exists purely through the prospective ledger — no amount of further backtesting on this data can move the verdict, because the binding constraints (execution verifiability, soft-holdout status, ROI power) are structural, not analytical.

---

### Appendix: audit artifacts

All under the session scratchpad `audit/` directory: `artifact_hashes_before.txt` (frozen manifest), `claim_reconciliation.csv` (41 checks), `recompute_claims.py`, `calibration_audit.py`, `policy_search_audit.py`, `incremental_audit_v2.py`, `execution_audit.py`, `repro/` (bit-exact re-run outputs), `patches/portability.patch`. External settlement sources: Yahoo Sports/CBS Sports (Gaethje–Topuria, UFC Freedom 250), MMA Mania/Tapology (Mitchell–Luna, UFC Vegas 118).
