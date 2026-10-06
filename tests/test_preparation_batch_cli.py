import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_preparation_batch import batch_input as batch_input
from test_preparation_batch import write_manifest

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run(
        [sys.executable, "-m", "jit_defect.preparation_batch", *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        timeout=15,
    )


def test_prepare_and_verify_cli_produce_reusable_snapshot(batch_input, tmp_path):
    manifest, _ = batch_input
    folder = tmp_path / "snapshots"
    original = {
        path.name: path.read_bytes()
        for path in manifest.parent.glob("*")
        if path.is_file()
    }
    first = run("prepare", "--manifest", manifest, "--snapshot-dir", folder)
    assert first.returncode == 0, first.stderr.decode()
    assert first.stdout, "batch CLI is missing"
    output = json.loads(first.stdout)
    path = Path(output["snapshotPath"])
    assert path.is_file()
    assert output["quality"]["candidates"] == 1
    assert output["trainingReady"] is False
    raw, modified = path.read_bytes(), path.stat().st_mtime_ns
    repeated = run("prepare", "--manifest", manifest, "--snapshot-dir", folder)
    assert repeated.returncode == 0
    assert repeated.stdout == first.stdout
    assert path.stat().st_mtime_ns == modified
    assert path.read_bytes() == raw
    verified = run("verify", "--snapshot", path)
    assert verified.returncode == 0
    assert json.loads(verified.stdout)["result"] == "VERIFIED"
    assert json.loads(verified.stdout)["snapshotId"] == output["snapshotId"]
    assert {
        path.name: path.read_bytes()
        for path in manifest.parent.glob("*")
        if path.is_file()
    } == original


def test_partial_failure_cli_saves_diagnosis_with_exit_one(batch_input, tmp_path):
    manifest, _ = batch_input
    (manifest.parent / "amq9330-8b6072d0.patch").unlink()
    result = run(
        "prepare", "--manifest", manifest, "--snapshot-dir", tmp_path / "snapshots"
    )
    assert result.returncode == 1
    output = json.loads(result.stdout)
    assert output["preparationStatus"] == "prepared_with_errors"
    assert output["quality"]["failed"] == 1
    assert Path(output["snapshotPath"]).is_file()


@pytest.mark.parametrize("failure", ["manifest", "existing_snapshot"])
def test_fatal_cli_failure_emits_no_success_and_never_overwrites(
    batch_input, tmp_path, failure
):
    manifest, value = batch_input
    folder = tmp_path / "snapshots"
    if failure == "manifest":
        value["sourceRef"] = "main"
        write_manifest(manifest, value)
        corrupt_path = None
    else:
        first = run("prepare", "--manifest", manifest, "--snapshot-dir", folder)
        assert first.stdout, "batch CLI is missing"
        corrupt_path = Path(json.loads(first.stdout)["snapshotPath"])
        corrupt_path.write_bytes(b"deliberately damaged snapshot")
    result = run("prepare", "--manifest", manifest, "--snapshot-dir", folder)
    assert result.returncode == 2
    assert result.stdout == b""
    assert b"batch preparation error:" in result.stderr
    assert b"Traceback" not in result.stderr
    if corrupt_path:
        assert corrupt_path.read_bytes() == b"deliberately damaged snapshot"
    else:
        assert not folder.exists()


def test_verify_cli_rejects_a_corrupted_snapshot(batch_input, tmp_path):
    manifest, _ = batch_input
    first = run(
        "prepare", "--manifest", manifest, "--snapshot-dir", tmp_path / "snapshots"
    )
    assert first.stdout, "batch CLI is missing"
    path = Path(json.loads(first.stdout)["snapshotPath"])
    path.write_bytes(path.read_bytes() + b" ")
    result = run("verify", "--snapshot", path)
    assert result.returncode == 2
    assert result.stdout == b""
    assert b"snapshot" in result.stderr
