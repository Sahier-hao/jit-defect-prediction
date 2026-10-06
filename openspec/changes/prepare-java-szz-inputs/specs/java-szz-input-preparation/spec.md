## Purpose

Prepare reproducible Java old-line inputs for future SZZ attribution while retaining source evidence, exclusions, policy versions, and unknown training labels.

## ADDED Requirements

### Requirement: Verified repair input
The preparer SHALL recompute an existing batch from its manifest and compare it to its immutable snapshot before selecting one qualified candidate. It MUST reject other records, changed sources, mismatched snapshots, unsafe paths, and malformed manifests without publishing partial targets.

#### Scenario: Changed historical input
- **WHEN** a ledger, source file, or candidate snapshot no longer matches the saved batch
- **THEN** preparation fails and publishes no derived snapshot

#### Scenario: Unqualified repair
- **WHEN** the selected record has unknown integration or another non-candidate status
- **THEN** preparation fails without treating it as a clean or buggy commit

### Requirement: Complete file evidence
The preparer SHALL require parent and fixed files for each eligible production file with removed lines, verify source hashes and exact repository/commit/path URLs, and reconstruct the fixed file from every hunk including context and terminal newlines. The asserted parent relationship MUST remain explicitly unverified by ancestry analysis.

#### Scenario: Wrong file version
- **WHEN** a URL identifies a different commit or path, or reconstructed contents differ
- **THEN** preparation fails without emitting partial old-line targets

### Requirement: Versioned Java line selection
The preparer SHALL retain raw diff counts and every removed line with a reason. The initial policy MUST select only Java files under src/main/java, exclude src/test paths, and classify removed lines using whole-parent lexical context. It MUST preserve comment delimiters inside literals and text blocks and refuse unsupported Unicode escape preprocessing, lone CR, or unterminated lexical constructs.

#### Scenario: ActiveMQ repair
- **WHEN** the saved AMQ-9481 candidate and independent file snapshots are prepared
- **THEN** production old lines 118 and 121 become targets, lines 119 and 120 are excluded as comments, and all four test deletions are excluded by file policy

#### Scenario: Comment starts outside the hunk
- **WHEN** a removed line lies inside a block comment beginning earlier in the full parent file
- **THEN** it is excluded even when the removed line has no comment prefix

#### Scenario: Unsupported lexical translation
- **WHEN** the source contains a Java Unicode escape or an unfinished comment or literal
- **THEN** preparation fails explicitly rather than guessing target line numbers

### Requirement: Reviewable immutable output
The preparer SHALL publish content-addressed, no-replace snapshots with policy versions, parent/fix identities, source evidence, line decisions, and reconciled counts. It MUST keep inducingLabel and kamei14 null and trainingReady false, including when no eligible target exists. The CLI SHALL return exit code 2 and an empty stdout on invalid input.

#### Scenario: Deterministic replay
- **WHEN** unchanged saved evidence is prepared twice
- **THEN** the same snapshot is reused without changing its bytes or modification time

#### Scenario: No eligible old lines
- **WHEN** every removed line is excluded by the documented policy
- **THEN** the output records zero targets and the exclusion reasons with no training label
