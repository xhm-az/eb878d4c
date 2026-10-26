"""Real public scoring arithmetic, artificial logits and prescribed risk decisions."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from examples.final_action_hook import submit_selected_action
from examples.scoring_support import ScriptedRiskPolicy, SymbolicPreparedProvider
from examples.synthetic_support import RecordingEnvironment, ScriptedPlanner, SymbolicAdapter, candidate, context, revision
from pacc_review import PACCController, PACCSettings, Variant
from pacc_review.scoring_evaluator import ScoringTargetEvaluator
from pacc_review.types import PTAResult, PTAStatus
from tools.model_free_guard import model_free_boundary


def run_scoring_demo() -> dict:
    current, selected, events = context(), candidate(), []
    provider = SymbolicPreparedProvider()
    policy = ScriptedRiskPolicy((PTAResult(PTAStatus.FLAGGED, None), PTAResult(PTAStatus.NOT_FLAGGED, None)))
    evaluator = ScoringTargetEvaluator(selected.provenance, provider, policy)
    controller = PACCController(PACCSettings(Variant.PACC), target_evaluator=evaluator)
    planner = ScriptedPlanner((revision(),), events=events)
    adapter = SymbolicAdapter(current.environment, (), events=events)
    environment = RecordingEnvironment(events)
    decision, _ = submit_selected_action(context=current, selected=selected, controller=controller,
                                         planner=planner, adapter=adapter, environment=environment)
    valid = all(math.isfinite(s.likelihood.mean_log_probability)
                for batch in policy.received_scores for s in batch)
    return {"kind": "synthetic_scoring_integration_only", "scoring_arithmetic_executed": bool(policy.received_scores),
            "finite_action_means": valid, "risk_decisions": "explicitly_scripted_fixture",
            "submitted": "original" if decision.submitted is selected else "revision",
            "summary": decision.public_summary(), "environment_submission_count": len(environment.submissions)}


def main() -> int:
    with model_free_boundary():
        print(json.dumps(run_scoring_demo(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
