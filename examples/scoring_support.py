"""Synthetic arithmetic/provider fixtures, never real model outputs or PTA policy."""
from __future__ import annotations

from pacc_review.conditions import PreparedCondition, public_context_key
from pacc_review.scoring_evaluator import PreparedScoringBatch
from pacc_review.types import Candidate, Context, PTAResult


def prepared_batch(current: Context, selected: Candidate) -> PreparedScoringBatch:
    # A tiny artificial vocabulary and symbolic token mapping for CPU unit checks.
    vocabulary = tuple(range(4))
    action_ids = (2, 3) if selected.action == "candidate" else (3, 2)
    ids = ((0, 1, *action_ids, 0), (0, 1, 1, *action_ids))
    attention = ((True, True, True, True, False), (True, True, True, True, True))
    action = ((False, False, True, True, False), (False, False, False, True, True))
    logits = tuple(tuple(tuple(0.0 for _ in vocabulary) for _ in row) for row in ids)
    key = public_context_key(current)
    conditions = (
        PreparedCondition("original", current.goal, selected.action, selected.provenance, key),
        PreparedCondition("comparison", "symbolic-comparison-goal", selected.action, selected.provenance, key),
    )
    return PreparedScoringBatch(conditions, logits, ids, attention, action, frozenset({0}))


class SymbolicPreparedProvider:
    """Supplies artificial matrices; does not construct real task-goal contrasts."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def prepare(self, current: Context, selected: Candidate) -> PreparedScoringBatch:
        self.calls.append(selected.action)
        return prepared_batch(current, selected)


class ScriptedRiskPolicy:
    """Preset categories exercise integration, not the private decision formula."""

    def __init__(self, replies: tuple[PTAResult, ...]) -> None:
        self.replies = list(replies)
        self.received_scores = []

    def decide(self, current, selected, scores):
        self.received_scores.append(scores)
        if not self.replies:
            raise AssertionError("Unexpected scripted-policy invocation")
        return self.replies.pop(0)
