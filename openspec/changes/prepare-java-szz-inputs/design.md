## Context

See proposal.md. The batch module verifies source ledgers and publishes canonical snapshots; the parent/fixed AMQ-9481 Java files are already saved. No Git is authorized. Product review is still pending.

## Goals / Non-Goals

Prepare auditable inputs from one qualified repair. Do not perform blame, infer inducing commits, label clean commits, fill Kamei history features, or imply compiler validation.

## Decisions

- Recompute the existing batch from its own manifest and compare the entire body to the verified saved snapshot. This reuses temporal eligibility and source checks instead of trusting a caller's rewritten candidate flag.
- A small derived manifest selects one record, asserts a full parent SHA, and binds each eligible modified production path to ledger keys for parent/fixed files. Exact raw.githubusercontent.com HTTPS URLs must bind repository, SHA and path. Parent ancestry remains caller-supplied; matching URLs and hunk reconstruction cannot prove ancestry.
- Use `java-production-old-lines-v1`: exact src/test path segment exclusion, only src/main/java/**/*.java included. This intentionally narrow Maven-style policy is separate from Kamei feature extraction. New files have no old targets; production file deletion with removed lines is explicitly unsupported in this version. Missing or extra source bindings fail atomically.
- Apply every hunk to physical lines from the full parent and compare all fixed text after documented CRLF-to-LF normalization. Preserve terminal newline flags; reject lone CR. File sources keep their original byte hashes.
- Scan the entire parent with bounded comment/string/character/text-block states, preserving literal contents. A line with non-comment token content is retained; a whitespace-only text-block content line is also retained because it belongs to a literal. This is lexical selection, not a claim that each target executes. Reject any backslash followed by one or more u characters conservatively, including potentially ineligible Unicode escapes. Reject unfinished constructs and invalid text-block openings. Full Java syntax/type/escape validity is outside scope.
- Reuse batch source verification and immutable snapshot IO unchanged. New body stage is `java_szz_inputs`, includes raw and selected counts, line decisions and null training fields. Per-source cap 2 MiB; batch replay and additional-source verification each have a 32 MiB read budget; source bindings capped at 1000. No wall-clock export timestamp in content identity.

## Risks / Trade-offs

- Maven paths omit valid non-Maven Java production layouts → versioned exclusions are visible and a later policy change needs new evidence.
- Comment/blank-line filtering does not detect formatting-only edits to code lines or resolve refactorings, moved lines, reverts, added-line fixes, or causality → future SZZ evaluation must use an independently reviewed oracle; do not claim an accuracy improvement.
- Asserted parent ancestry or branch integration can be wrong despite content consistency → carry original config verification and explicit parent verification status.
- Conservative Unicode refusal reduces coverage → fail visibly, retaining the unchanged source; future preprocessing requires an explicit new policy and tests.
- Lexical scanning does not compile Java → report non-comment old-line targets, never executable-line or proven-inducer claims.

## Migration Plan

Additive CLI/module and new derived artifacts only. Existing source ledger, batch snapshot, modules and product drafts retain their meaning. Remove the new derived artifacts/module to roll back; no database migration is needed.
