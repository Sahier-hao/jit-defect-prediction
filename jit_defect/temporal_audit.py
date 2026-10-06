"""Bound temporal eligibility declarations; upstream evidence still needs review."""

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from .data import MAX_BYTES, MAX_ROWS, CommitRecord, parse_csv
from .preparation import _time
from .preparation_batch import SHA256, _fields, _hash, _json, _string, write_snapshot

MAX_CONTRACT_BYTES = 8 * 1024 * 1024
POLICY_VERSION = "fixed-cutoff-label-availability-v1"
LABELS = {"buggy": 1, "clean_observed": 0, "unknown": None}


@dataclass(frozen=True)
class TemporalAudit:
    records: tuple[CommitRecord, ...]
    train: tuple[CommitRecord, ...]
    test: tuple[CommitRecord, ...]
    report: dict


def _nullable_time(value):
    return None if value is None else _time(value)


def _contract(raw: bytes, csv: bytes, records: list[CommitRecord]) -> tuple:
    value = _json(raw)
    _fields(value, {"formatVersion", "kind", "csvSha256", "config", "rows"})
    if type(value["formatVersion"]) is not int or value["formatVersion"] != 1:
        raise ValueError("unsupported temporal contract version")
    if value["kind"] != "temporal_label_contract":
        raise ValueError("invalid temporal contract kind")
    _string(value["csvSha256"], "CSV hash", SHA256.pattern)
    if _hash(csv) != value["csvSha256"]:
        raise ValueError("CSV hash differs from temporal contract")
    config = value["config"]
    _fields(config, {"trainCutoff", "evaluationCutoff", "maturityDays"})
    train_cutoff = _time(config["trainCutoff"])
    evaluation_cutoff = _time(config["evaluationCutoff"])
    if train_cutoff >= evaluation_cutoff:
        raise ValueError("evaluation cutoff must follow training cutoff")
    maturity = config["maturityDays"]
    if type(maturity) is not int or not 1 <= maturity <= 3650:
        raise ValueError("maturityDays must be an integer between 1 and 3650")
    rows = value["rows"]
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("invalid or excessive temporal rows")
    by_id = {}
    for row in rows:
        _fields(
            row,
            {
                "commitId",
                "featureAsOf",
                "labelStatus",
                "labelAvailableAt",
                "evidenceRef",
            },
        )
        commit_id = _string(row["commitId"], "commit ID", r"[^/\\\x00]{1,128}")
        if commit_id in by_id:
            raise ValueError("duplicate temporal commit ID")
        status = row["labelStatus"]
        if not isinstance(status, str) or status not in LABELS:
            raise ValueError("invalid label status")
        feature_as_of = _nullable_time(row["featureAsOf"])
        available_at = _nullable_time(row["labelAvailableAt"])
        reference = row["evidenceRef"]
        if reference is not None:
            if (
                not isinstance(reference, str)
                or not reference.strip()
                or len(reference) > 2048
                or any(ord(c) < 32 for c in reference)
            ):
                raise ValueError("invalid label evidence reference")
        by_id[commit_id] = (status, feature_as_of, available_at, reference)
    if set(by_id) != {row.commit_id for row in records}:
        raise ValueError("temporal row coverage must exactly match CSV commit IDs")
    for row in records:
        status, _, available, _ = by_id[row.commit_id]
        if LABELS[status] != row.label:
            raise ValueError("CSV label differs from temporal label status")
        if available is not None and available < row.committed_at:
            raise ValueError("label availability predates commit time")
    normalized = {
        "trainCutoff": train_cutoff.isoformat(),
        "evaluationCutoff": evaluation_cutoff.isoformat(),
        "maturityDays": maturity,
    }
    return normalized, train_cutoff, evaluation_cutoff, by_id


def _reason(row, information, cohort, cutoff, maturity):
    status, feature_as_of, available, evidence = information
    if cohort == "outside":
        return "outside_observation_window"
    if feature_as_of is None:
        return "missing_feature_cutoff"
    if feature_as_of > row.committed_at:
        return "future_feature_information"
    if feature_as_of < row.committed_at:
        return "inconsistent_feature_cutoff"
    if status == "unknown":
        return "unknown_label"
    if available is None:
        return "missing_label_availability"
    if evidence is None:
        return "missing_label_evidence"
    if available > cutoff:
        return "late_training_label" if cohort == "training" else "late_test_label"
    if status == "clean_observed" and available - row.committed_at < timedelta(
        days=maturity
    ):
        return "premature_clean_evidence"
    return "selected_training" if cohort == "training" else "selected_test"


def audit_temporal(
    csv: bytes, contract: bytes, *, max_contract_bytes: int = MAX_CONTRACT_BYTES
) -> TemporalAudit:
    """Select fixed cohorts without moving cutoffs or backfilling future labels."""
    if not contract or len(contract) > max_contract_bytes:
        raise ValueError("temporal contract size limit exceeded or empty contract")
    records = parse_csv(csv)
    config, train_cutoff, evaluation_cutoff, by_id = _contract(contract, csv, records)
    train, test, decisions = [], [], []
    for row in records:
        cohort = (
            "training"
            if row.committed_at < train_cutoff
            else "test"
            if row.committed_at < evaluation_cutoff
            else "outside"
        )
        cutoff = train_cutoff if cohort == "training" else evaluation_cutoff
        info = by_id[row.commit_id]
        reason = _reason(row, info, cohort, cutoff, config["maturityDays"])
        if reason == "selected_training":
            train.append(row)
        elif reason == "selected_test":
            test.append(row)
        decisions.append(
            {
                "commitId": row.commit_id,
                "committedAt": row.committed_at.isoformat(),
                "cohort": cohort,
                "labelCutoff": cutoff.isoformat(),
                "labelStatus": info[0],
                "featureAsOf": info[1].isoformat() if info[1] else None,
                "labelAvailableAt": info[2].isoformat() if info[2] else None,
                "evidenceRef": info[3],
                "reason": reason,
            }
        )
    reasons = Counter(row["reason"] for row in decisions)

    def classes(selected):
        return {
            "buggy": sum(row.label == 1 for row in selected),
            "cleanObserved": sum(row.label == 0 for row in selected),
        }

    report = {
        "formatVersion": 1,
        "kind": "offline_preparation_snapshot",
        "stage": "temporal_eligibility_audit",
        "policyVersion": POLICY_VERSION,
        "preparationStatus": "audited",
        "datasetStatus": "requires_upstream_evidence_review",
        "trainingReady": False,
        "evidenceVerification": "caller_supplied_requires_source_review",
        "config": config,
        "provenance": {"csvSha256": _hash(csv), "contractSha256": _hash(contract)},
        "trainingIds": [row.commit_id for row in train],
        "testIds": [row.commit_id for row in test],
        "decisions": decisions,
        "quality": {
            "submitted": len(records),
            "training": len(train),
            "test": len(test),
            "excluded": len(records) - len(train) - len(test),
            "trainingClasses": classes(train),
            "testClasses": classes(test),
            "byReason": dict(sorted(reasons.items())),
        },
    }
    return TemporalAudit(tuple(records), tuple(train), tuple(test), report)


def _bounded(path: Path, limit: int) -> bytes:
    with path.open("rb") as source:
        raw = source.read(limit + 1)
    if not raw or len(raw) > limit:
        raise ValueError("input size limit exceeded or empty input")
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        audit = audit_temporal(
            _bounded(args.csv, MAX_BYTES), _bounded(args.contract, MAX_CONTRACT_BYTES)
        )
        destination = write_snapshot(audit.report, args.snapshot_dir)
    except (OSError, ValueError) as exc:
        print("Temporal audit failed: " + str(exc), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "snapshot": str(destination),
                "snapshotId": destination.stem,
                "quality": audit.report["quality"],
                "trainingReady": False,
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
