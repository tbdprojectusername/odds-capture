# movement/ — MOV-HOLD-2 prospective dry run

Cloud-native paper-trading of the audited MMA moneyline movement strategy
(MOV-HOLD-1 → audited 2026-08-05 → refrozen as MOV-MKT-2 / MOV-HOLD-2).
Everything runs in GitHub Actions on this repo's captured odds; nothing local.

**Governance: PREREG.md.** Gates, tiers, counting rules, pass/fail bars and the
staking ramp are pre-registered there. Code changes that alter behavior require a
new policy id.

## How it works

1. `poll-odds.yml` captures BFO (per-book retail) + Pinnacle every ~10 min (hourly
   job, 5 internal polls), then runs `score_signals.py`:
   - new two-sided UFC moneylines are detected; their first sighting freezes the OPEN;
   - the frozen MOV-MKT-2 spec scores steam probability, movement magnitude,
     projected close, calibrated win probability, EV at the current ENTRY quote;
   - pre-registered gates assign tier A (audited policy) / tier B (paper expansion);
   - women's bouts are excluded (model domain is men's UFC; see PREREG);
   - each new A/B signal opens a GitHub issue with the bet card: fighter, side,
     **minimum acceptable price** (decimal + American), best captured price/book,
     paper stake. At or above the minimum: bet at any book. Below: pass. Never chase.
2. `grade-ledger.yml` (Mondays) freezes closes for started events, computes realized
   CLV vs the Pinnacle close (primary metric) and retail-consensus close, merges
   settlements from `results/results.csv`, refreshes `DASHBOARD.md`, and appends
   settled fights to the reference log so prior-fight counts stay current.

## Files

- `specs/` — frozen model + policy JSONs (hashes pinned in PREREG.md)
- `score_signals.py` / `grade_ledger.py` — scorer and grader (pure pandas/numpy)
- `reference/` — fighters_static.csv (stats as of last completed fight),
  fights_log.csv (prior/recency source), women_keys.csv (domain exclusion),
  build_reference.py (local rebuild; refresh roughly monthly or after big cards)
- `state/first_seen.csv` — frozen opens; `ledger/signals.csv` — append-only signals;
  `ledger/graded.csv` — CLV + settlement; `DASHBOARD.md` — cohort scoreboard
- `parity/parity_2026.csv` — live-vs-backtest feature parity evidence (93.8%)
- `results/results.csv` — settlement fill (columns: signal_key, winner_key; use
  `draw`/`nc` for voids)

## Operating notes

- The ledger is append-only and git-versioned; history rewrites on master are the
  tamper signal.
- A signal counts toward the prospective cohorts only if scored ≤7 days after line
  birth and ≥24h before the event (flag `counts_prospective`).
- Reference staleness: decayed-average stats update only on `build_reference.py`
  rebuilds; priors/recency update automatically as events settle. Run a rebuild
  after every few cards (locally; commit the CSVs).
