## Purpose

Define a draft training and evaluation contract that supports the course's classical and deep model comparison, both metric families, immutable model registration, and honest handling of failures or undefined metrics. Exact resource budgets and dataset policy values remain review candidates, not results or approved product parameters.

## ADDED Requirements

### Requirement: Model breadth is delivered in stages
系统 SHALL 在首轮支持至少一个真实训练的经典基线，最终范围支持经典／深度两类总计不少于八种不同方法；方法输入、参数、预算、随机性和失败记录可查。关联 US-3.1.1/3.2.1；US-3.1.2/3.2.2调参界面暂缓，但版本化配置与预算必须保留。

#### Scenario: First baseline and final breadth
- **WHEN** 检查首轮增量或最终模型清单
- **THEN** 首轮至少一个方法可训练和登记，最终至少八种方法覆盖两类，训练结果可追溯到同一评价协议

#### Scenario: Invalid inputs or incomplete training
- **WHEN** 输入不兼容、参数无效、任务超预算或失败
- **THEN** 系统记录原因，不生成 ready 模型，不用同一方法改名字凑模型数

### Requirement: Both evaluation families retain their definitions
系统 SHALL 报告 Precision、Recall、F1、AUC、混淆计数、阈值及 effort-aware 的 Recall@20%Effort、Popt；保存成本代理、排序、预算边界、测试清单与口径版本。关联 US-3.3.1/3.3.2。

#### Scenario: Comparable complete report
- **WHEN** 在固定测试清单生成报告
- **THEN** 两组指标同时存在，并能核对实际检查成本／数量、全范围 Popt 和成本基线

#### Scenario: Undefined metric
- **WHEN** 测试集仅一类、无真实正例或 Popt 归一化分母退化
- **THEN** 受影响指标标为未定义及原因，不填造 AUC、召回或提升幅度

### Requirement: Comparison uses the same test contract
系统 SHALL 仅对测试清单、标签、特征资格及指标口径相同的模型生成可比结论；保存重复运行、种子和基线结果。关联 US-3.3.3。

#### Scenario: Same evaluation manifest
- **WHEN** 用户选中满足同一评价契约的模型
- **THEN** 对比表／图显示两类指标、运行信息及原报告入口

#### Scenario: Incompatible evaluation
- **WHEN** 测试清单或口径不一致
- **THEN** 明确列出差异，不合成排名或宣称性能提升

### Requirement: Registered models are immutable and verifiable
系统 SHALL 保存数据／文件哈希、schema、训练及标签截止、参数、种子、预处理、依赖版本和指标口径；只把可读取且校验通过的成功模型标 ready。关联 US-3.3.4。

#### Scenario: Reload a model version
- **WHEN** 成功模型在服务重启后被读取
- **THEN** 版本与完整元数据仍可查，重新训练建立新版本而不覆盖旧结果

#### Scenario: Missing or corrupted artifact
- **WHEN** 模型文件丢失、校验失败或对应训练失败
- **THEN** 系统标记不可用并说明原因，不返回该模型生成的默认预测
