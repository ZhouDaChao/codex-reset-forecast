"""Experimental public-event forecaster. Python 3.7+, standard library only.
No network, account access, model inference, scheduling, or publication.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

UTC = dt.timezone.utc
KINDS = ("direct", "banked")
SCOPE = "public_codex_extra"
DOC = "https://github.com/ZhouDaChao/codex-reset-forecast/blob/main/MODEL.md"


def time(value):
    if not isinstance(value, str):
        raise ValueError("UTC/offset timestamp required")
    result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp has no timezone")
    return result.astimezone(UTC)


def iso(value):
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def number(value, positive=False):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError("Finite numeric parameter required")
    if positive and value <= 0:
        raise ValueError("Positive parameter required")
    return float(value)


def links(values):
    if not isinstance(values, list) or not values or len(values) > 8:
        raise ValueError("Public source links required")
    for value in values:
        if not isinstance(value, str) or any(c.isspace() for c in value):
            raise ValueError("Invalid source link")
        u = urlsplit(value)
        if u.scheme != "https" or not u.hostname or u.username or u.password:
            raise ValueError("Only public HTTPS source links")


def validate(ledger, params):
    if ledger.get("schemaVersion") != 1 or params.get("schemaVersion") != 1:
        raise ValueError("Unsupported schema")
    for kind in KINDS:
        prior = params["priors"][kind]
        number(prior["alpha0"], True)
        number(prior["betaDays0"], True)
    if params["horizonHours"] != 24 or not 0 < number(params["ttlHours"], True) <= 6:
        raise ValueError("This contract supports a 24h horizon and TTL <= 6h")
    weights = params["featureLikelihoodRatios"]
    if set(weights) != {"tiboStatement", "explicitCommitment", "versionRelease", "incidentCompensation", "executionClaim"}:
        raise ValueError("Explicit feature contract required")
    for key, value in weights.items():
        v = number(value, True)
        if (key != "explicitCommitment" and v != 1) or not 1 <= v <= 20:
            raise ValueError("Only qualified explicit commitments may have a subjective weight (1..20)")
    if params["evidenceAggregation"] != "maximum_single_event":
        raise ValueError("Correlated promises must not be multiplied")
    scenarios = params["evidenceSensitivityRatios"]
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 8 or any(not 1 <= number(v, True) <= 20 for v in scenarios):
        raise ValueError("Bounded subjective evidence scenarios required")
    if not isinstance(params["sensitivityBetaDays"], list) or not 1 <= len(params["sensitivityBetaDays"]) <= 8:
        raise ValueError("Bounded sensitivity scenarios required")
    for beta in params["sensitivityBetaDays"]:
        number(beta, True)
    seen = set()
    for e in ledger["events"]:
        key = (e["kind"], e["eventId"], time(e["knownAt"]))
        if key in seen:
            raise ValueError("Duplicate/conflicting revision; use one canonical event ID")
        seen.add(key)
        links(e["sources"])
        for field in ("occurredAt", "windowStart", "windowEnd", "expiresAt"):
            if e.get(field) is not None:
                time(e[field])
        if bool(e.get("windowStart")) != bool(e.get("windowEnd")):
            raise ValueError("Incomplete event window")
        if e.get("windowStart") and time(e["windowEnd"]) <= time(e["windowStart"]):
            raise ValueError("Invalid event window")
        if e.get("outcomeVerified") and not e.get("occurredAt"):
            raise ValueError("Verified occurrence needs an occurrence timestamp")
        if e.get("outcomeVerified") and time(e["occurredAt"]) > time(e["knownAt"]):
            raise ValueError("Occurrence cannot be verified before it happened")
    for c in ledger["coverage"]:
        start, end, known = time(c["start"]), time(c["end"]), time(c["knownAt"])
        links(c["sources"])
        if end <= start or known < end:
            raise ValueError("Complete coverage must be recorded after its end")


def revisions(ledger, cutoff):
    result = {}
    for e in ledger["events"]:
        if time(e["knownAt"]) > cutoff:
            continue
        key = (e["kind"], e["eventId"])
        if key not in result or time(e["knownAt"]) > time(result[key]["knownAt"]):
            result[key] = e
    return list(result.values())


def coverage(ledger, kind, cutoff):
    intervals = []
    for c in ledger["coverage"]:
        if (c["kind"] != kind or c.get("scope") != SCOPE or
                c.get("status") != "complete_verified" or time(c["knownAt"]) > cutoff):
            continue
        start, end = time(c["start"]), min(time(c["end"]), cutoff)
        if end > start:
            intervals.append((start, end))
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def occurred(e):
    return (e.get("scope") == SCOPE and e.get("state") == "fulfilled" and
            e.get("sourceVerified") is True and e.get("outcomeVerified") is True and e.get("occurredAt"))


def probability(alpha, beta_days, horizon_days):
    number(alpha, True); number(beta_days, True); number(horizon_days)
    if horizon_days < 0:
        raise ValueError("Negative horizon")
    return max(0.0, min(1.0, -math.expm1(-alpha * math.log1p(horizon_days / beta_days))))


def estimate_at(ledger, params, kind, cutoff):
    spans = coverage(ledger, kind, cutoff)
    exposure = sum((b - a).total_seconds() for a, b in spans) / 86400.0
    counted, excluded = [], []
    for e in revisions(ledger, cutoff):
        if e["kind"] != kind:
            continue
        when = time(e["occurredAt"]) if e.get("occurredAt") else None
        if occurred(e) and when < cutoff and any(a <= when < b for a, b in spans):
            counted.append(e["eventId"])
        else:
            excluded.append(e["eventId"])
    prior = params["priors"][kind]
    alpha, beta = prior["alpha0"] + len(counted), prior["betaDays0"] + exposure
    h = params["horizonHours"] / 24.0
    return {"probability": probability(alpha, beta, h), "alpha": alpha,
            "betaDays": beta, "verifiedEvents": len(counted), "observedDays": exposure,
            "coverageKnown": bool(spans), "coldStart": not spans and not counted, "countedEventIds": sorted(counted),
            "excludedEventIds": sorted(excluded),
            "priorSensitivity": [{"alpha0": 1, "betaDays0": b,
                "probability": probability(1 + len(counted), b + exposure, h)}
                for b in params["sensitivityBetaDays"]]}


def active_commitments(ledger, kind, at, horizon_end):
    eligible = []
    for e in revisions(ledger, at):
        if (e["kind"] != kind or e.get("scope") != SCOPE or e.get("state") != "announced"
                or e.get("sourceVerified") is not True or e.get("official") is not True
                or e.get("features", {}).get("explicitCommitment") is not True
                or not e.get("windowStart") or not e.get("expiresAt")):
            continue
        # Entire remaining target window must fit the evaluation horizon. A
        # promise for 'sometime this week' is not evidence of a reset in 24h.
        if time(e["expiresAt"]) > at and at < time(e["windowEnd"]) <= horizon_end:
            eligible.append(e["eventId"])
    return sorted(eligible)


def update_odds(p, multiplier):
    return p * multiplier / (1 - p + p * multiplier)


def model_estimate_at(ledger, params, kind, at):
    result = estimate_at(ledger, params, kind, at)
    ids = active_commitments(ledger, kind, at, at + dt.timedelta(hours=params["horizonHours"]))
    base = result["probability"]
    weight = params["featureLikelihoodRatios"]["explicitCommitment"] if ids else 1.0
    # A conservative single-event cap avoids pretending correlated posts or
    # multiple promises are independent. Weights are engineering assumptions.
    result.update({"baselineProbability": base, "probability": update_odds(base, weight),
                   "evidenceMultiplier": weight, "evidenceEventIds": ids,
                   "evidenceAggregation": params["evidenceAggregation"],
                   "evidenceSensitivity": [{"multiplier": v, "probability": update_odds(base, v if ids else 1)}
                                           for v in params["evidenceSensitivityRatios"]]})
    result["alertEligible"] = result["probability"] > 0.60 and bool(ids)
    return result


def forecast(ledger, params, now):
    validate(ledger, params)
    check = ledger["collection"]
    if check.get("status") != "ok":
        raise ValueError("Collection failed; do not publish or renew the old output")
    at = time(check["checkedAt"])
    if at > now:
        raise ValueError("Successful source check is in the future")
    expires = at + dt.timedelta(hours=params["ttlHours"])
    if now >= expires:
        raise ValueError("Source check is stale; leave existing feed unchanged and expired")
    end = at + dt.timedelta(hours=params["horizonHours"])
    estimates = {kind: model_estimate_at(ledger, params, kind, at) for kind in KINDS}
    gates = {kind: estimates[kind]["evidenceEventIds"] for kind in KINDS}
    # Never keep a promise's influence current past its known deadline, even if
    # the publisher or collection subsequently fails.
    for e in revisions(ledger, at):
        if e["kind"] in KINDS and e["eventId"] in gates[e["kind"]]:
            expires = min(expires, time(e["windowEnd"]), time(e["expiresAt"]))
    if now >= expires:
        raise ValueError("Evidence is stale; leave existing feed unchanged and expired")
    # No undocumented pooling/independence assumption: root is explicitly DIRECT.
    # Banked probability is a separate extension, never a claimed combined chance.
    direct = estimates["direct"]
    eligible = direct["probability"] > 0.60 and bool(gates["direct"])
    features = []
    for e in sorted(revisions(ledger, at), key=lambda e: (e["kind"], e["eventId"])):
        features.append({"eventId": e["eventId"], "kind": e["kind"], "state": e["state"],
                         "features": e.get("features", {}), "likelihoodRatio":
                         params["featureLikelihoodRatios"]["explicitCommitment"]
                         if e["kind"] in KINDS and e["eventId"] in gates[e["kind"]] else 1.0})
    source_urls = [DOC]
    for e in revisions(ledger, at):
        if e["kind"] in KINDS and e["eventId"] in gates[e["kind"]]:
            for url in e["sources"]:
                if url not in source_urls and len(source_urls) < 8:
                    source_urls.append(url)
    return {"schemaVersion": 1, "status": "prediction", "windowStart": iso(at),
            "windowEnd": iso(end), "resetType": "direct",
            "subjectiveProbability": None if direct["probability"] > 0.60 and not eligible else direct["probability"], "sources": source_urls,
            "updatedAt": iso(at), "expiresAt": iso(expires),
            "eventId": "experimental-direct-24h",
            "model": {"schemaVersion": 1, "name": "gamma-poisson", "version": "1.0.0-experimental",
                "experimental": True, "calibrated": False,
                "coldStart": direct["coldStart"],
                "windowSemantics": "evaluation_horizon", "horizonHours": params["horizonHours"],
                "targetScope": SCOPE, "alertEligible": eligible,
                "evidenceGate": "current_verified_commitment" if gates["direct"] else "no_current_verified_commitment",
                "evidenceEventIds": gates["direct"], "direct": direct, "banked": estimates["banked"],
                "features": features, "featureLikelihoodRatios": params["featureLikelihoodRatios"],
                "priors": params["priors"], "descriptionUrl": DOC}}


def backtest(ledger, params, cutoffs, evaluation_time):
    """Walk-forward predictions; labels require independently complete future coverage.
    Unknown labels remain null, never 'no reset'. No metric is calibration evidence.
    """
    validate(ledger, params)
    rows = []
    for at in cutoffs:
        end = at + dt.timedelta(hours=params["horizonHours"])
        if at > evaluation_time:
            raise ValueError("Prediction cutoff exceeds evaluation time")
        for kind in KINDS:
            pred = model_estimate_at(ledger, params, kind, at)
            spans = coverage(ledger, kind, evaluation_time)
            known = end <= evaluation_time and any(a <= at and end <= b for a, b in spans)
            label = None
            if known:
                label = int(any(occurred(e) and e["kind"] == kind and at <= time(e["occurredAt"]) < end
                                for e in revisions(ledger, evaluation_time)))
            rows.append({"cutoff": iso(at), "kind": kind, "probability": pred["probability"],
                         "outcome": label, "labelCoverageKnown": known,
                         "trainingEvents": pred["verifiedEvents"], "trainingDays": pred["observedDays"]})
    scored = [r for r in rows if r["outcome"] is not None]
    return {"rows": rows, "scoredCount": len(scored),
            "brierScore": sum((r["probability"] - r["outcome"]) ** 2 for r in scored) / len(scored) if scored else None,
            "calibrationEstablished": False}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > 65536:
        raise ValueError("Forecast exceeds client 64 KiB limit")
    if path.exists() and path.read_bytes() == raw:
        return
    fd, temp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(raw); out.flush(); os.fsync(out.fileno())
        os.replace(temp, str(path))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", default="events.json")
    parser.add_argument("--params", default="parameters.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--now", help="Explicit UTC/offset clock for reproducible checks")
    args = parser.parse_args()
    ledger = json.loads(Path(args.ledger).read_text(encoding="utf-8"))
    params = json.loads(Path(args.params).read_text(encoding="utf-8"))
    now = time(args.now) if args.now else dt.datetime.now(UTC)
    atomic_json(args.output, forecast(ledger, params, now))


if __name__ == "__main__":
    main()
