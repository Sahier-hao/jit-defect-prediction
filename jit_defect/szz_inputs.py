"""Whole-parent Java old-line inputs; no blame, inducing labels or Git execution."""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from .preparation import FileDiff, _path, _text, parse_patch
from .preparation_batch import (
    MAX_ITEMS,
    MAX_TOTAL_BYTES,
    _confined,
    _fields,
    _hash,
    _json,
    _read,
    _Sources,
    _string,
    prepare_batch,
    read_snapshot,
    write_snapshot,
)

POLICY_VERSION = "java-production-old-lines-v1"


def _lines(contents: bytes) -> list[str]:
    text = _text(contents)
    if "\r" in text:
        raise ValueError("unsupported lone CR line terminator")
    parts = text.split("\n")
    return [part + "\n" for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def classify_java(contents: bytes) -> list[str]:
    """Classify physical lines, conservatively refusing Unicode preprocessing.

    This bounded lexical scanner is not a Java parser or compiler. Text-block
    content, including blank lines, belongs to a literal and is retained.
    """
    lines = _lines(contents)
    if re.search(r"\\u", "".join(lines)):
        raise ValueError("unsupported Java Unicode escape preprocessing")
    state = "normal"
    result = []
    for line in lines:
        code = state == "text_block"
        comment = state == "block_comment"
        i = 0
        while i < len(line):
            char = line[i]
            if state == "block_comment":
                comment = True
                if line.startswith("*/", i):
                    state = "normal"
                    i += 2
                else:
                    i += 1
            elif state == "text_block":
                code = True
                if char == "\\":
                    i += 2
                elif line.startswith('"""', i):
                    state = "normal"
                    i += 3
                else:
                    i += 1
            elif state in ("string", "character"):
                code = True
                quote = '"' if state == "string" else "'"
                if char == "\n":
                    raise ValueError("unterminated Java literal")
                if char == "\\":
                    if i + 1 >= len(line) or line[i + 1] == "\n":
                        raise ValueError("unterminated Java literal")
                    i += 2
                elif char == quote:
                    state = "normal"
                    i += 1
                else:
                    i += 1
            elif line.startswith("//", i):
                comment = True
                break
            elif line.startswith("/*", i):
                comment = True
                state = "block_comment"
                i += 2
            elif line.startswith('"""', i):
                if not re.fullmatch(r"[ \t\f]*\n", line[i + 3 :]):
                    raise ValueError("unsupported Java text block opening")
                code = True
                state = "text_block"
                break
            elif char in ('"', "'"):
                code = True
                state = "string" if char == '"' else "character"
                i += 1
            else:
                code |= char not in " \t\f\n"
                i += 1
        if state in ("string", "character"):
            raise ValueError("unterminated Java literal")
        result.append("code" if code else "comment" if comment else "blank")
    if state != "normal":
        raise ValueError("unterminated Java comment or text block")
    return result


def verify_file_diff(file: FileDiff, parent: bytes, fixed: bytes) -> list[str]:
    """Rebuild all fixed text, checking context and exact terminal newlines."""
    old = _lines(parent)
    expected = _lines(fixed)
    result = []
    cursor = 0
    for hunk in file.hunks:
        start = hunk.old_start - 1 if hunk.old_count else hunk.old_start
        if start < cursor or start > len(old):
            raise ValueError("hunk range exceeds parent or overlaps")
        result.extend(old[cursor:start])
        cursor = start
        new_start = len(result) + 1 if hunk.new_count else len(result)
        if hunk.new_start != new_start:
            raise ValueError("hunk new range mismatch")
        for line in hunk.lines:
            raw = line.text + ("" if line.no_newline else "\n")
            if line.old_line is not None:
                if (
                    cursor >= len(old)
                    or line.old_line != cursor + 1
                    or old[cursor] != raw
                ):
                    raise ValueError("parent hunk context or terminal newline mismatch")
                cursor += 1
            if line.new_line is not None:
                if line.new_line != len(result) + 1:
                    raise ValueError("hunk new line mismatch")
                result.append(raw)
    result.extend(old[cursor:])
    if result != expected:
        raise ValueError("reconstructed fixed file mismatch")
    return old


def file_policy(path: str) -> str | None:
    """Maven-style attribution scope, independent from Kamei feature scope."""
    parts = _path(path).split("/")
    if any(parts[i : i + 2] == ["src", "test"] for i in range(len(parts) - 1)):
        return "excluded_test_path"
    if not path.endswith(".java"):
        return "excluded_non_java"
    if not any(
        parts[i : i + 3] == ["src", "main", "java"] for i in range(len(parts) - 3)
    ):
        return "excluded_outside_production_root"
    return None


def _bindings(manifest: dict) -> dict:
    _fields(
        manifest,
        {
            "formatVersion",
            "batchManifest",
            "batchSnapshot",
            "recordId",
            "parentCommit",
            "files",
        },
    )
    if type(manifest["formatVersion"]) is not int or manifest["formatVersion"] != 1:
        raise ValueError("unsupported input manifest version")
    _string(manifest["recordId"], "record id", r"[A-Za-z0-9_.-]{1,128}")
    _string(manifest["parentCommit"], "parent commit", r"(?:[a-f0-9]{40}|[a-f0-9]{64})")
    rows = manifest["files"]
    if not isinstance(rows, list) or len(rows) > MAX_ITEMS:
        raise ValueError("invalid or excessive file bindings")
    result = {}
    for row in rows:
        _fields(row, {"path", "parent", "fixed"})
        path = _path(_string(row["path"], "file path", r"[^\x00]{1,4096}"))
        if path in result:
            raise ValueError("duplicate file binding")
        for key in ("parent", "fixed"):
            _string(row[key], "source file key", r"[^/\\:\x00]{1,255}")
        result[path] = row
    return result


def _file_source(
    sources: _Sources, name: str, repository: str, commit: str, path: str
) -> bytes:
    raw = sources.read(name)
    expected_url = f"https://raw.githubusercontent.com/{repository}/{commit}/{path}"
    if sources.verified[name]["url"] != expected_url:
        raise ValueError("file source URL does not bind repository, commit and path")
    return raw


def prepare_inputs(manifest_path: Path) -> dict:
    """Verify all evidence before returning a complete derived input body."""
    manifest_path = Path(manifest_path)
    raw_manifest = _read(manifest_path)
    manifest = _json(raw_manifest)
    bindings = _bindings(manifest)
    root = manifest_path.parent.resolve()
    batch_path = _confined(root, manifest["batchManifest"])
    snapshot_path = _confined(root, manifest["batchSnapshot"])
    batch = read_snapshot(snapshot_path)
    if prepare_batch(batch_path) != batch:
        raise ValueError("recomputed batch snapshot differs from saved evidence")
    records = [row for row in batch["records"] if row["id"] == manifest["recordId"]]
    if len(records) != 1 or records[0]["status"] != "candidate":
        raise ValueError("selected record is not a qualified candidate")
    record = records[0]
    report = record["report"]
    batch_manifest = _json(_read(batch_path))
    ledger_path = _confined(batch_path.parent, batch_manifest["sourceLedger"]["path"])
    raw_ledger = _read(ledger_path)
    if _hash(raw_ledger) != batch["provenance"]["ledgerSha256"]:
        raise ValueError("source ledger changed during preparation")
    sources = _Sources(ledger_path.parent, _json(raw_ledger), MAX_TOTAL_BYTES)
    original = next(
        row["input"] for row in batch["inputs"] if row["id"] == record["id"]
    )
    raw_patch = sources.read(original["patch"])
    if _hash(raw_patch) != report["sources"]["patchSha256"]:
        raise ValueError("patch identity changed during preparation")
    patch = parse_patch(raw_patch)
    if patch.commit_id != report["patch"]["commitId"]:
        raise ValueError("patch commit identity mismatch")
    parent_commit = manifest["parentCommit"]
    if parent_commit == patch.commit_id:
        raise ValueError("parent differs from fix commit")
    required = set()
    for file in patch.files:
        if file.path_before and file.removed and file_policy(file.path_before) is None:
            if file.path_after != file.path_before:
                raise ValueError("unsupported production file deletion or path change")
            required.add(file.path_before)
    if set(bindings) != required:
        raise ValueError(
            "file bindings must exactly cover eligible removed production files"
        )
    decisions, evidence = [], []
    repository = batch["config"]["repository"]
    for file in patch.files:
        path = file.path_before or file.path_after
        reason = file_policy(path)
        if file.path_before is None:
            continue  # New files have no old lines.
        if reason is None and file.removed:
            binding = bindings[path]
            parent = _file_source(
                sources, binding["parent"], repository, parent_commit, path
            )
            fixed = _file_source(
                sources, binding["fixed"], repository, patch.commit_id, path
            )
            verify_file_diff(file, parent, fixed)
            classes = classify_java(parent)
            evidence.append(
                {
                    "path": path,
                    "parent": binding["parent"],
                    "fixed": binding["fixed"],
                    "reconstruction": "verified",
                }
            )
        for line in file.removed:
            selected_reason = (
                reason
                or {
                    "code": "selected_non_comment",
                    "comment": "excluded_comment",
                    "blank": "excluded_blank",
                }[classes[line.old_line - 1]]
            )
            decisions.append(
                {
                    "path": path,
                    "oldLine": line.old_line,
                    "text": line.text,
                    "noNewline": line.no_newline,
                    "reason": selected_reason,
                }
            )
    targets = [
        dict(row, parentCommit=parent_commit)
        for row in decisions
        if row["reason"] == "selected_non_comment"
    ]
    counts = Counter(row["reason"] for row in decisions)
    raw = patch.raw_counts
    if len(decisions) != raw["LD"]:
        raise ValueError("removed line accounting mismatch")
    return {
        "formatVersion": 1,
        "kind": "offline_preparation_snapshot",
        "stage": "java_szz_inputs",
        "policyVersion": POLICY_VERSION,
        "preparationStatus": "prepared",
        "selectionStatus": "targets_prepared"
        if targets
        else "no_eligible_removed_lines",
        "datasetStatus": "not_training_ready",
        "trainingReady": False,
        "inducingLabel": None,
        "labelStatus": "unknown_szz_not_executed",
        "kamei14": None,
        "config": batch["config"],
        "configVerification": batch["configVerification"],
        "recordId": record["id"],
        "issueKey": report["issue"]["key"],
        "fixCommit": patch.commit_id,
        "candidateAvailableAt": report["candidate"]["availableAt"],
        "parentCommit": parent_commit,
        "parentVerification": "caller_supplied_requires_ancestry_review",
        "provenance": {
            "manifestSha256": _hash(raw_manifest),
            "batchSnapshotId": snapshot_path.stem,
            "batchManifestSha256": batch["provenance"]["manifestSha256"],
            "ledgerSha256": _hash(raw_ledger),
        },
        "sources": [sources.verified[key] for key in sorted(sources.verified)],
        "fileEvidence": evidence,
        "decisions": decisions,
        "targets": targets,
        "quality": {
            "rawFiles": raw["NF"],
            "rawAdded": raw["LA"],
            "rawRemoved": raw["LD"],
            "selectedFiles": len({row["path"] for row in targets}),
            "selectedLines": len(targets),
            "excludedLines": len(decisions) - len(targets),
            "byReason": dict(sorted(counts.items())),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        body = prepare_inputs(args.manifest)
        destination = write_snapshot(body, args.snapshot_dir)
    except (OSError, ValueError) as exc:
        print("Preparation failed: " + str(exc), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "snapshot": str(destination),
                "snapshotId": destination.stem,
                "selectedLines": body["quality"]["selectedLines"],
                "excludedLines": body["quality"]["excludedLines"],
                "trainingReady": False,
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
