## Why

The existing CSV spike separates commits chronologically but can still learn a label revealed after its training cutoff. Current product drafts explicitly require label availability and mature observed negatives, so this temporal contract needs a testable implementation before real data training.

## What Changes

- Research verification latency and distinguish retrospective from continuous evaluation findings.
- Add a bounded offline auditor binding exact feature CSV bytes to a versioned per-row temporal contract, fixed training/evaluation cutoffs, and explicit clean maturity.
- Preserve every row decision and exclude future labels/features, missing evidence, unknowns and immature clean evidence without moving the cutoff or inventing labels.
- Add an audited training entrypoint; **BREAKING**: ordinary non-demo CSV training without a temporal contract is refused, even when sample-count thresholds are met. Existing synthetic demo behavior remains available with unchecked-label metadata.
- Save a clearly synthetic audit example and immutable audit snapshot; real SZZ labels and upstream timestamp truth remain unverified.

## Capabilities

### New Capabilities

- `temporal-label-audit`: Reproducible timestamp/evidence eligibility checks and fixed cohort selection.
- `audited-baseline-training`: Training only selected temporal cohorts and refusing unchecked non-demo training.

### Modified Capabilities

None in the main spec store (currently empty). Existing product draft requirements are not marked approved or complete.

## Impact

Adds a standard-library audit module, CLI, tests and research/evidence documents. Refactors the existing learning module to share fitting with an audited entrypoint. No database migration, UI change, Git, attribution, source collection or real model-effect claim.
