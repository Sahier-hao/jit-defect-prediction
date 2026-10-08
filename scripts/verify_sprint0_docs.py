"""Verify Sprint 0 document structure and placement without project dependencies.

Run: python scripts/verify_sprint0_docs.py
"""

import base64
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path


root = Path(__file__).resolve().parents[1]
prd_path = root / "docs/需求与设计/产品需求文档.md"
design_path = root / "docs/需求与设计/产品设计文档.md"
report_path = root / "docs/需求与设计/设计分析报告.md"
api_path = root / "docs/需求与设计/API清单与接口契约.md"
openapi_path = root / "docs/需求与设计/api/openapi.yaml"

prd = prd_path.read_text(encoding="utf-8")
design = design_path.read_text(encoding="utf-8")
report = report_path.read_text(encoding="utf-8")
api_contract = api_path.read_text(encoding="utf-8")
openapi = openapi_path.read_text(encoding="utf-8")
owner_documents = [
    prd,
    design,
    report,
    api_contract,
    (root / "docs/README.md").read_text(encoding="utf-8"),
    (root / "docs/团队协作/Sprint0前置工作清单.md").read_text(encoding="utf-8"),
    (
        root / "openspec/changes/establish-product-baseline/tasks.md"
    ).read_text(encoding="utf-8"),
]
deprecated_terms = [
    base64.b64decode("55So5oi3NTkwMzM3").decode(),
    base64.b64decode("54yr5aS06bmw").decode(),
]

checks = {
    "requirementsAppendixHasDesignReport": (
        "### 附录 D：设计分析报告（Sprint 0）" in prd
        and "[Sprint 0 设计分析报告](设计分析报告.md)" in prd
    ),
    "reportIsSubstantiveDesignAnalysis": all(
        heading in report
        for heading in (
            "## 2. 用户与任务模型",
            "## 5. 页面级设计分析",
            "## 9. 关键设计决策",
            "## 12. 验证计划",
            "## 14. 结论",
        )
    ),
    "reportMapsRequirementsAndDesign": (
        "## 8. 需求追踪与设计对应" in report
        and "US-1.1" in report
        and "US-5.2" in report
        and "设计响应" in report
    ),
    "reportOwnerIsYangWenzhao": "负责人：杨稳曌" in report,
    "apiContractIsSeparate": (
        api_path.exists()
        and "## 3. API清单" in api_contract
        and "## 5. 接口详细契约" in api_contract
    ),
    "apiInventoryHasTemplateColumns": all(
        heading in api_contract
        for heading in (
            "接口名称",
            "所属模块",
            "方法",
            "路径",
            "请求／入参",
            "成功响应",
            "返回结构",
            "鉴权",
            "调用模块",
        )
    ),
    "apiContractLinksOpenApiDraft": "(api/openapi.yaml)" in api_contract,
    "apiContractHasExplanatorySections": all(
        heading in api_contract
        for heading in (
            "## 2. 通用约定",
            "## 4. 公共数据契约",
            "## 5. 接口详细契约",
            "## 6. 异步流程与恢复",
            "## 7. 安全、性能与数据保护",
            "## 9. 验收要点",
        )
    ),
    "apiContractHasNoProcessMetadata": all(
        term not in api_contract
        for term in (
            "本文档独立维护",
            "并入产品设计文档",
            "课程模板",
            "Sprint 1",
            "技术试做",
        )
    ),
    "openApiIsDraftVersion": "version: 0.1.0-sprint0-draft" in openapi,
    "openApiHasV1Paths": "/api/v1/" in openapi,
    "openApiHasAuthAndErrorContract": (
        "bearerAuth" in openapi
        and "#/components/responses/Error" in openapi
    ),
    "taskAcceptedHasResourceIdentity": all(
        field in openapi
        for field in ("resourceType", "resourceId")
    ),
    "deprecatedOwnerIdentityRemoved": all(
        all(term not in document for term in deprecated_terms)
        for document in owner_documents
    ),
    "designDocumentUnmodified": subprocess.run(
        [
            "git",
            "diff",
            "--quiet",
            "HEAD",
            "--",
            "docs/需求与设计/产品设计文档.md",
        ],
        cwd=root,
        check=False,
    ).returncode
    == 0,
}

failed = [name for name, passed in checks.items() if not passed]
if failed:
    raise SystemExit("Sprint 0 document checks failed: " + ", ".join(failed))

api_ids = set(re.findall(r"^\| (API-\d+) \|", api_contract, flags=re.MULTILINE))
print(
    json.dumps(
        {
            "checkedAt": datetime.now(UTC).isoformat(),
            "checks": checks,
            "apiInventoryRows": len(api_ids),
            "requirementsDocument": str(prd_path.relative_to(root)),
            "designDocument": str(design_path.relative_to(root)),
            "designAnalysisReport": str(report_path.relative_to(root)),
            "apiContract": str(api_path.relative_to(root)),
            "openApiDraft": str(openapi_path.relative_to(root)),
        },
        ensure_ascii=False,
        indent=2,
    )
)
