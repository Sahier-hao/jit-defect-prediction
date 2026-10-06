## Context

See proposal.md. Current parser accepts exactly 14 precomputed features and binary/unknown labels. Existing learning filters unknowns before a ratio-based split; the importer cannot prove label observation dates. Product drafts already specify separate label cutoffs. No Git or database schema change is needed.

## Goals / Non-Goals

Make supplied temporal declarations testable and prevent unchecked non-demo fitting. This is not SZZ, a reconstructed sequence of clean-to-buggy label revisions, a full real training dataset, or independent authentication of feature/label evidence.

## Decisions

- Keep CSV schema unchanged. A JSON sidecar binds its exact hash, fixed train/evaluation cutoffs, explicitly supplied integer maturityDays (1–3650), and per-commit featureAsOf, labelStatus, labelAvailableAt, evidenceRef. Require complete ID coverage and consistent CSV labels. Null temporal/evidence values produce visible row exclusions; malformed values or labels available before their commit fail the whole contract.
- Use fixed half-open commit cohorts and inclusive label availability at their respective cutoffs. Do not derive a new 70/30 boundary after exclusions. FeatureAsOf must equal commit time: it represents the information cutoff of a reconstructed feature vector, not the later extraction time. Missing or unequal declarations are excluded.
- For clean_observed, require availability at or after commit+maturityDays; future availability additionally excludes it at the respective cutoff. This conservative v1 excludes a currently positive row unavailable at cutoff instead of inventing an earlier clean state. Future label-history reconstruction needs separate source evidence.
- EvidenceRef is a bounded nonempty review reference, not automatically fetched or authenticated. Both hashes and timestamps remain caller-supplied provenance assertions. Audit snapshots always have trainingReady=false. Counts mean eligible under the declared contract, not product readiness.
- Standard-library auditor returns immutable selected record tuples plus a report. CLI reuses existing atomic content-addressed publication. CSV cap 5MiB/20k rows; JSON cap 8MiB and same row limit; duplicate JSON fields and unsupported schema are rejected before publication.
- Refactor actual fitting into shared partition fitting. Ordinary fit_baseline retains synthetic demonstration behavior and sample-count checks but refuses non-demo training. New fit_temporal_baseline accepts the exact CSV and JSON bytes, audits them internally, applies sample/class gates after exclusions, fits and scores only admitted cohorts, and saves the full audit metadata. It does not accept a caller-made list of allegedly audited IDs.
- Reuse the current API error handling; no new sidecar upload or database migration. Non-demo API fitting now fails explicitly. The audited Python entrypoint is available for offline experiments, with source declarations still requiring review.

## Risks / Trade-offs

- Declarations can be wrong despite consistent hashes → record caller_supplied_requires_source_review and require real evidence before scientific claims.
- Current-positive labels may have been previously observed clean → v1 conservatively excludes them at earlier cutoffs; label revision histories are out of scope.
- Maturity alters sample distribution → expose it as a required parameter, preserve per-row and class counts, and do not present 90 days as universal.
- Existing non-demo callers relied on incomplete CSV metadata → fail clearly, document the new entrypoint, preserve synthetic demonstrations and existing stored models.
- Small admitted cohorts can produce unstable estimates → existing sample gates apply after filtering; software tests use explicitly synthetic data with no effect claim.

## Migration Plan

Add the auditor and audited entrypoint; update run documentation and product design's implementation note. Keep existing data/artifacts intact. No SQLite changes or remote actions. Do not mark actual product review complete.
