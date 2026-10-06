"""Offline source preparation; repair candidates are never inducing labels."""

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from email import policy
from email.parser import Parser
from email.utils import parsedate_to_datetime
from pathlib import Path

MAX_SOURCE_BYTES = 2 * 1024 * 1024
ISSUE_KEY = re.compile(r"(?<![\w-])([A-Z][A-Z0-9]*-\d+)(?![\w-])")
HUNK_HEADER = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?")


def _text(contents: bytes, max_bytes: int = MAX_SOURCE_BYTES) -> str:
    if not contents or len(contents) > max_bytes:
        raise ValueError("source size is empty or exceeds limit")
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("source must be UTF-8") from exc
    if "\x00" in text:
        raise ValueError("unsupported NUL in source")
    return text.replace("\r\n", "\n")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include timezone")
    return value.astimezone(UTC)


@dataclass(frozen=True)
class DiffLine:
    kind: str
    text: str
    old_line: int | None
    new_line: int | None
    no_newline: bool = False


@dataclass(frozen=True)
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: tuple[DiffLine, ...]


@dataclass(frozen=True)
class FileDiff:
    path_before: str | None
    path_after: str | None
    hunks: tuple[Hunk, ...]

    @property
    def removed(self) -> tuple[DiffLine, ...]:
        return tuple(line for h in self.hunks for line in h.lines if line.kind == "-")

    @property
    def added(self) -> int:
        return sum(line.kind == "+" for h in self.hunks for line in h.lines)


@dataclass(frozen=True)
class CommitPatch:
    commit_id: str
    authored_at: datetime
    message: str
    issue_refs: tuple[str, ...]
    cherry_picked_from: tuple[str, ...]
    files: tuple[FileDiff, ...]

    @property
    def raw_counts(self) -> dict[str, int]:
        return {
            "NF": len(self.files),
            "LA": sum(file.added for file in self.files),
            "LD": sum(len(file.removed) for file in self.files),
        }


def _path(value: str) -> str:
    if (
        not value
        or any(char in value for char in '\\:"\t\r\n')
        or any(part in ("", ".", "..") for part in value.split("/"))
    ):
        raise ValueError("unsafe or unsupported path")
    return value


def _hunk(lines: list[str], cursor: int) -> tuple[Hunk, int]:
    match = HUNK_HEADER.fullmatch(lines[cursor])
    if not match:
        raise ValueError("malformed hunk header")
    old_start, old_count, new_start, new_count = (
        int(match[1]),
        int(match[2] or 1),
        int(match[3]),
        int(match[4] or 1),
    )
    if (old_count and not old_start) or (new_count and not new_start):
        raise ValueError("invalid hunk range")
    old_used = new_used = 0
    parsed = []
    cursor += 1
    while cursor < len(lines):
        line = lines[cursor]
        if line == "\\ No newline at end of file":
            if not parsed or parsed[-1].no_newline:
                raise ValueError("orphan hunk newline marker")
            parsed[-1] = replace(parsed[-1], no_newline=True)
            cursor += 1
            continue
        if old_used == old_count and new_used == new_count:
            break
        if not line or line[0] not in " +-" or line.startswith("@@"):
            raise ValueError("hunk line count mismatch")
        kind = line[0]
        old_line = old_start + old_used if kind != "+" else None
        new_line = new_start + new_used if kind != "-" else None
        old_used += kind != "+"
        new_used += kind != "-"
        if old_used > old_count or new_used > new_count:
            raise ValueError("hunk line count overflow")
        parsed.append(DiffLine(kind, line[1:], old_line, new_line))
        cursor += 1
    if old_used != old_count or new_used != new_count:
        raise ValueError("hunk line count mismatch")
    return Hunk(old_start, old_count, new_start, new_count, tuple(parsed)), cursor


def _file_diff(lines: list[str]) -> FileDiff:
    match = re.fullmatch(r'diff --git a/([^\s"]+) b/([^\s"]+)', lines[0])
    if not match:
        raise ValueError("unsupported diff path format")
    before, after = _path(match[1]), _path(match[2])
    if before != after:
        raise ValueError("unsupported rename/copy change")
    cursor = 1
    while cursor < len(lines) and not lines[cursor].startswith("--- "):
        metadata = lines[cursor]
        if not (
            re.fullmatch(r"index [0-9a-f]+\.\.[0-9a-f]+(?: 100(?:644|755))?", metadata)
            or re.fullmatch(r"(?:new|deleted) file mode 100(?:644|755)", metadata)
        ):
            raise ValueError("unsupported binary, rename/copy or mode-only change")
        cursor += 1
    if cursor + 1 >= len(lines) or not lines[cursor + 1].startswith("+++ "):
        raise ValueError("unsupported change without text file headers")
    old_header, new_header = lines[cursor][4:], lines[cursor + 1][4:]
    if old_header not in ("a/" + before, "/dev/null") or new_header not in (
        "b/" + after,
        "/dev/null",
    ):
        raise ValueError("diff path and file header mismatch")
    before = None if old_header == "/dev/null" else before
    after = None if new_header == "/dev/null" else after
    if before is None and after is None:
        raise ValueError("invalid null file paths")
    cursor += 2
    hunks = []
    old_end = new_end = 0
    while cursor < len(lines) and lines[cursor].startswith("@@"):
        hunk, cursor = _hunk(lines, cursor)
        old_index = hunk.old_start - bool(hunk.old_count)
        new_index = hunk.new_start - bool(hunk.new_count)
        if old_index < old_end or new_index < new_end:
            raise ValueError("overlapping or unordered hunk ranges")
        if new_index - old_index != new_end - old_end:
            raise ValueError("inconsistent old/new hunk offsets")
        if (before is None and hunk.old_count) or (after is None and hunk.new_count):
            raise ValueError("hunk counts contradict added/deleted file")
        old_end, new_end = old_index + hunk.old_count, new_index + hunk.new_count
        hunks.append(hunk)
    remainder = lines[cursor:]
    if remainder and remainder[0] == "-- ":
        remainder = remainder[2:]
    if not hunks or any(line.strip() for line in remainder):
        raise ValueError("unsupported trailing hunk data or change without hunks")
    if not any(line.kind in "+-" for hunk in hunks for line in hunk.lines):
        raise ValueError("unsupported change without added/deleted lines")
    return FileDiff(before, after, tuple(hunks))


def parse_patch(contents: bytes, *, max_bytes: int = MAX_SOURCE_BYTES) -> CommitPatch:
    """Parse one bounded email text patch, rejecting unsupported formats."""
    text = _text(contents, max_bytes)
    lines = text.split("\n")
    envelope = re.fullmatch(r"From ([0-9a-f]{40}|[0-9a-f]{64}) .+", lines[0])
    if not envelope or sum(line.startswith("From ") for line in lines) != 1:
        raise ValueError("expected a single email-format patch")
    starts = [i for i, line in enumerate(lines) if line.startswith("diff --git ")]
    if not starts:
        raise ValueError("unsupported patch without text diffs")
    prefix = "\n".join(lines[1 : starts[0]])
    email = Parser(policy=policy.default).parsestr(prefix)
    subject = str(email.get("Subject", "")).replace("\n", " ")
    subject = re.sub(r"^\[PATCH[^\]]*\]\s*", "", subject)
    if not subject.strip():
        raise ValueError("missing patch subject")
    try:
        authored_at = _utc(parsedate_to_datetime(str(email["Date"])))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid patch author timestamp with timezone") from exc
    body = re.split(r"(?m)^---$", str(email.get_payload()), maxsplit=1)[0].strip()
    message = subject.strip() + ("\n\n" + body if body else "")
    files = tuple(
        _file_diff(lines[start:end])
        for start, end in zip(starts, starts[1:] + [len(lines)])
    )
    paths = [file.path_after or file.path_before for file in files]
    if len(set(paths)) != len(paths):
        raise ValueError("duplicate diff path")
    origins = re.findall(
        r"\(cherry picked from commit ([0-9a-f]{40}|[0-9a-f]{64})\)", message
    )
    return CommitPatch(
        envelope[1],
        authored_at,
        message,
        tuple(dict.fromkeys(ISSUE_KEY.findall(message))),
        tuple(dict.fromkeys(origins)),
        files,
    )


def _time(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO string with timezone")
    try:
        return _utc(datetime.fromisoformat(value))
    except ValueError as exc:
        raise ValueError("invalid timestamp; ISO format and timezone required") from exc


def _qualified(state: dict) -> bool:
    return (
        state["issuetype"] == "Bug"
        and state["resolution"] == "Fixed"
        and state["status"] in ("Resolved", "Closed")
    )


def _named_field(fields: dict, key: str, *, nullable: bool = False) -> str | None:
    value = fields[key]
    if nullable and value is None:
        return None
    if not isinstance(value, dict) or not isinstance(value.get("name"), str):
        raise ValueError("invalid issue field: " + key)
    return value["name"]


def _issue_at(issue: dict, cutoff: datetime, snapshot: datetime) -> dict:
    """Reconstruct from full history, validating its chain against current fields."""
    try:
        fields = issue["fields"]
        key = issue["key"]
        if not isinstance(key, str) or not ISSUE_KEY.fullmatch(key):
            raise ValueError("invalid issue key")
        created = _time(fields["created"])
        current = {
            "issuetype": _named_field(fields, "issuetype"),
            "status": _named_field(fields, "status"),
            "resolution": _named_field(fields, "resolution", nullable=True),
        }
        result = {
            "key": key,
            "source": issue.get("self"),
            "stateAtCutoff": None,
            "qualifyingAt": None,
            "rawResolutionDate": fields.get("resolutiondate"),
            "historyComplete": False,
            "assessment": "unknown_incomplete_history",
        }
        if cutoff > snapshot:
            return {**result, "assessment": "unknown_snapshot_outdated"}
        if cutoff < created:
            return {**result, "assessment": "unknown_issue_not_created"}
        history = issue.get("changelog")
        if history is None:
            return result
        events = history["histories"]
        total, start = history["total"], history["startAt"]
        if (
            not isinstance(events, list)
            or type(total) is not int
            or type(start) is not int
            or total < 0
            or start < 0
        ):
            raise ValueError("invalid history pagination")
        if start != 0 or total != len(events):
            return result
        ids = set()
        transitions = []
        for event in events:
            event_id = event["id"]
            if not isinstance(event_id, str) or not event_id or event_id in ids:
                raise ValueError("invalid or duplicate history id")
            ids.add(event_id)
            at = _time(event["created"])
            if at < created or at > snapshot:
                raise ValueError("history event outside issue/snapshot times")
            changes = []
            changed_fields = set()
            if not isinstance(event["items"], list):
                raise ValueError("invalid history items")
            for item in event["items"]:
                field = item["field"].lower().replace(" ", "")
                if field not in current:
                    continue
                if field in changed_fields:
                    raise ValueError("duplicate field within history event")
                changed_fields.add(field)
                before, after = item["fromString"], item["toString"]
                if any(
                    value is not None and not isinstance(value, str)
                    for value in (before, after)
                ):
                    raise ValueError("invalid history field value")
                changes.append((field, before, after))
            transitions.append((at, changes))
        transitions.sort(key=lambda event: event[0])
        initial = current.copy()
        for _, changes in reversed(transitions):
            for field, before, after in reversed(changes):
                if initial[field] != after:
                    raise ValueError("history contradicts current field chain")
                initial[field] = before
        state = initial
        qualified_at = None
        for at, changes in transitions:
            if at > cutoff:
                break
            was_qualified = _qualified(state)
            for field, _, after in changes:
                state[field] = after
            if not _qualified(state):
                qualified_at = None
            elif not was_qualified:
                qualified_at = at
        if state["issuetype"] != "Bug":
            assessment = "excluded_non_bug"
        elif not _qualified(state):
            assessment = "unverified_issue_state"
        elif qualified_at is None:
            assessment = "unknown_qualification_time"
        else:
            assessment = "qualified_issue"
        return {
            **result,
            "stateAtCutoff": state,
            "historyComplete": True,
            "qualifyingAt": qualified_at.isoformat() if qualified_at else None,
            "assessment": assessment,
        }
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("invalid issue/history structure") from exc


def prepare_fix(
    patch_contents: bytes,
    issue_contents: bytes,
    *,
    as_of: str,
    snapshot_at: str,
    target_branch: str,
    integrated_at: str | None = None,
    integration_source: str | None = None,
) -> dict:
    """Screen one repair with historical issue state and asserted branch evidence.

    Integration metadata is supplied by the caller and needs independent review.
    Historical reconstruction does not establish historical collection/observation.
    """
    cutoff, snapshot = _time(as_of), _time(snapshot_at)
    integrated = _time(integrated_at) if integrated_at is not None else None
    if not isinstance(target_branch, str) or not target_branch.strip():
        raise ValueError("target branch is required")
    if integration_source is not None and not isinstance(integration_source, str):
        raise ValueError("integration source must be a string")
    patch = parse_patch(patch_contents)
    try:
        issue = json.loads(_text(issue_contents))
    except json.JSONDecodeError as exc:
        raise ValueError("invalid issue JSON") from exc
    assessment = _issue_at(issue, cutoff, snapshot)
    status = assessment["assessment"]
    available_at = None
    if status == "qualified_issue":
        if assessment["key"] not in patch.issue_refs:
            status = "unlinked_issue"
        elif (
            integrated is None
            or not integration_source
            or not integration_source.strip()
        ):
            status = "unknown_integration"
        else:
            available_at = max(integrated, _time(assessment["qualifyingAt"]))
            status = "candidate" if available_at <= cutoff else "unknown_not_integrated"
    return {
        "formatVersion": 1,
        "kind": "offline_fix_preparation",
        "policyVersion": "jira-history-and-integration-v1",
        "asOf": cutoff.isoformat(),
        "snapshotAt": snapshot.isoformat(),
        "observation": "historical_reconstruction_not_historic_collection",
        "sources": {
            "patchSha256": hashlib.sha256(patch_contents).hexdigest(),
            "issueSha256": hashlib.sha256(issue_contents).hexdigest(),
        },
        "patch": {
            "commitId": patch.commit_id,
            "authoredAt": patch.authored_at.isoformat(),
            "message": patch.message,
            "issueRefs": list(patch.issue_refs),
            "cherryPickedFrom": list(patch.cherry_picked_from),
            "rawCounts": patch.raw_counts,
            "files": [
                {
                    "pathBefore": file.path_before,
                    "pathAfter": file.path_after,
                    "LA": file.added,
                    "LD": len(file.removed),
                    "removed": [asdict(line) for line in file.removed],
                }
                for file in patch.files
            ],
        },
        "issue": assessment,
        "integration": {
            "targetBranch": target_branch,
            "integratedAt": integrated.isoformat() if integrated else None,
            "source": integration_source,
            "verification": "caller_supplied_requires_review",
        },
        "candidate": {
            "status": status,
            "availableAt": available_at.isoformat() if available_at else None,
        },
        "inducingLabel": None,
        "labelStatus": "unknown_szz_not_executed",
        "kamei14": None,
        "attributionPolicy": "pending_file_and_comment_review",
    }


def _read_source(path: Path) -> bytes:
    with path.open("rb") as stream:
        return stream.read(MAX_SOURCE_BYTES + 1)


def main(argv: list[str] | None = None) -> int:
    """Read local sources and emit JSON only; errors produce no report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--issue", type=Path, required=True)
    parser.add_argument("--as-of", required=True, help="Aware ISO cutoff")
    parser.add_argument("--snapshot-at", required=True, help="Jira retrieval time")
    parser.add_argument("--target-branch", required=True)
    parser.add_argument("--integrated-at", help="Explicit branch integration time")
    parser.add_argument("--integration-source", help="Integration evidence reference")
    args = parser.parse_args(argv)
    try:
        report = prepare_fix(
            _read_source(args.patch),
            _read_source(args.issue),
            as_of=args.as_of,
            snapshot_at=args.snapshot_at,
            target_branch=args.target_branch,
            integrated_at=args.integrated_at,
            integration_source=args.integration_source,
        )
        report["sources"].update(
            {
                "patchPath": args.patch.as_posix(),
                "issuePath": args.issue.as_posix(),
            }
        )
    except (OSError, ValueError) as exc:
        print("preparation error: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
