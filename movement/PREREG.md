# MOV-HOLD-2 — pre-registration (prospective dry run)

Registered 2026-08-05, before the first prospective signal. This document governs the run.
Nothing below changes mid-run; a change requires a new policy id and a fresh cohort.

## System under test

- Movement model `MOV-MKT-2`: MOV-MKT-1 architecture (audited 2026-08-05, verdict
  prospective-shadow-ready), expanding-window refit on all completed fights through
  2026-07-25 (4,843 rows). The candidate heavy-favorite band correction FAILED nested
  pre-2026 validation (pooled R² 0.0656 → 0.0619) and is NOT included.
- Policy `MOV-HOLD-2` (specs/mov_hold_2_policy_spec.json):
  - **Tier A (the audited policy)** — steam ≥ 75%, predicted CLV ≥ 2.0pp, EV ≥ 1%.
    Kelly-staked on the paper bankroll (0.25×, 0.5% bet cap, 1% event cap).
  - **Tier B (expansion cohort, paper only)** — steam ≥ 60%, predicted CLV ≥ 1.0pp,
    EV ≥ 1%. Flat 1u. Pre-registered NOW, before any prospective data: it exists to
    (a) triple observation volume for the CLV question and (b) catch audited-policy
    bets that drift below A gates under live features.
  - **Execution floor** — minimum acceptable price = 1.02 / p_market (EV ≥ 2% at the
    price actually taken). At or above: bet. Below: pass. No chasing, no rebets.
  - **Underdogs are included** (user decision 2026-08-05), tracked as a separate
    cohort. Pre-registered caveat: the pre-2026 dog evidence is 6 bets, net losers;
    the 2026 dog windfall was execution-unverifiable. The dog cohort must earn its
    own prospective record before any real-money weight.

## Known live-vs-backtest gaps (measured, accepted)

- Feature parity vs the audited backtest construction: **93.8% same qualify/reject**
  on 2026 H1 (227 fights). Drift direction is conservative (live fires fewer A-tier);
  all 10 backtest-A bets that drift land in Tier B. Sources: fighter stats one fight
  stale (refreshed after each event for priors/recency; decayed averages refreshed on
  manual reference rebuild), card position unknown pre-event (median-imputed,
  |std coef| 0.07), division approximated by last bout's class.
- The live "open" is the first two-sided capture sighting (retail consensus of
  BetWay/Caesars/BetRivers/FanDuel/Unibet; Pinnacle fallback), not the BFO archive
  composite. Entry EV and CLV are measured from the ENTRY quote (scoring time), which
  is the price a bettor can actually act on.

## Domain restriction

**Women's bouts are excluded from scoring** (reference/women_keys.csv, built from
UFCStats weight classes). The training frame is men's UFC bouts only; scoring women
would run the model out-of-distribution with fabricated imputed profiles — the first
live board demonstrated this (fake +21% to +34% dog EVs on women's fights, all from
male-median imputations). Excluded bouts are logged with tier=excluded_womens. A
women's model is a separate future registration ([[wmma-model-plan]]).

## Counting rules

A signal **counts toward the prospective cohorts** only if: its tier gate passed,
the line was first seen ≤ 7 days before scoring, and the event starts ≥ 24h after
scoring. Late discoveries and none-tier rows are logged but excluded. One signal per
pair per event; scored exactly once; never rescored on price moves.

## Metrics and pass/fail (evaluated at scheduled quarterly reviews only)

Primary: realized CLV of the selected side vs the **Pinnacle close** (no-vig),
event-clustered. Secondary: CLV vs retail-consensus close. ROI: monitored, never a
mid-run decision input.

- **GREEN (open real-money discussion for Tier A favorites):** Tier A prospective
  CLV vs Pinnacle close positive with clustered 95% CI clear of zero and point
  estimate ≥ +1.5pp, over ≥ 60 counted A signals; AND executable-match rate
  (best price ≥ min price at scoring) ≥ 60%.
- **YELLOW (continue):** CLV positive, CI not yet clear, or n < 60.
- **RED (stop, do not retune):** CLV CI upper bound < +0.5pp after 60 counted A
  signals, or executable-match rate < 30% sustained for a quarter (the historical
  opener edge was not obtainable), or any data-integrity failure.

Expected volume: ~40 A signals/year, ~90–110 A+B/year. ROI at ±5pp resolution needs
several hundred bets and is explicitly out of scope for this run's verdict.

## Amendment 2026-08-05b — bespoke staking (supersedes 05a; policy id → MOV-HOLD-2.1)

Re-registered the same day, with **zero graded outcomes** at the time of change
(nothing settled; no outcome was peeked). Gates, tiers, counting rules and metrics
unchanged; the cohort continues. Staking is now derived from this strategy's own
qualifier stream instead of the backtest's proof-stage caps: 0.25×Kelly at the
takeable price, **5% per-bet cap, NO event cap**, 25% open-exposure circuit
breaker, $10,000 paper bankroll, B-tier flat $50 paper units, non-counting
signals $0. Simulation basis and dollar expectations: STAKING.md. Pre-accepted
consequence: ~95%/yr handle, 10%+ drawdowns every few seasons, ~1-in-6 losing
seasons if the edge is real. Any further sizing change after outcomes exist ends
the cohort.

## Staking ramp (pre-committed)

Paper throughout the dry run. IF GREEN at a quarterly review: token real stakes
allowed on Tier A favorites only (≤ 0.1% bankroll per bet) as an execution probe,
named-book prices only, while the ledger continues. Full frozen fractions (0.25×
Kelly, 0.5%/1% caps) only after a second consecutive GREEN review. Dogs and Tier B
remain paper until their own cohorts meet the same bar.

## Refit schedule

Model coefficients may be refit on completed fights once per year (January), same
architecture, same gates, new model id suffix; the prospective cohort continues
uninterrupted. Any change to FEATURES, GATES, SIZING, or COUNTING RULES ends
MOV-HOLD-2 and starts a new pre-registration.

## Frozen artifact hashes (SHA-256)

- specs/mov_mkt_2_model_spec.json: FB8C38A373086BB4E5E0FA7017B4CA1613827C5B8C1929828473D855D192BEDB
- Policy spec + code: hashes pinned by git history in this repo (append-only ledger;
  force-pushes to master are the tamper signal).
