## Purpose

Define the proposed user-facing review workflow from a valid commit and compatible model to a versioned risk score, globally sorted list, detail view and genuine explanation. Historical label trends are kept distinct from predicted risk; these future product scenarios are not proof of implementation, interviews or acceptance.

## ADDED Requirements

### Requirement: Prediction identifies its source
系统 SHALL 对有兼容特征及 ready 模型的提交返回有限 [0,1] 分数、预测 ID、模型版本与解释状态；历史重放标明训练窗口，不把分数描述成已确认缺陷。关联 US-4.1.1；风险等级US-4.1.3暂缓。

#### Scenario: Valid user-triggered prediction
- **WHEN** 用户选择有完整特征的提交及兼容模型
- **THEN** 得到带来源的风险结果，若显示等级则附版本化阈值规则

#### Scenario: Unavailable input or model
- **WHEN** 特征缺失、模型失效或 schema 不匹配
- **THEN** 给出原因和下一步，不显示默认分数或低风险标签

### Requirement: Local explanations have explicit lifecycle
系统 SHALL 区分 pending、ready、failed；ready 解释至少有三个真实特征贡献、方向、方法和单位，零贡献如实标注，解释不作为因果证明。关联 US-4.2.1。

#### Scenario: Cached or completed explanation
- **WHEN** 解释可用
- **THEN** 用户查看真实贡献、方法、单位和对应模型版本

#### Scenario: Cache miss or failure
- **WHEN** 解释未计算或计算失败／超出已配置时限
- **THEN** 返回 pending 或 failed，提供查询／重试及原因，不用固定话术冒充解释，不把失败计验收通过

### Requirement: Review lists are globally sorted and actionable
系统 SHALL 对用户选择的仓库与模型先在全部匹配结果中按概率降序排序，再分页；展示提交、分数、时间和来源。关联 US-5.1.1；高级时间／分数筛选US-5.1.2暂缓。

#### Scenario: Repository selection and paging
- **WHEN** 用户选择仓库／模型并翻页
- **THEN** 条件、总数及全局顺序一致，详情入口关联该提交和模型版本

#### Scenario: Empty or failed loading
- **WHEN** 无仓库、无模型、无匹配结果或服务请求失败
- **THEN** 分别展示对应状态与下一步，错误不伪装成空列表

### Requirement: Detail views retain commit and model context
系统 SHALL 展示同一提交／模型的变更上下文、14维特征、版本和解释状态，切换后旧响应不能替换当前内容。关联 US-2.1.2、5.1.3。

#### Scenario: Inspect a list item
- **WHEN** 用户打开详情
- **THEN** 可查模型来源、特征有效性、解释状态并返回原仓库／模型列表

#### Scenario: Outdated response or absent commit
- **WHEN** 旧请求迟到或提交不存在
- **THEN** 不显示上一提交的分数和解释；缺失记录有明确错误

### Requirement: Trends distinguish labels from predictions
系统 SHALL 在最终范围展示固定标签快照的历史数量／比例、观察窗口、unknown、成熟状态；不得把模型高风险数量当作已发生缺陷。关联 US-5.2.1；目录分布US-5.2.2暂缓。

#### Scenario: Available historical labels
- **WHEN** 用户查看固定窗口和时间桶
- **THEN** 展示时间桶内buggy／可标注提交及unknown，分母不包含unknown

#### Scenario: No eligible labels
- **WHEN** 桶内无可标注样本或观察窗口未成熟
- **THEN** 比例显示未定义或成熟限制，不绘制假零缺陷结论
