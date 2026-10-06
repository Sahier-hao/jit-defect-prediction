"""Read-only replay of preserved files and immutable preparation snapshots."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jit_defect.preparation_batch import prepare_batch, read_snapshot  # noqa: E402
from jit_defect.szz_inputs import prepare_inputs  # noqa: E402
from jit_defect.temporal_audit import audit_temporal  # noqa: E402


def main():
    mapping = json.loads((ROOT / "docs/验证记录/目录整理映射.json").read_bytes())
    for row in mapping["protectedFiles"]:
        path = (ROOT / row["currentPath"]).resolve()
        assert path.is_relative_to(ROOT), row["currentPath"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"], row[
            "currentPath"
        ]

    docs = ROOT / "docs/数据核查"
    example = docs / "标签时间合成示例"
    cases = [
        (
            docs
            / "批量准备结果/b750305c5fdde4a47b82f6d9035243b2f8bff2739a2f83648db1f8c40e775672.json",
            lambda: prepare_batch(docs / "批量准备示例.json"),
        ),
        (
            docs
            / "Java旧行准备结果/8537a3c2771653741a661a4785220527455a695562623a18386bdbaf0e9b028b.json",
            lambda: prepare_inputs(docs / "Java旧行准备示例.json"),
        ),
        (
            docs
            / "标签时间审计结果/4a86d1a4266b3b0db23c8e7c0022b47a8391df488d6f43b84ca4fdaf0d3d8691.json",
            lambda: (
                audit_temporal(
                    (example / "synthetic-features.csv").read_bytes(),
                    (example / "synthetic-contract.json").read_bytes(),
                ).report
            ),
        ),
    ]
    for path, recompute in cases:
        before = path.read_bytes(), path.stat().st_mtime_ns
        assert read_snapshot(path) == recompute(), path.name
        assert before == (path.read_bytes(), path.stat().st_mtime_ns), path.name
    print(
        json.dumps(
            {
                "result": "PASS",
                "preservedFiles": len(mapping["protectedFiles"]),
                "snapshotsRecomputed": len(cases),
                "historicalReportsRewritten": False,
                "softwareTestsRerun": False,
            }
        )
    )


if __name__ == "__main__":
    main()
