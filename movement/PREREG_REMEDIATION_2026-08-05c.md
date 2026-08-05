# MOV-HOLD-2.2 — remediation addendum (2026-08-05c)

Registered in response to the Codex V8 deployment audit (`movement/audits/`),
**before the first counted settlement** (earliest counted event: 2026-08-08).
Historical ledgers are immutable; every correction here is an append-only field,
a new artifact, or a forward rule. This addendum supersedes conflicting prose in
PREREG.md and STAKING.md; it does not reopen the accepted MOV-HOLD-1 statistical
record.

## Errata against prior documents (V8 F3, F2, F14)

1. **"All 10 audited-A drift rows land in B" was wrong.** Exact-precision truth
   for the old artifact: **9/10** (Sutherland–Pericic steam 0.599976 < 0.60).
2. **The shipped 93.8% "parity" tested MOV-MKT-1, not the deployed model.** The
   regenerated deployed-pipeline artifact (`parity/parity_2026_movmkt2.csv`,
   MOV-MKT-2 live side, literal-row reference semantics) shows **91.6%**
   agreement vs the shipped MOV-HOLD-1 artifact: 15 both-A, 11 live-only-A,
   8 shipped-only-A of which **7/8** meet exact B gates. This measures combined
   refit + feature-transport drift; it is a pipeline-fidelity description, not
   an OOS performance claim (MOV-MKT-2 trains through 2026-07-25).
3. **Cap contradiction resolved:** the ACTIVE paper policy is 05b
   (0.25×Kelly, 5% bet cap, no event cap, 25% open-exposure ceiling). The
   0.5%/1% figures elsewhere in PREREG are the superseded 05a text and are void.
   Real-money sizing is NOT governed by either: see "Staking separation" below.

## Execution integrity (V8 F1)

- A threshold is never a fill. Signals carry immutable
  `clears_min_at_scoring, paper_filled, paper_fill_dec, paper_fill_book,
  paper_fill_time`; stakes and ROI exist only for `paper_filled` rows at the
  recorded fill price. Non-filled settled signals grade `settled_unfilled`
  (CLV only, no unit return).
- **Paper fill/ROI/staking evidence restarts at remediation_ts
  (2026-08-05T20:30Z).** Pre-addendum rows keep descriptive CLV, flagged
  `pre_remediation`.

## Domain and identity (V8 F7, F12)

- Women's bouts remain excluded. Additionally the scorer now **fails closed**:
  any bout containing a fighter absent from the static reference is quarantined
  (`excluded_unverified_domain`) until a human classifies it in the append-only
  `reference/bout_domain.csv` (signal_key, domain, classified_by, basis).
  "Unmatched means male debutant" is retired.
- Reference tables use literal-latest-row semantics (`tail(1)`); the
  `groupby.last()` column-wise resurrection defect is fixed and the static
  table rebuilt.

## Cohorts and promotion (V8 F4, F9, F10)

- **The primary promotion cohort is prospectively-tagged live Tier A
  favorites**, evaluated exactly as scored by the deployed system. Tier B is
  never added retrospectively. Signals additionally carry `open_gate_tier`
  (EV at the frozen open) alongside the operative entry-gate tier; the
  promotion decision validates the entry-gated system and says so.
- **Opening-source cohorts:** `open_source` and `open_n_books` are frozen per
  signal. Retail-consensus opens and Pinnacle-only opens are reported
  separately; they are not pooled for GREEN unless a pre-declared transport
  test (signed Pinnacle-vs-first-retail gap, ≥30 pairs, |mean gap| < 0.5pp)
  passes first.

## Close quality (V8 F13)

Grades store `close_*_t` and `close_*_gap_min`. Primary GREEN rows require a
Pinnacle close snapshot **≤60 minutes** before start (≤30 reported as high
quality). Stale-close rows are reported separately and excluded from the
primary statistic. GREEN additionally requires ≥60% eligible-close coverage
with no material source/side imbalance.

## GREEN criteria (restated, binding)

≥60 counted, paper-filled, eligible-close live Tier A favorite signals across
≥30 events; event-clustered 95% CI lower bound > 0 on mean CLV vs eligible
Pinnacle close; point estimate ≥ +1.5pp; executable-at-scoring ≥60%; ≥30
consecutive days without an unexplained signal/grade gap; sensitivity reported
for source cohorts, unmatched rate, close quality, and missed runs.

## Staking separation (V8 F5, F6)

The 5% cap is a **risk preference, not a validated optimum**: the 05b
simulation sized at historical opens without the live fill floor (open-basis
+60.4%/14.3% DD vs conservative minimum-price replay +42.5%/9.0% DD). GREEN
validates signal/execution quality only. The first real probe stays ≤0.1%
bankroll per eligible Tier A favorite; anything larger requires a fill-aware
staking simulation on prospective fills and a second independently audited
GREEN.

## Real bets (V8 F15)

Real bets require book, bet id, accepted time, price, stake, currency, and
confirmation. Rows carry `protocol_eligible` and `exception_reason`; assumed
fills and discretionary exceptions (the 2026-08-05 Brahimaj B-dog) never enter
system P&L claims.

## Operations (V8 F8, F16)

Scorer failure now fails the workflow after capture is safe; pushes verify
success; signal issues are deduplicated; the morning brief has its own
concurrency group. Remaining follow-ups: heartbeat alarms and expected-pair
reconciliation (open item before GREEN, per prerequisite 10).

## Independent recheck (V8 prerequisite 16)

Before any GREEN is trusted, an independent reviewer re-runs: chain hashes,
the MOV-MKT-2 parity generator, a scratch scorer run, the failure paths, and
the GREEN aggregation.
