## Context

See [proposal](proposal.md) for motivation. The saved ActiveMQ sources contain text patches, complete Jira changelogs, and independent parent/fixed snapshots. Existing `jit_defect/data.py` consumes complete precomputed CSV features and cannot represent these incomplete inputs. The user forbids Git; all work uses saved local files.

## Goals / Non-Goals

**Goals:** reusable standard-library parsing, historical repair screening, explicit provenance and a machine-readable offline report. Keep CSV contracts intact.

**Non-Goals:** network collectors, automatic merge/backport attribution, Java lexing, SZZ/blame, Kamei history features, training, team approval and production acceptance. Removed comments and tests remain visible for a later independently versioned SZZ policy.

## Decisions

1. Accept a deliberately bounded unquoted-path, single email text-patch subset; reject binary, rename/copy and mode-only changes. Strict old/new counters and parent reconstruction tests are preferable to silently accepting every patch format.
2. Replay complete Jira history by first reversing from current field values and checking every relevant transition, then applying events through the cutoff. Pagination gaps mean unknown; contradictory field chains mean invalid input. Use aware UTC times and changelog qualification events. AMQ-9481 has a 10ms resolutiondate/history discrepancy: retain the raw field separately and use the later observed qualification event, without rewriting the prior audit evidence.
3. Accept integration time, target branch and source reference as explicit caller assertions. Never infer them from author time or automatically deduplicate related patches; retain cherry-pick origin SHAs and state that integration evidence needs independent verification.
4. Emit versioned JSON from a pure report function plus a local CLI; include SHA-256 of exact source bytes. This avoids introducing DB migrations or changing the existing API to ingest incomplete training rows.

## Risks / Trade-offs

- Restricted patch subset → clear failures, tested diagnostics and documented accepted formats.
- Historical changelog is reconstructed now, not an observation made at the historical cutoff → record snapshot time and reconstruction policy, without claiming real-time availability.
- Caller-provided integration metadata can be wrong → provenance is explicit, missing metadata gives unknown; no claim of automatic source validation.
- Removed lines include comments/tests → mark attribution policy pending and preserve original evidence rather than use a misleading generic Java filter.

## Migration Plan

Add an independent module, CLI and tests; no existing database or CSV migration. Rollback is removal of this isolated module and its entrypoint. Keep the change active after implementation for non-author review; do not archive or approve the product baseline automatically.
