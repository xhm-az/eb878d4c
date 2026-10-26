from dataclasses import FrozenInstanceError, fields, replace
import unittest

from examples.synthetic_support import candidate, context, enabled_fact
from pacc_review.diagnostics import build_diagnostic
from pacc_review.evidence import assess
from pacc_review.types import (Assessment, Condition, DiagnosticEnvelope, DiagnosticKind,
                               EEAResult, PTAResult, PTAStatus)


class DiagnosticContracts(unittest.TestCase):
    def setUp(self):
        self.condition = Condition("enabled", ("candidate",), True, ())
        self.conflict = assess(self.condition, (enabled_fact("candidate", False),))
        self.unknown = assess(self.condition, ())
        self.support = assess(self.condition, (enabled_fact("candidate", True),))

    def test_evidence_envelope_filters_noncontradicted_conditions(self):
        a = Assessment(EEAResult(False, (self.support, self.unknown, self.conflict)),
                       PTAResult(PTAStatus.NOT_RUN, None))
        result = build_diagnostic(context(), candidate(), a, structured=True)
        self.assertIs(result.kind, DiagnosticKind.EVIDENCE)
        self.assertEqual(result.counterevidence, (self.conflict,))
        self.assertIsNone(result.original_goal)

    def test_syntax_diagnosis_does_not_invent_counterevidence(self):
        a = Assessment(EEAResult(True, ()), PTAResult(PTAStatus.NOT_RUN, None))
        result = build_diagnostic(context(), candidate(), a, structured=True)
        self.assertTrue(result.syntax_error)
        self.assertEqual(result.counterevidence, ())

    def test_target_envelope_has_original_goal_and_no_interface_conflicts(self):
        a = Assessment(EEAResult(False, ()), PTAResult(PTAStatus.FLAGGED, None))
        result = build_diagnostic(context(), candidate(), a, structured=True)
        self.assertIs(result.kind, DiagnosticKind.TARGET)
        self.assertEqual(result.original_goal, context().goal)
        self.assertEqual(result.original_action, candidate().action)
        self.assertEqual(result.counterevidence, ())

    def test_eea_diagnosis_has_priority_even_with_a_flagged_target_result(self):
        a = Assessment(EEAResult(False, (self.conflict,)), PTAResult(PTAStatus.FLAGGED, None))
        result = build_diagnostic(context(), candidate(), a, structured=True)
        self.assertIs(result.kind, DiagnosticKind.EVIDENCE)

    def test_generic_retry_carries_no_structured_details(self):
        a = Assessment(EEAResult(False, (self.conflict,)), PTAResult(PTAStatus.NOT_RUN, None))
        result = build_diagnostic(context(), candidate(), a, structured=False)
        self.assertIs(result.kind, DiagnosticKind.GENERIC_RETRY)
        self.assertIsNone(result.original_goal)
        self.assertFalse(result.syntax_error)
        self.assertEqual(result.counterevidence, ())

    def test_nonflagged_assessment_cannot_create_diagnosis(self):
        a = Assessment(EEAResult(False, ()), PTAResult(PTAStatus.NOT_FLAGGED, None))
        with self.assertRaises(ValueError):
            build_diagnostic(context(), candidate(), a, structured=True)

    def test_envelope_has_no_internal_score_alternative_or_parameter_fields(self):
        self.assertEqual({f.name for f in fields(DiagnosticEnvelope)},
                         {"kind", "original_action", "original_goal", "syntax_error", "counterevidence"})

    def test_inconsistent_envelope_is_rejected(self):
        with self.assertRaises(ValueError):
            DiagnosticEnvelope(DiagnosticKind.EVIDENCE, candidate().action, None, False, (self.unknown,))
        with self.assertRaises(ValueError):
            DiagnosticEnvelope(DiagnosticKind.TARGET, candidate().action, context().goal, True, ())
        with self.assertRaises(ValueError):
            DiagnosticEnvelope(DiagnosticKind.GENERIC_RETRY, candidate().action, context().goal, False, ())

    def test_envelope_is_immutable(self):
        a = Assessment(EEAResult(True, ()), PTAResult(PTAStatus.NOT_RUN, None))
        result = build_diagnostic(context(), candidate(), a, structured=True)
        with self.assertRaises(FrozenInstanceError):
            result.original_action = "changed"
