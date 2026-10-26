"""Model-free reference arithmetic over supplied causal logits.

No model, tokenizer, goal constructor, support-gap calculation or risk policy is
included. Values passed to this module can be sensitive; there is no file logger.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Real

from .conditions import PreparedCondition, validate_conditions
from .types import Candidate, Context


class ScoringInputError(ValueError):
    pass


@dataclass(frozen=True)
class ActionLikelihood:
    mean_log_probability: float
    token_count: int
    token_fingerprint: str


@dataclass(frozen=True)
class ConditionLikelihood:
    condition_id: str
    likelihood: ActionLikelihood


def _binary(value) -> bool:
    if type(value) not in {bool, int} or value not in (0, 1):
        raise ScoringInputError("Masks must contain Boolean/binary entries")
    return bool(value)


def _target_logp(logits: Sequence[float], target: int) -> float:
    if any(isinstance(v, bool) or not isinstance(v, Real) for v in logits):
        raise ScoringInputError("Scored logits must be real numerical values")
    try:
        values = tuple(float(v) for v in logits)
    except (OverflowError, ValueError) as exc:
        raise ScoringInputError("Scored logits cannot be represented as finite floats") from exc
    if not all(math.isfinite(v) for v in values):
        raise ScoringInputError("Nonfinite logits at a scored predictor position")
    maximum = max(values)
    normalizer = math.log(math.fsum(math.exp(v - maximum) for v in values))
    result = (values[target] - maximum) - normalizer
    if not math.isfinite(result):
        raise ScoringInputError("Nonfinite action-token log probability")
    return result


def causal_action_likelihoods(logits: Sequence[Sequence[Sequence[float]]],
                              input_ids: Sequence[Sequence[int]],
                              attention_mask: Sequence[Sequence[bool]],
                              action_mask: Sequence[Sequence[bool]], *,
                              forbidden_action_token_ids: frozenset[int]) -> tuple[ActionLikelihood, ...]:
    """Score identical action targets under already prepared conditions.

    Logits at position j-1 predict input_ids at j. Only action-mask target
    positions enter the mean. Prompt/padding/unmasked suffix positions do not.
    Forbidden stop/special IDs must be supplied explicitly by the private backend.
    This pure-Python reference prioritizes inspectability, not GPU throughput.
    """
    if not input_ids or len(logits) != len(input_ids) or len(attention_mask) != len(input_ids) or len(action_mask) != len(input_ids):
        raise ScoringInputError("Empty batch or inconsistent batch dimensions")
    if any(type(t) is not int or t < 0 for t in forbidden_action_token_ids):
        raise ScoringInputError("Invalid forbidden token identifier")
    vocabulary = None
    rows = []
    common_tokens = None
    for row_logits, ids, attention, mask in zip(logits, input_ids, attention_mask, action_mask):
        if not ids or len(row_logits) != len(ids) or len(attention) != len(ids) or len(mask) != len(ids):
            raise ScoringInputError("Inconsistent sequence dimensions")
        for predictor in row_logits:
            if not predictor:
                raise ScoringInputError("Empty vocabulary dimension")
            if vocabulary is None:
                vocabulary = len(predictor)
            if len(predictor) != vocabulary:
                raise ScoringInputError("Ragged vocabulary dimensions")
        if any(type(t) is not int or t < 0 or t >= vocabulary for t in ids):
            raise ScoringInputError("Input token identifier is outside the supplied vocabulary")
        attended = tuple(_binary(v) for v in attention)
        selected = tuple(_binary(v) for v in mask)
        active = tuple(i for i, v in enumerate(attended) if v)
        targets = tuple(i for i, v in enumerate(selected) if v)
        if not active or active != tuple(range(active[0], active[-1] + 1)):
            raise ScoringInputError("Attended tokens must form a contiguous region")
        if not targets or targets != tuple(range(targets[0], targets[-1] + 1)):
            raise ScoringInputError("Action targets must form a nonempty contiguous region")
        if any(not attended[i] for i in targets):
            raise ScoringInputError("Action mask includes padding")
        if targets[0] == 0 or not attended[targets[0] - 1]:
            raise ScoringInputError("Action has no attended causal prefix")
        tokens = tuple(ids[i] for i in targets)
        if any(t in forbidden_action_token_ids for t in tokens):
            raise ScoringInputError("Action mask includes a forbidden stop/special token")
        if common_tokens is None:
            common_tokens = tokens
        elif tokens != common_tokens:
            raise ScoringInputError("Scored action token sequences differ across conditions")
        rows.append((row_logits, ids, targets))
    fingerprint = hashlib.sha256(",".join(str(t) for t in common_tokens).encode("ascii")).hexdigest()
    outputs = []
    for row_logits, ids, targets in rows:
        mean = math.fsum(_target_logp(row_logits[j - 1], ids[j]) / len(targets) for j in targets)
        if not math.isfinite(mean):
            raise ScoringInputError("Nonfinite action-token mean")
        outputs.append(ActionLikelihood(mean, len(targets), fingerprint))
    return tuple(outputs)


def score_prepared_conditions(context: Context, candidate: Candidate,
                               conditions: tuple[PreparedCondition, ...],
                               logits: Sequence[Sequence[Sequence[float]]],
                               input_ids: Sequence[Sequence[int]],
                               attention_mask: Sequence[Sequence[bool]],
                               action_mask: Sequence[Sequence[bool]], *,
                               forbidden_action_token_ids: frozenset[int]) -> tuple[ConditionLikelihood, ...]:
    validate_conditions(context, candidate, conditions)
    if len(conditions) != len(input_ids):
        raise ScoringInputError("Condition count differs from scoring batch")
    scores = causal_action_likelihoods(logits, input_ids, attention_mask, action_mask,
                                       forbidden_action_token_ids=forbidden_action_token_ids)
    return tuple(ConditionLikelihood(c.condition_id, score) for c, score in zip(conditions, scores))
