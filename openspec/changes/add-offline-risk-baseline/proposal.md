## Why

**Status correction, 2026-10-04:** This is an early technical spike, not an approved product baseline or accepted Sprint 1 increment. The user clarified that requirements and other prerequisites are unfinished. The verified software work remains available for discussion; current product preparation is tracked by `establish-product-baseline`. Completed engineering tasks do not establish user research, product approval, real-data validity, or coursework acceptance.

Original spike motivation, before implementation: draft product requirements existed without executable software. The local feature-import-to-risk-review workflow was intended as an experimental foundation for US-2.2.1, US-3.1.1, US-3.3.1/2/4, US-4.1.1, US-4.2.1, and US-5.1.1 without running Git commands. It did not establish that requirements or preparatory work had been completed.

## What Changes

- Import UTF-8 CSV datasets containing commit identifiers, UTC timestamps, labels, and all 14 Kamei features; validate the complete file before persistence and retain source hashes and provenance.
- Train a standardized logistic-regression baseline using a strictly temporal split and training-only preprocessing. Exclude unknown labels, preserve immutable model versions, and report both metric groups.
- Serve risk-ranked commits, paginated results, individual probabilities, and exact linear contributions in log-odds units through FastAPI.
- Provide a locally bundled Vue review interface with CSV import, explicit demo loading, model training, model evaluation, risk filtering, and commit details.
- Include deterministic synthetic demo data, automated tests, local persistence, and reproducible running instructions. Demo metrics are smoke evidence only.

## Capabilities

### New Capabilities

- `offline-risk-baseline`: Validated feature datasets, reproducible baseline training and evaluation, model registration, and risk review through API and UI.

### Modified Capabilities

None; the durable spec inventory is empty.

## Impact

Adds `jit_defect/`, `frontend/`, `tests/`, packaging files, and implementation documentation. Uses FastAPI, scikit-learn, SQLAlchemy, Vue, and Vite. SQLite is the local persistence default; the final database is still a design candidate, with PostgreSQL unverified. Repository mining, SZZ, the remaining model types, and formal performance/user studies remain separate product work. This spike was implemented before the user clarified that requirements and other prerequisites were unfinished. The current work is product preparation; the spike is not an approved product scope. No Git or external publishing operations were performed.
