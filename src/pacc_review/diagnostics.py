from __future__ import annotations

from .types import (Assessment, Candidate, Context, DiagnosticEnvelope,
                    DiagnosticKind, Trigger)


def build_diagnostic(context: Context, candidate: Candidate, assessment: Assessment,
                     *, structured: bool) -> DiagnosticEnvelope:
    """Select permitted repair information without exposing private PTA internals.

    EEA counterevidence has priority. The target-risk path receives the original
    action and task goal only; a categorical kind indicates why repair is needed.
    Exact prompt wording and model-side serialization remain undistributed.
    """
    if assessment.trigger is Trigger.NONE:
        raise ValueError("A non-flagged candidate does not require diagnostic repair")
    if not structured:
        return DiagnosticEnvelope(DiagnosticKind.GENERIC_RETRY, candidate.action, None, False, ())
    if assessment.trigger is Trigger.EEA:
        return DiagnosticEnvelope(DiagnosticKind.EVIDENCE, candidate.action, None,
                                  assessment.eea.syntax_error, assessment.eea.contradictions)
    return DiagnosticEnvelope(DiagnosticKind.TARGET, candidate.action, context.goal, False, ())
