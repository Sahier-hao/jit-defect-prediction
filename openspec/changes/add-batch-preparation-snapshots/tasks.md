## 1. Batch preparation

- [x] 1.1 Implement manifest/ledger/source validation and bounded per-item processing; verify real two-patch reports, hash/size failures, path escape, bad schema and partial-failure accounting tests.
- [x] 1.2 Implement duplicate/branch eligibility and quality reconciliation; verify exact duplicates, conflicting evidence, backport branch exclusion, candidate/unknown totals and unset training labels/features.

## 2. Immutable artifacts

- [x] 2.1 Implement canonical IDs, verified reads and atomic no-replace publication; verify deterministic replay, unchanged prior files, corrupted-file refusal, changed cutoff, simulated interrupted publication and concurrent reuse tests.

## 3. Reviewable delivery

- [x] 3.1 Add prepare/verify CLI and a real two-repair example; verify subprocess success/failure statuses, saved snapshot recomputation, source immutability, backend regression, Ruff, source audit, local links and strict OpenSpec validation. Record software evidence without claiming SZZ, training or team acceptance.
