from __future__ import annotations

from .config import PACCSettings, Variant
from .diagnostics import build_diagnostic
from .evidence import EvidenceAuditSession, ExplicitEvidenceAudit
from .ports import (Adapter, AssessmentUnavailable, Planner,
                    PrivateComponentRequired, RevisionUnavailable, TargetEvaluator)
from .types import (Assessment, Candidate, Context, Decision,
                    PTAResult, PTAStatus, Reason, Trigger)


class PACCController:
    """Public bounded-control implementation, with explicit private dependencies."""

    def __init__(self, settings: PACCSettings, *,
                 target_evaluator: TargetEvaluator | None = None) -> None:
        self.settings = settings
        self.eea = ExplicitEvidenceAudit()
        self.target_evaluator = target_evaluator
        if settings.use_pta and target_evaluator is None:
            raise PrivateComponentRequired(
                "The PTA implementation and its configuration are not distributed "
                "during review; supply an external TargetEvaluator")

    def _evaluate(self, context: Context, candidate: Candidate, session: EvidenceAuditSession) -> Assessment:
        eea = session.evaluate(candidate)
        pta = PTAResult(PTAStatus.NOT_RUN, None)
        if eea.passed and self.settings.use_pta:
            # Applicability is owned by the private evaluator, not a stale public
            # environment allowlist. This does not expose any scope-selection rule.
            evaluator = self.target_evaluator
            if evaluator is None:
                raise PrivateComponentRequired("A private TargetEvaluator is required")
            if evaluator.provenance != candidate.provenance:
                raise ValueError("PTA and original generation provenance must agree")
            try:
                pta = evaluator.evaluate(context, candidate)
            except AssessmentUnavailable:
                pta = PTAResult(PTAStatus.ABSTAINED, Reason.ASSESSMENT_UNAVAILABLE)
            if not isinstance(pta, PTAResult):
                raise TypeError("The private evaluator must return a categorical PTAResult")
            if pta.status is PTAStatus.NOT_RUN:
                raise ValueError("An invoked evaluator must assess or explicitly abstain")
        return Assessment(eea, pta)

    def process(self, context: Context, candidate: Candidate,
                planner: Planner, adapter: Adapter) -> Decision:
        # Vanilla preserves the exact upstream object, even an invalid action.
        if self.settings.variant is Variant.VANILLA:
            return Decision(candidate, candidate, None, None, None, False, False)
        if candidate.provenance != planner.provenance:
            raise ValueError("Original generation and revision provenance must agree")
        # This session is local to one process call, never a cross-step cache.
        session = self.eea.session(context, adapter)
        initial = self._evaluate(context, candidate, session)
        if initial.trigger is Trigger.NONE:
            return Decision(candidate, candidate, initial, None, None, False, False)
        diagnosis = build_diagnostic(
            context, candidate, initial,
            structured=self.settings.variant is not Variant.RETRY_WITHOUT_DIAGNOSIS)
        try:
            revised = planner.revise_once(context, candidate, diagnosis)
        except RevisionUnavailable:
            return Decision(candidate, candidate, initial, None, None, True, True, diagnosis)
        if not isinstance(revised, Candidate):
            raise TypeError("A local revision must return one Candidate")
        if revised.provenance != candidate.provenance:
            raise ValueError("Revision changed model, tokenizer or prompt provenance")
        checked = self._evaluate(context, revised, session)
        fallback = checked.trigger is not Trigger.NONE
        return Decision(candidate, candidate if fallback else revised, initial,
                        revised, checked, True, fallback, diagnosis)
