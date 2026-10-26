from dataclasses import fields, replace
import importlib
import json
from pathlib import Path
import socket
import sys
import unittest

from examples.control_flow_demo import run_scenarios
from examples.final_action_hook import submit_selected_action
from examples.synthetic_support import RecordingEnvironment, context, revision
from pacc_review import PACCSettings, Variant
from pacc_review.types import Context, DiagnosticKind, PTAResult, PTAStatus, Reason
from tests.test_controller import flagged, not_flagged, process, system
from tools.model_free_guard import ModelRuntimeBlocked, NetworkBlocked
from tools.run_contract_tests import contract_exit_code


class PublicBoundaryContracts(unittest.TestCase):
    def test_context_has_no_evaluator_or_hidden_environment_fields(self):
        names = {f.name for f in fields(Context)}
        self.assertEqual(names, {"environment", "goal", "observation", "history", "instructions", "scope_id"})
        with self.assertRaises(TypeError):
            replace(context(), reward="not a public context field")

    def test_public_summary_contains_only_allowed_categorical_metadata(self):
        s = system(facts=(), target_replies=(flagged(), not_flagged()), repair_replies=(revision(),))
        result = process(s)
        summary = result.public_summary()
        self.assertEqual(set(summary), {"release_scope", "eea_checked", "trigger", "pta_status", "pta_reason",
                                        "diagnostic_kind", "revision_attempted", "revision_available",
                                        "revision_accepted", "fell_back"})
        self.assertTrue(all(type(v) in {str, bool} for v in summary.values()))
        rendered = json.dumps(summary)
        for secret in (s.context.goal, s.context.observation, s.context.instructions):
            self.assertNotIn(secret, rendered)
        self.assertEqual(summary["diagnostic_kind"], DiagnosticKind.TARGET.value)

    def test_settings_schema_and_dataclass_expose_only_mode(self):
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "configs/settings.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(schema["properties"]), {"variant"})
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual({f.name for f in fields(PACCSettings)}, {"variant"})

    def test_invalid_mode_is_not_silently_enabled(self):
        with self.assertRaises(ValueError):
            PACCSettings("unknown-mode")

    def test_abstention_requires_reason_and_nonabstention_rejects_reason(self):
        with self.assertRaises(ValueError):
            PTAResult(PTAStatus.ABSTAINED, None)
        with self.assertRaises(ValueError):
            PTAResult(PTAStatus.NOT_FLAGGED, Reason.UNSUPPORTED_INPUT)

    def test_final_action_hook_submits_only_after_control_returns(self):
        s = system(facts=(), target_replies=(not_flagged(),), repair_replies=())
        environment = RecordingEnvironment(s.events)
        result, _ = submit_selected_action(context=s.context, selected=s.selected, controller=s.controller,
                                            planner=s.planner, adapter=s.adapter, environment=environment)
        self.assertIs(result.submitted, s.selected)
        self.assertEqual(environment.submissions, [s.selected.action])
        self.assertEqual(s.events[-1], "environment_submission:" + s.selected.action)
        self.assertEqual(s.evaluator.calls, [s.selected.action])

    def test_demo_exercises_actual_control_routes_and_submits_once_per_case(self):
        results = {r["case"]: r for r in run_scenarios()}
        self.assertEqual(set(results), {"direct_submission", "eea_revision_accepted", "pta_revision_accepted",
                                        "revision_fallback", "pta_abstention"})
        for result in results.values():
            self.assertEqual(result["kind"], "synthetic_control_flow_only")
            self.assertEqual(result["environment_submission_count"], 1)
            self.assertTrue(result["events"][-1].startswith("environment_submission:"))
        self.assertEqual(results["eea_revision_accepted"]["submitted"], "revision")
        self.assertEqual(results["pta_revision_accepted"]["summary"]["diagnostic_kind"], "target")
        self.assertTrue(results["revision_fallback"]["summary"]["fell_back"])
        self.assertFalse(results["pta_abstention"]["summary"]["revision_attempted"])

    def test_guard_blocks_model_runtime_imports(self):
        with self.assertRaises(ModelRuntimeBlocked):
            importlib.import_module("torch")
        self.assertNotIn("torch", sys.modules)

    def test_guard_blocks_socket_networking(self):
        with self.assertRaises(NetworkBlocked):
            socket.socket()


class TestRunnerContracts(unittest.TestCase):
    def test_empty_run_is_not_validation(self):
        self.assertNotEqual(contract_exit_code(unittest.TestResult()), 0)

    def test_nonempty_successful_run_is_validation(self):
        result = unittest.TestResult()
        result.testsRun = 1
        self.assertEqual(contract_exit_code(result), 0)

    def test_skipped_run_is_incomplete_even_without_failures(self):
        result = unittest.TestResult()
        result.testsRun = 1
        result.skipped.append((self, "synthetic skip"))
        self.assertTrue(result.wasSuccessful())
        self.assertNotEqual(contract_exit_code(result), 0)

    def test_expected_failure_is_not_a_validated_contract(self):
        result = unittest.TestResult()
        result.testsRun = 1
        result.expectedFailures.append((self, "synthetic expected failure"))
        self.assertNotEqual(contract_exit_code(result), 0)

    def test_failed_run_is_not_validation(self):
        result = unittest.TestResult()
        result.testsRun = 1
        result.failures.append((self, "synthetic failure"))
        self.assertNotEqual(contract_exit_code(result), 0)
