"""Check current document links, scope consistency and saved source hashes.

Run: python scripts/verify_docs.py
Historical browser results are read as historical evidence, never rerun here.
"""

import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote

root = Path(__file__).resolve().parents[1]
report_path = root / "docs/验证记录/目录整理检查结果.json"
prd = (root / "docs/需求与设计/产品需求文档.md").read_text(encoding="utf-8")
rows = [x for x in prd.splitlines() if re.match(r"\| \d+ \|.*\*\*US-", x)]
ids, priorities, incomplete = [], Counter(), []
for row in rows:
    cells = row.split("|")
    assert len(cells) == 7, row
    sid = re.search(r"\*\*US-([\d.]+)\*\*", cells[3]).group(1)
    ids.append(sid)
    priority = re.search(r"\*\*(P[012])\*\*", cells[4]).group(1)
    priorities[priority] += 1
    criteria = cells[4].split("**验收（草案）**：", 1)
    if (
        len(criteria) != 2
        or criteria[1].count("WHEN") < 2
        or criteria[1].count("THEN") < 2
    ):
        incomplete.append(sid)
assert len(ids) == len(set(ids)) == 42
assert priorities == {"P0": 18, "P1": 17, "P2": 7}, priorities
assert not incomplete, incomplete
business_core = sum(
    1
    for r in rows
    if not re.search(r"\*\*US-6\.", r) and re.search(r"\*\*P[01]\*\*", r)
)
assert business_core == 32

plan = json.loads(
    (root / "docs/团队协作/评审/准备计划.json").read_text(encoding="utf-8")
)
assert plan["status"] == "draft" and plan["scopeVersion"] == "v0.6"
assert plan["summary"] == {
    "firstMvpBusinessStories": 16,
    "coreBusinessStories": 24,
    "coreProcessStories": 2,
    "deferredStories": 16,
    "backlogStories": 42,
}
story_map = {item["id"]: item for item in plan["stories"]}
assert len(story_map) == len(plan["stories"]) == 42
assert set(story_map) == {"US-" + sid for sid in ids}
scope_counts = Counter(s["scope"] for s in plan["stories"])
assert scope_counts == {"首轮链路": 16, "核心扩展": 8, "全程协作": 2, "暂缓候选": 16}
assert all(s["scope"] != "暂缓候选" for s in plan["stories"] if s["priority"] == "P0")
selected = {s["id"] for s in plan["stories"] if s["scope"] != "暂缓候选"}
for row in rows:
    cells = row.split("|")
    sid = re.search(r"\*\*US-([\d.]+)\*\*", cells[3]).group(1)
    item = story_map["US-" + sid]
    assert (
        item["title"]
        == re.search(r"\*\*US-[\d.]+\*\*\s*(.+)", cells[3]).group(1).strip()
    )
    assert item["priority"] == re.search(r"\*\*(P[012])\*\*", cells[4]).group(1)
    assert item["criteria"] == cells[4].split("**验收（草案）**：", 1)[1].strip()
tasks = {t["id"]: t for t in plan["tasks"]}
assert set(tasks) == {f"R-{i:02d}" for i in range(1, 13)}
assert len(plan["decisions"]) == 8 and len({d["id"] for d in plan["decisions"]}) == 8
assert {t["parentTask"] for t in tasks.values()} == {f"P-{i:02d}" for i in range(1, 11)}


def visit(tid, trail):
    assert tid in tasks and tid not in trail, (tid, trail)
    for dep in tasks[tid]["dependsOn"]:
        visit(dep, trail + [tid])


for tid in tasks:
    visit(tid, [])
worksheet = (root / "docs/团队协作/评审/评审工作页.html").read_text(encoding="utf-8")
embedded = json.loads(
    re.search(
        r'<script id="plan-data" type="application/json">(.*?)</script>',
        worksheet,
        re.S,
    ).group(1)
)
assert embedded == plan, "Worksheet has a stale embedded plan"
case_source = (root / "docs/需求与设计/验收测试设计.md").read_text(encoding="utf-8")
case_rows = [line for line in case_source.splitlines() if re.match(r"\| TC-\d+", line)]
assert len(case_rows) == 14
covered = {
    "US-" + sid
    for line in case_rows
    for sid in re.findall(r"(?<![\d.])(\d+\.\d+\.\d+)(?![\d.])", line.split("|")[2])
}
assert selected <= covered, selected - covered
review_checks = json.loads(
    (root / "docs/验证记录/前置材料/工作页检查结果.json").read_text(encoding="utf-8")
)
assert len(review_checks["checks"]) == 7
assert not review_checks["pageErrors"] and not review_checks["externalRequests"]
math_checks = json.loads(
    (root / "docs/验证记录/前置材料/验收算例核算.json").read_text(encoding="utf-8")
)
assert math_checks["areas"]["popt"] == "27/29"
audit_dir = root / "docs/数据核查/activemq-2024-sample-20261004"
audit_sources = json.loads((audit_dir / "sources.json").read_text(encoding="utf-8"))
audit_study = json.loads((audit_dir / "case-study.json").read_text(encoding="utf-8"))
assert len(audit_sources) == audit_study["sourceCount"] == 15
assert len(audit_study["issues"]) == 4 and len(audit_study["cases"]) == 8
third_party_sources = set()
for source in audit_sources:
    filename = source["file"]
    assert Path(filename).name == filename
    path = audit_dir / filename
    raw = path.read_bytes()
    assert source["status"] == 200 and len(raw) == source["bytes"]
    assert hashlib.sha256(raw).hexdigest() == source["sha256"]
    third_party_sources.add(path.resolve())
assert all(
    i["inducingCommitLabel"] == "unknown_szz_not_executed"
    for i in audit_study["issues"]
)

files = (
    [root / "README.md", root / "scripts/README.md"]
    + sorted((root / "docs").rglob("*.md"))
    + sorted((root / "openspec/changes").rglob("*.md"))
)
broken, local_links, whitespace, table_errors = [], 0, [], []
for file in files:
    source = file.read_text(encoding="utf-8-sig")
    for target in re.findall(r"!?\[[^\]\n]*\]\(([^)\n]+)\)", source):
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:|^#", target):
            continue
        raw = target.strip().split(' "', 1)[0].strip("<>")
        raw = unquote(raw.split("#", 1)[0])
        local_links += 1
        dest = (file.parent / raw).resolve()
        if not dest.exists() and dest != report_path:
            broken.append({"file": str(file.relative_to(root)), "target": target})
    inside_code = False
    table_width = None
    for n, line in enumerate(source.splitlines(), 1):
        if line.startswith("```"):
            inside_code = not inside_code
        if line.rstrip() != line:
            whitespace.append(f"{file.relative_to(root)}:{n}")
        if not inside_code and line.lstrip().startswith("|"):
            width = len(re.split(r"(?<!\\)\|", line.strip())) - 2
            if table_width is not None and width != table_width:
                table_errors.append(
                    f"{file.relative_to(root)}:{n}: {width}!={table_width}"
                )
            table_width = width
        else:
            table_width = None
assert not broken, broken
assert not table_errors, table_errors
assert not whitespace, whitespace
for file in (root / "docs").rglob("*.html"):
    if file.resolve() in third_party_sources:
        continue
    source = file.read_text(encoding="utf-8")
    for target in re.findall(r'(?:href|src)="([^"]+)"', source):
        if target.startswith("#") or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
            continue
        local_links += 1
        assert (file.parent / unquote(target.split("#", 1)[0])).exists(), (file, target)

specs = sorted(
    (root / "openspec/changes/establish-product-baseline/specs").glob("*/spec.md")
)
assert len(specs) == 3
requirements, scenarios = 0, 0
for file in specs:
    source = file.read_text(encoding="utf-8")
    blocks = re.split(r"^### Requirement: ", source, flags=re.M)[1:]
    requirements += len(blocks)
    for block in blocks:
        assert "SHALL" in block
        scenes = re.split(r"^#### Scenario: ", block, flags=re.M)[1:]
        assert len(scenes) >= 2, file
        scenarios += len(scenes)
        for scene in scenes:
            assert "**WHEN**" in scene and "**THEN**" in scene

for i in range(1, 6):
    png = root / f"docs/需求与设计/原型/WF-0{i}.png"
    assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
tasks_source = (
    root / "openspec/changes/establish-product-baseline/tasks.md"
).read_text(encoding="utf-8")
task_rows = re.findall(r"^- \[([ x])\] (\d+\.\d+) ", tasks_source, flags=re.M)
assert len(task_rows) == 16
assert {sid for done, sid in task_rows if done == "x"} == {"0.1", "0.2"}
assert all(t["specTask"] in {sid for _, sid in task_rows} for t in tasks.values())
wireframes = json.loads(
    (root / "docs/验证记录/前置材料/原型布局历史记录.json").read_text(encoding="utf-8")
)
evidence = {
    "date": datetime.now(UTC).date().isoformat(),
    "checkedAt": datetime.now(UTC).isoformat(),
    "scope": "Fresh document structure, links and source hashes; worksheet, wireframe and acceptance-math results are cached evidence, not rerun browser tests; no product approval, SZZ or model-result evidence",
    "stories": len(ids),
    "storiesWithSuccessAndFailureDrafts": len(ids),
    "priorities": dict(priorities),
    "businessBacklogP0P1Candidates": business_core,
    "selectedScopeDraft": plan["summary"],
    "recognizablePreparationCards": len(tasks),
    "decisionDrafts": len(plan["decisions"]),
    "acceptanceCaseDesigns": len(case_rows),
    "selectedStoriesLinkedToCaseDesigns": len(selected),
    "reviewWorksheet": {
        "functionalChecks": len(review_checks["checks"]),
        "layoutChecks": len(review_checks["layouts"]),
        "pageErrors": review_checks["pageErrors"],
        "externalRequests": review_checks["externalRequests"],
    },
    "acceptanceMath": math_checks["areas"],
    "markdownFilesChecked": len(files),
    "localLinksChecked": local_links,
    "realDataSourceAudit": {
        "sourceFiles": len(audit_sources),
        "sourceBytes": audit_study["sourceBytes"],
        "historicalIssues": 4,
        "caseDesigns": 8,
        "sourceHashesVerified": True,
        "inducingLabels": "unknown_szz_not_executed",
    },
    "missingLocalLinks": broken,
    "tableStructureErrors": table_errors,
    "trailingWhitespace": whitespace,
    "specCapabilities": 3,
    "requirements": requirements,
    "scenarios": scenarios,
    "preparationTasks": {
        "completedLocalMaterialChecks": 2,
        "pendingRealReviewAndFutureImplementation": 14,
    },
    "wireframes": wireframes,
    "sourceSha256": {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [
            root / "docs/需求与设计/产品需求文档.md",
            root / "docs/需求与设计/产品设计文档.md",
            root / "docs/需求与设计/原型/低保真原型.html",
            root / "docs/团队协作/评审/准备计划.json",
            root / "docs/团队协作/评审/评审工作页.html",
            root / "docs/需求与设计/验收测试设计.md",
            root / "docs/数据核查/ActiveMQ数据可行性核查.md",
            audit_dir / "sources.json",
            audit_dir / "case-study.json",
        ]
    },
}
report_path.write_text(
    json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(
    json.dumps(
        {k: v for k, v in evidence.items() if k not in ("sourceSha256", "wireframes")},
        ensure_ascii=False,
    )
)
