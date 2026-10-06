import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "docs/数据核查/activemq-2024-sample-20261004"


def command(patch=None, issue=None, *, cutoff="2024-04-23T00:00:00Z"):
    return [
        sys.executable,
        "-m",
        "jit_defect.preparation",
        "--patch",
        str(patch or SAMPLES / "fix-72befc14.patch"),
        "--issue",
        str(issue or SAMPLES / "AMQ-9481.json"),
        "--as-of",
        cutoff,
        "--snapshot-at",
        "2026-10-04T02:29:03Z",
        "--target-branch",
        "main",
        "--integrated-at",
        "2024-04-22T15:01:36Z",
        "--integration-source",
        "https://github.com/apache/activemq/pull/1206",
    ]


def run(args):
    return subprocess.run(args, cwd=ROOT, capture_output=True, timeout=15)


def test_json_cli_matches_exact_saved_sources_and_does_not_modify_them():
    paths = [SAMPLES / "fix-72befc14.patch", SAMPLES / "AMQ-9481.json"]
    before = [path.read_bytes() for path in paths]
    result = run(command())
    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout, "offline JSON command is missing"
    report = json.loads(result.stdout)
    assert report["formatVersion"] == 1
    assert report["candidate"]["status"] == "candidate"
    assert report["patch"]["rawCounts"] == {"NF": 2, "LA": 17, "LD": 8}
    assert report["sources"]["patchSha256"] == hashlib.sha256(before[0]).hexdigest()
    assert report["sources"]["issueSha256"] == hashlib.sha256(before[1]).hexdigest()
    assert report["sources"]["patchPath"] == paths[0].as_posix()
    assert report["inducingLabel"] is None
    assert [path.read_bytes() for path in paths] == before
    assert result.stderr == b""


@pytest.mark.parametrize("bad_input", ["patch", "json", "timestamp", "missing_file"])
def test_invalid_cli_input_has_nonzero_status_and_no_report(tmp_path, bad_input):
    patch = issue = None
    cutoff = "2024-04-23T00:00:00Z"
    if bad_input == "timestamp":
        cutoff = "2024-04-23"
    elif bad_input == "missing_file":
        patch = tmp_path / "missing.patch"
    elif bad_input == "patch":
        patch = tmp_path / "broken.patch"
        patch.write_bytes(b"not an email patch")
    else:
        issue = tmp_path / "broken.json"
        issue.write_bytes(b"{bad json")
    result = run(command(patch, issue, cutoff=cutoff))
    assert result.returncode == 2
    assert result.stdout == b""
    assert b"preparation error:" in result.stderr
    assert b"Traceback" not in result.stderr


def test_missing_integration_is_a_successful_unknown_report():
    args = command()
    del args[-4:]
    result = run(args)
    assert result.returncode == 0
    assert result.stdout, "offline JSON command is missing"
    assert json.loads(result.stdout)["candidate"]["status"] == "unknown_integration"
