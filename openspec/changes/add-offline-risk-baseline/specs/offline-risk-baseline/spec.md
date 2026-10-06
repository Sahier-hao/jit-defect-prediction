## Purpose

Provide a reproducible local workflow from imported commit features to a trained baseline and explainable risk review, while clearly distinguishing synthetic demonstration evidence from real project evaluation.

## ADDED Requirements

### Requirement: Validated feature dataset import
The system SHALL accept UTF-8 CSV with unique commit IDs, timezone-aware commit timestamps, labels of 0, 1, or unknown, and exactly the required Kamei feature columns. It MUST reject missing, nonfinite, negative, malformed, or duplicate records atomically. It SHALL retain a SHA-256 source hash, provenance, label policy, sample counts, and an explicit synthetic-data flag. Imports SHALL be limited to 5 MiB and 20,000 rows.

#### Scenario: Valid import
- **WHEN** a valid feature CSV is imported
- **THEN** the dataset and all records are persisted with stable identifiers and provenance

#### Scenario: Invalid file
- **WHEN** any record is invalid or an input limit is exceeded
- **THEN** a readable error is returned and no partial dataset is created

### Requirement: Strict temporal baseline training
The system SHALL exclude unknown labels from model fitting and evaluation, split eligible records chronologically using an outer 70/30 ratio, and keep equal-timestamp records on the same side. Preprocessing MUST fit only on training data. Non-synthetic datasets MUST contain at least 1,000 eligible commits and 50 positive labels; synthetic data SHALL be allowed at 20 eligible commits and SHALL remain visibly marked. Training MUST fail clearly if the training partition lacks either class. It SHALL persist feature order, training window, split timestamp, seed, parameters, dependency versions, dataset hash, and an immutable model artifact.

#### Scenario: Leakage prevention
- **WHEN** a model is trained
- **THEN** every training timestamp is earlier than every test timestamp and the preprocessing statistics are fitted on the training partition only

#### Scenario: Insufficient data
- **WHEN** eligibility or class requirements are not met
- **THEN** training returns a readable error without creating a ready model

### Requirement: Reproducible metric groups
The system SHALL report Precision, Recall, F1, ROC-AUC, Recall@20%Effort, and full-curve Popt with test counts and the fixed 0.5 classification threshold. ROC-AUC SHALL be null with an explanation for a one-class test set. Effort SHALL use max(1, LA+LD), descending probability-per-effort ordering with commit-ID tie breaks, and whole-commit prefix selection at the 20% budget. Popt SHALL compare trapezoidal cumulative-recall areas with oracle and worst density rankings; undefined normalized areas SHALL be null with an explanation. Saved per-commit test scores and labels SHALL permit recomputation.

#### Scenario: Undefined AUC
- **WHEN** the test partition contains only one class
- **THEN** the report contains null AUC and an explicit reason rather than a fabricated score

#### Scenario: Budget interpretation
- **WHEN** no complete commit fits the leading 20% effort prefix
- **THEN** the budgeted recall is zero and the method remains documented

### Requirement: Explainable versioned risk review
The system SHALL provide globally probability-ranked, server-paginated commits for a selected model and dataset, with probability, risk level, timestamp, commit ID, and training/holdout scope. Default results SHALL include only commits at or after the split timestamp. Commit detail SHALL show feature values and at least three exact logistic-regression contributions with direction, baseline, and method in log-odds units. Features SHALL be ordered identically for fitting and inference. Missing models, cross-dataset model use, missing commits, or corrupt artifacts MUST return readable errors without fabricated probabilities.

#### Scenario: Global pagination
- **WHEN** two pages are requested for the same filter
- **THEN** both pages follow one global order without duplicate records

#### Scenario: Restart
- **WHEN** the service restarts with the same storage directory
- **THEN** imported datasets, registered models, and their predictions remain available

### Requirement: Local review interface
The system SHALL offer a locally bundled responsive interface for loading an explicitly synthetic demo, importing CSV, selecting datasets and models, training the baseline, viewing both metric groups, filtering risks, and inspecting a commit. It MUST show progress, empty, failure, and synthetic-data states, preserve the displayed error until the user acts, and prevent stale results after dataset/model selection changes. No external CDN SHALL be required for the interface.

#### Scenario: New workspace
- **WHEN** no dataset exists
- **THEN** the interface offers CSV import and explicit demo loading instead of a blank table

#### Scenario: Selection change
- **WHEN** the selected dataset or model changes
- **THEN** the interface clears incompatible details and displays only results matching the current selection
