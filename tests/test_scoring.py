from dataclasses import replace
import math
import unittest

from examples.scoring_support import ScriptedRiskPolicy, SymbolicPreparedProvider, prepared_batch
from examples.scoring_demo import run_scoring_demo
from examples.synthetic_support import ScriptedPlanner, SymbolicAdapter, candidate, context, revision
from pacc_review import PACCController, PACCSettings, Variant
from pacc_review.conditions import ConditionInputError, public_context_key, validate_conditions
from pacc_review.ports import AssessmentUnavailable
from pacc_review.scoring import ScoringInputError, causal_action_likelihoods, score_prepared_conditions
from pacc_review.scoring_evaluator import ScoringTargetEvaluator
from pacc_review.types import HistoryTurn, PTAResult, PTAStatus, Reason


def score(batch):
    return score_prepared_conditions(context(), candidate(), batch.conditions, batch.logits,
                                      batch.input_ids, batch.attention_mask, batch.action_mask,
                                      forbidden_action_token_ids=batch.forbidden_action_token_ids)


def mutable_logits(batch):
    return [[list(v) for v in row] for row in batch.logits]


class ScoringArithmeticContracts(unittest.TestCase):
    def setUp(self):
        self.batch = prepared_batch(context(), candidate())

    def test_uniform_logits_give_expected_action_mean(self):
        outputs = score(self.batch)
        for output in outputs:
            self.assertAlmostEqual(output.likelihood.mean_log_probability, -math.log(len(self.batch.logits[0][0])))
            self.assertEqual(output.likelihood.token_count, 2)

    def test_causal_shift_uses_predictor_before_target(self):
        logits = [[[0.0, 0.0, math.log(3), 0.0], [0.0, 0.0, -math.log(3), 0.0], [0.0] * 4]]
        result = causal_action_likelihoods(logits, ((1, 2, 0),), ((True, True, True),),
                                           ((False, True, False),), forbidden_action_token_ids=frozenset({0}))
        self.assertAlmostEqual(result[0].mean_log_probability, math.log(3 / 6))

    def test_token_mean_is_not_a_sum(self):
        logits = mutable_logits(self.batch)
        expected = []
        for target_position in (2, 3):
            target = self.batch.input_ids[0][target_position]
            weight = target + 1
            logits[0][target_position - 1][target] = math.log(weight)
            expected.append(math.log(weight / (weight + len(logits[0][0]) - 1)))
        result = score(replace(self.batch, logits=logits))
        self.assertAlmostEqual(result[0].likelihood.mean_log_probability, math.fsum(expected) / len(expected))

    def test_unscored_prompt_logits_do_not_enter_mean(self):
        logits = mutable_logits(self.batch)
        logits[0][0] = [float("nan")] * len(logits[0][0])
        self.assertAlmostEqual(score(replace(self.batch, logits=logits))[0].likelihood.mean_log_probability,
                               score(self.batch)[0].likelihood.mean_log_probability)

    def test_unscored_padding_logits_do_not_enter_mean(self):
        logits = mutable_logits(self.batch)
        logits[0][-1] = [float("nan")] * len(logits[0][-1])
        self.assertAlmostEqual(score(replace(self.batch, logits=logits))[0].likelihood.mean_log_probability,
                               score(self.batch)[0].likelihood.mean_log_probability)

    def test_variable_prefixes_keep_identical_action_identity(self):
        outputs = score(self.batch)
        self.assertEqual(outputs[0].likelihood.token_count, outputs[1].likelihood.token_count)
        self.assertEqual(outputs[0].likelihood.token_fingerprint, outputs[1].likelihood.token_fingerprint)

    def test_left_padding_has_valid_attended_predictor(self):
        logits = [[[0.0] * 4 for _ in range(4)]]
        result = causal_action_likelihoods(logits, ((0, 1, 2, 3),), ((False, True, True, True),),
                                           ((False, False, True, True),), forbidden_action_token_ids=frozenset({0}))
        self.assertAlmostEqual(result[0].mean_log_probability, -math.log(4))

    def test_forbidden_stop_inside_action_is_rejected(self):
        with self.assertRaises(ScoringInputError):
            score(replace(self.batch, forbidden_action_token_ids=frozenset({2})))

    def test_action_mask_cannot_include_padding(self):
        masks = [list(row) for row in self.batch.action_mask]
        masks[0][-1] = True
        with self.assertRaises(ScoringInputError):
            score(replace(self.batch, action_mask=masks))

    def test_action_requires_causal_prefix(self):
        masks = ((True, True, True, True, False), self.batch.action_mask[1])
        with self.assertRaises(ScoringInputError):
            score(replace(self.batch, action_mask=masks))

    def test_empty_action_is_rejected(self):
        with self.assertRaises(ScoringInputError):
            score(replace(self.batch, action_mask=((False,) * 5, self.batch.action_mask[1])))

    def test_noncontiguous_action_mask_is_rejected(self):
        with self.assertRaises(ScoringInputError):
            score(replace(self.batch, action_mask=((False, True, False, True, False), self.batch.action_mask[1])))

    def test_attention_holes_are_rejected(self):
        with self.assertRaises(ScoringInputError):
            score(replace(self.batch, attention_mask=((True, False, True, True, False), self.batch.attention_mask[1])))

    def test_same_length_different_action_tokens_are_rejected(self):
        ids = [list(row) for row in self.batch.input_ids]
        ids[1][-1] = ids[1][-2]
        with self.assertRaises(ScoringInputError):
            score(replace(self.batch, input_ids=ids))

    def test_nonfinite_scored_logits_are_rejected(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                logits = mutable_logits(self.batch)
                logits[0][1][0] = value
                with self.assertRaises(ScoringInputError):
                    score(replace(self.batch, logits=logits))

    def test_stable_under_large_common_logit_shift(self):
        offset = math.ldexp(1.0, 10)
        logits = [[[v + offset for v in predictor] for predictor in row] for row in self.batch.logits]
        self.assertAlmostEqual(score(replace(self.batch, logits=logits))[0].likelihood.mean_log_probability,
                               score(self.batch)[0].likelihood.mean_log_probability)

    def test_nonreal_or_unrepresentable_scored_logits_are_rejected(self):
        for value in (True, "symbolic-not-a-number", 10 ** 400):
            with self.subTest(value_type=type(value).__name__):
                logits = mutable_logits(self.batch)
                logits[0][1][0] = value
                with self.assertRaises(ScoringInputError):
                    score(replace(self.batch, logits=logits))

    def test_ragged_sequence_and_vocabulary_are_rejected(self):
        with self.assertRaises(ScoringInputError):
            score(replace(self.batch, attention_mask=(self.batch.attention_mask[0][:-1], self.batch.attention_mask[1])))
        logits = mutable_logits(self.batch)
        logits[0][0].pop()
        with self.assertRaises(ScoringInputError):
            score(replace(self.batch, logits=logits))

    def test_nonbinary_masks_and_invalid_tokens_are_rejected(self):
        for value in (-1, len(self.batch.logits[0][0]), True, 1.5):
            with self.subTest(value=value):
                ids = [list(row) for row in self.batch.input_ids]
                ids[0][0] = value
                with self.assertRaises(ScoringInputError):
                    score(replace(self.batch, input_ids=ids))
        masks = [list(row) for row in self.batch.action_mask]
        masks[0][0] = 2
        with self.assertRaises(ScoringInputError):
            score(replace(self.batch, action_mask=masks))

    def test_empty_batch_and_condition_count_mismatch_are_rejected(self):
        with self.assertRaises(ScoringInputError):
            causal_action_likelihoods((), (), (), (), forbidden_action_token_ids=frozenset())
        with self.assertRaises(ScoringInputError):
            score(replace(self.batch, input_ids=self.batch.input_ids[:1]))


class ConditionConsistencyContracts(unittest.TestCase):
    def setUp(self):
        self.batch = prepared_batch(context(), candidate())

    def test_valid_prepared_conditions_preserve_order(self):
        outputs = score(self.batch)
        self.assertEqual(tuple(s.condition_id for s in outputs), tuple(c.condition_id for c in self.batch.conditions))

    def test_original_must_be_first_and_ids_and_goals_must_be_unique(self):
        original, comparison = self.batch.conditions
        cases = ((comparison, original), (original, replace(comparison, condition_id=original.condition_id)),
                 (original, replace(comparison, goal=original.goal)), (original, replace(comparison, goal="")))
        for conditions in cases:
            with self.subTest(conditions=conditions):
                with self.assertRaises(ConditionInputError):
                    validate_conditions(context(), candidate(), conditions)

    def test_action_provenance_or_context_change_is_rejected(self):
        original, comparison = self.batch.conditions
        cases = (replace(comparison, action="another-symbolic-action"),
                 replace(comparison, provenance=replace(comparison.provenance, prompt_version="another-symbolic-prompt")),
                 replace(comparison, context_key="different-symbolic-context"))
        for changed in cases:
            with self.subTest(changed=changed):
                with self.assertRaises(ConditionInputError):
                    validate_conditions(context(), candidate(), (original, changed))

    def test_context_fingerprint_excludes_goal_but_tracks_public_inputs(self):
        current = context()
        self.assertEqual(public_context_key(current), public_context_key(replace(current, goal="another-symbolic-goal")))
        variants = (replace(current, observation="another-symbolic-observation"),
                    replace(current, instructions="another-symbolic-instruction"),
                    replace(current, scope_id="another-symbolic-scope"),
                    replace(current, history=(HistoryTurn("symbolic-action", "symbolic-response"),)))
        for changed in variants:
            self.assertNotEqual(public_context_key(current), public_context_key(changed))

    def test_one_condition_or_empty_identifier_is_rejected(self):
        original, comparison = self.batch.conditions
        with self.assertRaises(ConditionInputError):
            validate_conditions(context(), candidate(), (original,))
        with self.assertRaises(ConditionInputError):
            validate_conditions(context(), candidate(), (original, replace(comparison, condition_id="")))


class ScoringBridgeContracts(unittest.TestCase):
    def test_real_arithmetic_runs_before_private_policy(self):
        provider = SymbolicPreparedProvider()
        policy = ScriptedRiskPolicy((PTAResult(PTAStatus.NOT_FLAGGED, None),))
        evaluator = ScoringTargetEvaluator(candidate().provenance, provider, policy)
        result = evaluator.evaluate(context(), candidate())
        self.assertIs(result.status, PTAStatus.NOT_FLAGGED)
        self.assertTrue(policy.received_scores)
        self.assertTrue(all(math.isfinite(s.likelihood.mean_log_probability) for s in policy.received_scores[0]))

    def test_preparation_can_abstain_without_a_policy_call(self):
        class Inapplicable:
            def prepare(self, current, selected):
                return PTAResult(PTAStatus.ABSTAINED, Reason.UNSUPPORTED_INPUT)
        policy = ScriptedRiskPolicy(())
        result = ScoringTargetEvaluator(candidate().provenance, Inapplicable(), policy).evaluate(context(), candidate())
        self.assertIs(result.status, PTAStatus.ABSTAINED)
        self.assertEqual(policy.received_scores, [])

    def test_preparation_cannot_bypass_scoring_with_a_risk_decision(self):
        class Bypass:
            def prepare(self, current, selected):
                return PTAResult(PTAStatus.NOT_FLAGGED, None)
        with self.assertRaises(ValueError):
            ScoringTargetEvaluator(candidate().provenance, Bypass(), ScriptedRiskPolicy(())).evaluate(context(), candidate())

    def test_invalid_prepared_input_abstains_through_controller(self):
        class Invalid:
            def prepare(self, current, selected):
                batch = prepared_batch(current, selected)
                return replace(batch, forbidden_action_token_ids=frozenset({2}))
        policy = ScriptedRiskPolicy(())
        evaluator = ScoringTargetEvaluator(candidate().provenance, Invalid(), policy)
        controller = PACCController(PACCSettings(Variant.PACC), target_evaluator=evaluator)
        result = controller.process(context(), candidate(), ScriptedPlanner(()), SymbolicAdapter(context().environment, ()))
        self.assertIs(result.initial.pta.reason, Reason.ASSESSMENT_UNAVAILABLE)
        self.assertFalse(result.revision_attempted)
        self.assertEqual(policy.received_scores, [])

    def test_bad_policy_return_and_changed_provenance_are_rejected(self):
        for reply in ("not a PTAResult", PTAResult(PTAStatus.NOT_RUN, None)):
            with self.subTest(reply=reply):
                evaluator = ScoringTargetEvaluator(candidate().provenance, SymbolicPreparedProvider(), ScriptedRiskPolicy((reply,)))
                with self.assertRaises((TypeError, ValueError)):
                    evaluator.evaluate(context(), candidate())
        evaluator = ScoringTargetEvaluator(replace(candidate().provenance, tokenizer_revision="different-symbolic-tokenizer"),
                                           SymbolicPreparedProvider(), ScriptedRiskPolicy(()))
        with self.assertRaises(ValueError):
            evaluator.evaluate(context(), candidate())

    def test_scoring_demo_reaches_controller_with_real_public_scores(self):
        result = run_scoring_demo()
        self.assertEqual(result["kind"], "synthetic_scoring_integration_only")
        self.assertTrue(result["scoring_arithmetic_executed"])
        self.assertTrue(result["finite_action_means"])
        self.assertEqual(result["risk_decisions"], "explicitly_scripted_fixture")
        self.assertEqual(result["submitted"], "revision")
        self.assertEqual(result["environment_submission_count"], 1)

    def test_invalid_comparison_rejects_whole_batch_before_policy(self):
        class InvalidComparison:
            def prepare(self, current, selected):
                batch = prepared_batch(current, selected)
                logits = mutable_logits(batch)
                action_position = next(i for i, active in enumerate(batch.action_mask[1]) if active)
                logits[1][action_position - 1][0] = float("nan")
                return replace(batch, logits=logits)

        policy = ScriptedRiskPolicy(())
        evaluator = ScoringTargetEvaluator(candidate().provenance, InvalidComparison(), policy)
        with self.assertRaises(AssessmentUnavailable):
            evaluator.evaluate(context(), candidate())
        self.assertEqual(policy.received_scores, [])

    def test_condition_specific_logits_change_only_the_corresponding_score(self):
        batch = prepared_batch(context(), candidate())
        baseline = score(batch)

        class ChangedComparison:
            def prepare(self, current, selected):
                logits = mutable_logits(batch)
                action_position = next(i for i, active in enumerate(batch.action_mask[1]) if active)
                target = batch.input_ids[1][action_position]
                logits[1][action_position - 1][target] = math.log(3)
                return replace(batch, logits=logits)

        policy = ScriptedRiskPolicy((PTAResult(PTAStatus.NOT_FLAGGED, None),))
        ScoringTargetEvaluator(candidate().provenance, ChangedComparison(), policy).evaluate(context(), candidate())
        original, comparison = policy.received_scores[0]
        self.assertEqual(original, baseline[0])
        self.assertGreater(comparison.likelihood.mean_log_probability, baseline[1].likelihood.mean_log_probability)
        self.assertEqual(comparison.likelihood.token_fingerprint, original.likelihood.token_fingerprint)
