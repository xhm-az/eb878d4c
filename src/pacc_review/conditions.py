"""Consistency of supplied conditions, not construction of task-goal contrasts."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .types import Candidate, Context, Provenance


class ConditionInputError(ValueError):
    pass


@dataclass(frozen=True)
class PreparedCondition:
    condition_id: str
    goal: str
    action: str
    provenance: Provenance
    context_key: str


def public_context_key(context: Context) -> str:
    """Semantic identity excluding the varied goal, not a model prompt serializer."""
    payload = {"environment": context.environment.value, "scope": context.scope_id,
               "observation": context.observation, "instructions": context.instructions,
               "history": [(h.action, h.observation) for h in context.history]}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_conditions(context: Context, candidate: Candidate,
                        conditions: tuple[PreparedCondition, ...]) -> None:
    if len(conditions) < 2:
        raise ConditionInputError("Supply the original and at least one comparison condition")
    if any(not isinstance(c, PreparedCondition) for c in conditions):
        raise ConditionInputError("Expected typed prepared conditions")
    if conditions[0].goal != context.goal:
        raise ConditionInputError("The original goal must be the first condition")
    if any(not isinstance(c.condition_id, str) or not c.condition_id.strip() for c in conditions):
        raise ConditionInputError("Condition identifiers must be nonempty")
    if len({c.condition_id for c in conditions}) != len(conditions):
        raise ConditionInputError("Condition identifiers must be unique")
    if any(not isinstance(c.goal, str) or not c.goal.strip() for c in conditions):
        raise ConditionInputError("Condition goals must be nonempty")
    if len({c.goal for c in conditions}) != len(conditions):
        raise ConditionInputError("Comparison goals must differ from the original and each other")
    key = public_context_key(context)
    if any(c.context_key != key for c in conditions):
        raise ConditionInputError("Public context differs between conditions")
    if any(c.action != candidate.action for c in conditions):
        raise ConditionInputError("The scored action must remain unchanged")
    if any(c.provenance != candidate.provenance for c in conditions):
        raise ConditionInputError("Model/tokenizer/base-prompt provenance differs")
