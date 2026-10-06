## Why

Verified repair candidates still contain test deletions and comments. Before a later SZZ run, the project needs reproducible old-line inputs checked against complete parent and fixed files; the AMQ-9481 fixture makes this gap directly testable without Git.

## What Changes

- Research public SZZ implementations and Java lexical rules, recording primary sources and the limits of a project-specific policy.
- Add a standard-library offline Java input preparer that consumes a verified candidate snapshot and the unchanged source ledger.
- Verify patch identity, fixed-SHA file URLs, complete hunk reconstruction, and whole-parent lexical context before selecting removed production lines.
- Retain excluded lines with reasons and publish an immutable derived snapshot, leaving attribution labels and full Kamei features unset.

## Capabilities

### New Capabilities

- `java-szz-input-preparation`: Source-verified, versioned Java old-line selection for later attribution.

### Modified Capabilities

None. Main specifications remain empty; product drafts and their actual review tasks are unchanged.

## Impact

Adds a Python module, tests, a manifest, derived evidence, and research/run documentation. Reuses existing snapshot publication and source verification without changing previous snapshots or raw sources. No dependencies, Git execution, blame, model training, remote writes, or product acceptance.
