from __future__ import annotations

from typing import Protocol

from .types import (Candidate, Condition, Context, DiagnosticEnvelope, EvidenceSnapshot,
                    ParsedAction, Provenance, PTAResult)


class InvalidAction(ValueError):
    """The public atomic-action grammar rejects the candidate."""


class AssessmentUnavailable(RuntimeError):
    """Data-dependent assessment failure; not a missing implementation or success."""


class RevisionUnavailable(RuntimeError):
    """The allowed local revision could not be generated."""


class PrivateComponentRequired(RuntimeError):
    """A withheld provider has not been supplied; do not simulate its result."""


class Adapter(Protocol):
    """Private environment rules; interface declarations are intentionally public.

    Parsing and preconditions use the fixed public action interface. The snapshot
    provider owns scope-aware state updates, conflict resolution and permitted
    interface implications. Rechecking the same context must not advance time.
    A decision-local public session freezes its first valid snapshot for repair.
    No hidden state, reward, future candidate feedback or gold actions are inputs.
    """
    environment: str

    def parse(self, context: Context, candidate: Candidate) -> ParsedAction: ...

    def preconditions(self, context: Context, action: ParsedAction) -> tuple[Condition, ...]: ...

    def public_snapshot(self, context: Context) -> EvidenceSnapshot: ...


class TargetEvaluator(Protocol):
    """Private task-specific PTA implementation behind a categorical boundary.

    Follow the method scope specified in the manuscript. Use public pre-action
    information and the declared planner model. Return explicit abstention when
    inapplicable or unavailable. Do not execute a candidate or use an evaluator
    oracle. Missing implementation/configuration is not ordinary abstention.
    """
    provenance: Provenance

    def evaluate(self, context: Context, candidate: Candidate) -> PTAResult: ...


class Planner(Protocol):
    """External planner; exact prompts and model-side serialization are withheld.

    A revision uses the public diagnostic envelope within the manuscript's stated
    information boundary. Generic retry has no structured diagnosis. Use the same
    declared backend; do not run search or execute an action to implement repair.
    """
    provenance: Provenance

    def revise_once(self, context: Context, candidate: Candidate,
                    diagnosis: DiagnosticEnvelope) -> Candidate: ...
