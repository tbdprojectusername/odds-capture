# MOV-HOLD-2 staking (amendment 2026-08-05a — mechanics; fractions unchanged)

Paper bankroll: **$10,000** (`paper_bankroll_usd` in the policy spec — one number to
change; every stake scales linearly with it).

## Tier A — the audited policy (Kelly, capped)

1. **Edge basis:** the calibrated market probability `p` and the price actually
   taken (best available if it clears the minimum; otherwise the minimum price).
2. **Kelly fraction:** `k = (p·O − 1)/(O − 1)`, staked at **0.25×k**.
3. **Per-bet cap: 0.50%** of bankroll ($50). Heavy favorites almost always hit this
   cap (their raw Kelly is 2–6%), so most A stakes are cap-bound.
4. **Per-event cap: 1.00%** ($100), A-tier only. First-come remaining-budget;
   signals arriving in the same scoring run that jointly exceed the remaining
   budget scale proportionally (the backtest's rule). Placed stakes never resize.
5. Non-counting signals (late discovery, <24h to event, past events): **$0**.

Why these numbers: they were frozen from the pre-2026 staking registry (highest
log-growth among variants with max drawdown ≤15%, verified in the audit — the
historical path staked ~87% of bankroll cumulatively over 8 years with a 2.3% max
drawdown). They are deliberately proof-stage small: the dry run's job is to settle
whether the edge is real, not to make money while unproven.

## Tier B — expansion cohort

Flat **$10** (0.10%) paper units, outside the event cap. B exists to accumulate CLV
evidence at 3× volume; its stakes are bookkeeping, never money.

## What this looks like in dollars

Roughly 40 A-signals/year, mostly cap-bound: ~$1,400–1,800/year total staked at the
$10k paper bankroll. At the audit's debiased ROI expectation (low-to-mid single
digits if the edge is real), that is on the order of **$50–120/year of expected
paper profit** — intentionally tiny. The instrument is the CLV ledger, not the P&L.

## Scaling (pre-committed path, PREREG "Staking ramp")

Stakes grow only two ways, both gated on the green criteria:
- **Bankroll scaling** — same fractions on a larger base (e.g., $50k bankroll →
  $250 max bet, $500 event cap). This is the intended lever ("up our stake
  amounts"): fractions stay frozen, the base grows with evidence.
- **Token-real probe** after first GREEN review: ≤0.1% real per bet, A-tier
  favorites only, named-book prices at or better than the minimum.
- Full frozen fractions in real money only after a second consecutive GREEN.

| Bankroll | Max/bet (0.5%) | Event cap (1%) | ~Annual staked | B unit |
|---|---|---|---|---|
| $10,000 | $50 | $100 | ~$1,500 | $10 |
| $25,000 | $125 | $250 | ~$3,800 | $25 |
| $50,000 | $250 | $500 | ~$7,500 | $50 |

Changing the Kelly multiplier, the caps, or moving B-tier to real money is a
policy change: new id, new pre-registration, cohort restarts.
