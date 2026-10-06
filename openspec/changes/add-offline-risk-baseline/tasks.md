## 1. Dataset and evaluation

Status correction, 2026-10-04: the checked items record engineering work and its earlier software verification for a technical spike. They do not prove product approval, user research, real-data validity, quality validation or Sprint 1 acceptance. Current preparation is tracked in `establish-product-baseline`; this spike has not been archived into an approved product baseline.

- [x] 1.1 Implement validated atomic CSV import with provenance and limits; verify invalid-field, unknown-label, duplicate, timezone, and persistence tests.
- [x] 1.2 Implement tie-safe temporal splitting and both metric families; verify training-only preprocessing and hand-computable effort/AUC edge-case tests.

## 2. Model and service

- [x] 2.1 Implement durable baseline training, immutable artifacts, exact log-odds explanations, and model reload; verify end-to-end API, restart, failure, and explanation-reconstruction tests.
- [x] 2.2 Implement global risk filtering and pagination with holdout scope and explicit demo loading; verify pagination, cross-dataset errors, and idempotent-demo tests.

## 3. Interface and delivery

- [x] 3.1 Implement bundled responsive Vue interface with import, training, evaluation, risk review, detail, loading, empty, and error states; verify frontend tests and production build.
- [x] 3.2 Exercise the complete local browser workflow, including upload, demo, training, detail, filtering, and persistence; verify Playwright output and capture a screenshot.
- [x] 3.3 Document startup, CSV format, database/model/API design, metric conventions, evidence boundaries, and remaining product work; verify documented commands and OpenSpec strict validation.
