## Purpose

Fit the existing baseline only on cohorts selected by a bound temporal audit while preserving clearly labelled synthetic demonstrations and refusing unchecked ordinary CSV training.

## ADDED Requirements

### Requirement: Refuse unchecked non-demo fitting
The ordinary CSV training entrypoint SHALL reject non-demo fitting without a temporal contract even when count and class thresholds are met. The API MUST propagate the refusal without registering a model. Synthetic demos MUST identify that label-time eligibility was not checked.

#### Scenario: Large unchecked import
- **WHEN** a non-demo CSV meets existing sample thresholds but has no temporal contract
- **THEN** training fails with an explicit contract requirement and no model artifact or registration

### Requirement: Fit audited cohorts only
The audited entrypoint SHALL revalidate bound CSV/contract bytes and use only selected training rows for classifier/scaler fitting and only selected test rows for evaluation. Predictions MUST exclude rejected rows. Existing minimum sample and training class checks SHALL apply after temporal filtering, and an empty test cohort MUST fail.

#### Scenario: Late label with extreme features
- **WHEN** a pre-cutoff row has extreme features but a label available after the training cutoff
- **THEN** it does not influence the scaler, classifier, metrics or emitted predictions

#### Scenario: Filtering empties the holdout
- **WHEN** temporal exclusions remove every test row
- **THEN** fitting fails without inventing evaluation metrics

### Requirement: Audit metadata
The fitted baseline SHALL retain fixed cutoffs, audit policy and input hashes, per-row selection report and class/exclusion counts. It MUST distinguish checks against supplied timestamps from independent verification of upstream feature/SZZ provenance.

#### Scenario: Reproducible audit trail
- **WHEN** a temporally audited model is returned
- **THEN** its metadata identifies the exact contract and CSV hashes and reports caller-supplied source verification status
