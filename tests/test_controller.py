from dataclasses import replace
from types import SimpleNamespace
import unittest

from examples.synthetic_support import (RecordingEnvironment, ScriptedPlanner, ScriptedTargetEvaluator,
                                         SymbolicAdapter, candidate, context, enabled_fact, revision)
from pacc_review import PACCController, PACCSettings, Variant
from pacc_review.ports import AssessmentUnavailable, PrivateComponentRequired, RevisionUnavailable
from pacc_review.types import DiagnosticKind, Environment, PTAResult, PTAStatus, Reason, Trigger


def system(*, facts, target_replies, repair_replies, variant=Variant.PACC,
           environment=Environment.WEBSHOP):
    current, events = context(environment), []
    evaluator = ScriptedTargetEvaluator(target_replies, events=events)
    planner = ScriptedPlanner(repair_replies, events=events)
    adapter = SymbolicAdapter(environment, facts, events=events)
    controller = PACCController(PACCSettings(variant), target_evaluator=evaluator)
    return SimpleNamespace(context=current, events=events, evaluator=evaluator, planner=planner,
                           adapter=adapter, controller=controller, selected=candidate())


def process(s):
    return s.controller.process(s.context, s.selected, s.planner, s.adapter)


def not_flagged():
    return PTAResult(PTAStatus.NOT_FLAGGED, None)


def flagged():
    return PTAResult(PTAStatus.FLAGGED, None)


class ControllerContracts(unittest.TestCase):
    def test_vanilla_preserves_exact_object_without_evaluation(self):
        s = system(facts=(), target_replies=(), repair_replies=(), variant=Variant.VANILLA)
        s.selected = replace(s.selected, action="unrecognized")
        result = process(s)
        self.assertIs(result.submitted, s.selected)
        self.assertIsNone(result.initial)
        self.assertEqual(s.events, [])

    def test_direct_submission_requests_no_revision(self):
        s = system(facts=(enabled_fact("candidate", True),), target_replies=(not_flagged(),), repair_replies=())
        result = process(s)
        self.assertIs(result.submitted, s.selected)
        self.assertFalse(result.revision_attempted)
        self.assertEqual(s.planner.requests, [])

    def test_unknown_evidence_does_not_trigger_repair(self):
        s = system(facts=(), target_replies=(not_flagged(),), repair_replies=())
        result = process(s)
        self.assertTrue(result.initial.eea.passed)
        self.assertIs(result.submitted, s.selected)

    def test_eea_short_circuit_and_failed_revision_fallback(self):
        s = system(facts=(enabled_fact("candidate", False), enabled_fact("revision", False)),
                   target_replies=(), repair_replies=(revision(),))
        result = process(s)
        self.assertIs(result.initial.trigger, Trigger.EEA)
        self.assertIs(result.initial.pta.status, PTAStatus.NOT_RUN)
        self.assertEqual(s.evaluator.calls, [])
        self.assertEqual(len(s.planner.requests), 1)
        self.assertIs(result.submitted, s.selected)
        self.assertTrue(result.fell_back)

    def test_evidence_guided_revision_is_rechecked_and_accepted(self):
        s = system(facts=(enabled_fact("candidate", False), enabled_fact("revision", True)),
                   target_replies=(not_flagged(),), repair_replies=(revision(),))
        result = process(s)
        self.assertIs(result.submitted, result.revision)
        self.assertEqual(s.evaluator.calls, ["revision"])
        self.assertIs(result.diagnosis.kind, DiagnosticKind.EVIDENCE)
        self.assertFalse(result.fell_back)

    def test_target_guided_revision_is_rechecked_and_accepted(self):
        s = system(facts=(enabled_fact("candidate", True), enabled_fact("revision", True)),
                   target_replies=(flagged(), not_flagged()), repair_replies=(revision(),))
        result = process(s)
        self.assertIs(result.submitted, result.revision)
        self.assertEqual(s.evaluator.calls, ["candidate", "revision"])
        self.assertIs(result.diagnosis.kind, DiagnosticKind.TARGET)

    def test_repeated_target_flag_does_not_start_another_revision(self):
        s = system(facts=(), target_replies=(flagged(), flagged()), repair_replies=(revision(),))
        result = process(s)
        self.assertEqual(len(s.planner.requests), 1)
        self.assertTrue(result.fell_back)
        self.assertIs(result.submitted, s.selected)

    def test_original_pta_abstention_does_not_trigger_repair(self):
        abstention = PTAResult(PTAStatus.ABSTAINED, Reason.UNSUPPORTED_INPUT)
        s = system(facts=(), target_replies=(abstention,), repair_replies=())
        result = process(s)
        self.assertFalse(result.revision_attempted)
        self.assertEqual(s.planner.requests, [])

    def test_revised_pta_abstention_is_not_a_risk_flag(self):
        abstention = PTAResult(PTAStatus.ABSTAINED, Reason.UNSUPPORTED_INPUT)
        s = system(facts=(), target_replies=(flagged(), abstention), repair_replies=(revision(),))
        result = process(s)
        self.assertIs(result.submitted, result.revision)
        self.assertIs(result.reassessment.pta.status, PTAStatus.ABSTAINED)

    def test_revision_unavailable_records_attempt_and_fallback(self):
        s = system(facts=(), target_replies=(flagged(),),
                   repair_replies=(RevisionUnavailable("synthetic unavailability"),))
        result = process(s)
        self.assertTrue(result.revision_attempted)
        self.assertTrue(result.fell_back)
        self.assertIsNone(result.revision)
        self.assertIsNotNone(result.diagnosis)

    def test_assessment_unavailable_abstains_without_repair(self):
        s = system(facts=(), target_replies=(AssessmentUnavailable("synthetic unavailability"),), repair_replies=())
        result = process(s)
        self.assertIs(result.initial.pta.reason, Reason.ASSESSMENT_UNAVAILABLE)
        self.assertFalse(result.revision_attempted)

    def test_missing_private_evaluator_is_not_pass_through(self):
        with self.assertRaises(PrivateComponentRequired):
            PACCController(PACCSettings(Variant.PACC))

    def test_eea_only_never_calls_target_evaluator(self):
        s = system(facts=(), target_replies=(), repair_replies=(), variant=Variant.EEA_ONLY)
        result = process(s)
        self.assertIs(result.initial.pta.status, PTAStatus.NOT_RUN)
        self.assertEqual(s.evaluator.calls, [])

    def test_private_evaluator_owns_applicability_in_each_environment(self):
        for environment in Environment:
            with self.subTest(environment=environment.value):
                abstention = PTAResult(PTAStatus.ABSTAINED, Reason.UNSUPPORTED_INPUT)
                s = system(facts=(), target_replies=(abstention,), repair_replies=(), environment=environment)
                result = process(s)
                self.assertIs(result.initial.pta.reason, Reason.UNSUPPORTED_INPUT)
                self.assertEqual(s.evaluator.calls, [s.selected.action])
                self.assertFalse(result.revision_attempted)

    def test_retry_omits_structured_diagnosis_but_keeps_trigger(self):
        s = system(facts=(enabled_fact("candidate", False), enabled_fact("revision", True)),
                   target_replies=(not_flagged(),), repair_replies=(revision(),),
                   variant=Variant.RETRY_WITHOUT_DIAGNOSIS)
        result = process(s)
        self.assertIs(result.initial.trigger, Trigger.EEA)
        self.assertIs(result.diagnosis.kind, DiagnosticKind.GENERIC_RETRY)
        self.assertEqual(result.diagnosis.counterevidence, ())
        self.assertIsNone(result.diagnosis.original_goal)

    def test_original_revision_and_evaluator_provenance_checks(self):
        changed = replace(candidate().provenance, checkpoint_revision="different-synthetic-identity")
        s = system(facts=(), target_replies=(), repair_replies=())
        s.planner.provenance = changed
        with self.assertRaises(ValueError):
            process(s)
        s = system(facts=(), target_replies=(), repair_replies=())
        s.evaluator.provenance = changed
        with self.assertRaises(ValueError):
            process(s)
        s = system(facts=(), target_replies=(flagged(),), repair_replies=(replace(revision(), provenance=changed),))
        with self.assertRaises(ValueError):
            process(s)

    def test_unexpected_evaluator_errors_are_not_silent_abstentions(self):
        s = system(facts=(), target_replies=(RuntimeError("synthetic programming failure"),), repair_replies=())
        with self.assertRaises(RuntimeError):
            process(s)

    def test_unexpected_reviser_errors_are_not_silent_fallbacks(self):
        s = system(facts=(), target_replies=(flagged(),),
                   repair_replies=(RuntimeError("synthetic programming failure"),))
        with self.assertRaises(RuntimeError):
            process(s)

    def test_bad_evaluator_return_is_rejected(self):
        s = system(facts=(), target_replies=("not a PTAResult",), repair_replies=())
        with self.assertRaises(TypeError):
            process(s)
        s = system(facts=(), target_replies=(PTAResult(PTAStatus.NOT_RUN, None),), repair_replies=())
        with self.assertRaises(ValueError):
            process(s)

    def test_bad_revision_return_is_rejected(self):
        s = system(facts=(), target_replies=(flagged(),), repair_replies=("not a Candidate",))
        with self.assertRaises(TypeError):
            process(s)

    def test_controller_never_submits_to_environment(self):
        s = system(facts=(), target_replies=(not_flagged(),), repair_replies=())
        environment = RecordingEnvironment(s.events)
        process(s)
        self.assertEqual(environment.submissions, [])
        self.assertFalse(any(e.startswith("environment_submission:") for e in s.events))

    def test_reassessment_cannot_pick_up_changed_adapter_evidence(self):
        s = system(facts=(enabled_fact("candidate", False), enabled_fact("revision", False)),
                   target_replies=(), repair_replies=(revision(),), variant=Variant.EEA_ONLY)
        original_reviser = s.planner.revise_once

        def mutating_reviser(current, selected, diagnosis):
            s.adapter.facts = (enabled_fact("revision", True),)
            return original_reviser(current, selected, diagnosis)

        s.planner.revise_once = mutating_reviser
        result = process(s)
        self.assertIs(result.submitted, s.selected)
        self.assertTrue(result.fell_back)
        self.assertEqual(s.events.count("snapshot"), 1)

    def test_evidence_session_is_not_cached_across_process_calls(self):
        s = system(facts=(enabled_fact("candidate", True),), target_replies=(),
                   repair_replies=(RevisionUnavailable("synthetic unavailability"),), variant=Variant.EEA_ONLY)
        self.assertFalse(process(s).revision_attempted)
        s.adapter.facts = (enabled_fact("candidate", False),)
        result = process(s)
        self.assertIs(result.initial.trigger, Trigger.EEA)
        self.assertTrue(result.revision_attempted)
        self.assertEqual(s.events.count("snapshot"), 2)
