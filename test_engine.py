import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
import model_engine as m

HERE = Path(__file__).resolve().parent
P = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
AT = m.time("2030-01-02T00:00:00Z")
SOURCE = ["https://example.com/synthetic-offline-test"]


def ledger():
    return {"schemaVersion": 1, "collection": {"status": "ok", "checkedAt": m.iso(AT)}, "events": [], "coverage": []}


def covered(kind="direct", start=None, end=None, known=None, status="complete_verified"):
    return {"kind": kind, "scope": m.SCOPE, "start": m.iso(start or AT-dt.timedelta(days=1)),
            "end": m.iso(end or AT), "knownAt": m.iso(known or end or AT), "status": status, "sources": SOURCE}


def event(event_id="one", kind="direct", known=None, when=None, **extra):
    e = {"eventId": event_id, "kind": kind, "scope": m.SCOPE, "state": "fulfilled",
         "knownAt": m.iso(known or AT), "occurredAt": m.iso(when or AT-dt.timedelta(hours=12)),
         "official": True, "sourceVerified": True, "outcomeVerified": True, "features": {}, "sources": SOURCE}
    e.update(extra)
    return e


def promise(event_id="promise", kind="direct", **extra):
    e=event(event_id,kind,state="announced",occurredAt=None,outcomeVerified=False,
            features={"explicitCommitment":True},windowStart=m.iso(AT+dt.timedelta(hours=1)),
            windowEnd=m.iso(AT+dt.timedelta(hours=2)),expiresAt=m.iso(AT+dt.timedelta(hours=3)),
            author="any_verified_official")
    e.update(extra)
    return e


class EngineTests(unittest.TestCase):
    def test_same_instant_different_offsets_conflicting_revision_rejected(self):
        x=ledger();x["events"]=[promise(knownAt="2030-01-02T00:00:00Z"),
                                 promise(knownAt="2030-01-02T08:00:00+08:00",state="cancelled")]
        with self.assertRaisesRegex(ValueError,"Duplicate/conflicting revision"):
            m.forecast(x,P,AT)

    def test_official_commitment_changes_odds_with_public_sensitivity(self):
        x=ledger();x["events"]=[promise()];f=m.forecast(x,P,AT);d=f["model"]["direct"]
        self.assertAlmostEqual(d["baselineProbability"],0.1)
        self.assertAlmostEqual(d["probability"],4/13)
        self.assertAlmostEqual(f["subjectiveProbability"],d["probability"])
        self.assertEqual(d["evidenceMultiplier"],4)
        for row,expected in zip(d["evidenceSensitivity"],[2/11,4/13,8/17]):
            self.assertAlmostEqual(row["probability"],expected)
        self.assertAlmostEqual(f["model"]["banked"]["probability"],0.1)
        self.assertFalse(f["model"]["alertEligible"])
        self.assertIn(SOURCE[0],f["sources"])
        p=copy.deepcopy(P);p["featureLikelihoodRatios"]["explicitCommitment"]=2
        self.assertAlmostEqual(m.forecast(x,p,AT)["subjectiveProbability"],2/11)

    def test_duplicate_correlated_promises_not_multiplied(self):
        x=ledger();x["events"]=[promise(knownAt=m.iso(AT-dt.timedelta(minutes=1))),promise(),promise("second")]
        d=m.forecast(x,P,AT)["model"]["direct"]
        self.assertEqual(d["evidenceEventIds"],["promise","second"])
        self.assertEqual(d["evidenceMultiplier"],4)
        self.assertAlmostEqual(d["probability"],4/13)

    def test_cancel_correction_expiry_retract_evidence(self):
        for replacement in (dict(state="cancelled"),dict(state="feature_release"),dict(scope="unknown"),
                            dict(expiresAt=m.iso(AT)),dict(windowEnd=m.iso(AT+dt.timedelta(hours=25)))):
            x=ledger();x["events"]=[promise(knownAt=m.iso(AT-dt.timedelta(minutes=1))),promise(**replacement)]
            d=m.forecast(x,P,AT)["model"]["direct"]
            self.assertEqual(d["evidenceEventIds"],[])
            self.assertAlmostEqual(d["probability"],0.1)

    def test_noncommitment_or_unverified_or_narrow_scope_is_neutral(self):
        for replacement in (dict(official=False),dict(sourceVerified=False),dict(kind="unknown"),
                            dict(scope="personal_normal_cycle"),dict(features={"versionRelease":True}),
                            dict(features={"incidentCompensation":True}),dict(state="execution_reported")):
            x=ledger();x["events"]=[promise(**replacement)]
            self.assertAlmostEqual(m.forecast(x,P,AT)["subjectiveProbability"],0.1)

    def test_banked_commitment_is_separate(self):
        x=ledger();x["events"]=[promise(kind="banked")];f=m.forecast(x,P,AT)
        self.assertAlmostEqual(f["subjectiveProbability"],0.1)
        self.assertAlmostEqual(f["model"]["banked"]["probability"],4/13)

    def test_promise_deadline_caps_feed_ttl(self):
        x=ledger();x["events"]=[promise()];f=m.forecast(x,P,AT)
        self.assertEqual(f["expiresAt"],m.iso(AT+dt.timedelta(hours=2)))
        with self.assertRaises(ValueError):m.forecast(x,P,AT+dt.timedelta(hours=2))

    def test_subjective_weight_crosses_threshold_only_with_gate(self):
        x=ledger();x["events"]=[promise()];p=copy.deepcopy(P)
        p["featureLikelihoodRatios"]["explicitCommitment"]=20
        f=m.forecast(x,p,AT);self.assertAlmostEqual(f["subjectiveProbability"],20/29)
        self.assertTrue(f["model"]["alertEligible"])

    def test_walk_forward_evidence_uses_only_known_revisions(self):
        x=ledger();x["events"]=[promise(knownAt=m.iso(AT+dt.timedelta(seconds=1)))]
        b=m.backtest(x,P,[AT],AT+dt.timedelta(days=2))
        self.assertAlmostEqual(b["rows"][0]["probability"],0.1)
        x["events"][0]["knownAt"]=m.iso(AT)
        b=m.backtest(x,P,[AT],AT+dt.timedelta(days=2))
        self.assertAlmostEqual(b["rows"][0]["probability"],4/13)

    def test_cold_start_without_new_posts(self):
        x=m.forecast(ledger(),P,AT)
        self.assertAlmostEqual(x["subjectiveProbability"],0.1)
        self.assertAlmostEqual(x["model"]["banked"]["probability"],0.1)
        self.assertTrue(x["model"]["coldStart"])
        self.assertFalse(x["model"]["calibrated"])
        self.assertFalse(x["model"]["alertEligible"])

    def test_prior_sensitivity_is_not_empirical(self):
        x=m.forecast(ledger(),P,AT)["model"]["direct"]
        for got,expected in zip(x["priorSensitivity"],[0.05,0.1,0.2]):
            self.assertAlmostEqual(got["probability"],expected)

    def test_candidate_history_not_samples(self):
        x=json.loads((HERE/"events.json").read_text(encoding="utf-8"))
        f=m.forecast(x,P,m.time(x["collection"]["checkedAt"]))
        self.assertEqual(f["model"]["direct"]["verifiedEvents"],0)
        self.assertEqual(f["model"]["direct"]["observedDays"],0)

    def test_three_primary_source_audits_not_outcomes(self):
        x=json.loads((HERE/"events.json").read_text(encoding="utf-8"))
        audits=[e for e in x["events"] if e["eventId"].startswith("source-audit-")]
        self.assertEqual(len(audits),3)
        self.assertTrue(all(e["sourceVerified"] and not e["outcomeVerified"] and e["occurredAt"] is None for e in audits))
        after=max(m.time(e["knownAt"]) for e in audits)+dt.timedelta(seconds=1)
        self.assertEqual(m.estimate_at(x,P,"direct",after)["verifiedEvents"],0)
        self.assertEqual(m.estimate_at(x,P,"banked",after)["observedDays"],0)

    def test_independent_cold_start_flags(self):
        x=ledger();x["coverage"]=[covered("banked")]
        f=m.forecast(x,P,AT)
        self.assertTrue(f["model"]["coldStart"])
        self.assertTrue(f["model"]["direct"]["coldStart"])
        self.assertFalse(f["model"]["banked"]["coldStart"])

    def test_formula_and_zero_horizon(self):
        self.assertEqual(m.probability(1,9,0),0)
        self.assertAlmostEqual(m.probability(3,11,1),1-(11/12)**3)

    def test_direct_banked_separate_and_revision_dedup(self):
        x=ledger();x["coverage"]=[covered(),covered("banked")]
        a=event();b=event(known=AT-dt.timedelta(hours=1));c=event(kind="banked")
        x["events"]=[a,b,c];f=m.forecast(x,P,AT)
        self.assertEqual(f["model"]["direct"]["verifiedEvents"],1)
        self.assertEqual(f["model"]["banked"]["verifiedEvents"],1)

    def test_overlapping_coverage_not_double_counted(self):
        x=ledger();x["coverage"]=[covered(),covered(start=AT-dt.timedelta(hours=12))]
        self.assertEqual(m.forecast(x,P,AT)["model"]["direct"]["observedDays"],1)

    def test_unknown_coverage_is_not_negative_exposure(self):
        x=ledger();x["coverage"]=[covered(status="unknown")];x["events"]=[event()]
        f=m.forecast(x,P,AT)["model"]["direct"]
        self.assertEqual((f["verifiedEvents"],f["observedDays"]),(0,0))
        self.assertAlmostEqual(f["probability"],0.1)

    def test_personal_normal_cycle_is_excluded(self):
        x=ledger();x["coverage"]=[covered()];x["events"]=[event(scope="personal_normal_cycle")]
        self.assertEqual(m.forecast(x,P,AT)["model"]["direct"]["verifiedEvents"],0)

    def test_announcements_and_execution_claims_not_outcomes(self):
        for state in ("announced","execution_reported","unresolved_past_promise","cancelled"):
            x=ledger();x["coverage"]=[covered()];x["events"]=[event(state=state,outcomeVerified=False)]
            self.assertEqual(m.forecast(x,P,AT)["model"]["direct"]["verifiedEvents"],0)

    def test_release_features_are_neutral(self):
        x=ledger();x["events"]=[event(kind="non_reset",state="feature_release",outcomeVerified=False,features={"versionRelease":True,"tiboStatement":True})]
        self.assertAlmostEqual(m.forecast(x,P,AT)["subjectiveProbability"],0.1)
        p=copy.deepcopy(P);p["featureLikelihoodRatios"]["versionRelease"]=2
        with self.assertRaises(ValueError):m.forecast(x,p,AT)

    def test_high_baseline_is_not_alert_or_legacy_alert(self):
        x=ledger();x["coverage"]=[covered()]
        x["events"]=[event(str(n),when=AT-dt.timedelta(hours=n+1)) for n in range(17)]
        f=m.forecast(x,P,AT)
        self.assertGreater(f["model"]["direct"]["probability"],0.6)
        self.assertFalse(f["model"]["alertEligible"])
        self.assertIsNone(f["subjectiveProbability"])

    def test_current_commitment_gate_and_expiry(self):
        x=ledger();x["coverage"]=[covered()]
        x["events"]=[event(str(n),when=AT-dt.timedelta(hours=n+1)) for n in range(17)]
        promise=event("promise",state="announced",occurredAt=None,outcomeVerified=False,features={"explicitCommitment":True},windowStart=m.iso(AT+dt.timedelta(hours=2)),windowEnd=m.iso(AT+dt.timedelta(hours=3)),expiresAt=m.iso(AT+dt.timedelta(hours=4)))
        x["events"].append(promise);self.assertTrue(m.forecast(x,P,AT)["model"]["alertEligible"])
        promise["expiresAt"]=m.iso(AT);self.assertFalse(m.forecast(x,P,AT)["model"]["alertEligible"])

    def test_failed_collection_does_not_renew_existing_file(self):
        with tempfile.TemporaryDirectory(dir=str(HERE)) as temp:
            target=Path(temp)/"forecast.json";original=m.forecast(ledger(),P,AT);m.atomic_json(target,original)
            before=target.read_bytes();x=ledger();x["collection"]["status"]="failed"
            with self.assertRaises(ValueError):m.atomic_json(target,m.forecast(x,P,AT+dt.timedelta(hours=2)))
            self.assertEqual(before,target.read_bytes())

    def test_same_check_is_deterministic_no_expiry_extension(self):
        self.assertEqual(m.forecast(ledger(),P,AT),m.forecast(ledger(),P,AT+dt.timedelta(hours=2)))

    def test_stale_check_and_future_check_fail(self):
        with self.assertRaises(ValueError):m.forecast(ledger(),P,AT+dt.timedelta(hours=3))
        with self.assertRaises(ValueError):m.forecast(ledger(),P,AT-dt.timedelta(seconds=1))

    def test_timezone_and_horizon_not_event_clock(self):
        x=ledger();x["collection"]["checkedAt"]="2030-01-02T08:00:00+08:00"
        f=m.forecast(x,P,AT);self.assertEqual(f["windowStart"],"2030-01-02T00:00:00Z")
        self.assertEqual(f["windowEnd"],"2030-01-03T00:00:00Z")
        self.assertEqual(f["model"]["windowSemantics"],"evaluation_horizon")
        with self.assertRaises(ValueError):m.time("2030-01-02T00:00:00")

    def test_walk_forward_no_future_training_leakage(self):
        x=ledger();future=AT+dt.timedelta(days=2)
        x["coverage"]=[covered(start=AT-dt.timedelta(days=1),end=AT+dt.timedelta(days=1),known=future)]
        x["events"]=[event(known=future,when=AT+dt.timedelta(hours=2))]
        b=m.backtest(x,P,[AT],future)
        row=b["rows"][0];self.assertAlmostEqual(row["probability"],0.1)
        self.assertEqual((row["trainingEvents"],row["trainingDays"]),(0,0))
        self.assertEqual(row["outcome"],1)
        self.assertFalse(b["calibrationEstablished"])

    def test_unknown_backtest_outcome_not_failure(self):
        b=m.backtest(ledger(),P,[AT],AT+dt.timedelta(days=2))
        self.assertIsNone(b["rows"][0]["outcome"]);self.assertIsNone(b["brierScore"])
        self.assertEqual(b["scoredCount"],0)

    def test_unmatured_backtest_not_scored(self):
        b=m.backtest(ledger(),P,[AT],AT+dt.timedelta(hours=1))
        self.assertEqual(b["scoredCount"],0)

    def test_known_at_boundary_and_late_verification(self):
        x=ledger();x["coverage"]=[covered()];x["events"]=[event(known=AT+dt.timedelta(seconds=1))]
        self.assertEqual(m.estimate_at(x,P,"direct",AT)["verifiedEvents"],0)
        self.assertEqual(m.estimate_at(x,P,"direct",AT+dt.timedelta(seconds=1))["verifiedEvents"],1)

    def test_invalid_foreknowledge_and_parameters(self):
        x=ledger();x["coverage"]=[covered(known=AT-dt.timedelta(seconds=1))]
        with self.assertRaises(ValueError):m.forecast(x,P,AT)
        p=copy.deepcopy(P);p["priors"]["direct"]["alpha0"]=float("nan")
        with self.assertRaises(ValueError):m.forecast(ledger(),p,AT)


if __name__ == "__main__":
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(EngineTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    (HERE/"engine-test-results.json").write_text(json.dumps({"passed":result.wasSuccessful(),"tests":result.testsRun,"failures":len(result.failures),"errors":len(result.errors)},indent=2),encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
