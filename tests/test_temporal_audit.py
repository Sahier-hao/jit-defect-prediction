import hashlib
import importlib
import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from conftest import csv_bytes

ROOT = Path(__file__).resolve().parents[1]
START = datetime(2025, 1, 1, tzinfo=UTC)


def module():
    assert importlib.util.find_spec("jit_defect.temporal_audit") is not None, (
        "bound label availability audit is missing"
    )
    return importlib.import_module("jit_defect.temporal_audit")


def encode(value):
    return json.dumps(value, ensure_ascii=False).encode()


def temporal_inputs(count=80, mutate=None):
    from jit_defect.data import parse_csv

    def change(rows):
        for i, row in enumerate(rows):
            row["committed_at"] = (START + timedelta(days=i)).isoformat()
        if mutate:
            mutate(rows)

    raw = csv_bytes(count, mutate=change)
    records = parse_csv(raw)
    return raw, {
        "formatVersion": 1,
        "kind": "temporal_label_contract",
        "csvSha256": hashlib.sha256(raw).hexdigest(),
        "config": {
            "trainCutoff": (START + timedelta(days=int(count * 0.7))).isoformat(),
            "evaluationCutoff": (START + timedelta(days=count + 2)).isoformat(),
            "maturityDays": 1,
        },
        "rows": [
            {
                "commitId": row.commit_id,
                "featureAsOf": row.committed_at.isoformat(),
                "labelStatus": "unknown"
                if row.label is None
                else "buggy"
                if row.label
                else "clean_observed",
                "labelAvailableAt": None
                if row.label is None
                else (row.committed_at + timedelta(days=1)).isoformat(),
                "evidenceRef": None
                if row.label is None
                else "synthetic:" + row.commit_id,
            }
            for row in records
        ],
    }


def test_fixed_cohorts_and_late_training_label_are_independent_of_evaluation_cutoff():
    raw, contract = temporal_inputs(mutate=lambda rows: rows[5].update(la=999999))
    contract["rows"][5]["labelAvailableAt"] = (START + timedelta(days=60)).isoformat()
    contract["rows"][7]["evidenceRef"] = None
    audit = module().audit_temporal(raw, encode(contract))
    assert len(audit.train) == 54 and len(audit.test) == 24
    assert {r.commit_id for r in audit.train}.isdisjoint({"commit-0005", "commit-0007"})
    assert audit.report["config"]["trainCutoff"] == contract["config"]["trainCutoff"]
    assert audit.report["quality"]["submitted"] == 80
    assert audit.report["quality"]["excluded"] == 2
    assert audit.report["quality"]["byReason"]["late_training_label"] == 1
    assert audit.report["quality"]["byReason"]["missing_label_evidence"] == 1
    assert audit.report["trainingReady"] is False
    assert (
        audit.report["evidenceVerification"] == "caller_supplied_requires_source_review"
    )


def test_timestamps_equal_to_cutoff_stay_in_test_and_availability_is_inclusive():
    raw, contract = temporal_inputs(
        mutate=lambda rows: rows[57].update(committed_at=rows[56]["committed_at"])
    )
    contract["rows"][55]["labelAvailableAt"] = contract["config"]["trainCutoff"]
    audit = module().audit_temporal(raw, encode(contract))
    assert "commit-0055" in {r.commit_id for r in audit.train}
    assert {"commit-0056", "commit-0057"} <= {r.commit_id for r in audit.test}
    assert max(r.committed_at for r in audit.train) < min(
        r.committed_at for r in audit.test
    )


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("featureAsOf", None, "missing_feature_cutoff"),
        ("featureAsOf", "2025-01-08T00:00:00Z", "future_feature_information"),
        ("featureAsOf", "2025-01-06T00:00:00Z", "inconsistent_feature_cutoff"),
        ("labelAvailableAt", None, "missing_label_availability"),
        ("evidenceRef", None, "missing_label_evidence"),
    ],
)
def test_visible_per_row_exclusions(field, value, reason):
    raw, contract = temporal_inputs()
    contract["rows"][6][field] = value
    audit = module().audit_temporal(raw, encode(contract))
    decision = next(
        row for row in audit.report["decisions"] if row["commitId"] == "commit-0006"
    )
    assert decision["reason"] == reason
    assert audit.report["quality"]["excluded"] == 1


def test_clean_maturity_and_test_label_cutoff_are_separate():
    raw, contract = temporal_inputs()
    contract["rows"][1]["labelAvailableAt"] = contract["rows"][1]["featureAsOf"]
    contract["rows"][78]["labelAvailableAt"] = "2025-04-01T00:00:00Z"
    audit = module().audit_temporal(raw, encode(contract))
    assert audit.report["quality"]["byReason"]["premature_clean_evidence"] == 1
    assert audit.report["quality"]["byReason"]["late_test_label"] == 1


def test_unknown_and_outside_observation_are_not_converted_to_clean():
    raw, contract = temporal_inputs(mutate=lambda rows: rows[2].update(label="unknown"))
    contract["config"]["evaluationCutoff"] = (START + timedelta(days=79)).isoformat()
    audit = module().audit_temporal(raw, encode(contract))
    assert audit.report["quality"]["byReason"]["unknown_label"] == 1
    assert audit.report["quality"]["byReason"]["outside_observation_window"] == 1
    assert all(r.label is not None for r in audit.train + audit.test)


@pytest.mark.parametrize(
    "change,diagnostic",
    [
        ({"formatVersion": True}, "version"),
        ({"kind": "another_kind"}, "kind"),
        ({"csvSha256": "0" * 64}, "hash"),
        ({"extra": "field"}, "fields"),
        ({"rows": []}, "coverage"),
        ({"rows": "bad"}, "rows"),
    ],
)
def test_contract_binding_and_schema_failures(change, diagnostic):
    raw, contract = temporal_inputs()
    contract.update(change)
    with pytest.raises(ValueError, match=diagnostic):
        module().audit_temporal(raw, encode(contract))


@pytest.mark.parametrize("mode", ["duplicate", "extra", "missing", "mismatch"])
def test_commit_and_label_coverage_is_strict(mode):
    raw, contract = temporal_inputs()
    if mode == "duplicate":
        contract["rows"].append(contract["rows"][0])
    elif mode == "extra":
        contract["rows"][0]["commitId"] = "outside"
    elif mode == "missing":
        contract["rows"].pop()
    else:
        contract["rows"][0]["labelStatus"] = "buggy"
    with pytest.raises(ValueError, match="duplicate|coverage|label"):
        module().audit_temporal(raw, encode(contract))


@pytest.mark.parametrize("value", [True, 0, -1, 3651, 1.5, "90"])
def test_maturity_must_be_explicit_bounded_positive_integer(value):
    raw, contract = temporal_inputs()
    contract["config"]["maturityDays"] = value
    with pytest.raises(ValueError, match="maturity"):
        module().audit_temporal(raw, encode(contract))


@pytest.mark.parametrize(
    "mode", ["naive", "reverse_cutoffs", "pre_commit_label", "unknown_field"]
)
def test_invalid_temporal_declarations_fail(mode):
    raw, contract = temporal_inputs()
    if mode == "naive":
        contract["config"]["trainCutoff"] = "2025-02-26"
    elif mode == "reverse_cutoffs":
        contract["config"]["evaluationCutoff"] = contract["config"]["trainCutoff"]
    elif mode == "pre_commit_label":
        contract["rows"][0]["labelAvailableAt"] = "2024-01-01T00:00:00Z"
    else:
        contract["rows"][0]["futureFlag"] = True
    with pytest.raises(ValueError):
        module().audit_temporal(raw, encode(contract))


def test_duplicate_json_fields_size_limit_and_row_order():
    raw, contract = temporal_inputs()
    encoded = encode(contract)
    with pytest.raises(ValueError, match="duplicate"):
        module().audit_temporal(
            raw,
            encoded.replace(
                b'"formatVersion": 1', b'"formatVersion": 1, "formatVersion": 1'
            ),
        )
    with pytest.raises(ValueError, match="size"):
        module().audit_temporal(raw, encoded, max_contract_bytes=10)
    first = module().audit_temporal(raw, encoded)
    contract["rows"].reverse()
    second = module().audit_temporal(raw, encode(contract))
    assert first.train == second.train and first.test == second.test
    assert first.report["quality"] == second.report["quality"]
    assert first.report["provenance"] != second.report["provenance"]


def test_cli_snapshot_replay_and_failure(tmp_path):
    from jit_defect.preparation_batch import read_snapshot

    raw, contract = temporal_inputs()
    csv_path, contract_path = tmp_path / "features.csv", tmp_path / "contract.json"
    csv_path.write_bytes(raw)
    contract_path.write_bytes(encode(contract))
    args = [
        sys.executable,
        "-m",
        "jit_defect.temporal_audit",
        "--csv",
        str(csv_path),
        "--contract",
        str(contract_path),
        "--snapshot-dir",
        str(tmp_path / "output"),
    ]
    first = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    snapshot = Path(json.loads(first.stdout)["snapshot"])
    stamp = snapshot.stat().st_mtime_ns
    assert read_snapshot(snapshot)["stage"] == "temporal_eligibility_audit"
    second = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    assert second.stdout == first.stdout and second.returncode == 0
    assert snapshot.stat().st_mtime_ns == stamp
    original_files = set(snapshot.parent.iterdir())
    csv_path.write_bytes(raw + b"\n")
    bad = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    assert bad.returncode == 2 and bad.stdout == "" and "hash" in bad.stderr
    assert set(snapshot.parent.iterdir()) == original_files
