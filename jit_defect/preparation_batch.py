"""Source-verified offline batches; preparation snapshots are not training data."""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from .preparation import MAX_SOURCE_BYTES, _time, prepare_fix

MAX_ITEMS = 1000
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024
SHA256 = re.compile(r"[a-f0-9]{64}")


class SourceError(ValueError):
    """One source failed integrity or retrieval checks; retain its item outcome."""


def _canonical(value: dict) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _hash(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def _json(contents: bytes):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON field: " + key)
            result[key] = value
        return result

    try:
        return json.loads(contents.decode("utf-8-sig"), object_pairs_hook=unique)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid UTF-8 JSON") from exc


def _read(path: Path) -> bytes:
    with path.open("rb") as stream:
        contents = stream.read(MAX_SOURCE_BYTES + 1)
    if not contents or len(contents) > MAX_SOURCE_BYTES:
        raise ValueError("source size limit exceeded or empty source")
    return contents


def _fields(value, required: set[str], optional: set[str] = frozenset()):
    if (
        not isinstance(value, dict)
        or not required <= value.keys()
        or value.keys() - (required | optional)
    ):
        raise ValueError("invalid or unexpected manifest fields")


def _string(value, label: str, pattern: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError("invalid " + label)
    return value


def _confined(root: Path, relative: str) -> Path:
    if (
        not isinstance(relative, str)
        or not relative
        or any(char in relative for char in "\\:\x00")
        or any(part in ("", ".", "..") for part in relative.split("/"))
    ):
        raise ValueError("unsafe relative source path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("source path escapes manifest directory")
    return path


def _manifest(value: dict) -> dict:
    _fields(
        value,
        {
            "formatVersion",
            "repository",
            "targetBranch",
            "sourceRef",
            "asOf",
            "sourceLedger",
            "items",
        },
    )
    if type(value["formatVersion"]) is not int or value["formatVersion"] != 1:
        raise ValueError("unsupported manifest version")
    _string(value["repository"], "repository", r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
    _string(value["targetBranch"], "target branch", r"[A-Za-z0-9_./-]{1,255}")
    _string(value["sourceRef"], "sourceRef", r"(?:[a-f0-9]{40}|[a-f0-9]{64})")
    _time(value["asOf"])
    _fields(value["sourceLedger"], {"path", "sha256"})
    _string(value["sourceLedger"]["sha256"], "ledger hash", SHA256.pattern)
    items = value["items"]
    if not isinstance(items, list) or not items:
        raise ValueError("items must be a nonempty list")
    if len(items) > MAX_ITEMS:
        raise ValueError("item limit exceeded")
    ids = set()
    for item in items:
        _fields(item, {"id", "patch", "issue"}, {"integration"})
        item_id = _string(item["id"], "input id", r"[A-Za-z0-9_.-]{1,128}")
        if item_id in ids:
            raise ValueError("duplicate input id")
        ids.add(item_id)
        for key in ("patch", "issue"):
            _string(item[key], "source file key", r"[^/\\:\x00]{1,255}")
            if item[key] in (".", ".."):
                raise ValueError("unsafe source path")
        integration = item.get("integration")
        if integration is not None:
            _fields(integration, {"branch"}, {"integratedAt", "source"})
            _string(
                integration["branch"], "integration branch", r"[A-Za-z0-9_./-]{1,255}"
            )
            if integration.get("integratedAt") is not None:
                _time(integration["integratedAt"])
            if integration.get("source") is not None:
                _string(integration["source"], "source file key", r"[^/\\:\x00]{1,255}")
    return value


class _Sources:
    def __init__(self, root: Path, rows: list, max_total_bytes: int):
        if not isinstance(rows, list) or not rows:
            raise ValueError("invalid source ledger")
        self.root = root
        self.rows = {}
        self.cache = {}
        self.verified = {}
        self.used_bytes = 0
        self.max_total_bytes = max_total_bytes
        for row in rows:
            if not isinstance(row, dict) or "file" not in row:
                raise ValueError("invalid ledger fields")
            name = _string(row["file"], "ledger file key", r"[^/\\:\x00]{1,255}")
            _confined(root, name)
            if name in self.rows:
                raise ValueError("duplicate ledger file key")
            self.rows[name] = row

    def read(self, name: str) -> bytes:
        if name in self.cache:
            contents = self.cache[name]
            if isinstance(contents, SourceError):
                raise contents
            return contents
        try:
            row = self.rows[name]
            if type(row.get("status")) is not int or row["status"] != 200:
                raise SourceError("unsuccessful retrieval: " + name)
            expected_size = row["bytes"]
            if (
                type(expected_size) is not int
                or not 0 < expected_size <= MAX_SOURCE_BYTES
            ):
                raise SourceError("invalid source byte count: " + name)
            expected_hash = _string(row["sha256"], "source hash", SHA256.pattern)
            _time(row["fetchedAt"])
            url = urlsplit(row["url"])
            if (
                url.scheme not in ("http", "https")
                or not url.hostname
                or url.username
                or url.password
            ):
                raise SourceError("invalid public source URL: " + name)
            try:
                remaining = self.max_total_bytes - self.used_bytes
                if remaining <= 0:
                    raise RuntimeError("unique source byte budget exceeded")
                with _confined(self.root, name).open("rb") as stream:
                    contents = stream.read(min(MAX_SOURCE_BYTES, remaining) + 1)
            except (OSError, ValueError) as exc:
                raise SourceError(
                    "source read failed: " + name + ": " + str(exc)
                ) from exc
            self.used_bytes += len(contents)
            if self.used_bytes > self.max_total_bytes:
                raise RuntimeError("unique source byte budget exceeded")
            if not contents or len(contents) > MAX_SOURCE_BYTES:
                raise SourceError("source size limit exceeded or empty source: " + name)
            if len(contents) != expected_size or _hash(contents) != expected_hash:
                raise SourceError(
                    "source hash/bytes mismatch: "
                    + name
                    + "; actual SHA-256="
                    + _hash(contents)
                )
            self.cache[name] = contents
            self.verified[name] = {
                "file": name,
                "url": row["url"],
                "bytes": len(contents),
                "sha256": expected_hash,
                "fetchedAt": row["fetchedAt"],
            }
            return contents
        except RuntimeError as exc:
            raise ValueError(str(exc)) from exc
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            error = (
                exc
                if isinstance(exc, SourceError)
                else SourceError("invalid source metadata: " + name + ": " + str(exc))
            )
            self.cache[name] = error
            if error is exc:
                raise
            raise error from exc


def prepare_batch(
    manifest_path: Path, *, max_total_bytes: int = MAX_TOTAL_BYTES
) -> dict:
    """Process saved sources without modifying them; preserve every item outcome."""
    manifest_path = Path(manifest_path)
    raw_manifest = _read(manifest_path)
    manifest = _manifest(_json(raw_manifest))
    root = manifest_path.parent.resolve()
    ledger_path = _confined(root, manifest["sourceLedger"]["path"])
    raw_ledger = _read(ledger_path)
    if _hash(raw_ledger) != manifest["sourceLedger"]["sha256"]:
        raise ValueError("source ledger hash mismatch")
    sources = _Sources(ledger_path.parent, _json(raw_ledger), max_total_bytes)
    outcomes, records, identities = [], [], {}
    reasons = Counter()
    duplicates = failed = 0
    for item in sorted(manifest["items"], key=lambda row: row["id"]):
        integration = item.get("integration") or {}
        try:
            patch, issue = sources.read(item["patch"]), sources.read(item["issue"])
            evidence = integration.get("source")
            if evidence:
                sources.read(evidence)
            integration_ref = sources.verified[evidence]["url"] if evidence else None
        except SourceError as exc:
            failed += 1
            reasons["source_error"] += 1
            outcomes.append(
                {"id": item["id"], "status": "source_error", "diagnostic": str(exc)}
            )
            continue
        try:
            report = prepare_fix(
                patch,
                issue,
                as_of=manifest["asOf"],
                snapshot_at=sources.verified[item["issue"]]["fetchedAt"],
                target_branch=manifest["targetBranch"],
                integrated_at=integration.get("integratedAt"),
                integration_source=integration_ref,
            )
        except ValueError as exc:
            failed += 1
            reasons["parse_error"] += 1
            outcomes.append(
                {"id": item["id"], "status": "parse_error", "diagnostic": str(exc)}
            )
            continue
        if integration and integration["branch"] != manifest["targetBranch"]:
            report["candidate"] = {"status": "excluded_branch", "availableAt": None}
        report["integration"]["assertedBranch"] = integration.get("branch")
        identity = (report["patch"]["commitId"], report["issue"]["key"])
        if identity in identities:
            retained = identities[identity]
            if report != retained["report"]:
                raise ValueError("conflicting duplicate evidence: " + item["id"])
            duplicates += 1
            outcomes.append(
                {"id": item["id"], "status": "duplicate", "duplicateOf": retained["id"]}
            )
            continue
        status = report["candidate"]["status"]
        record = {"id": item["id"], "status": status, "report": report}
        identities[identity] = record
        records.append(record)
        reasons[status] += 1
        outcomes.append({"id": item["id"], "status": status, "recordId": item["id"]})
    candidates = sum(row["status"] == "candidate" for row in records)
    excluded = sum(
        row["status"].startswith("excluded_") or row["status"] == "unlinked_issue"
        for row in records
    )
    quality = {
        "submitted": len(outcomes),
        "duplicates": duplicates,
        "unique": len(records) + failed,
        "parsed": len(records),
        "failed": failed,
        "candidates": candidates,
        "excluded": excluded,
        "unknown": len(records) - candidates - excluded,
        "byReason": dict(sorted(reasons.items())),
        "rawDiffTotals": {
            key: sum(row["report"]["patch"]["rawCounts"][key] for row in records)
            for key in ("NF", "LA", "LD")
        },
    }
    assert quality["submitted"] == quality["unique"] + duplicates
    assert quality["unique"] == quality["parsed"] + failed
    original_inputs = {item["id"]: item for item in manifest["items"]}
    for outcome in outcomes:
        outcome["input"] = original_inputs[outcome["id"]]
    return {
        "formatVersion": 1,
        "kind": "offline_preparation_snapshot",
        "policyVersion": "batch-source-verification-v1",
        "preparationStatus": "prepared_with_errors" if failed else "prepared",
        "datasetStatus": "not_training_ready",
        "trainingReady": False,
        "config": {
            key: manifest[key]
            for key in ("repository", "targetBranch", "sourceRef", "asOf")
        },
        "configVerification": "caller_supplied_requires_ancestry_and_integration_review",
        "provenance": {
            "manifestSha256": _hash(raw_manifest),
            "ledgerSha256": _hash(raw_ledger),
            "ledgerPath": manifest["sourceLedger"]["path"],
        },
        "sources": [sources.verified[name] for name in sorted(sources.verified)],
        "inputs": outcomes,
        "records": records,
        "quality": quality,
    }


def snapshot_id(body: dict) -> str:
    """Return the content ID for the exact canonical preparation body."""
    return _hash(_canonical(body))


def _envelope(body: dict) -> bytes:
    if (
        not isinstance(body, dict)
        or type(body.get("formatVersion")) is not int
        or body.get("formatVersion") != 1
        or body.get("kind") != "offline_preparation_snapshot"
        or body.get("trainingReady") is not False
    ):
        raise ValueError("invalid preparation snapshot body")
    contents = _canonical({"snapshotId": snapshot_id(body), "body": body}) + b"\n"
    if len(contents) > MAX_SNAPSHOT_BYTES:
        raise ValueError("snapshot size limit exceeded")
    return contents


def read_snapshot(path: Path, *, max_bytes: int = MAX_SNAPSHOT_BYTES) -> dict:
    """Verify the filename, body identity and exact canonical file bytes."""
    path = Path(path)
    if path.suffix != ".json" or not SHA256.fullmatch(path.stem) or path.is_symlink():
        raise ValueError("invalid snapshot path or identity")
    with path.open("rb") as stream:
        raw = stream.read(max_bytes + 1)
    if not raw or len(raw) > max_bytes:
        raise ValueError("snapshot size limit exceeded or empty file")
    try:
        envelope = _json(raw)
        if not isinstance(envelope, dict) or set(envelope) != {"snapshotId", "body"}:
            raise ValueError("invalid snapshot envelope")
        body = envelope["body"]
        if envelope["snapshotId"] != path.stem or snapshot_id(body) != path.stem:
            raise ValueError("snapshot content identity mismatch")
        if raw != _envelope(body):
            raise ValueError("snapshot canonical bytes mismatch")
    except (TypeError, KeyError, ValueError) as exc:
        raise ValueError("invalid snapshot: " + str(exc)) from exc
    return body


def write_snapshot(body: dict, folder: Path) -> Path:
    """Atomically publish a complete snapshot, verifying existing IDs on reuse.

    Requires a filesystem supporting atomic no-replace hard-link creation.
    Any failure removes only the temporary file created by this operation.
    """
    contents = _envelope(body)
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / (snapshot_id(body) + ".json")
    if destination.exists():
        if read_snapshot(destination) != body:
            raise ValueError("existing snapshot differs from requested content")
        return destination
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=folder,
            prefix=".preparation-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if read_snapshot(destination) != body:
                raise ValueError("concurrent snapshot differs from requested content")
        return destination
    finally:
        if temporary is not None:
            if not temporary.resolve().is_relative_to(folder):
                raise ValueError("owned temporary snapshot path escaped its directory")
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Prepare a saved-source manifest")
    prepare.add_argument("--manifest", type=Path, required=True)
    prepare.add_argument("--snapshot-dir", type=Path, required=True)
    verify = commands.add_parser("verify", help="Verify an existing snapshot")
    verify.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            body = prepare_batch(args.manifest)
            path = write_snapshot(body, args.snapshot_dir)
        else:
            path = args.snapshot
            body = read_snapshot(path)
        summary = {
            "snapshotId": snapshot_id(body),
            "snapshotPath": path.as_posix(),
            "preparationStatus": body.get("preparationStatus"),
            "trainingReady": body["trainingReady"],
            "quality": body.get("quality"),
        }
        if args.command == "verify":
            summary["result"] = "VERIFIED"
        print(json.dumps(summary, ensure_ascii=True, indent=2))
        return int(
            args.command == "prepare"
            and body["preparationStatus"] == "prepared_with_errors"
        )
    except (OSError, ValueError) as exc:
        print("batch preparation error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
