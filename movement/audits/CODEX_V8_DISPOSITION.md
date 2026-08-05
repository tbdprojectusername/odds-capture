# Codex V8 deployment audit — archive note

The full V8 report and MOV_V8_MINIMAL_PATCHES.diff were delivered 2026-08-05 in
the working session. Verdict: FIX-BEFORE-CONTINUING (9x P1, 7x P2, 2x P3-pass).
Remediation implemented same day as MOV-HOLD-2.2 — see
PREREG_REMEDIATION_2026-08-05c.md and commits tagged "V8" in this repo.

Finding disposition (all accepted):
F1 paper-fill fabrication -> patched (paper_filled fields, fill-only ROI)
F2 parity tested MOV-MKT-1 -> regenerated with MOV-MKT-2: 91.6% (was "93.8%")
F3 "all 10 land in B" -> erratum: 9/10 (old artifact); 7/8 (new artifact)
F4 Pinnacle-only opens -> open-source cohorts frozen, no pooling until transport test
F5 staking sim != live rule -> acknowledged; 5% cap relabeled risk preference
F6 cap not objective-chosen -> same; fill-aware sim required before real sizing
F7 women guard fails open -> fail-closed + bout_domain.csv
F8 silent ops failures -> workflows fail loudly, push checks, issue dedup
F9 GREEN cohort wording -> live Tier A favorites, prospectively tagged
F10 entry-EV redefinition -> ev_open + open_gate_tier stored per signal
F11 groupby.last() resurrection -> tail(1), reference rebuilt
F12 name matching fail-open -> covered by F7 fail-closed
F13 close staleness -> close_t/gap_min recorded; <=60min primary rule
F14 cap contradiction -> resolved in addendum
F15 real-bet discipline -> protocol_eligible/exception_reason added
F16 concurrency/gaps -> brief decoupled; heartbeats remain open pre-GREEN
F17 05a/05b timing -> PASS (verified)
F18 band-correction rejection -> PASS (upheld, incl. their OOF variant)

## Focused recheck round 2 — CLEARED (2026-08-05)

Codex verified all six focused tests at d8a4442: hashes exact, push-failure
paths exit nonzero, ROI cohort boundary enforced end-to-end (pre-remediation
winner descriptive-only), fresh rows carry cohort fields, policy/dashboard
identity correct, issue dedup fail-closed, GREEN aggregator NOT_GREEN with
empty funnel as expected. Independent-recheck prerequisite SATISFIED.
Model-directed real-bet pause LIFTED. Still gated: GREEN (n>=60 eligible),
transport test (Pinnacle-only vs retail pooling), real sizing above token
(GREEN + fill-aware sim + second GREEN). Non-blocking note 1 (explicit
booleans on quarantined rows) fixed same day; note 2 (ops attestation
hard-coded false in green_report) is intentional fail-safe design.
