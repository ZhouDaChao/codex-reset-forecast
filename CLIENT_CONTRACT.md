# Schema1 model extension contract

Version: gamma-poisson /1.0.0-experimental. Producer and client must agree before the parent switches the live feed. HTTPS transport and the existing64KiB cap remain unchanged. A model-bearing record must have root resetType=direct; banked, unknown or missing root types are rejected rather than borrowing the direct evidence gate. Legacy records without model retain their existing type support.

## Existing root fields

| Field | Meaning |
| --- | --- |
| schemaVersion | 1 |
| status | prediction for experimental estimates; never official confirmed merely because p is high |
| windowStart/windowEnd | UTC/offset evaluation horizon, checkedAt through checkedAt+24hours; not a promised event clock |
| resetType | direct for this producer's root; banked is a separate extension estimate |
| subjectiveProbability | Same updated direct probability as model.direct.probability, except the legacy safety case below |
| sources | Public model documentation plus eligible public commitment sources, max8 HTTPS URLs |
| updatedAt | Successful current-source check, never calculation/HTTP download time |
| expiresAt | Min(check+3hours, each applied commitment's target end/expiry) |

The existing optional eventId is `experimental-direct-24h`. A later valid updatedAt is a revision of this continuing estimate; changes to the model extension participate in the cache identity. Equal updatedAt with changed content is rejected by the existing conflict guard, so an actual new source check must accompany revised production content.

Legacy safety case: when direct probability>0.60 but no qualified evidence gate exists, subjectiveProbability is null and model.direct.probability retains the true estimate. Null means unavailable to a legacy client, not0 or no event. This prevents the already deployed old client from highlighting a pure baseline. The new client displays the true model probability. All other nonnull root values must match the model probability within1e-9; mismatches are invalid. Rootnull plus model known is accepted only for this safety case. The actual previous EXE was tested with the extension without running its Program or quota client.

## Optional model object

Required identity/semantics: schemaVersion1, name gamma-poisson, version1.0.0-experimental, experimental=true, calibrated=false, coldStart boolean for the ROOT direct estimate, windowSemantics evaluation_horizon, horizonHours24, targetScope public_codex_extra or explicit unknown, descriptionUrl public HTTPS.

`direct` and `banked` each contain probability (updated p ornull), baselineProbability(p0), alpha, betaDays, verifiedEvents, observedDays, coverageKnown, coldStart, countedEventIds, excludedEventIds, priorSensitivity, evidenceMultiplier, evidenceEventIds, evidenceAggregation maximum_single_event, evidenceSensitivity, alertEligible. All probabilities are fractions0..1. Prior sensitivity records alpha0/betaDays0/p0; evidence sensitivity records multiplier/updatedp. These are separate unvalidated engineering scenarios, not uncertainty intervals. alpha/beta describe the baseline only; they are not a fitted posterior after the subjective odds update.

Top-level model.evidenceEventIds, evidenceGate and alertEligible refer ONLY to the root direct estimate. evidenceGate is current_verified_commitment when eligible current evidence exists, otherwise no_current_verified_commitment. alertEligible requires updatedp>0.60 and that gate. Banked metadata remains in model.banked and does not turn a direct label into a combined forecast. No banked high probability is silently described as direct. A future publisher wanting banked in the root needs a coordinated contract revision; this producer always uses direct in the root.

`features` lists latest as-of public records, classification flags and qualifying likelihoodRatio; featureLikelihoodRatios and priors disclose parameters. Nonqualifying features have effective ratio1. The historical ledger is authoritative for source details; no personal input exists.

## Display and expiry

The taskbar shows `实验重置10%` at baseline, including0%,20%,60% and unknown. It shows the evidence-updated value, not the baseline when evidence is active. Active double-click/right-click details show the two independent estimates, baseline values, applied subjective multipliers, cold-start/uncalibrated caveat, observation counts, time horizon, expiry and links. Unknown type/scope/time is explicit. A cancelled/expired/invalid record uses its existing distinct state and cannot highlight or produce an expired countdown.

Strict>60% is necessary for highlight. Model records also require the valid evidence gate and known public type/scope/time. Low values are visible; no automatic hover, notification, model request or account upload is introduced. Taskbar-only bounds, adaptive compression and stability fixes are untouched.

## Parent coordination checklist

1. Review and publish the allowlisted public code/docs/ledger under ZhouDaChao/codex-reset-forecast; no workflow/permission changes are required by this package.
2. Perform the existing bounded current-source check. Only success may append new audit facts and advance collection.checkedAt; history-only audit cannot do so. Do not invent complete coverage.
3. Run tests and ordinary Python generation with current clock. Review the output types/time/evidence gate. Publish forecast.json via the existing single writer; no concurrent second writer.
4. Return the actual published revision and checkedAt to the Windows task. Windows then does one bounded anonymous GET and checks actual model parsing before backup/install/live validation.
5. On source/publish failure retain the last output and original expiry. This delivery does not claim an unattended cloud scheduler was installed.
