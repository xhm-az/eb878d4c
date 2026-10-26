from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from .ports import Adapter, InvalidAction
from .types import (Candidate, Condition, ConditionResult, Context, EEAResult,
                    EvidenceSnapshot, Fact, Truth)


def assess(condition: Condition, facts: tuple[Fact, ...]) -> ConditionResult:
    """Three-valued counterevidence logic; no closed-world negation."""
    if condition.alternatives:
        children = tuple(assess(c, facts) for c in condition.alternatives)
        if any(c.truth is Truth.SUPPORTED for c in children):
            truth = Truth.SUPPORTED
        elif all(c.truth is Truth.CONTRADICTED for c in children):
            truth = Truth.CONTRADICTED
        else:
            truth = Truth.UNKNOWN
        evidence = tuple(f for c in children for f in c.evidence)
        return ConditionResult(condition, truth, evidence)
    matching = tuple(f for f in facts if (f.predicate, f.args) == (condition.predicate, condition.args))
    values = {f.value for f in matching}
    if len(values) != 1:
        truth = Truth.UNKNOWN
    else:
        truth = Truth.SUPPORTED if next(iter(values)) == condition.value else Truth.CONTRADICTED
    return ConditionResult(condition, truth, matching)


class EvidenceAuditSession:
    """One decision's lazy, frozen evidence view, shared by its reassessment.

    The adapter still owns fact extraction and rule correctness. A session only
    prevents an initial check and local revision from observing different fact
    snapshots before an environment action has actually been submitted.
    """

    def __init__(self, context: Context, adapter: Adapter) -> None:
        if context.environment.value != adapter.environment:
            raise ValueError("Context and adapter environments must match")
        self._context, self._adapter = context, adapter
        self._snapshot: EvidenceSnapshot | None = None

    def _facts(self) -> tuple[Fact, ...]:
        if self._snapshot is None:
            snapshot = self._adapter.public_snapshot(self._context)
            if not isinstance(snapshot, EvidenceSnapshot):
                raise TypeError("The adapter must return an EvidenceSnapshot")
            if snapshot.scope_id != self._context.scope_id:
                raise ValueError("Stale evidence snapshot: current public scope is required")
            frozen = []
            for fact in snapshot.facts:
                if not isinstance(fact, Fact):
                    raise TypeError("An evidence snapshot may contain only Fact objects")
                if (not isinstance(fact.args, Sequence) or isinstance(fact.args, (str, bytes))
                        or not all(isinstance(a, str) for a in fact.args)):
                    raise TypeError("Fact arguments must be a sequence of strings")
                # Copy even incorrectly supplied mutable containers at the port.
                frozen.append(replace(fact, args=tuple(fact.args)))
            self._snapshot = EvidenceSnapshot(snapshot.scope_id, tuple(frozen))
        return self._snapshot.facts

    def evaluate(self, candidate: Candidate) -> EEAResult:
        try:
            parsed = self._adapter.parse(self._context, candidate)
        except InvalidAction:
            return EEAResult(True, ())
        facts = self._facts()
        conditions = self._adapter.preconditions(self._context, parsed)
        return EEAResult(False, tuple(assess(c, facts) for c in conditions))


class ExplicitEvidenceAudit:
    """Public comparison logic; all environment-specific rules remain external."""

    def session(self, context: Context, adapter: Adapter) -> EvidenceAuditSession:
        return EvidenceAuditSession(context, adapter)

    def evaluate(self, context: Context, candidate: Candidate, adapter: Adapter) -> EEAResult:
        """A one-shot check; controllers share a session for local reassessment."""
        return self.session(context, adapter).evaluate(candidate)
