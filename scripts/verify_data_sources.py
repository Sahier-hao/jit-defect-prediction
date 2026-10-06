"""Offline checks against independently retrieved upstream responses.

Run from the project root: python scripts/verify_data_sources.py
No network requests, Git commands, model training or writes are performed.
"""

import hashlib
import json
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

base = (
    Path(__file__).resolve().parents[1] / "docs/数据核查/activemq-2024-sample-20261004"
)
ledger = json.loads((base / "sources.json").read_text(encoding="utf-8"))
study = json.loads((base / "case-study.json").read_text(encoding="utf-8"))
assert len(ledger) == study["sourceCount"] == 15
for record in ledger:
    filename = record["file"]
    assert Path(filename).name == filename
    raw = (base / filename).read_bytes()
    assert record["status"] == 200
    assert len(raw) == record["bytes"]
    assert hashlib.sha256(raw).hexdigest() == record["sha256"], filename
assert sum(r["bytes"] for r in ledger) == study["sourceBytes"]

issues = {r["id"]: r for r in study["issues"]}
for key, item in issues.items():
    original = json.loads((base / (key + ".json")).read_text(encoding="utf-8"))
    fields = original["fields"]
    assert item["issueType"] == fields["issuetype"]["name"]
    assert item["status"] == fields["status"]["name"]
    assert item["resolution"] == (fields["resolution"] or {}).get("name")
    assert item["resolvedAt"] == fields["resolutiondate"]
    assert original["changelog"]["total"] == len(original["changelog"]["histories"])
    assert fields["comment"]["total"] == len(fields["comment"]["comments"])
    assert item["inducingCommitLabel"] == "unknown_szz_not_executed"
assert (issues["AMQ-9481"]["issueType"], issues["AMQ-9481"]["resolution"]) == (
    "Bug",
    "Fixed",
)
assert (issues["AMQ-9461"]["issueType"], issues["AMQ-9461"]["resolution"]) == (
    "Task",
    "Fixed",
)
assert issues["AMQ-9482"]["resolution"] is None

patch = (base / "fix-72befc14.patch").read_text(encoding="utf-8")
header = re.search(
    r"(\d+) files changed, (\d+) insertions\(\+\), (\d+) deletions\(-\)", patch
)
assert tuple(map(int, header.groups())) == (2, 17, 8)
assert study["diffChecks"]["rawAllPaths"] == {"NF": 2, "LA": 17, "LD": 8}
assert study["patches"][0]["messageIssueRefs"] == ["AMQ-9481"]
assert "AMQ-9330" in patch and "AMQ-9418" in patch

before = (
    (base / "parent-AsyncServletRequest.java.txt")
    .read_text(encoding="utf-8")
    .splitlines()
)
after = (
    (base / "fixed-AsyncServletRequest.java.txt")
    .read_text(encoding="utf-8")
    .splitlines()
)
old_changed = []
new_changed = []
for tag, a0, a1, b0, b1 in SequenceMatcher(
    a=before, b=after, autojunk=False
).get_opcodes():
    if tag != "equal":
        old_changed.extend(range(a0, a1))
        new_changed.extend(range(b0, b1))
assert len(old_changed) == len(new_changed) == 4
executable = [
    n + 1
    for n in old_changed
    if before[n].strip() and not before[n].lstrip().startswith("//")
]
comments = [n + 1 for n in old_changed if before[n].lstrip().startswith("//")]
assert (
    executable
    == study["diffChecks"]["oldExecutableLinesForLaterAttribution"]
    == [118, 121]
)
assert comments == study["diffChecks"]["excludedCommentLines"] == [119, 120]
assert before[120].strip() == "context.complete();"
assert after[120].strip() == "context.dispatch();"

case = study["availabilityCase"]


def parse(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


pr_html = (base / "pr-1206.html").read_text(encoding="utf-8")
merge_event = pr_html.split("merged commit <a", 1)[1]
assert (
    re.search(r'<relative-time datetime="([^"]+)"', merge_event)[1] == case["mergedAt"]
)
assert (
    parse(case["authoredAt"]) < parse("2024-04-22T00:00:00Z") < parse(case["mergedAt"])
)
assert parse(case["proposedPolicyAvailableAt"]) == max(
    parse(case["mergedAt"]), parse(case["issueFixedAt"])
)
assert case["issueFixedAt"] == issues["AMQ-9481"]["resolvedAt"]
assert study["commitMetadata"]["merge"]["parents"][1] == study["patches"][0]["sha"]
assert len(study["commitMetadata"]["merge"]["parents"]) == 2
assert study["patches"][1]["cherryPickedFrom"] == [study["patches"][0]["sha"]]
assert {c["id"] for c in study["cases"]} == {f"DATA-{n:02}" for n in range(1, 9)}

print(
    json.dumps(
        {
            "result": "PASS",
            "sourceFiles": 15,
            "historicalIssues": 4,
            "caseDesigns": 8,
            "rawDiffCounts": {"NF": 2, "LA": 17, "LD": 8},
            "verifiedOldExecutableLines": executable,
            "scope": "saved public evidence only; no SZZ, training, Git or product acceptance",
        },
        ensure_ascii=False,
    )
)
