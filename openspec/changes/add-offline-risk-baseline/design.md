## Context

Status correction, 2026-10-04: this design describes an early technical spike. Product requirements, research and design preparation are not complete; see `establish-product-baseline` and the current prerequisite checklist. Technology choices and fixed parameters here describe the spike, not approved final product decisions.

Original starting context: the local project had no business code or durable specifications before this spike. The local Python environment provided FastAPI, SQLAlchemy, scikit-learn, pytest and httpx. The product draft proposed FastAPI/Vue/PostgreSQL and temporal evaluation, explanations and risk ranking; those draft choices did not establish that prerequisite work was finished. Git operations were prohibited.

## Goals / Non-Goals

**Goals:** Build an executable feature-import-to-baseline-to-risk workflow with automated evidence, durable storage, and a bundled Vue interface. Keep genuine model computation distinct from synthetic data and formal research results.

**Non-Goals:** Claim full Sprint 1 completion, mine repositories, run Git commands, construct SZZ labels, meet the eight-model final requirement, or claim production/physical/performance evidence. These remain product work, not waived requirements.

## Decisions

1. **Input contract:** CSV contains `commit_id,committed_at,label,ns,nd,nf,entropy,la,ld,lt,fix,ndev,age,nuc,exp,rexp,sexp`; optional `message` is retained for review. Features are imported, not claimed to be extracted. Labels are supplied with a recorded policy; the importer cannot certify historical label maturity or SZZ quality. Dataset metadata includes raw-file hash, provenance, synthetic flag, and label policy. All rows validate before one transaction.
2. **Storage:** SQLAlchemy models for datasets, commits, models, and predictions. SQLite under configurable `JIT_DATA_DIR` makes first run require no database service; configurable `JIT_DATABASE_URL` preserves a path to PostgreSQL. PostgreSQL integration is not validated in this change. Model artifacts are server-generated, never user-uploaded joblib files. Database and artifact writes have failure cleanup; a missing artifact never yields a ready response.
3. **Training:** Fixed StandardScaler + LogisticRegression, `random_state=42`, no hyperparameter search. Sort by timestamp and commit ID, select a nearest nonempty 70% boundary keeping ties together. Unknown labels never enter fitting or metrics. The model stores data hash, timestamps, feature order, configuration, and runtime versions. The baseline does not consume the `fix` label or messages as targets; the `fix` feature describes the current change's purpose, distinct from a future defect label.
4. **Prediction and explanation:** Store scores for imported commits at training completion to support SQL global sorting and paging. Training-period examples are marked `training`; default risk review is `holdout`. Logistic explanations use `coef * standardized feature` and the intercept as exact log-odds contributions, not SHAP or causal explanations. Thresholds are 0.7 high / 0.3 low / otherwise medium, explicitly recorded baseline configuration.
5. **Metrics:** Fixed probability threshold 0.5. Test reports contain both metric families and per-row scores. Effort uses max(1, LA+LD); budget recall uses a non-skipping whole-commit prefix in score/effort order. Full Popt uses trapezoidal full curves and label/effort oracle/worst orders. Tie breaks are deterministic commit IDs. This project convention is explicit and must not be compared to other implementations without aligning definitions.
6. **UI:** Vue 3 + Vite, plain JavaScript, same-origin production API; Vite proxies `/api` in development. A restrained engineering-console layout uses warm white, dark green, amber risk emphasis, compact data tables, and a responsive commit panel. Fonts fall back to locally available Segoe UI, Georgia, and Consolas; no external font/CDN requirement. Dataset and model changes invalidate old view state and concurrent stale responses.
7. **Demo:** Deterministic, clearly synthetic feature rows generated locally by a fixed seed; enough for the reduced smoke gate, never presented as ActiveMQ/SZZ data. The demo action imports through the same validation path and is idempotent. Model computation remains real; results only show software-chain behavior.

## Risks / Trade-offs

- [Supplied labels may contain leakage or noise] -> Require provenance and label-policy metadata; document that maturity and SZZ correctness remain unverified until real-data work.
- [Synchronous baseline fitting can block a request] -> Cap file rows at 20,000, use small bounded baseline settings, expose loading/error states, and leave asynchronous job infrastructure to a later change.
- [SQLite and PostgreSQL differ] -> Use SQLAlchemy portable types/queries, test SQLite honestly, and retain PostgreSQL as unverified.
- [Local model files are trusted serialization] -> Never accept uploaded model artifacts; load only server-created artifact names and report missing/corrupt files.
- [Temporal partition alone does not certify historical availability of labels] -> Retain imported label policy and keep formal evaluation claims out of smoke results.

## Migration Plan

This is the first implementation, so no existing application schema is migrated. Runtime data stays under `JIT_DATA_DIR` (default `runtime/`) and is ignored as generated output. Start the API, build the UI locally, explicitly load the synthetic demo, and test the complete flow. Rollback means stop the service and preserve the runtime directory; no user data is deleted automatically. Later schema changes will require an explicit migration.
