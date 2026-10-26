# Integration contract

## Public inputs

`Context` contains the task goal, current public observation, executed history, base instructions and declared public scope. It has no reward, success or hidden-simulator fields. Caller-supplied text and provenance are not independently authenticated.

`Candidate` identifies an already selected atomic action and declared model/tokenizer/base-prompt provenance. Original generation, the invoked evaluator and the reviser must agree on that declaration. Identity strings alone do not establish actual model sharing or freezing.

## Private provider implementations

The protocols in [ports.py](../src/pacc_review/ports.py) require external implementations:

- `Adapter`: actual atomic grammar, fixed preconditions and scope-aware public fact consolidation.
- `TargetEvaluator`: a private PTA implementation or the public scoring bridge with private preparation and risk-policy providers; returns a categorical outcome.
- `Planner`: actual local revision using the public `DiagnosticEnvelope`, with private prompt text and model-side serialization.

The public builder selects permitted diagnostic information before the planner is called. The planner receives an envelope, not an unrestricted assessment object. Exact prompt templates are not supplied.

Each enabled controller process call creates a decision-local evidence session. It lazily captures and copies the adapter's public facts once, then reuses them for the revised action without advancing the environment. A new process call creates a new session. Parsing and precondition retrieval must still be pure with respect to the given context and fixed rules; the session does not make an incorrect or oracle-using provider trustworthy.

Missing private evaluation code raises `PrivateComponentRequired`. An invoked evaluator must assess or explicitly abstain, never return `not_run`. `AssessmentUnavailable` represents a data-dependent inability to evaluate, not missing implementation or a programming error. No demo provider is automatically substituted.

## Prepared scoring bridge

[ScoringTargetEvaluator](../src/pacc_review/scoring_evaluator.py) accepts a private prepared-input provider and private risk policy. It invokes the public [condition checks and causal likelihood arithmetic](SCORING.md) before consulting that policy. The private provider supplies genuine model logits, tokenization and masks in actual use; the public code neither loads a model nor constructs goal contrasts. Invalid numerical/condition inputs become assessment unavailability; missing components and programming errors remain distinct.

The prepared-input path uses ordinary Python sequences. Actual tokenizer IDs, special markers, exact serialization and accelerated backend details are private. The public helper does not prove the supplied token sequence decodes to the action text or that comparisons preserve other requirements.

## Public modes and private parameters

[PACCSettings](../src/pacc_review/config.py) and the [schema](../configs/settings.schema.json) expose mode selection only. Core settings, selected values, decoding policies, task lists, trial budgets and seeds stay in private providers. No benchmark runner or parameter-selection recipe is distributed.

## Final-action boundary

Call [final_action_hook.py](../examples/final_action_hook.py) only after the external planner selects its final action. ReAct reasoning, Reflexion memory and RAP search stay outside the controller. The actual environment wrapper must convert the submitted text dialect when necessary.

The public controller performs no environment operation and does not hardcode a target-assessment environment allowlist. The private evaluator owns applicability and abstention under the current manuscript's scope. WebArena-Lite does not denote Lite-v2. No complete grammar or real task subset is bundled.

## Model-free inspection path

The examples use [explicit synthetic test doubles](../examples/synthetic_support.py) so that reviewers can execute the public layer without private components. The fixture adapter has its own symbolic dialect, not a benchmark grammar. The control fixture supplies prescribed categories. The scoring fixture supplies artificial logits to the actual public arithmetic and prescribes risk outcomes separately. Neither produces real model or benchmark results. Do not use these doubles to report PACC performance.

The supplied runner and demo use an [accidental-use guard](../tools/model_free_guard.py) against model-runtime imports and socket networking. It is not a security sandbox. Use [REVIEW_GUIDE.md](REVIEW_GUIDE.md) to interpret what each check covers.

## Runtime privacy and later release

Full contexts, evidence and diagnostic envelopes can contain sensitive text; actual logits and likelihood records can also contain private numerical information. There is no automatic full-object logger. Public summaries select status metadata only; private logging/redaction remains an external responsibility.

The full source code will be released upon acceptance of the paper. This future commitment does not change current reproduction limits.
