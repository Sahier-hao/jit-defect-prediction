# JIT 缺陷预测系统

厚积薄发团队 · 《2026-2027-1 软件开发与测试综合实训》

我们计划用历史代码变更预测提交风险，帮助评审者安排检查顺序。**当前是 Sprint 0：需求分析与产品设计，材料为待团队复核的初稿。**

## 从这里开始

| 你想做什么 | 打开哪份材料 |
|---|---|
| 第一次了解项目 | [项目一页概要](docs/团队协作/项目一页概要.md) |
| 查看 Sprint 0 要交什么、四个人怎么分工 | [文档导航与分工](docs/README.md) |
| 修改需求、MVP 与功能范围 | [产品需求文档](docs/需求与设计/产品需求文档.md) |
| 修改架构、数据库、流程与原型 | [产品设计文档](docs/需求与设计/产品设计文档.md) |
| 整理工程基线 | [Sprint 0 OpenSpec 提案](openspec/changes/establish-product-baseline/proposal.md) |

本阶段交付需求与设计初版（包含用户／场景、竞品或替代方案、技术架构、数据库、流程图、时序图、低保真原型）、项目管理看板及 OpenSpec 初始材料。团队协作约定为可选交付物；[Sprint 0验收要求截图](docs/课程资料/Sprint0验收要求.png)已保存，方便共同核对。

## 目录怎么读

```text
jit-defect-prediction/
├── docs/          文档；先看 docs/README.md
├── openspec/      提案、能力规格和任务；Sprint 0 从 establish-product-baseline 开始
├── jit_defect/    Python 后端与数据处理的技术试做
├── frontend/      Vue 页面和前端测试的技术试做
├── tests/         Python 软件测试
├── scripts/       可随仓库共享的文档与样本复核工具
├── pyproject.toml Python 项目与依赖配置
├── .gitattributes 保留文件字节，避免换行转换破坏证据哈希
└── .gitignore     本机缓存、依赖和运行产物的忽略规则
```

`.cache/`、`runtime/`、`node_modules/`、`frontend/dist/` 是本机生成目录，已经配置忽略。

项目的 OpenSpec 技能与命令模板通过 `.gitignore` 单独放行；`.agents/`、`.claude/` 中的本机配置和工具标记继续忽略。版本化内容包括文档、规格、源码、测试、共享复核工具及依赖配置／锁文件。

## 当前进度

- **已有初稿**：需求、设计、流程与原型，以及 Sprint 0 的 OpenSpec 规划材料。
- **待团队完成**：核对用户／场景与范围、修改材料、实际任务认领、项目管理看板和评审记录。离线评审页只保存个人草稿。
- **已有技术试做**：合成 CSV 上的训练、评价、风险列表和解释；以及数据核查工具。它们不表示 Sprint 1 已验收。
- **待后续实现**：真实仓库的完整 SZZ 归因、14 维特征提取与产品链路；正式模型效果尚无结论。

准备进入实现时再看[技术试做运行说明](docs/技术试做/本地基线实现与运行.md)。历史检查与数据案例通过[文档导航](docs/README.md)按需查阅。

English: We are in Sprint 0, preparing requirements and product design. Start with the [team introduction](docs/团队协作/团队入门指南_中英.md) and [document guide](docs/README.md). Existing code is a technical spike; team decisions and product acceptance remain pending.
