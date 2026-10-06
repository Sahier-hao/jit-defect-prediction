"""Explicit input contract for precomputed features; no repository mining."""

import csv
import io
import math
from dataclasses import dataclass
from datetime import datetime, timezone

FEATURES = (
    "ns",
    "nd",
    "nf",
    "entropy",
    "la",
    "ld",
    "lt",
    "fix",
    "ndev",
    "age",
    "nuc",
    "exp",
    "rexp",
    "sexp",
)
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 20_000


@dataclass(frozen=True)
class CommitRecord:
    commit_id: str
    committed_at: datetime
    label: int | None
    features: dict[str, float]
    message: str = ""


def parse_csv(
    contents: bytes, *, max_bytes=MAX_BYTES, max_rows=MAX_ROWS
) -> list[CommitRecord]:
    if len(contents) > max_bytes:
        raise ValueError(f"CSV size exceeds limit of {max_bytes} bytes")
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("CSV must use UTF-8 encoding") from error
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    required = {"commit_id", "committed_at", "label", *FEATURES}
    if not reader.fieldnames:
        raise ValueError("CSV requires a header and records")
    missing = required - set(reader.fieldnames)
    if missing:
        raise ValueError("Missing columns: " + ", ".join(sorted(missing)))
    if len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError("CSV contains duplicate columns")
    extra = set(reader.fieldnames) - required - {"message"}
    if extra:
        raise ValueError("Unexpected columns: " + ", ".join(sorted(extra)))
    records, seen = [], set()
    try:
        for line, row in enumerate(reader, start=2):
            if len(records) >= max_rows:
                raise ValueError(f"CSV row count exceeds limit of {max_rows}")
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Row {line}: column count does not match header")
            commit_id = row["commit_id"].strip()
            if (
                not commit_id
                or len(commit_id) > 128
                or "/" in commit_id
                or "\\" in commit_id
            ):
                raise ValueError(f"Row {line}: invalid commit_id")
            if commit_id in seen:
                raise ValueError(f"Row {line}: duplicate commit_id {commit_id}")
            seen.add(commit_id)
            try:
                timestamp = datetime.fromisoformat(
                    row["committed_at"].strip().replace("Z", "+00:00")
                )
                if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                    raise ValueError("timezone required")
                timestamp = timestamp.astimezone(timezone.utc)
            except ValueError as error:
                raise ValueError(
                    f"Row {line}: committed_at requires an ISO-8601 timestamp with timezone"
                ) from error
            label_text = row["label"].strip().lower()
            if label_text not in {"0", "1", "", "unknown"}:
                raise ValueError(f"Row {line}: label must be 0, 1, or unknown")
            label = int(label_text) if label_text in {"0", "1"} else None
            features = {}
            for name in FEATURES:
                try:
                    value = float(row[name])
                except ValueError as error:
                    raise ValueError(f"Row {line}: invalid {name}") from error
                if (
                    not math.isfinite(value)
                    or value < 0
                    or (name == "fix" and value not in (0, 1))
                ):
                    raise ValueError(
                        f"Row {line}: {name} must be finite, nonnegative"
                        + (" and 0 or 1" if name == "fix" else "")
                    )
                features[name] = value
            records.append(
                CommitRecord(
                    commit_id, timestamp, label, features, row.get("message", "")[:2000]
                )
            )
    except csv.Error as error:
        raise ValueError(f"Malformed CSV: {error}") from error
    if not records:
        raise ValueError("CSV contains no records")
    return sorted(records, key=lambda row: (row.committed_at, row.commit_id))
