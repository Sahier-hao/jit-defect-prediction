import copy
import hashlib
import importlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SAMPLES = (
    Path(__file__).resolve().parents[1] / "docs/数据核查/activemq-2024-sample-20261004"
)


def batch_module():
    assert importlib.util.find_spec("jit_defect.preparation_batch") is not None, (
        "batch preparation module is missing"
    )
    return importlib.import_module("jit_defect.preparation_batch")


def write_manifest(path, manifest):
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def update_ledger(path, manifest, *, changed_file=None, mutate=None):
    ledger_path = path.parent / manifest["sourceLedger"]["path"]
    rows = json.loads(ledger_path.read_bytes())
    if changed_file:
        raw = (path.parent / changed_file).read_bytes()
        row = next(row for row in rows if row["file"] == changed_file)
        row.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    if mutate:
        mutate(rows)
    write_manifest(ledger_path, rows)
    manifest["sourceLedger"]["sha256"] = hashlib.sha256(
        ledger_path.read_bytes()
    ).hexdigest()
    write_manifest(path, manifest)


@pytest.fixture
def batch_input(tmp_path):
    names = {
        "fix-72befc14.patch",
        "AMQ-9481.json",
        "pr-1206.html",
        "amq9330-8b6072d0.patch",
        "AMQ-9330.json",
        "backport-827ad101.patch",
    }
    rows = json.loads((SAMPLES / "sources.json").read_bytes())
    for name in names:
        shutil.copyfile(SAMPLES / name, tmp_path / name)
    ledger_path = tmp_path / "sources.json"
    write_manifest(ledger_path, [row for row in rows if row["file"] in names])
    manifest = {
        "formatVersion": 1,
        "repository": "apache/activemq",
        "targetBranch": "main",
        "sourceRef": "6e6caf7c6060efadc1ba524147e71d9720fcd935",
        "asOf": "2024-04-23T00:00:00Z",
        "sourceLedger": {
            "path": "sources.json",
            "sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
        },
        "items": [
            {
                "id": "amq9481",
                "patch": "fix-72befc14.patch",
                "issue": "AMQ-9481.json",
                "integration": {
                    "branch": "main",
                    "integratedAt": "2024-04-22T15:01:36Z",
                    "source": "pr-1206.html",
                },
            },
            {
                "id": "amq9330",
                "patch": "amq9330-8b6072d0.patch",
                "issue": "AMQ-9330.json",
            },
        ],
    }
    path = tmp_path / "batch.json"
    write_manifest(path, manifest)
    return path, manifest


def test_real_batch_preserves_integrity_and_all_candidate_outcomes(batch_input):
    path, _ = batch_input
    result = batch_module().prepare_batch(path)
    assert result["preparationStatus"] == "prepared"
    assert result["trainingReady"] is False
    assert result["datasetStatus"] == "not_training_ready"
    quality = result["quality"]
    assert {
        key: quality[key]
        for key in (
            "submitted",
            "duplicates",
            "unique",
            "parsed",
            "failed",
            "candidates",
            "excluded",
            "unknown",
        )
    } == dict(
        submitted=2,
        duplicates=0,
        unique=2,
        parsed=2,
        failed=0,
        candidates=1,
        excluded=0,
        unknown=1,
    )
    assert quality["byReason"] == {"candidate": 1, "unknown_integration": 1}
    assert len(result["sources"]) == 5
    assert (
        result["provenance"]["manifestSha256"]
        == hashlib.sha256(path.read_bytes()).hexdigest()
    )
    for source in result["sources"]:
        assert (
            source["sha256"]
            == hashlib.sha256((path.parent / source["file"]).read_bytes()).hexdigest()
        )
    assert all(
        record["report"]["inducingLabel"] is None for record in result["records"]
    )
    assert all(record["report"]["kamei14"] is None for record in result["records"])
    assert quality["rawDiffTotals"]["NF"] == 4


@pytest.mark.parametrize("failure", ["hash", "bytes", "missing", "http_status"])
def test_source_failures_are_retained_without_losing_healthy_input(
    batch_input, failure
):
    path, manifest = batch_input
    if failure == "hash":
        patch = path.parent / "amq9330-8b6072d0.patch"
        patch.write_bytes(patch.read_bytes().replace(b"AMQ-9330", b"AMQ-9999", 1))
    elif failure == "missing":
        (path.parent / "amq9330-8b6072d0.patch").unlink()
    else:

        def mutate(rows):
            row = next(row for row in rows if row["file"] == "amq9330-8b6072d0.patch")
            row["bytes" if failure == "bytes" else "status"] = 0

        update_ledger(path, manifest, mutate=mutate)
    result = batch_module().prepare_batch(path)
    assert result["preparationStatus"] == "prepared_with_errors"
    assert result["quality"]["submitted"] == 2
    assert result["quality"]["failed"] == 1
    assert result["quality"]["candidates"] == 1
    outcome = next(item for item in result["inputs"] if item["id"] == "amq9330")
    assert outcome["status"] == "source_error"
    assert outcome["diagnostic"]
    assert len(result["records"]) == 1


def test_verified_but_unsupported_patch_is_an_explicit_parse_failure(batch_input):
    path, manifest = batch_input
    name = "amq9330-8b6072d0.patch"
    (path.parent / name).write_bytes(b"a synthetic unsupported binary patch")
    update_ledger(path, manifest, changed_file=name)
    result = batch_module().prepare_batch(path)
    assert result["quality"]["byReason"] == {"candidate": 1, "parse_error": 1}
    assert result["quality"]["rawDiffTotals"] == {"NF": 2, "LA": 17, "LD": 8}
    assert (
        result["quality"]["unique"]
        == result["quality"]["parsed"] + result["quality"]["failed"]
    )


def test_identical_duplicate_is_linked_and_never_double_counted(batch_input):
    path, manifest = batch_input
    duplicate = copy.deepcopy(manifest["items"][0])
    duplicate["id"] = "zz-duplicate"
    manifest["items"].append(duplicate)
    write_manifest(path, manifest)
    result = batch_module().prepare_batch(path)
    assert result["quality"]["submitted"] == 3
    assert result["quality"]["duplicates"] == 1
    assert result["quality"]["unique"] == 2
    assert result["quality"]["candidates"] == 1
    duplicate_result = next(
        item for item in result["inputs"] if item["id"] == "zz-duplicate"
    )
    assert duplicate_result["status"] == "duplicate"
    assert duplicate_result["duplicateOf"] == "amq9481"


def test_conflicting_duplicate_cannot_choose_an_earlier_availability(batch_input):
    path, manifest = batch_input
    duplicate = copy.deepcopy(manifest["items"][0])
    duplicate["id"] = "zz-conflicting"
    duplicate["integration"]["integratedAt"] = "2024-04-22T23:00:00Z"
    manifest["items"].append(duplicate)
    write_manifest(path, manifest)
    with pytest.raises(ValueError, match="conflicting duplicate"):
        batch_module().prepare_batch(path)


def test_other_branch_backport_remains_distinct_and_excluded(batch_input):
    path, manifest = batch_input
    backport = copy.deepcopy(manifest["items"][0])
    backport.update(id="backport9481", patch="backport-827ad101.patch")
    backport["integration"]["branch"] = "activemq-5.18.x"
    manifest["items"].append(backport)
    write_manifest(path, manifest)
    result = batch_module().prepare_batch(path)
    record = next(row for row in result["records"] if row["id"] == "backport9481")
    assert record["status"] == "excluded_branch"
    assert record["report"]["candidate"]["status"] == "excluded_branch"
    assert record["report"]["patch"]["cherryPickedFrom"] == [
        "72befc14fbb69c24bdec0c7d4a1002da8874380d"
    ]
    assert result["quality"]["unique"] == 3
    assert result["quality"]["excluded"] == 1
    assert result["quality"]["candidates"] == 1


@pytest.mark.parametrize(
    "mutation,diagnostic",
    [
        ("empty", "items"),
        ("mutable_ref", "sourceRef"),
        ("duplicate_id", "id"),
        ("ledger_hash", "ledger"),
        ("escape", "path"),
        ("version", "version"),
        ("naive_time", "timezone"),
        ("extra_key", "field"),
        ("too_many", "limit"),
    ],
)
def test_invalid_manifest_is_rejected_before_processing(
    batch_input, mutation, diagnostic
):
    path, manifest = batch_input
    if mutation == "empty":
        manifest["items"] = []
    elif mutation == "mutable_ref":
        manifest["sourceRef"] = "main"
    elif mutation == "duplicate_id":
        manifest["items"][1]["id"] = "amq9481"
    elif mutation == "ledger_hash":
        manifest["sourceLedger"]["sha256"] = "0" * 64
    elif mutation == "escape":
        manifest["sourceLedger"]["path"] = "../sources.json"
    elif mutation == "version":
        manifest["formatVersion"] = True
    elif mutation == "naive_time":
        manifest["asOf"] = "2024-04-23"
    elif mutation == "extra_key":
        manifest["guessLabels"] = True
    else:
        base = manifest["items"][0]
        manifest["items"] = [{**base, "id": f"item{i}"} for i in range(1001)]
    write_manifest(path, manifest)
    with pytest.raises(ValueError, match=diagnostic):
        batch_module().prepare_batch(path)


def test_total_unique_source_budget_is_enforced(batch_input):
    path, _ = batch_input
    with pytest.raises(ValueError, match="budget"):
        batch_module().prepare_batch(path, max_total_bytes=100)


def test_oversized_failed_source_still_consumes_batch_read_budget(batch_input):
    path, _ = batch_input
    module = batch_module()
    (path.parent / "amq9330-8b6072d0.patch").write_bytes(
        b"x" * (module.MAX_SOURCE_BYTES + 100)
    )
    with pytest.raises(ValueError, match="budget"):
        module.prepare_batch(path, max_total_bytes=module.MAX_SOURCE_BYTES + 4096)


def test_cutoff_changes_keep_both_issues_unverified_before_resolution(batch_input):
    path, manifest = batch_input
    manifest["asOf"] = "2024-04-01T00:00:00Z"
    write_manifest(path, manifest)
    result = batch_module().prepare_batch(path)
    assert result["quality"]["candidates"] == 0
    assert result["quality"]["unknown"] == 2


def test_symlink_escape_is_rejected_before_reading_source(batch_input, tmp_path):
    path, manifest = batch_input
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    (outside / "sources.json").write_text("[]", encoding="utf-8")
    link = path.parent / "linked-ledger"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            raise
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0, "directory-junction control unavailable"
    manifest["sourceLedger"]["path"] = link.name + "/sources.json"
    write_manifest(path, manifest)
    with pytest.raises(ValueError, match="path"):
        batch_module().prepare_batch(path)


def test_failed_input_retains_original_source_references(batch_input):
    path, _ = batch_input
    (path.parent / "amq9330-8b6072d0.patch").unlink()
    result = batch_module().prepare_batch(path)
    outcome = next(item for item in result["inputs"] if item["id"] == "amq9330")
    assert outcome["input"]["patch"] == "amq9330-8b6072d0.patch"
    assert outcome["input"]["issue"] == "AMQ-9330.json"
