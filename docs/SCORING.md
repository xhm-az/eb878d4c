# Public fixed-action scoring foundation

This release includes actual action-likelihood arithmetic and a controller-compatible bridge. It does not include a model, task-goal contrast builder or complete PTA risk policy.

## Executable components

- [conditions.py](../src/pacc_review/conditions.py) checks supplied condition order, unique identifiers/goals, unchanged action text, common declared provenance and a common public-context identity.
- [scoring.py](../src/pacc_review/scoring.py) computes stable causal action-token mean log probabilities from supplied logits and masks. It checks identical action token sequences across conditions.
- [scoring_evaluator.py](../src/pacc_review/scoring_evaluator.py) connects private input preparation, the public arithmetic and a private decision policy through the existing evaluator interface.

The arithmetic uses the predictor immediately before each target token, normalizes the selected vocabulary logits, and averages over action targets only. Unselected prompt, padding and suffix positions do not contribute. Stop/special token identifiers must be supplied by the private backend and cannot be selected as action targets. There are no tokenizer-specific identifiers or numerical core settings in the public implementation.

Each attended region and action-target region must be contiguous. Left/right padding is supported when every selected target has an attended causal predecessor. Goal-dependent prefix lengths can differ, but action token identities must match exactly, not merely in count. A failed condition invalidates the supplied batch; the helper does not average a selectively successful subset.

The reference accepts ordinary Python nested sequences, not device tensors, and makes no throughput claim. The undistributed backend is responsible for obtaining genuine logits and correct masks from the actual frozen model.

## What remains private

Task-specific eligibility, requirement localization, contrast generation/validation, exact prompt serialization, actual model forward calls, score-comparison/decision rules and settings remain undistributed. The public arithmetic does not calculate a combined support difference, choose comparisons or implement a risk threshold.

Condition identity checks do not prove that supplied goals preserve all other task requirements. A semantic context hash does not prove that the actual serialized model inputs match. Matching token IDs does not prove they decode to the supplied action text: the private tokenizer/backend must establish that link. Actual special-token identities and any repeated goal text inside a prompt are also backend responsibilities.

## Scoring bridge

The private provider supplies a prepared batch or explicitly abstains. It cannot bypass scoring by returning a non-flagged/flagged decision. After public scoring, the private risk policy receives the computed condition likelihoods and returns a categorical assessment. Invalid prepared inputs become assessment unavailability, which the controller records as abstention. Programming errors are not silently treated as successful evaluation.

The controller can accept this bridge as its evaluator; integration tests and the scoring demo exercise this path. No statement is made that the undistributed experimental system already uses this exact reference helper.

## Model-free check

```bash
python -B tools/run_contract_tests.py
python -B examples/scoring_demo.py
```

[Arithmetic and integration tests](../tests/test_scoring.py) use tiny artificial matrices, symbolic goals and a scripted policy. The new demo executes the real public scorer through the controller and prints only categorical checks. It is labelled `synthetic_scoring_integration_only`; risk decisions are expressly scripted. It neither loads a model nor validates real PTA detection quality or task success.

Real supplied logits, condition text and returned numerical likelihoods can be sensitive at runtime. No automatic file logger or public score export is provided. Diagnostic envelopes and the existing public decision summary do not include these numerical results.
