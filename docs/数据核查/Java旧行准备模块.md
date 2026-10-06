# Java 旧行准备模块

本轮在已有修复候选准备后增加 SZZ 输入校验。它读取保存的文件，不运行 Git、blame 或外部 SZZ 工具。输出的是**供后续归因使用的非注释旧行目标**，不是已证实的缺陷引入行或训练标签。产品需求仍待小组真实评审。

## 调研落点

[本轮调研](SZZ输入策略调研_20261005.md)核对 SZZ Unleashed、ICSE 2021 开发者参照研究、PySZZ v2 与 Java SE 17 词法规范。实现了版本化的 `java-production-old-lines-v1`：只纳入 `src/main/java` 下的 Java 文件，排除包含完整 `src/test` 路径段的文件；文件范围与 Kamei 特征范围独立。

对完整父版本扫描，识别行注释、跨行注释、字符串、字符和文本块。含有非注释内容的行保留；普通空白行排除，文本块内部的空白行保留为字面量内容。字符串里的注释符不会错误排除。它不验证完整Java语法、类型或执行语义，也不识别代码行仅改变缩进的格式变更。

任何疑似 `\u` Unicode 转义、未闭合注释／字面量、错误文本块开头、独立CR、非UTF-8都会明确失败。Unicode转义即使实际不可用也保守拒绝。比较时去除可选UTF-8 BOM并统一CRLF为LF，来源哈希始终针对原始字节。

## 输入校验

入口为[派生清单](Java旧行准备示例.json)，其中包含原批量清单与快照路径、候选ID、调用方声明的完整父SHA，以及生产文件对应的父／修复后来源键。

1. 按[原批量清单](批量准备示例.json)重新校验来源并生成完整批量body，与[原快照](批量准备结果/b750305c5fdde4a47b82f6d9035243b2f8bff2739a2f83648db1f8c40e775672.json)一致才继续。仅重算内容ID而伪造candidate状态也会被拒绝。
2. 所选记录必须已经是合格修复候选。AMQ-9330因集成证据不足不会被误纳入。
3. 对每个纳入且有删除行的生产文件，要求来源账本中的父／修复后文件；校验HTTP状态、字节数、SHA-256、获取时间，以及精确的 `raw.githubusercontent.com/仓库/完整SHA/路径` HTTPS URL。
4. 应用所有补丁块并检查上下文、行号及末尾换行；重建全文必须与独立修复后文件一致，补丁范围外的错误也会失败。
5. 所有文件校验成功才返回完整body并发布快照，文件缺失、绑定多余／重复、错误版本或不一致均失败。

文件路径限定在清单目录内，复用既有来源和快照校验。单来源／清单／账本上限2MiB，源文件绑定最多1000条。批量重算与追加来源核验分别有32MiB读取预算，快照最多64MiB。每个派生快照覆盖**一个**合格候选；本轮未实现跨候选归因批处理。

固定SHA URL和全文重建仅验证所声明版本内容一致，不能证明该版本确是祖先。输出保留 `parentVerification=caller_supplied_requires_ancestry_review`，分支与集成验证继承原批量快照的待核对状态。

## 真实样本结果

| 原始删除位置 | 数量 | 决策 |
|---|---:|---|
| `RestTest.java` 旧行89、90、91、93 | 4 | `excluded_test_path` |
| `AsyncServletRequest.java` 旧行119、120 | 2 | `excluded_comment` |
| `AsyncServletRequest.java` 旧行118、121 | 2 | `selected_non_comment` |

原始计数仍为NF=2、LA=17、LD=8；目标计数为1个文件、2条旧行，排除6条，共8条逐行决策。原候选可得时间仍为 `2024-04-22T15:07:37.776000+00:00`。原始15份来源、账本与既有批量快照均保留。

已保存[派生快照](Java旧行准备结果/8537a3c2771653741a661a4785220527455a695562623a18386bdbaf0e9b028b.json)，内容ID：`8537a3c2771653741a661a4785220527455a695562623a18386bdbaf0e9b028b`。body包含阶段、策略版本、父／修复SHA、源文件摘要、全文重建结果、逐行文本／理由、目标及质量计数。`inducingLabel=null`、`kamei14=null`、`trainingReady=false`；零目标也保持未知，不能转成clean。

## 运行和验证

项目根目录执行，模块仅依赖Python标准库：

```powershell
python -m jit_defect.szz_inputs --manifest docs/数据核查/Java旧行准备示例.json --snapshot-dir docs/数据核查/Java旧行准备结果
python -m jit_defect.preparation_batch verify --snapshot docs/数据核查/Java旧行准备结果/8537a3c2771653741a661a4785220527455a695562623a18386bdbaf0e9b028b.json
```

第一次发布与以后重算均使用既有不可覆盖快照机制。重复执行复用同一文件，字节和mtime不变。成功退出0，输出小型JSON摘要；无效输入退出2、stderr诊断、stdout为空，不生成部分目标文件。

新增测试先在模块／接口缺失时失败，再实现通过。覆盖真实目标、完整文件状态、字符串与文本块、Unicode显式拒绝、多补丁块／插入锚点、末尾换行、哈希、来源URL绑定、独立修复文件错误、伪造候选快照、未知候选、清单异常、零目标及CLI重放。

```powershell
C:/Python314/python.exe -m pytest tests/test_szz_java.py tests/test_szz_inputs.py -q
C:/Python314/python.exe -m pytest -q
ruff check jit_defect tests
python scripts/verify_data_sources.py
python scripts/verify_docs.py
openspec validate --all --strict --no-interactive
```

机器上的Python3.14环境用于完整后端回归；标准库入口另外由默认Python3.12运行。本轮结果、环境、文件指纹与命令记录在[验证记录](Java旧行准备验证记录.json)。

## 后续边界

整生产文件删除显式不支持；新增文件无旧行目标。非Maven Java布局、测试缺陷、格式变更、重构、移动、revert、纯新增行修复及跨文件因果均需后续策略或SZZ实现处理。本例属于工程夹具，不构成归因精度、真实数据集或模型指标。

后续先由小组核对文件策略与首轮范围，再在允许的条件下验证完整历史、选定SZZ变体并用独立参照复核。对应[变更计划](../../openspec/changes/prepare-java-szz-inputs/proposal.md)，需求基线中的访谈／认领／真实评审任务仍保持未完成。
