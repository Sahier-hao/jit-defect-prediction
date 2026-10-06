import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from test_szz_java import module

from jit_defect.preparation_batch import prepare_batch, read_snapshot, write_snapshot

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/数据核查"


def save(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


@pytest.fixture
def inputs(tmp_path):
    shutil.copytree(
        DOCS / "activemq-2024-sample-20261004",
        tmp_path / "activemq-2024-sample-20261004",
    )
    shutil.copyfile(DOCS / "批量准备示例.json", tmp_path / "批量准备示例.json")
    manifest = json.loads((DOCS / "Java旧行准备示例.json").read_bytes())
    batch_snapshot = Path(manifest["batchSnapshot"])
    (tmp_path / batch_snapshot.parent).mkdir()
    shutil.copyfile(DOCS / batch_snapshot, tmp_path / batch_snapshot)
    path = tmp_path / "inputs.json"
    save(path, manifest)
    return path


def refresh_batch(path):
    """Update synthetic source evidence and recompute its independent batch."""
    root = path.parent
    ledger = root / "activemq-2024-sample-20261004/sources.json"
    rows = json.loads(ledger.read_bytes())
    for row in rows:
        raw = (ledger.parent / row["file"]).read_bytes()
        row["sha256"] = hashlib.sha256(raw).hexdigest()
        row["bytes"] = len(raw)
    save(ledger, rows)
    batch_path = root / "批量准备示例.json"
    batch = json.loads(batch_path.read_bytes())
    batch["sourceLedger"]["sha256"] = hashlib.sha256(ledger.read_bytes()).hexdigest()
    save(batch_path, batch)
    snapshot = write_snapshot(prepare_batch(batch_path), root / "批量准备结果")
    manifest = json.loads(path.read_bytes())
    manifest["batchSnapshot"] = snapshot.relative_to(root).as_posix()
    save(path, manifest)


def test_real_candidate_has_two_targets_and_six_visible_exclusions(inputs):
    before = {p: p.read_bytes() for p in inputs.parent.rglob("*") if p.is_file()}
    result = module().prepare_inputs(inputs)
    assert result["stage"] == "java_szz_inputs"
    assert result["policyVersion"] == "java-production-old-lines-v1"
    assert result["quality"] == {
        "rawFiles": 2,
        "rawAdded": 17,
        "rawRemoved": 8,
        "selectedFiles": 1,
        "selectedLines": 2,
        "excludedLines": 6,
        "byReason": {
            "excluded_comment": 2,
            "excluded_test_path": 4,
            "selected_non_comment": 2,
        },
    }
    assert [r["oldLine"] for r in result["targets"]] == [118, 121]
    assert [
        r["oldLine"] for r in result["decisions"] if r["reason"] == "excluded_comment"
    ] == [119, 120]
    assert len(result["decisions"]) == 8
    assert result["inducingLabel"] is None and result["kamei14"] is None
    assert result["trainingReady"] is False
    assert result["parentVerification"] == "caller_supplied_requires_ancestry_review"
    assert result["candidateAvailableAt"] == "2024-04-22T15:07:37.776000+00:00"
    assert before == {
        p: p.read_bytes() for p in inputs.parent.rglob("*") if p.is_file()
    }
    destination = write_snapshot(result, inputs.parent / "derived")
    stamp = destination.stat().st_mtime_ns
    assert read_snapshot(destination) == result
    assert (
        write_snapshot(module().prepare_inputs(inputs), destination.parent)
        == destination
    )
    assert destination.stat().st_mtime_ns == stamp


@pytest.mark.parametrize(
    "path,reason",
    [
        ("m/src/test/java/X.java", "excluded_test_path"),
        ("src/test/java/X.java", "excluded_test_path"),
        ("m/src/main/java/src/test/java/X.java", "excluded_test_path"),
        ("m/src/main/java/X.java", None),
        ("src/main/java/X.java", None),
        ("m/src/main/java/X.txt", "excluded_non_java"),
        ("m/src/main/javaish/X.java", "excluded_outside_production_root"),
        ("src/testsupport/java/X.java", "excluded_outside_production_root"),
    ],
)
def test_explicit_versioned_file_policy(path, reason):
    assert module().file_policy(path) == reason


@pytest.mark.parametrize(
    "change,diagnostic",
    [
        ({"formatVersion": True}, "version"),
        ({"recordId": "AMQ-9330-original"}, "qualified candidate"),
        ({"recordId": "missing"}, "qualified candidate"),
        ({"parentCommit": "short"}, "parent commit"),
        (
            {"parentCommit": "72befc14fbb69c24bdec0c7d4a1002da8874380d"},
            "parent differs",
        ),
        ({"batchManifest": "../elsewhere.json"}, "path"),
        ({"files": []}, "bindings"),
        ({"files": "invalid"}, "bindings"),
        ({"unexpected": 1}, "fields"),
    ],
)
def test_invalid_manifest_or_unknown_candidate_is_atomic_failure(
    inputs, change, diagnostic
):
    value = json.loads(inputs.read_bytes())
    value.update(change)
    save(inputs, value)
    with pytest.raises(ValueError, match=diagnostic):
        module().prepare_inputs(inputs)


def test_duplicate_binding_rejected(inputs):
    value = json.loads(inputs.read_bytes())
    value["files"] *= 2
    save(inputs, value)
    with pytest.raises(ValueError, match="duplicate"):
        module().prepare_inputs(inputs)


def test_changed_batch_and_bad_parent_hash_rejected(inputs):
    parent = (
        inputs.parent
        / "activemq-2024-sample-20261004/parent-AsyncServletRequest.java.txt"
    )
    parent.write_bytes(parent.read_bytes() + b"// tampered\n")
    with pytest.raises(ValueError, match="hash"):
        module().prepare_inputs(inputs)


def test_batch_semantics_recomputed_even_with_valid_new_content_id(inputs):
    value = json.loads(inputs.read_bytes())
    body = read_snapshot(inputs.parent / value["batchSnapshot"])
    body["records"][0]["status"] = "candidate"
    forged = write_snapshot(body, inputs.parent / "批量准备结果")
    value["batchSnapshot"] = forged.relative_to(inputs.parent).as_posix()
    save(inputs, value)
    with pytest.raises(ValueError, match="batch snapshot"):
        module().prepare_inputs(inputs)


@pytest.mark.parametrize("wrong", ["commit", "path", "scheme", "host"])
def test_parent_url_is_bound_to_repository_commit_and_path(inputs, wrong):
    ledger = inputs.parent / "activemq-2024-sample-20261004/sources.json"
    rows = json.loads(ledger.read_bytes())
    row = next(r for r in rows if r["file"] == "parent-AsyncServletRequest.java.txt")
    row["url"] = {
        "commit": row["url"].replace(
            "6084867b26619ab614bc117667a32649def5887a", "c" * 40
        ),
        "path": row["url"] + ".wrong",
        "scheme": row["url"].replace("https:", "http:"),
        "host": row["url"].replace("raw.githubusercontent.com", "example.com"),
    }[wrong]
    save(ledger, rows)
    refresh_batch(inputs)
    with pytest.raises(ValueError, match="URL"):
        module().prepare_inputs(inputs)


def test_correct_hash_but_wrong_independent_fixed_content_rejected(inputs):
    fixed = (
        inputs.parent
        / "activemq-2024-sample-20261004/fixed-AsyncServletRequest.java.txt"
    )
    fixed.write_bytes(fixed.read_bytes() + b"// unexpected full-file content\n")
    refresh_batch(inputs)
    with pytest.raises(ValueError, match="fixed file"):
        module().prepare_inputs(inputs)


def test_zero_targets_remain_unknown(inputs):
    root = inputs.parent / "activemq-2024-sample-20261004"
    # Keep synthetic unchanged regions consistent in both full-file versions.
    for name in (
        "fix-72befc14.patch",
        "parent-AsyncServletRequest.java.txt",
        "fixed-AsyncServletRequest.java.txt",
    ):
        path = root / name
        raw = path.read_bytes()
        raw = raw.replace(b"if (context != null) {", b"// if (context != null) {")
        raw = raw.replace(b"context.complete();", b"// context.complete();")
        path.write_bytes(raw)
    refresh_batch(inputs)
    body = module().prepare_inputs(inputs)
    assert body["targets"] == []
    assert body["quality"]["selectedLines"] == 0
    assert body["quality"]["excludedLines"] == 8
    assert body["selectionStatus"] == "no_eligible_removed_lines"
    assert body["inducingLabel"] is None


def test_cli_success_and_replay(inputs):
    args = [
        sys.executable,
        "-m",
        "jit_defect.szz_inputs",
        "--manifest",
        str(inputs),
        "--snapshot-dir",
        str(inputs.parent / "derived"),
    ]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["selectedLines"] == 2
    assert read_snapshot(Path(summary["snapshot"]))["trainingReady"] is False
    second = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    assert second.returncode == 0 and second.stdout == result.stdout


def test_cli_invalid_input_has_no_partial_stdout_or_output(inputs):
    manifest = json.loads(inputs.read_bytes())
    manifest["files"] = []
    save(inputs, manifest)
    destination = inputs.parent / "derived"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "jit_defect.szz_inputs",
            "--manifest",
            str(inputs),
            "--snapshot-dir",
            str(destination),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert result.stdout == "" and "bindings" in result.stderr
    assert not destination.exists()
