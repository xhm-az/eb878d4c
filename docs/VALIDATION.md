# Validation status

Validation date: 2026-10-26. Scope: public reference layer, not the undistributed experimental system.

## Executed model-free checks

| Check | Observed result | Scope |
| --- | --- | --- |
| `python -B tools/run_contract_tests.py` | 96 tests passed; no failures, errors or skips | Evidence/control/diagnostic contracts, causal scoring arithmetic, prepared-condition checks, scoring-bridge integration, privacy/schema checks and accidental-use guards |
| `python -B examples/control_flow_demo.py` | All five synthetic scenarios completed | Actual public control functions with explicitly scripted providers |
| `python -B examples/scoring_demo.py` | Completed; public arithmetic executed and reached controller repair | Artificial logits and explicitly scripted risk decisions, with no model forward |
| `python -B tools/check_release.py` | Passed | Syntax/AST, local references, release allowlist, settings schema, encoding and basic sensitive-content patterns |

Test counts are executed unittest cases, not benchmark measurements or a count of independent experimental trials. Some cases contain additional subchecks. No performance timing or method-success metric is claimed.

The test runner disables bytecode generation, rejects model-library imports and blocks socket networking. It rejects empty runs, skipped cases and expected failures rather than presenting them as completed validation. It imports and executes only the public Python layer and standard-library/symbolic or numerical fixtures. The guard is not a security sandbox for hostile code.

## Interpretation

The observed results establish that the listed public contracts and scoring arithmetic work for the supplied synthetic cases. Numerical checks include causal shifting, masking, variable prefix lengths, padding, nonfinite inputs and action-token identity. A preset target-risk category tests routing, not PTA prediction quality. The recording environment checks submission order, not a task outcome. No passing test certifies that a real action is safe, relevant or successful.

Reassessment tests exercise the actual controller with an adapter whose supplied facts change during revision. The local evidence session preserves the initial snapshot, including copied argument containers, while a later process call obtains fresh evidence. Scoring-bridge regressions ensure an invalid comparison prevents the private policy from receiving a partial score set, and that condition-specific artificial logits affect only their corresponding score.

Static release checks do not inspect Git history or remote hosting and are not a universal confidentiality audit. The source package and archive are checked for equality and normalized ZIP metadata before delivery.

## Not performed

- Package installation, build execution or dependency resolution.
- Model load/download, tokenizer/chat-template integration, actual-model teacher-forced forwards or real model generation.
- Real environment deployment, benchmark interaction, real evaluators or baseline reproduction.
- Validation of the private contrast constructor and risk policy, actual model masks/logits, complete environment rules, fact extraction or precise prompt templates.
- Parameter selection, task success, inference cost or statistical significance measurement.
- Venue-specific artifact acceptance, hosting-anonymity or license certification.

The public reference layer is not a snapshot or verification of the server experiment code. No private implementation or paper source was modified as part of this release.

The full source code will be released upon acceptance of the paper.
