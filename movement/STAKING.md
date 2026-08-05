# MOV-HOLD staking (amendment 2026-08-05b — bespoke, replaces 05a)

This staking policy is derived **only from this strategy's own qualifier stream**
(favorite-heavy, ~87% historical win rate, mean price ≈ −330, ~40 A-signals/yr) —
not inherited from the picks-model policy or the backtest's proof-stage caps.
Variant simulation over the 172 pre-2026 + 23 holdout bets and a 2,000-season
event bootstrap: `staking_design.py` (audit scratchpad); results table below.

Paper bankroll: **$10,000** (`paper_bankroll_usd` — the single scaling knob).

## Tier A rules

1. **Stake = 0.25 × Kelly** at the price actually takeable (best available if it
   clears the minimum acceptable price, else the minimum).
   `k = (p·O − 1)/(O − 1)`, `f = min(0.25·k, 5%)`.
2. **Per-bet cap 5%** of bankroll ($500). Binds on heavy favorites (raw quarter-
   Kelly reaches 10%+ there); costs almost no growth vs uncapped and removes the
   −8% single-event tail.
3. **No event cap.** Fight outcomes on one card are approximately independent;
   the old 1% event cap was a proof-stage artifact. Multiple same-card signals
   each get full size.
4. **Open-exposure circuit breaker: 25%** of bankroll in unsettled A stakes at
   once. Rarely binds (a 3-signal card ≈ 10–13%); exists for pathological weeks.
   An over-ceiling batch scales proportionally; placed stakes never resize.
5. Non-counting signals (late discovery, <24h, past events): $0.

## Tier B

Flat **$50** (0.5%) paper units, unlimited count. Evidence collection only.

## Why this point on the curve (simulated on the strategy's own bets)

| Variant (no event cap) | 8-season path | Max DD | Handle/yr | Boot p95 DD | P(losing season) |
|---|---|---|---|---|---|
| old 0.25K + 0.5% cap | +7.7% | 2.4% | 11% | — | — |
| 0.25K + 3% cap | +47% | 10.7% | 68% | 7.9% | 16% |
| **0.25K + 5% cap (chosen)** | **+60%** | **14.3%** | **95%** | **10.5%** | **16%** |
| 0.25K uncapped | +69% | 15.0% | 114% | 13.1% | 20% |
| 0.50K + 5% cap | +91% | 18.6% | 135% | 14.4% | 19% |
| 0.50K uncapped | +172% | 28.3% | 311% | 24.1% | 18% |

Half-Kelly is the visible next rung, and it is deliberately NOT taken while the
edge estimate carries selection-debias uncertainty (audit: raw +8.8% → debiased
≈ +7.4% pre-2026). Over-Kelly on an overestimated edge is how bankrolls die.
Revisit at the first GREEN review with prospective data in hand.

## What this means in dollars at $10k

- Typical A bet **$300–500** (cap-bound on big favorites), ~40/yr.
- **Handle ≈ $9,500/yr** (~95% of bankroll turned over) — 6.3× the 05a design.
- Median season ≈ **+7%** if the edge is real; a losing season happens ~1 year
  in 6; expect a **10%+ drawdown ($1,000+) every few seasons** — that is the
  price of this aggression and it is pre-accepted here, in writing.
- 2026 H1 replay under these rules: +19.1% on the 7 months, max DD 3.0%.

## Scaling

Fractions are frozen; the base scales. $25k → $1,250 max bet / ~$24k handle;
$50k → $2,500 max bet / ~$48k handle. Real money still ramps per PREREG (paper →
GREEN → token probe → second GREEN → full fractions). Changing the Kelly
multiplier or caps again after outcomes exist = new policy id, cohort restart.
