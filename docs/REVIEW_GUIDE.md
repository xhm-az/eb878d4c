# Reviewer inspection guide

The public subset can be run without models or external services. Its purpose is to check control/diagnostic contracts and fixed-action scoring arithmetic, not reproduce benchmark performance.

## Suggested order

From the repository root:

```bash
python -B tools/run_contract_tests.py
python -B examples/control_flow_demo.py
python -B examples/scoring_demo.py
python -B tools/check_release.py
```

The test and demo entry points reject model runtimes and socket networking. The source checker does not execute the algorithm. All supplied commands use the standard library; no package installation is required.

## Checks and source evidence

| Question | Implementation | Executable check |
| --- | --- | --- |
| Does missing evidence remain unknown? | [evidence.py](../src/pacc_review/evidence.py) | [Evidence contracts](../tests/test_evidence.py) |
| Are disjunction and conflicting facts handled consistently? | [evidence.py](../src/pacc_review/evidence.py) | Three-valued truth-table subchecks |
| Does local reassessment use the same evidence state without caching it across steps? | [Evidence session](../src/pacc_review/evidence.py), controller | Snapshot copy, mutation, lazy acquisition and cross-call freshness contracts |
| Does EEA take priority over target assessment? | [controller.py](../src/pacc_review/controller.py) | EEA short-circuit and private-applicability contracts |
| Does repair receive selected information, not internal PTA values? | [diagnostics.py](../src/pacc_review/diagnostics.py) | [Diagnostic contracts](../tests/test_diagnostics.py) |
| Is causal action-token scoring implemented correctly? | [scoring.py](../src/pacc_review/scoring.py) | [Scoring arithmetic contracts](../tests/test_scoring.py) |
| Are supplied conditions consistent and connected to control? | [Scoring bridge](../src/pacc_review/scoring_evaluator.py) | Condition and bridge integration contracts |
| Can one failed comparison be silently discarded? | [Scoring bridge](../src/pacc_review/scoring_evaluator.py) | Invalid comparison prevents any private-policy call |
| Is repair bounded and is fallback the original candidate? | [controller.py](../src/pacc_review/controller.py) | [Controller contracts](../tests/test_controller.py) |
| Is submission outside assessment and after final selection? | [Final-action hook](../examples/final_action_hook.py) | [Boundary contracts](../tests/test_public_contracts.py) |
| Are numerical settings and task text omitted from public metadata? | [types.py](../src/pacc_review/types.py), mode schema | Summary and schema contracts |

The stale-scope check validates the declared scope identity, and a decision-local session freezes that supplied view for reassessment. Neither proves completeness or accuracy of a real fact extractor. Likewise, matching provenance strings does not independently verify a backend's actual identity. Empty or skipped test runs are rejected by the supplied runner.

## Interpreting the demo

Each printed record is labelled `synthetic_control_flow_only`. Read `events` in order: parse, evidence snapshot, condition comparison, any preset target assessment, any diagnostic request, re-evaluation, then final symbolic submission. Re-evaluation parses and compares again but reuses the decision's snapshot. The public functions execute; the providers are explicit fixtures.

The direct-submission and abstention paths do not request repair. Evidence and target fixtures select different diagnostic envelopes. Failed re-evaluation restores the original candidate. The recording environment receives only the final selected action.

A scripted target flag is an input to this demonstration, not a successful prediction by private PTA. No toy result is evidence of task success, detector precision or benchmark improvement. The fixture dialect is symbolic and does not implement the real environment grammar.

## Scoring-integration demo

The separate scoring demo is labelled `synthetic_scoring_integration_only`. It runs the public likelihood kernel and scoring bridge inside the controller path, using artificial logits and a scripted risk policy. It prints categorical checks rather than raw likelihoods. The policy is not a public implementation of the private risk rule. Consult [SCORING.md](SCORING.md) for token-mask, input-consistency and backend limitations.

## Retained privately

Task-specific contrast construction, support-comparison/risk policy, the complete environment rule libraries, exact model prompts, backend integration, real settings and experimental material remain undistributed. They are neither validated nor recreated by these tests. The public envelope builder exposes information-selection policy; the scoring kernel exposes generic likelihood arithmetic only.

The code is a reference control layer, not a snapshot of the undistributed experiment code. Current scope and the acceptance-triggered full-source commitment are stated in [DISCLOSURE.md](../DISCLOSURE.md).
