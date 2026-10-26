"""Executable scoring bridge with private preparation and private risk policy."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from .conditions import ConditionInputError, PreparedCondition
from .ports import AssessmentUnavailable
from .scoring import ConditionLikelihood, ScoringInputError, score_prepared_conditions
from .types import Candidate, Context, Provenance, PTAResult, PTAStatus


@dataclass(frozen=True)
class PreparedScoringBatch:
    conditions: tuple[PreparedCondition, ...]
    logits: Sequence[Sequence[Sequence[float]]]
    input_ids: Sequence[Sequence[int]]
    attention_mask: Sequence[Sequence[bool]]
    action_mask: Sequence[Sequence[bool]]
    forbidden_action_token_ids: frozenset[int]


class PreparedInputProvider(Protocol):
    """Private applicability, contrast construction, tokenization and model forward."""
    def prepare(self, context: Context, candidate: Candidate) -> PreparedScoringBatch | PTAResult: ...


class PrivateRiskPolicy(Protocol):
    """Private score comparison/decision; no policy formula or settings are supplied."""
    def decide(self, context: Context, candidate: Candidate,
               scores: tuple[ConditionLikelihood, ...]) -> PTAResult: ...


class ScoringTargetEvaluator:
    def __init__(self, provenance: Provenance, provider: PreparedInputProvider,
                 policy: PrivateRiskPolicy) -> None:
        self.provenance, self.provider, self.policy = provenance, provider, policy

    def evaluate(self, context: Context, candidate: Candidate) -> PTAResult:
        if candidate.provenance != self.provenance:
            raise ValueError("Scoring bridge and candidate provenance differ")
        prepared = self.provider.prepare(context, candidate)
        if isinstance(prepared, PTAResult):
            if prepared.status is not PTAStatus.ABSTAINED:
                raise ValueError("Preparation may abstain but cannot substitute a risk decision")
            return prepared
        if not isinstance(prepared, PreparedScoringBatch):
            raise TypeError("Provider must return a prepared batch or explicit abstention")
        try:
            scores = score_prepared_conditions(
                context, candidate, prepared.conditions, prepared.logits, prepared.input_ids,
                prepared.attention_mask, prepared.action_mask,
                forbidden_action_token_ids=prepared.forbidden_action_token_ids)
        except (ConditionInputError, ScoringInputError) as exc:
            raise AssessmentUnavailable("Prepared scoring input is invalid") from exc
        result = self.policy.decide(context, candidate, scores)
        if not isinstance(result, PTAResult):
            raise TypeError("Private risk policy must return PTAResult")
        if result.status is PTAStatus.NOT_RUN:
            raise ValueError("An invoked risk policy must assess or explicitly abstain")
        return result
