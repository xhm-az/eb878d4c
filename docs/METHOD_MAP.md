# Manuscript-to-source map

This map covers the public subset and its tested behavior. Task-specific contrast construction, support-comparison/risk policy, complete environment rules and exact prompts remain undistributed; a generic causal scoring foundation is public. The full source code will be released upon acceptance of the paper.

## Evidence comparison

The adapter supplies fixed interface preconditions and a current public evidence snapshot. The comparator treats absent or contradictory direct evidence as unknown. A disjunction is supported when any child is supported, contradicted when all children are contradicted, and otherwise unknown.

For a submission decision, a lazy evidence session copies the first valid public snapshot and reuses it for the local reassessment. It is not retained across process calls. Syntax rejection does not fetch evidence; the first syntactically valid check does. This enforces a common evidence view without implementing the private fact-extraction or update policy.

Sources: [evidence.py](../src/pacc_review/evidence.py), [evidence tests](../tests/test_evidence.py).

Fact extraction, evidence age, permitted implications and priority rules belong to the private adapter. Scope equality does not prove semantic correctness of a snapshot.

## Risk routing

The selected candidate is evaluated before any submission. EEA failure skips PTA. Otherwise the supported evaluator can return a categorical target outcome. An explicit flag requests repair; abstention does not. No candidate generation, search or environment operation occurs inside assessment.

Sources: [controller.py](../src/pacc_review/controller.py), [controller tests](../tests/test_controller.py).

The private `TargetEvaluator` implements the manuscript's supported scope. This repository publishes the generic post-logit scoring arithmetic, but not task-specific contrast construction, the support-comparison/risk-decision policy or its parameters.

## Public scoring foundation

[scoring.py](../src/pacc_review/scoring.py) performs causal action-token log-likelihood arithmetic on supplied logits; [conditions.py](../src/pacc_review/conditions.py) checks consistency of the prepared conditions. [scoring_evaluator.py](../src/pacc_review/scoring_evaluator.py) can be passed to the existing controller, with private input preparation and decision-policy providers. These are executable components, not interface-only declarations.

Only selected action targets enter the mean. The same action token sequence must be scored across conditions, with each predictor at the preceding position. Prompt/padding/unselected suffix positions do not contribute; declared stop/special IDs cannot enter the action mask. Actual tokenization and semantic validity of the supplied goal contrasts remain private-backend responsibilities. See [scoring scope](SCORING.md) and [tests](../tests/test_scoring.py).

## Public diagnostic information-selection policy

[diagnostics.py](../src/pacc_review/diagnostics.py) implements a typed policy actually called by the controller:

| Trigger/mode | Envelope contents |
| --- | --- |
| Interface conflict or syntax error | Original action, syntax status, explicitly contradicted conditions and their evidence |
| Target-risk flag | Original action and original task goal |
| Retry without diagnosis | Original action and generic-retry type, without structured diagnostic details |

Evidence diagnosis has priority. Noncontradicted conditions are not included as conflicts. The envelope has no internal-score, alternative-goal or numerical-setting fields. It is not an exact prompt template; text rendering, model serialization and actual revision generation remain private.

Sources: [types.py](../src/pacc_review/types.py), [diagnostic tests](../tests/test_diagnostics.py).

## Revision and submission

The controller requests a bounded local revision and re-evaluates it. An unflagged revision, including PTA abstention, is selected; failed re-evaluation or revision unavailability restores the original. Programming and configuration errors are not converted into success. Final environment submission is outside the controller.

Sources: [final action hook](../examples/final_action_hook.py), [synthetic demo](../examples/control_flow_demo.py).

ReAct reasoning, Reflexion trial memory and RAP search remain external. These contracts do not reproduce their algorithms or establish real-environment performance.
