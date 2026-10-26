"""Final-action hook; real planner generation and environment stay external."""
from __future__ import annotations

from typing import Protocol

from pacc_review import Candidate, Context, PACCController
from pacc_review.ports import Adapter, Planner


class TextActionEnvironment(Protocol):
    def step(self, action: str) -> object: ...


def submit_selected_action(*, context: Context, selected: Candidate,
                           controller: PACCController, planner: Planner,
                           adapter: Adapter, environment: TextActionEnvironment):
    """Call after ReAct/Reflexion generation or RAP final search selection.

    This hook does not perform original generation, reflection, search or action
    format conversion. Environment execution and resulting evaluation stay outside
    the controller. Real environments require their private adapter/wrapper.
    """
    decision = controller.process(context, selected, planner, adapter)
    return decision, environment.step(decision.submitted.action)
