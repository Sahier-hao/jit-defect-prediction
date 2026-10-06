## Purpose

Define the proposed repository-to-dataset contract for the course product: observable progress, reproducible commit features, traceable candidate fixes and SZZ evidence, and versioned labels whose availability is checked against the training cutoff. These draft requirements do not assert that repository mining has been implemented or approved.

## ADDED Requirements

### Requirement: Repository preparation is observable
系统 SHALL 接受合法公开仓库地址和采集窗口，返回可查询任务 ID，并展示仓库、阶段、进度、更新时间和失败原因。关联 US-1.1.1/1.1.2/1.1.3。

#### Scenario: Valid preparation request
- **WHEN** 用户提交有效地址和窗口且符合已配置资源限制
- **THEN** 系统返回任务 ID，后续状态可查询，成功后提供数据质量摘要

#### Scenario: Invalid request or failed task
- **WHEN** 地址／窗口无效或采集失败
- **THEN** 系统说明原因，不生成 ready 半成品；失败重试保留旧 attempt

### Requirement: Commit parsing retains provenance
系统 SHALL 保存提交标识、父提交、author／committer时间、匿名作者、变更路径和增删行，并记录目标分支、固定source_ref及可得的集成事件，并按版本化规则统计过滤和解析失败。关联 US-1.2.1；纯格式自动识别US-1.2.2暂缓，不取消基本解析支持边界和失败计数。

#### Scenario: Reproducible history window
- **WHEN** 解析固定历史窗口
- **THEN** 记录数、过滤数和异常数与原始窗口可核对，相同配置可复核同一清单

#### Scenario: Unsupported change
- **WHEN** 二进制、重命名或特殊提交不能正确解析
- **THEN** 系统保留状态和原因，不以零值伪装成功，不静默丢失异常计数

### Requirement: Fix candidates and SZZ labels are evidence based
系统 SHALL 区分候选修复、核对结果、可疑引入关系与无法归因，保存tracker／issue键、类型／状态历史、原始来源哈希、获取时间与分页完整性、fix与inducing标识、目标分支、旧路径行号、规则及文件过滤版本、标签可得时间。关联 US-1.3.1/1.3.2/1.3.3。

#### Scenario: Traceable attribution
- **WHEN** 候选在固定规则下完成 SZZ 归因
- **THEN** 可查看 fix 到可疑引入提交的证据，不把 SZZ 标签描述成绝对事实

#### Scenario: Ambiguous or missing evidence
- **WHEN** 仅匹配关键词、issue 不可得或 SZZ 无法归因
- **THEN** 系统标注待核对／无法归因并统计，不直接赋 buggy 或 clean 结论

#### Scenario: Fixed non-Bug issue
- **WHEN** 来源记录为Task／Improvement且resolution为Fixed
- **THEN** 不把它当Bug-only规则下的已核对Bug修复；也不因此把某个提交标clean，保留排除理由

#### Scenario: Merge and backport of one repair
- **WHEN** 同一修复有原提交、两父merge和其它分支backport
- **THEN** 保存来源关系和分支资格，不对同一目标分支修复重复归因；diff中的历史issue键不当额外修复关联

### Requirement: Features use available history
系统 SHALL 提供固定 schema 的全部 Kamei 14 特征、公式／单位／特征文件范围版本、历史截止与有效性；SZZ归因文件过滤另用独立版本；预测特征只使用该提交发生时及之前可得信息。关联 US-2.1.1/2.1.2。

#### Scenario: Deterministic valid features
- **WHEN** 同一提交在相同 schema 和历史窗口计算特征
- **THEN** 14维结果一致，FIX 不使用该提交后来被修复的标签

#### Scenario: Incomplete features
- **WHEN** 历史不足或解析异常造成特征不可得
- **THEN** 系统保留原因与计数，不静默填零进入正常训练样本

### Requirement: Dataset snapshots preserve label status
系统 SHALL 保存不可变数据集清单与来源哈希，区分 buggy、clean_observed、unknown 和排除原因，展示可核对分布；重训不得读取后来标签覆盖旧快照。关联 US-1.4.1、2.2.2/2.2.3。

#### Scenario: Persistent snapshot
- **WHEN** 成功数据集在服务重启后被读取
- **THEN** 清单与哈希一致，重复导入不重复生成提交主记录

#### Scenario: Interrupted write or immature labels
- **WHEN** 持久化中断或标签观察期未成熟
- **THEN** 半成品不标 ready，未成熟样本保持 unknown，不默认为负例

### Requirement: Temporal eligibility prevents future information use
系统 SHALL 以版本化时间配置切分样本，相同时间戳不跨训练／测试边界；训练特征和标签在训练截止已可得，保存所需分支集成事件及历史issue核对证据；当前获取时间不冒充历史可得时间，预处理和调参仅使用训练期，最终测试清单冻结。关联 US-2.2.1。

#### Scenario: Eligible temporal split
- **WHEN** 数据量与类别满足已确认资格规则
- **THEN** 训练提交时间严格早于测试；训练负例在训练截止已成熟，测试期新出现的修复不参与训练标签

#### Scenario: Authored repair is integrated after cutoff
- **WHEN** 修复自身时间早于训练截止，但目标分支集成或所需Bug/Fixed历史证据晚于截止
- **THEN** 该证据不参与历史训练标签；缺少可重构事件时保持unknown或排除，不能仅按修复author时间回填

#### Scenario: Invalid split or unavailable labels
- **WHEN** 时间边界、类别或标签可得性不满足资格
- **THEN** 系统拒绝或明确排除并报告原因，不退回随机切分或把 unknown 当 clean
