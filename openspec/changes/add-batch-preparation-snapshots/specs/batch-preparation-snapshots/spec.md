## Purpose

Prepare multiple saved repair sources as a reproducible, bounded batch with integrity checks, complete quality accounting and immutable local snapshots, retaining unknown labels and incomplete feature vectors for the later attribution and dataset stages.

## ADDED Requirements

### Requirement: Validated batch and source provenance
The batch SHALL require a versioned nonempty manifest, repository namespace, target branch, full immutable source_ref, aware cutoff and a source ledger bound by SHA-256. Referenced sources MUST remain within the manifest directory, have successful retrieval metadata, exact byte counts and hashes, and aware retrieval times. Input/resource bounds and malformed manifests MUST fail explicitly.

#### Scenario: Valid saved sources
- **WHEN** a valid manifest references matching saved patch, Jira and integration evidence files
- **THEN** the batch preserves the manifest/ledger hashes and each used source's URL, hash, bytes and retrieval time

#### Scenario: Altered source
- **WHEN** one referenced source has different bytes or hash than its ledger
- **THEN** its input retains a source_error diagnosis and is not treated as a parsed repair; unaffected inputs remain accounted for

#### Scenario: Unsafe or invalid manifest
- **WHEN** source paths escape the manifest directory, the ledger hash mismatches, IDs duplicate, source_ref is mutable, or bounds/schema fail
- **THEN** the batch rejects the manifest and emits no success snapshot

### Requirement: Complete per-input and duplicate accounting
The batch SHALL preserve a terminal outcome for every submitted input, reuse the existing historical candidate rules, retain explicit parse/source failures, and exclude integration assertions for a different target branch. It MUST count identical repair/issue inputs once and link duplicates to the retained record; contradictory duplicate reports MUST reject the batch. Different cherry-pick SHAs MUST remain distinct records rather than inferred deduplication.

#### Scenario: Valid and malformed inputs together
- **WHEN** one supported patch and one ledger-verified unsupported patch are submitted
- **THEN** a candidate/unknown outcome and a parse_error outcome are both retained, with exact submitted/unique/failed totals

#### Scenario: Exact duplicate
- **WHEN** two distinct input IDs produce identical reports for the same repair SHA and issue
- **THEN** one repair record is retained and the second input identifies its duplicateOf relationship

#### Scenario: Conflicting duplicate
- **WHEN** the same repair SHA and issue produce differing integration or source reports
- **THEN** the batch fails explicitly instead of choosing a convenient report

#### Scenario: Other branch backport
- **WHEN** the integration assertion concerns a branch different from the batch target
- **THEN** the distinct backport record retains its origin SHAs and is excluded from target-branch candidates

### Requirement: Auditable quality summary
The batch SHALL report input, duplicate, unique, parsed, failed, candidate, excluded and unknown counts, per-reason counts and raw all-path diff totals over unique parsed records. Accounting MUST reconcile every submitted input. A preparation snapshot MUST explicitly remain not_training_ready with unknown inducing labels and unset Kamei14 vectors.

#### Scenario: Mixed candidate and insufficient evidence
- **WHEN** AMQ-9481 has explicit mainline integration evidence and AMQ-9330 lacks that evidence
- **THEN** the summary contains one candidate and one unknown, while both inducing labels remain unset

#### Scenario: Partial preparation
- **WHEN** any input fails source or patch validation
- **THEN** preparation status is prepared_with_errors, failed inputs remain visible, and training readiness is false

### Requirement: Immutable atomic preparation snapshots
The system SHALL derive a stable snapshot ID from canonical batch content, publish a complete local file without overwriting an existing ID, and verify both content identity and file bytes when reading or reusing it. Failed publication MUST leave no completed partial file and no temporary residue. A local CLI SHALL prepare a manifest or verify an existing snapshot without changing sources.

#### Scenario: Same batch replay
- **WHEN** identical manifest bytes and source evidence are processed twice
- **THEN** the snapshot ID and content match, the existing valid file is reused without modification, and verification succeeds

#### Scenario: Corrupted existing snapshot
- **WHEN** the file for the derived ID has been altered
- **THEN** reuse and verification fail without replacing the corrupted file

#### Scenario: Interrupted publication
- **WHEN** publication fails before the final file becomes visible
- **THEN** no completed snapshot is exposed and temporary files are cleaned up

#### Scenario: Changed cutoff
- **WHEN** the same sources are processed at a different cutoff
- **THEN** a separate snapshot records the new assessment and preserves the previous snapshot
