## Purpose

Provide a bounded offline preparation step that turns saved text patches and complete Jira histories into traceable repair candidates and old-line evidence for later attribution, while preserving unknown inducing labels and incomplete feature vectors.

## ADDED Requirements

### Requirement: Strict text patch evidence
The module SHALL parse a single UTF-8 email-format text patch, associate issue keys only from the commit message, preserve cherry-pick references, and report all-path NF/LA/LD and removed parent-version lines. It MUST reject malformed hunks, unsafe paths, binary, rename/copy, and unsupported changes explicitly rather than publish partial counts.

#### Scenario: Real source patch
- **WHEN** the saved 72befc14 patch is prepared
- **THEN** issue association contains AMQ-9481 alone, all-path NF/LA/LD equals 2/17/8, and production removed old lines are 118 through 121 with their original text

#### Scenario: Inconsistent hunk
- **WHEN** a hunk's consumed old/new lines differ from its declared counts
- **THEN** preparation fails with a diagnostic and no candidate report

#### Scenario: Unsupported changes
- **WHEN** a patch contains binary changes, a rename/copy, unsafe paths or changes outside the supported text subset
- **THEN** preparation fails explicitly rather than treating the change as zero added/deleted lines

### Requirement: Historical issue state
The module SHALL reconstruct issue type, status and resolution at an aware cutoff using a complete, internally consistent Jira changelog. It MUST use qualifying state transitions as evidence time, preserve unknown when history is incomplete or the requested cutoff exceeds the saved snapshot time, and reject inconsistent histories.

#### Scenario: Historical type differs from current type
- **WHEN** AMQ-9461 is examined before its June 2024 type change
- **THEN** its type is Improvement rather than today's Task and it remains excluded from Bug-only repair candidates

#### Scenario: Before resolution
- **WHEN** AMQ-9481 is examined at 2024-04-22T00:00:00Z
- **THEN** its state is Bug / In Progress / unresolved and no verified repair candidate is emitted

#### Scenario: Missing history page
- **WHEN** changelog startAt is nonzero or history count differs from total
- **THEN** historical state and repair eligibility remain unknown

#### Scenario: Conflicting evidence timestamps
- **WHEN** resolutiondate precedes the observed Fixed transition by ten milliseconds
- **THEN** eligibility does not precede that qualifying transition

### Requirement: Branch and temporal eligibility
The module SHALL require an issue link in the commit message, qualifying Bug/Fixed/resolved-or-closed history, an explicit target branch, and caller-supplied branch integration time with a source reference before treating a repair as a candidate. Availability MUST use the later of qualification and integration, and MUST NOT use author time as integration evidence.

#### Scenario: Integration after cutoff
- **WHEN** an otherwise qualifying repair has target-branch integration after the cutoff
- **THEN** the repair remains unavailable at that cutoff

#### Scenario: Missing integration evidence
- **WHEN** branch integration time or its source reference is missing
- **THEN** eligibility remains unknown even if the issue is currently Fixed

#### Scenario: Different issue
- **WHEN** the supplied issue key is absent from the commit message
- **THEN** the issue is not linked to this repair

### Requirement: Portable offline report
The module SHALL provide a read-only local command that emits versioned JSON with input hashes, cutoff, historical assessment, explicit integration provenance, raw file/line evidence and candidate reason. Invalid inputs MUST return a nonzero exit status without a success report. Every report MUST retain unknown inducing labels, unset Kamei14 vectors and a requirement for later SZZ file/comment policy review.

#### Scenario: Successful command
- **WHEN** valid saved sources and explicit integration metadata are supplied
- **THEN** JSON can be consumed by a downstream tool without network access or source modification

#### Scenario: Invalid command
- **WHEN** a malformed source or naive timestamp is supplied
- **THEN** the command returns a diagnostic and nonzero status with empty report output

#### Scenario: Candidate is not a label
- **WHEN** a repair passes all candidate checks
- **THEN** its inducing label remains null with unknown_szz_not_executed, and no history-dependent features are filled with zero
