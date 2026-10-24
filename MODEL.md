# Experimental public Codex extra-reset model

This is executable Python 3.7+ standard-library code, not a calibrated forecast or an official promise. It performs no network requests, model inference, account access, scheduling, or publication. The public event ledger contains no personal quota or normal renewal cycle. Direct extra resets and banked-card issuance are separate targets; their probabilities are never added or called an aggregate chance.

## Baseline and assumptions

For each type independently, a Gamma-Poisson model uses `alpha = alpha0 + verifiedEvents`, `beta = betaDays0 + observedDays`, and `p0(H) = 1 - (beta / (beta + H)) ** alpha`. H is measured in days. The output horizon is 24 hours. This assumes a constant event rate within the horizon, an unvalidated simplification.

The initial engineering prior is alpha0=1, betaDays0=9 for each type: 10% over 24 hours with zero usable observations. This is NOT a measured historical frequency. Prior sensitivity betaDays0=19,9,4 produces 5%,10%,20% with alpha0=1 and no data; these are hypothetical scenarios, not confidence intervals. Current usable observations and verified outcomes are both zero. The output is explicitly cold-start and uncalibrated. No new post still yields this baseline after a successful source check; no inference call is needed for the calculation.

Only `complete_verified` coverage of `public_codex_extra`, with type and UTC interval known, supplies exposure. Overlapping coverage intervals are merged. Missing/unknown coverage contributes neither no-event days nor positive-event counts. An occurrence is counted only when its latest known revision is fulfilled, source and outcome independently verified, its actual occurrence time is known, and that time lies inside eligible coverage. Selected historical posts do not establish complete coverage.

## Subjective evidence update

An explicit verified official FUTURE commitment, by Tibo or any other verified official author, can change the odds of the SAME type of public extra event in the SAME 24-hour horizon. Qualification requires: canonical event ID; state announced; sourceVerified=true; official=true; scope public_codex_extra; kind direct or banked; explicitCommitment=true; timezone-aware target window and expiry; remaining window ends inside the horizon and has not passed. Unknown scope/type, a broad window beyond the horizon, a feature release, usage doubling, recovery from an incident, popularity or community discussion does not qualify. Actual authorship/source classification is audited input, not inferred by this program.

The default subjective multiplier L=4 transforms odds: `p = L*p0 / (1-p0 + L*p0)`. At p0=10%, this gives 30.7692%. Sensitivity L=2,4,8 gives 18.1818%,30.7692%,47.0588%. These are public engineering assumptions, NOT learned likelihood ratios or backtested accuracy. Parameters allow L from1 through20 for qualified commitments only. All other feature multipliers remain1. Any future nonneutral release/incident weight requires a separate documented model revision.

Revisions are selected by knownAt at the prediction cutoff. Same (kind,eventId) is one event; duplicate posts belong in its sources, not new events. Multiple current promises use a single maximum-event cap, never a product: posts and promises may be correlated. A newer cancellation, scope correction, reclassification, expired target or expired evidence removes the update. An execution claim is distinct from an independently verified fulfilled outcome. Commitments do not count as historical outcomes. Feed expiry is capped by the earliest applied commitment deadline, so a collection failure cannot keep its influence current indefinitely.

`baselineProbability` is p0; `probability` is the updated p for that same event/horizon; `evidenceMultiplier` and evidenceEventIds explain the change. They do not refer to different events. Direct and banked updates are independent. Default10% plus a commitment remains below60%, so it is displayed without highlight. Highlight additionally requires p strictly greater than60% AND current qualified official evidence. A high baseline alone never passes the gate.

## Ledger and source audit

`events.json` is an append-only revision ledger in normal operation. Preserve prior records when corrections are added with a later knownAt. A cancellation uses the same kind and eventId. A type correction also revokes the old type's record; the two types are intentionally independent. Every record needs sources and knownAt; never backdate knowledge to a post's publishedAt. Duplicate revision keys compare the parsed UTC instant, so different offset spellings of the same instant cannot evade conflict rejection. `occurredAt` is the actual verified occurrence time, not announcement or observation time. When unknown, keep it null. Observation coverage is a separate reviewed assertion; a successful search is not automatically complete historical coverage.

The three exact primary-post audits recorded on 2026-10-24 were supplied by the source reviewer; this engine did not scrape them. The October20 wording announces a reset but leaves product scope/type/execution time unresolved. The October17 and October15 URLs support future promises, not the aggregator's claimed completion text/time. All three are excluded from fulfilled training samples. The mismatches do not prove nonoccurrence. The20 unverified candidates over90days are explicitly not samples. A separate successful current Posts/Replies review at2026-10-24T08:31:23Z found no new reset evidence and advances collection.checkedAt. Historical auditing alone never renews current-feed freshness.

## Time, publication and failure

`updatedAt` is the successful current-source check time; `windowStart` equals it, and `windowEnd` is exactly24hours later. This is an evaluation horizon, NOT a predicted execution clock. Unknown event clocks remain unknown in the ledger. `expiresAt` is no later than checkedAt+3hours or any applied evidence deadline. A repeated calculation from the same check is deterministic and does not renew expiry. Failed collection, a future check, or stale evidence produces an error before writing. Existing output remains byte-identical; consumers must show it expired when its original expiry arrives.

The program writes an atomic JSON replacement bounded by64KiB. It never publishes. The parent publisher remains the single writer of forecast.json. The model's no-inference claim applies to computation; public-source collection and publication remain separate operational responsibilities. No new scheduler or workflow is included.

## Walk-forward evaluation

`backtest_runner.py` uses only events and coverage known by each cutoff for training and evidence. Future labels require an independently complete observation interval covering the entire forecast horizon, known by evaluation time. Missing, immature or unverified labels are null, not failures or zeroes. Brier score is returned only for known labels and never establishes calibration. Current real ledger has no scorable coverage; no accuracy score is claimed. Synthetic tests demonstrate leakage protection and update/retraction behavior, not predictive skill.

## Run

From this folder, run `python test_engine.py`. Then use `python model_engine.py --ledger events.json --params parameters.json --output candidate-forecast.json` after a genuinely successful source check has been recorded. Do not change checkedAt merely to make a stale candidate pass. For reproducible review only, add `--now 2026-10-24T08:31:23Z`; the bundled candidate retains its historical expiry.

Example offline backtest: `python backtest_runner.py --ledger events.json --params parameters.json --cutoffs 2026-10-23T07:48:07Z --evaluation-time 2026-10-24T08:09:00Z --output backtest-review.json`.

For publishing, upload model_engine.py, parameters.json, events.json, test_engine.py, backtest_runner.py, MODEL.md and CLIENT_CONTRACT.md. Run the tested engine from a fresh legitimate source-check ledger, and publish its generated forecast.json together with the documentation/ledger revision. The bundled candidate-forecast.json and synthetic fixtures are review artifacts, not production announcements. Never publish Windows settings, quota, health reports or app resources to this repository.
