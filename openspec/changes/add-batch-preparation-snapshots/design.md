## Context

See [proposal](proposal.md). `jit_defect/preparation.py` provides one-patch historical screening. The saved ActiveMQ ledger already contains URLs, retrieval times, SHA-256 and byte counts. Product architecture/DB decisions are drafts; use independent local JSON snapshots without changing the CSV spike or its database.

## Goals / Non-Goals

**Goals:** bounded batch processing, integrity/provenance, exact failure accounting, reproducible immutable preparation artifacts and a local CLI.

**Non-Goals:** automatic integration/ancestry validation, cross-branch repair-family inference, Git/network mining, SZZ, history features, training readiness or team approval.

## Decisions

1. Use a manifest with a SHA-bound ledger; source names are ledger file keys and files are under the ledger directory. Resolve and check relative paths, including symlink escapes. Strictly validate configuration before item processing. Bounds: 1000 inputs, 2MiB per source/manifest/ledger, 32MiB total unique source bytes.
2. Verify actual source bytes before calling the existing pure preparation function. Ledger-verified integration files provide provenance, but branch/time/source_ref assertions remain manually supplied. Source failure or unsupported patch becomes a retained item failure; invalid shared configuration or conflicting duplicate evidence rejects the batch.
3. Repair identity is `(commit SHA, issue key)` within one repository/target-branch snapshot. Equal reports deduplicate; conflicting reports reject. Cherry-picks with distinct SHAs stay separate; branch mismatch excludes eligibility. Order by input ID for stable records, while exact manifest bytes remain part of snapshot provenance.
4. The canonical JSON body includes all inputs, unique records, source metadata, manifest/ledger hashes, policy and quality counts. A SHA-256 content ID names an envelope containing that body. No wall-clock export time is added, so replay is deterministic. Existing artifacts are byte- and identity-verified before reuse.
5. Write a temporary file in the destination directory, flush/fsync, then create the final path via atomic no-replace hard link. Remove only the owned temporary file. If the filesystem lacks this operation, fail explicitly rather than overwrite or expose partial JSON. NTFS is the current target; tests exercise failure and concurrent reuse.

## Risks / Trade-offs

- A valid ledger proves internal byte integrity, not authentic upstream truth → preserve URLs and explicit caller assertions for independent review.
- Unsupported source types or resource overrun → retain item errors or reject oversized shared input; never zero-fill a failed record.
- Filesystems without hard-link support → clear write failure and no partial final file; no weakening fallback.
- Immutable JSON is preparation storage, not the final product database → mark not_training_ready and keep final DB choice open for team review.

## Migration Plan

Add a standalone module and CLI using existing dependencies. Store the reviewable demo under documentation and local generated snapshots only in an explicitly chosen directory. Reuse/verify existing snapshots; no source or prior snapshot overwrite. Keep both implemented changes active for non-author review; real product baseline tasks remain pending.
