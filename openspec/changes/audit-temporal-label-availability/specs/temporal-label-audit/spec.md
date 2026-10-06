## Purpose

Audit historical feature and label eligibility using explicit cutoffs and observation maturity, with reproducible per-row decisions instead of assuming commit order proves label availability.

## ADDED Requirements

### Requirement: Exact input binding
The auditor SHALL bind a versioned JSON contract to the SHA-256 of exact CSV bytes, require exactly one temporal row per CSV commit, and reject duplicate fields/IDs, unknown fields, mismatched labels, malformed timestamps, invalid limits and inconsistent chronology before publishing output.

#### Scenario: Changed feature data
- **WHEN** the CSV bytes differ from the contract hash
- **THEN** the audit fails without publishing a partial snapshot

#### Scenario: Incomplete temporal coverage
- **WHEN** temporal rows are missing, extra or duplicated
- **THEN** the audit fails rather than dropping unmatched commits silently

### Requirement: Fixed temporal cohorts
The auditor SHALL select training commits strictly before trainCutoff and test commits in [trainCutoff, evaluationCutoff). Availability of training labels MUST be checked at trainCutoff, and test labels at evaluationCutoff, using inclusive as-of comparisons. Filtering MUST NOT move either cutoff or split equal timestamps between cohorts.

#### Scenario: Training positive revealed later
- **WHEN** a training commit's positive label becomes available after trainCutoff
- **THEN** it is excluded from training with a late-label reason, even when evaluationCutoff is later

#### Scenario: Same-time boundary
- **WHEN** several commits have timestamps exactly equal to trainCutoff
- **THEN** all are assigned to the test cohort

### Requirement: Evidence and maturity decisions
The auditor SHALL preserve unknown labels and exclude missing historical feature cutoffs, mismatched feature cutoffs, missing label evidence, late labels, and premature clean evidence with explicit reasons. Observed clean evidence MUST be available no earlier than commit time plus the explicitly supplied positive maturityDays parameter. Evidence references and timestamps MUST remain identified as caller assertions requiring source review.

#### Scenario: Clean label has insufficient observation
- **WHEN** the claimed clean label predates the configured maturity time
- **THEN** it is excluded rather than assumed mature because it is currently labelled zero

#### Scenario: Historical feature declaration
- **WHEN** featureAsOf differs from the CSV commit timestamp
- **THEN** the row is excluded from fitting, including future-information declarations

### Requirement: Immutable review report
The auditor SHALL report all row IDs, cohorts, decisions, selected IDs, class counts, source hashes, normalized configuration and policy version in an immutable canonical snapshot. Submitted MUST equal selected training plus selected test plus excluded. The snapshot MUST keep trainingReady false because source truth is not established by timestamp declarations. The CLI SHALL return 2 and empty stdout on failure.

#### Scenario: Replay
- **WHEN** unchanged CSV and contract bytes are audited twice
- **THEN** the same snapshot is reused without rewriting it
