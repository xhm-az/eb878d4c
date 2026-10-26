# Executable Partial Review Source

 [Reviewer guide](docs/REVIEW_GUIDE.md) · [Method map](docs/METHOD_MAP.md) · [Disclosure](DISCLOSURE.md)

This is a **partial source release** of the PACC reference control layer. The public controller, evidence comparator, diagnostic information-selection policy and fixed-action scoring foundation can be inspected and exercised without a model. This is not a snapshot of the undistributed experimental system.

**The full source code will be released upon acceptance of the paper.**

## Quick start: no model and no installation

From the extracted repository root, using Python with standard-library support:

```bash
python -B tools/run_contract_tests.py
python -B examples/control_flow_demo.py
python -B examples/scoring_demo.py
python -B tools/check_release.py
```

The commands run the public contracts, synthetic control demo, synthetic scoring-to-controller demo, and static release checks. No dependency installation, checkpoint, network service or benchmark deployment is needed.

**Executed validation:** 96 model-free contract tests passed; all five control-demo scenarios and the scoring-integration demo completed. No models or benchmark experiments have been run. See [validation scope](docs/VALIDATION.md).

The supplied entry points reject model-runtime imports and socket networking. This is an accidental-use guard for trusted local checks, not a sandbox for untrusted code.

## What the demo shows

| Scenario | Observed control behavior |
| --- | --- |
| Direct submission | The original candidate is submitted without revision |
| EEA-triggered revision | Interface counterevidence selects an evidence diagnostic; an accepted revision is submitted |
| PTA-triggered revision | A preset categorical risk selects a target diagnostic; re-evaluation is performed |
| Failed revision | The original candidate is restored |
| PTA abstention | No target-risk revision is requested |

The demo calls the actual public controller, comparator, diagnostic builder and final-action hook. Its adapter, planner and target evaluator are explicitly named test doubles. Their symbolic actions and preset PTA states are **not benchmark data, model outputs or measurements of PTA effectiveness**. Environment names in fixture contexts select controller branches only.

## Inspectable design

- **Open-world evidence comparison:** unknown evidence is not counterevidence; contradictory direct facts remain unknown; disjunction is three-valued.
- **Same-state reassessment:** the initial check and local revision share a copied, frozen public evidence snapshot. A later submission decision obtains a fresh snapshot; syntax rejection alone does not request one.
- **Fixed-action scoring foundation:** causal target alignment, action-only means, padding/stop checks, identical action tokens and prepared-condition consistency. A public bridge executes this arithmetic before an external private risk policy.
- **Prioritized risk routing:** EEA failure skips PTA; non-flagged and abstained states remain distinct.
- **Diagnostic information selection:** an evidence envelope includes only contradicted conditions or a syntax issue; a target envelope carries the original action and original goal; generic retry omits structured details.
- **Bounded repair:** request a local revision, recheck it and restore the original on failed re-evaluation.
- **Information boundary:** diagnostic envelopes have no internal-score, alternative-goal or numerical-parameter fields. Public summaries contain status metadata only.

These operations have executable tests. The [scoring foundation](docs/SCORING.md) is actual arithmetic over supplied logits, not a constant-score replacement. Tests also verify that a failed comparison invalidates the entire scoring batch before the private policy runs. Task-specific comparison construction, support-comparison/risk policy, exact prompts and model-side serialization remain private.

## Source navigation

| File | Purpose |
| --- | --- |
| `src/pacc_review/controller.py` | Submission, short-circuiting, revision and fallback |
| `src/pacc_review/evidence.py` | Three-valued condition comparison and decision-local evidence sessions |
| `src/pacc_review/diagnostics.py` | Diagnostic information-selection policy |
| `src/pacc_review/conditions.py` | Prepared-condition identity and consistency |
| `src/pacc_review/scoring.py` | Causal action-token likelihood arithmetic |
| `src/pacc_review/scoring_evaluator.py` | Scoring bridge usable by the controller |
| `src/pacc_review/types.py` | Typed assessment and diagnostic boundaries |
| `src/pacc_review/ports.py` | Contracts for undistributed components |
| `tests/` | Model-free contracts and privacy-boundary checks |
| `examples/control_flow_demo.py` | Independently runnable synthetic control demo |
| `examples/scoring_demo.py` | Actual public scoring arithmetic with scripted risk decisions |

## Public/private boundary

| Included | Retained privately during review |
| --- | --- |
| Tested control, diagnostic-envelope logic and causal scoring foundation | Task-specific comparison construction, support-comparison/risk-decision policy |
| Generic evidence comparison and symbolic fixture adapter | Complete environment grammars, rule libraries and fact extraction |
| Typed model/planner boundaries | Model backend, exact prompts and full baseline implementations |
| Mode-selection schema | Core settings, selected values, tuning ranges and experimental protocols |

No real task records, trajectories, measured benchmark results, model weights or numerical core settings are included. Symbolic and artificial numerical fixtures are provided solely for tests and demonstration; they are not actual model outputs or selected parameter values. Literal counters, software versions and structural constants are not experimental parameters.

The public package is named `pacc_review`. Real integration follows [INTEGRATION.md](docs/INTEGRATION.md) and needs the undistributed components. An absent core evaluator raises `PrivateComponentRequired`; it is never silently replaced by the demo fixture.

The scoring demo calls the public likelihood calculation and bridge before entering the controller's repair path. Its logits are artificial and its risk decisions are prescribed, so it does not validate real PTA detection. The tests establish behavior of the public layer under supplied symbolic/numerical fixtures. They do not establish correctness of the undistributed PTA, real-environment rules, actual-model scoring or reported paper results. The release is not sufficient for independent benchmark reproduction. Full scope, hosting anonymity and authorization notes are in [DISCLOSURE.md](DISCLOSURE.md).
