from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Truth(str, Enum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNKNOWN = "unknown"


class PTAStatus(str, Enum):
    NOT_RUN = "not_run"
    ABSTAINED = "abstained"
    NOT_FLAGGED = "not_flagged"
    FLAGGED = "flagged"


class Reason(str, Enum):
    UNSUPPORTED_ENVIRONMENT = "unsupported_environment"
    UNSUPPORTED_INPUT = "unsupported_input"
    ASSESSMENT_UNAVAILABLE = "assessment_unavailable"


class Trigger(str, Enum):
    NONE = "none"
    EEA = "eea"
    PTA = "pta"


class DiagnosticKind(str, Enum):
    EVIDENCE = "evidence"
    TARGET = "target"
    GENERIC_RETRY = "generic_retry"


class Environment(str, Enum):
    ALFWORLD = "alfworld"
    WEBSHOP = "webshop"
    WEBARENA_LITE = "webarena_lite"


@dataclass(frozen=True)
class Provenance:
    """Declared identity, not proof that an external provider used this model."""
    checkpoint_revision: str
    tokenizer_revision: str
    prompt_version: str

    def __post_init__(self) -> None:
        if not all(isinstance(v, str) and v.strip() for v in (
                self.checkpoint_revision, self.tokenizer_revision, self.prompt_version)):
            raise ValueError("Complete model, tokenizer and prompt provenance is required")


@dataclass(frozen=True)
class HistoryTurn:
    action: str
    observation: str


@dataclass(frozen=True)
class Context:
    environment: Environment
    goal: str
    observation: str
    history: tuple[HistoryTurn, ...]
    instructions: str
    scope_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "environment", Environment(self.environment))
        if not self.scope_id:
            raise ValueError("An explicit current public scope is required")


@dataclass(frozen=True)
class Candidate:
    action: str
    provenance: Provenance


@dataclass(frozen=True)
class Fact:
    predicate: str
    args: tuple[str, ...]
    value: bool
    source: str
    evidence: str

    def __post_init__(self) -> None:
        if self.source not in {"observation", "executed_feedback", "public_interface"}:
            raise ValueError("Facts must be grounded in public pre-action information")
        if type(self.value) is not bool:
            raise TypeError("Fact values must be Boolean")


@dataclass(frozen=True)
class EvidenceSnapshot:
    scope_id: str
    facts: tuple[Fact, ...]


@dataclass(frozen=True)
class ParsedAction:
    schema: str
    args: tuple[str, ...]


@dataclass(frozen=True)
class Condition:
    predicate: str
    args: tuple[str, ...]
    value: bool
    alternatives: tuple[Condition, ...]

    def __post_init__(self) -> None:
        if type(self.value) is not bool:
            raise TypeError("Condition values must be Boolean")
        if bool(self.predicate) == bool(self.alternatives):
            raise ValueError("Use either an atomic predicate or a disjunction")
        if self.alternatives and self.args:
            raise ValueError("A disjunction has child conditions, not bound arguments")
        if self.alternatives and not self.value:
            raise ValueError("Negate atomic children explicitly, not an entire disjunction")


@dataclass(frozen=True)
class ConditionResult:
    condition: Condition
    truth: Truth
    evidence: tuple[Fact, ...]


@dataclass(frozen=True)
class EEAResult:
    syntax_error: bool
    conditions: tuple[ConditionResult, ...]

    @property
    def contradictions(self) -> tuple[ConditionResult, ...]:
        return tuple(c for c in self.conditions if c.truth is Truth.CONTRADICTED)

    @property
    def passed(self) -> bool:
        return not self.syntax_error and not self.contradictions


@dataclass(frozen=True)
class PTAResult:
    """Categorical boundary only; private calculations and parameters stay private."""
    status: PTAStatus
    reason: Reason | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", PTAStatus(self.status))
        if self.reason is not None:
            object.__setattr__(self, "reason", Reason(self.reason))
        if self.status is PTAStatus.ABSTAINED and self.reason is None:
            raise ValueError("Abstention requires a public categorical reason")
        if self.status is not PTAStatus.ABSTAINED and self.reason is not None:
            raise ValueError("Only abstention carries a reason")


@dataclass(frozen=True)
class Assessment:
    eea: EEAResult
    pta: PTAResult

    @property
    def trigger(self) -> Trigger:
        if not self.eea.passed:
            return Trigger.EEA
        return Trigger.PTA if self.pta.status is PTAStatus.FLAGGED else Trigger.NONE


@dataclass(frozen=True)
class DiagnosticEnvelope:
    """Public information-selection policy, not an exact textual prompt.

    Internal PTA values and alternative goals have no fields in this envelope.
    It can contain private task text at runtime: never serialize it for sharing.
    """
    kind: DiagnosticKind
    original_action: str
    original_goal: str | None
    syntax_error: bool
    counterevidence: tuple[ConditionResult, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", DiagnosticKind(self.kind))
        if type(self.syntax_error) is not bool:
            raise TypeError("syntax_error must be Boolean")
        if any(c.truth is not Truth.CONTRADICTED for c in self.counterevidence):
            raise ValueError("Only explicitly contradicted conditions enter a diagnosis")
        if self.kind is DiagnosticKind.EVIDENCE:
            if self.original_goal is not None or not (self.syntax_error or self.counterevidence):
                raise ValueError("Evidence diagnosis requires a syntax issue or counterevidence")
        elif self.kind is DiagnosticKind.TARGET:
            if not isinstance(self.original_goal, str) or self.syntax_error or self.counterevidence:
                raise ValueError("Target diagnosis carries the original goal, not interface conflicts")
        elif self.original_goal is not None or self.syntax_error or self.counterevidence:
            raise ValueError("Generic retry must not carry structured diagnostic details")


@dataclass(frozen=True)
class Decision:
    original: Candidate
    submitted: Candidate
    initial: Assessment | None
    revision: Candidate | None
    reassessment: Assessment | None
    revision_attempted: bool
    fell_back: bool
    diagnosis: DiagnosticEnvelope | None = None

    def public_summary(self) -> dict[str, str | bool]:
        """Allowlisted metadata only; this is not a detailed experimental log."""
        return {
            "release_scope": "partial_inspection_source",
            "eea_checked": self.initial is not None,
            "trigger": self.initial.trigger.value if self.initial else Trigger.NONE.value,
            "pta_status": self.initial.pta.status.value if self.initial else PTAStatus.NOT_RUN.value,
            "pta_reason": self.initial.pta.reason.value if self.initial and self.initial.pta.reason else "",
            "diagnostic_kind": self.diagnosis.kind.value if self.diagnosis else "",
            "revision_attempted": self.revision_attempted,
            "revision_available": self.revision is not None,
            "revision_accepted": self.reassessment is not None and not self.fell_back,
            "fell_back": self.fell_back,
        }
