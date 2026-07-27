# odds-capture

Timestamped MMA betting-odds snapshots, collected automatically every 20 minutes
by GitHub Actions. Scrapers only — no models, no predictions, no strategy.

## Why this exists

Odds move continuously, but most public archives keep only an "opening" and
"closing" number with no timestamps. That makes it impossible to prove a price
was actually available when a decision was made. This repo records *when* each
quote was observed, so downstream analysis can be honest about executability.

## What it collects

| File | Source | Contents |
|---|---|---|
| `data/bfo_YYYY-MM.csv` | BestFightOdds | Moneylines from ~7 named books per bout, all upcoming UFC events |
| `data/pinnacle_YYYY-MM.csv` | Pinnacle public guest feed | Moneylines for UFC, plus Pinnacle's published max-stake |

One row per (poll, matchup, side, book). Monthly files keep diffs small.
`poll_time` is UTC and is the authoritative clock — the GitHub scheduler is
best-effort and may lag, so cadence is irregular by design; timestamps are not.

BFO is **primary** because it posts earliest and covers multiple books and
multiple future events at once. Pinnacle is **secondary**: it posts UFC late and
caps MMA limits, but it is a single named book with an explicit limit field.

## Caveats worth knowing

- `american` is the price as displayed. De-vig before treating anything as a
  probability, and check that a two-side pair sums to a plausible overround.
- Pinnacle's `max_risk` is denominated in the **account's** currency (observed as
  CAD), not USD. Normalize before comparing across books.
- **BetOnline and Pinnacle are not among BFO's listed books**, so BFO is a
  timing/consensus instrument rather than a record of any one venue's executable
  price.
- BFO **props** (round totals, method, decision) live behind a per-matchup link
  and are *not* captured here yet.
- The BFO parser depends on that site's two-parallel-tables layout. If a poll
  reports 0 quotes, the layout changed — the workflow fails loudly on purpose.

## Running locally

```bash
pip install -r requirements.txt
python poll_bfo.py --out-dir data
python poll_pinnacle.py --out-dir data
```

## Notes on the schedule

The workflow commits its own data, which counts as repository activity — that
keeps GitHub from auto-disabling the cron after 60 idle days. Scheduled runs are
free on public repositories.
