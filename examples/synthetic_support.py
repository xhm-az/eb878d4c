"""Explicit test doubles, NOT the undistributed evaluator or a benchmark adapter.

All text below is symbolic test material. Environment labels exercise controller
branches only; no website, task set, model, reward or numerical score is used.
"""
from __future__ import annotations

from pacc_review import Candidate, Context, Provenance
from pacc_review.ports import InvalidAction
from pacc_review.types import (Condition, DiagnosticEnvelope, Environment,
                               EvidenceSnapshot, Fact, ParsedAction, PTAResult)


def provenance() -> Provenance:
    return Provenance("synthetic-model-identity", "synthetic-tokenizer-identity", "synthetic-base-prompt")


def context(environment: Environment = Environment.WEBSHOP) -> Context:
    return Context(environment, "symbolic-task-goal", "symbolic-public-observation", (),
                   "symbolic-base-instructions", "symbolic-current-scope")


def candidate() -> Candidate:
    return Candidate("candidate", provenance())


def revision() -> Candidate:
    return Candidate("revision", provenance())


def enabled_fact(action: str, value: bool) -> Fact:
    return Fact("enabled", (action,), value, "public_interface", "symbolic-public-evidence")


class SymbolicAdapter:
    """A tiny fixture dialect, not a partial WebShop/ALFWorld/WebArena grammar."""

    def __init__(self, environment: Environment, facts: tuple[Fact, ...], *,
                 events: list[str] | None = None, scope_override: str | None = None) -> None:
        self.environment = environment.value
        self.facts = facts
        self.events = events if events is not None else []
        self.scope_override = scope_override

    def parse(self, current: Context, selected: Candidate) -> ParsedAction:
        self.events.append("parse:" + selected.action)
        if selected.action not in {"candidate", "revision"}:
            raise InvalidAction("Not a symbolic fixture action")
        return ParsedAction("symbolic_action", (selected.action,))

    def preconditions(self, current: Context, action: ParsedAction) -> tuple[Condition, ...]:
        self.events.append("preconditions:" + action.args[0])
        return (Condition("enabled", action.args, True, ()),)

    def public_snapshot(self, current: Context) -> EvidenceSnapshot:
        self.events.append("snapshot")
        return EvidenceSnapshot(self.scope_override or current.scope_id, self.facts)


class ScriptedTargetEvaluator:
    """Preset categorical replies test routing, not actual PTA risk detection."""

    def __init__(self, replies: tuple[PTAResult | Exception, ...], *,
                 events: list[str] | None = None) -> None:
        self.provenance = provenance()
        self.replies = list(replies)
        self.calls: list[str] = []
        self.events = events if events is not None else []

    def evaluate(self, current: Context, selected: Candidate) -> PTAResult:
        self.calls.append(selected.action)
        self.events.append("pta_fixture:" + selected.action)
        if not self.replies:
            raise AssertionError("Unexpected target-evaluator call")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class ScriptedPlanner:
    """Returns supplied symbolic revisions; never calls or emulates a model."""

    def __init__(self, replies: tuple[Candidate | Exception, ...], *,
                 events: list[str] | None = None) -> None:
        self.provenance = provenance()
        self.replies = list(replies)
        self.requests: list[DiagnosticEnvelope] = []
        self.events = events if events is not None else []

    def revise_once(self, current: Context, selected: Candidate,
                    diagnosis: DiagnosticEnvelope) -> Candidate:
        self.requests.append(diagnosis)
        self.events.append("revision_request:" + diagnosis.kind.value)
        if not self.replies:
            raise AssertionError("Unexpected revision request")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class RecordingEnvironment:
    """Records the submitted symbolic action; not a task simulator or evaluator."""

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.submissions: list[str] = []

    def step(self, action: str) -> dict[str, str]:
        self.submissions.append(action)
        self.events.append("environment_submission:" + action)
        return {"observation": "symbolic-response"}
