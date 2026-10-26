"""Executable synthetic routing demo, not PACC benchmark performance."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from examples.final_action_hook import submit_selected_action
from examples.synthetic_support import (RecordingEnvironment, ScriptedPlanner,
                                         ScriptedTargetEvaluator, SymbolicAdapter,
                                         candidate, context, enabled_fact, revision)
from pacc_review import PACCController, PACCSettings, Variant
from pacc_review.types import PTAResult, PTAStatus, Reason
from tools.model_free_guard import model_free_boundary


def run_scenarios() -> tuple[dict, ...]:
    not_flagged = PTAResult(PTAStatus.NOT_FLAGGED, None)
    flagged = PTAResult(PTAStatus.FLAGGED, None)
    abstained = PTAResult(PTAStatus.ABSTAINED, Reason.UNSUPPORTED_INPUT)
    cases = (
        ("direct_submission", (enabled_fact("candidate", True),), (not_flagged,), ()),
        ("eea_revision_accepted", (enabled_fact("candidate", False), enabled_fact("revision", True)),
         (not_flagged,), (revision(),)),
        ("pta_revision_accepted", (enabled_fact("candidate", True), enabled_fact("revision", True)),
         (flagged, not_flagged), (revision(),)),
        ("revision_fallback", (enabled_fact("candidate", False), enabled_fact("revision", False)),
         (), (revision(),)),
        ("pta_abstention", (enabled_fact("candidate", True),), (abstained,), ()),
    )
    outputs = []
    for name, facts, target_replies, planner_replies in cases:
        current, selected, events = context(), candidate(), []
        evaluator = ScriptedTargetEvaluator(target_replies, events=events)
        planner = ScriptedPlanner(planner_replies, events=events)
        adapter = SymbolicAdapter(current.environment, facts, events=events)
        environment = RecordingEnvironment(events)
        controller = PACCController(PACCSettings(Variant.PACC), target_evaluator=evaluator)
        decision, _ = submit_selected_action(context=current, selected=selected,
                                             controller=controller, planner=planner,
                                             adapter=adapter, environment=environment)
        outputs.append({"kind": "synthetic_control_flow_only", "case": name,
                        "submitted": "original" if decision.submitted is selected else "revision",
                        "summary": decision.public_summary(), "events": events,
                        "environment_submission_count": len(environment.submissions)})
    return tuple(outputs)


def main() -> int:
    with model_free_boundary():
        for result in run_scenarios():
            print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
