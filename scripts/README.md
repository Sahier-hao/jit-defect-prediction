# 共享复核工具

从项目根目录运行，均使用 Python 标准库；快照复核同时调用仓库内的标准库模块。无需安装前端依赖。

| 命令 | 检查内容 | 是否写文件 |
|---|---|---|
| `python scripts/verify_docs.py` | Markdown／HTML 本地链接、原型图片、需求与计划一致性、保存的来源哈希 | 写入[当前文档检查结果](../docs/验证记录/目录整理检查结果.json)；不覆盖历史记录 |
| `python scripts/verify_data_sources.py` | 15份保存的公开来源、4个历史 issue、8个案例设计及修复前后行 | 只读 |
| `python scripts/verify_saved_evidence.py` | 整理中保留文件的哈希；批量准备、Java旧行和时间审计快照的重新计算 | 只读 |

工具不执行 Git、网络请求或模型训练。[文档导航](../docs/README.md)是团队日常阅读入口，以上脚本按需复核。
