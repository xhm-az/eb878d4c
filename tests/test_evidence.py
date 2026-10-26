from dataclasses import replace
from itertools import product
import unittest

from examples.synthetic_support import SymbolicAdapter, candidate, context, enabled_fact, revision
from pacc_review.evidence import ExplicitEvidenceAudit, assess
from pacc_review.types import Condition, Environment, EvidenceSnapshot, Fact, Truth


class EvidenceContracts(unittest.TestCase):
    def setUp(self):
        self.condition = Condition("enabled", ("candidate",), True, ())

    def test_explicit_positive_supports_condition(self):
        result = assess(self.condition, (enabled_fact("candidate", True),))
        self.assertIs(result.truth, Truth.SUPPORTED)

    def test_explicit_negative_contradicts_condition(self):
        result = assess(self.condition, (enabled_fact("candidate", False),))
        self.assertIs(result.truth, Truth.CONTRADICTED)

    def test_missing_evidence_is_unknown(self):
        self.assertIs(assess(self.condition, ()).truth, Truth.UNKNOWN)

    def test_unrelated_fact_is_not_counterevidence(self):
        result = assess(self.condition, (enabled_fact("revision", False),))
        self.assertIs(result.truth, Truth.UNKNOWN)

    def test_direct_conflict_is_unknown(self):
        facts = (enabled_fact("candidate", True), enabled_fact("candidate", False))
        self.assertIs(assess(self.condition, facts).truth, Truth.UNKNOWN)

    def test_negative_condition_is_not_closed_world_negation(self):
        negative = replace(self.condition, value=False)
        self.assertIs(assess(negative, ()).truth, Truth.UNKNOWN)
        self.assertIs(assess(negative, (enabled_fact("candidate", False),)).truth, Truth.SUPPORTED)

    def test_disjunction_exhaustive_three_valued_contract(self):
        child = Condition("enabled", ("revision",), True, ())
        disjunction = Condition("", (), True, (self.condition, child))
        for left, right in product(Truth, repeat=2):
            with self.subTest(left=left.value, right=right.value):
                facts = []
                for action, truth in (("candidate", left), ("revision", right)):
                    if truth is not Truth.UNKNOWN:
                        facts.append(enabled_fact(action, truth is Truth.SUPPORTED))
                expected = (Truth.SUPPORTED if Truth.SUPPORTED in (left, right)
                            else Truth.CONTRADICTED if left is right is Truth.CONTRADICTED
                            else Truth.UNKNOWN)
                self.assertIs(assess(disjunction, tuple(facts)).truth, expected)

    def test_stale_declared_scope_is_rejected(self):
        current = context()
        adapter = SymbolicAdapter(current.environment, (), scope_override="symbolic-other-scope")
        with self.assertRaises(ValueError):
            ExplicitEvidenceAudit().evaluate(current, candidate(), adapter)

    def test_syntax_failure_is_distinct_from_unknown(self):
        current = context()
        adapter = SymbolicAdapter(current.environment, ())
        result = ExplicitEvidenceAudit().evaluate(current, replace(candidate(), action="unrecognized"), adapter)
        self.assertTrue(result.syntax_error)
        self.assertFalse(result.passed)
        self.assertNotIn("snapshot", adapter.events)

    def test_adapter_environment_mismatch_is_configuration_error(self):
        with self.assertRaises(ValueError):
            ExplicitEvidenceAudit().evaluate(context(), candidate(), SymbolicAdapter(Environment.ALFWORLD, ()))

    def test_nonpublic_fact_source_is_rejected(self):
        with self.assertRaises(ValueError):
            Fact("enabled", ("candidate",), True, "hidden_simulator", "not public")

    def test_invalid_condition_shapes_are_rejected(self):
        child = self.condition
        constructors = (
            lambda: Condition("", (), True, ()),
            lambda: Condition("enabled", (), True, (child,)),
            lambda: Condition("", ("candidate",), True, (child,)),
            lambda: Condition("", (), False, (child,)),
        )
        for constructor in constructors:
            with self.subTest(constructor=constructor):
                with self.assertRaises(ValueError):
                    constructor()

    def test_session_reuses_one_snapshot_for_both_candidates(self):
        current = context()
        adapter = SymbolicAdapter(current.environment, (enabled_fact("candidate", False),
                                                        enabled_fact("revision", False)))
        session = ExplicitEvidenceAudit().session(current, adapter)
        self.assertFalse(session.evaluate(candidate()).passed)
        adapter.facts = (enabled_fact("revision", True),)
        self.assertFalse(session.evaluate(revision()).passed)
        self.assertEqual(adapter.events.count("snapshot"), 1)

    def test_session_copies_mutable_fact_container_and_arguments(self):
        current = context()
        args = ["revision"]
        facts = [enabled_fact("candidate", False), replace(enabled_fact("revision", False), args=args)]
        adapter = SymbolicAdapter(current.environment, facts)
        session = ExplicitEvidenceAudit().session(current, adapter)
        session.evaluate(candidate())
        args[0] = "another-symbolic-action"
        facts.clear()
        result = session.evaluate(revision())
        self.assertFalse(result.passed)
        self.assertEqual(result.contradictions[0].evidence[0].args, ("revision",))

    def test_session_defers_snapshot_until_a_syntactically_valid_action(self):
        current = context()
        adapter = SymbolicAdapter(current.environment, ())
        session = ExplicitEvidenceAudit().session(current, adapter)
        self.assertTrue(session.evaluate(replace(candidate(), action="unrecognized")).syntax_error)
        self.assertNotIn("snapshot", adapter.events)
        self.assertTrue(session.evaluate(revision()).passed)
        self.assertEqual(adapter.events.count("snapshot"), 1)

    def test_new_session_uses_new_public_snapshot(self):
        current = context()
        adapter = SymbolicAdapter(current.environment, (enabled_fact("candidate", True),))
        audit = ExplicitEvidenceAudit()
        self.assertTrue(audit.session(current, adapter).evaluate(candidate()).passed)
        adapter.facts = (enabled_fact("candidate", False),)
        self.assertFalse(audit.session(current, adapter).evaluate(candidate()).passed)
        self.assertEqual(adapter.events.count("snapshot"), 2)

    def test_malformed_snapshot_or_fact_is_rejected(self):
        current = context()
        for snapshot in ("not a snapshot", EvidenceSnapshot(current.scope_id, ("not a fact",)),
                         EvidenceSnapshot(current.scope_id, (replace(enabled_fact("candidate", True), args="candidate"),))):
            with self.subTest(snapshot=snapshot):
                adapter = SymbolicAdapter(current.environment, ())
                adapter.public_snapshot = lambda _context, value=snapshot: value
                with self.assertRaises(TypeError):
                    ExplicitEvidenceAudit().evaluate(current, candidate(), adapter)
