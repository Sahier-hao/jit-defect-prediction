# JIT 缺陷预测系统：API清单与接口契约

版本：v0.2 草案。日期：2026-10-06。阶段：Sprint 0。负责人：杨稳曌。

## 1. API设计目标

### 1.1 业务背景

系统 API 围绕四类业务能力组织：仓库与数据准备、模型训练与评价、风险预测与解释、风险评审与历史趋势。采集、训练和解释属于长任务，预测和查询属于在线请求；接口设计需要同时保证长任务可恢复、数据版本可追溯和用户查询稳定。

接口契约的核心不是罗列 URL，而是明确资源边界、状态语义、错误恢复和版本依赖。任何接口都不得通过默认分数、空数据或静态状态掩盖失败、等待和未知。

### 1.2 设计目标

| 目标 | 设计要求 |
|---|---|
| 业务资源清晰 | 仓库、任务、数据集、模型、预测和解释分别建立资源边界 |
| 长任务可恢复 | 创建任务返回任务 ID，查询接口持续提供 queued、running、ready、failed 或 cancelled |
| 版本可追溯 | 数据集、特征、标签、模型和评价均绑定明确版本与哈希 |
| 失败不伪装 | 无数据、无特征、模型失效和历史不足返回明确状态或错误 |
| 查询稳定 | 风险列表全局排序后分页，同分使用稳定排序键 |
| 解释可验证 | explanation 返回方法、单位、贡献方向和数据来源状态 |
| 安全边界明确 | 本地访问与正式部署的鉴权方式分开描述 |

### 1.3 契约范围

首轮契约覆盖仓库接入、采集任务、任务查询、数据集快照、训练任务、模型版本、模型比较、单条预测、解释查询、风险列表和历史趋势。

批量预测、高级时间／概率筛选、目录分布和风险等级接口不作为首轮接口。原型中的相关入口属于候选设计，不应被客户端视为已承诺能力。

本文描述的是候选契约，不代表服务已经实现；实际字段、状态码和错误码在实施 change 中仍需通过测试验证。

## 2. 通用约定

### 2.1 传输与数据约定

接口使用资源化路径和 JSON 数据。所有时间使用 UTC，所有 ID 均为不透明字符串，客户端不得从 ID 推导数据库主键、时间顺序或业务层级。

| 项 | 约定 |
|---|---|
| 基础路径 | `/api/v1` |
| 媒体类型 | `application/json; charset=utf-8` |
| 时间 | ISO-8601 UTC，例如 `2026-10-08T08:00:00Z` |
| 分页 | `page` 从 1 开始；`pageSize` 默认 20、最大 100 |
| 排序 | 资源接口明确排序字段和同分规则；分页前完成全局排序 |
| 幂等 | 资源创建支持 `Idempotency-Key`；同键同请求返回同一结果 |
| 追踪 | 服务端返回 `requestId`，错误响应和日志使用同一值关联 |
| 版本 | 路径使用 `/api/v1`；模型、特征、标签和评价分别版本化 |

### 2.2 鉴权约定

| 代号 | 场景 | 约定 |
|---|---|---|
| A0 | 首轮本地单用户 | 不设登录，仅允许本机和受控内网访问 |
| A1 | 正式内网 | Bearer Token、角色校验和访问审计，具体权限矩阵待安全评审 |

A0 不是公网部署方案。部署边界、用户范围或数据范围发生变化时，必须重新设计鉴权、授权和敏感日志策略。

### 2.3 幂等与重复请求

`Idempotency-Key` 用于避免重试产生重复仓库、任务或预测。相同键和相同请求体应返回首次处理结果；相同键但请求体不同返回 `409 STATE_CONFLICT`。任务失败后的重试创建新 attempt，原失败记录不得被覆盖。

### 2.4 错误响应

错误响应统一包含稳定错误码、可读信息、可选细节和请求追踪 ID。客户端应依据错误码决定是否重试，而不是解析自然语言。

```json
{
  "code": "ELIGIBILITY_FAILED",
  "message": "Training requires at least two label classes",
  "details": {
    "eligibleCount": 18,
    "positiveCount": 4
  },
  "requestId": "opaque-request-id"
}
```

## 3. API清单

接口按资源分组，编号用于需求、设计和测试追踪。接口名称描述业务动作，路径保留资源语义。下表路径均省略公共前缀 `/api/v1`，请求、响应和返回结构使用简洁类型名，完整字段见后续契约。

| 编号 | 接口名称 | 所属模块 | 方法 | 路径 | 请求／入参 | 成功响应 | 返回结构 | 鉴权 | 调用模块 |
|---|---|---|---|---|---|---|---|---|---|
| API-01 | 接入仓库 | 仓库管理 | POST | repositories | 地址、名称、分支 | `201` | Repository | A1 | 仓库接入页 |
| API-02 | 查询仓库列表 | 仓库管理 | GET | repositories | 页码、状态 | `200` | RepositoryPage | A1 | 仓库接入页 |
| API-03 | 创建采集任务 | 数据准备 | POST | repositories/{repositoryId}/mining-runs | 窗口、规则版本 | `202` | TaskAccepted | A1 | 仓库接入页 |
| API-04 | 查询任务 | 任务中心 | GET | tasks/{taskId} | 无 | `200` | Task | A1 | 仓库页、训练页 |
| API-05 | 查询数据集列表 | 数据准备 | GET | datasets | 仓库、资格、页码 | `200` | DatasetPage | A1 | 训练页、趋势页 |
| API-06 | 查询数据集快照 | 数据准备 | GET | datasets/{datasetId} | 无 | `200` | DatasetVersion | A1 | 训练页、趋势页 |
| API-07 | 创建训练任务 | 模型训练 | POST | training-runs | 数据集、方法、预算 | `202` | TaskAccepted | A1 | 训练与比较页 |
| API-08 | 查询训练结果 | 模型训练 | GET | training-runs/{trainingRunId} | 无 | `200` | TrainingRun | A1 | 训练与比较页 |
| API-09 | 查询模型列表 | 模型登记 | GET | models | 数据集、状态、页码 | `200` | ModelPage | A1 | 风险列表、比较页 |
| API-10 | 查询模型版本 | 模型登记 | GET | models/{modelId} | 无 | `200` | ModelVersion | A1 | 训练与比较页、详情页 |
| API-11 | 比较模型 | 模型评价 | POST | model-comparisons | 模型版本列表 | `200` | ModelComparison | A1 | 模型比较页 |
| API-12 | 创建单条预测 | 风险预测 | POST | predictions | 提交、模型版本 | `201` | Prediction | A1 | 风险列表、详情页 |
| API-13 | 查询解释 | 风险解释 | GET | predictions/{predictionId}/explanation | 无 | `200` | Explanation | A1 | 提交详情 |
| API-14 | 查询提交详情 | 风险评审 | GET | commits/{commitId} | 模型版本 | `200` | CommitDetail | A1 | 提交详情 |
| API-15 | 查询风险列表 | 风险评审 | GET | risk-items | 仓库、模型、页码 | `200` | RiskItemPage | A1 | 风险列表 |
| API-16 | 查询历史趋势 | 历史趋势 | GET | trends | 数据集、时间桶 | `200` | TrendPage | A1 | 历史趋势页 |

接口清单体现以下约束：

1. API-01 和 API-02 管理仓库资源，API-03 才创建采集任务。
2. API-04 统一查询采集、训练和解释任务，客户端不依赖任务内部实现。
3. API-05～API-11 绑定数据集、训练结果、模型版本和评价口径，不能跨版本拼接结果。
4. API-12～API-13 分离预测和解释，允许解释异步完成。
5. API-14 提供与预测关联的提交特征和标签上下文，避免详情页依赖列表缓存。
6. API-15～API-16 区分风险预测结果和历史标签统计，不能混用数量口径。

## 4. 公共数据契约

### 4.1 公共对象

公共对象定义跨接口共享的字段语义。各接口可以省略不适用字段，但不能改变字段含义或使用默认值替代缺失状态。

| 对象 | 关键字段 | 说明 |
|---|---|---|
| `Task` | `taskId`、`type`、`state`、`progress`、`counts`、`error`、`updatedAt` | 采集、训练和解释任务共用；失败保留 attempt |
| `TaskAccepted` | `taskId`、`state`、`resourceType`、`resourceId` | 长任务创建响应，明确任务与业务资源的关系 |
| `Repository` | `repositoryId`、`canonicalUrl`、`name`、`language`、`targetBranch`、`createdAt` | 同一规范地址和目标分支唯一 |
| `DatasetVersion` | `datasetId`、`miningRunId`、`featureSchemaVersion`、`labelPolicyVersion`、`contentHash`、`counts` | 成功后不可覆盖 |
| `ModelVersion` | `modelId`、`trainingRunId`、`state`、`metrics`、`artifactHash`、`dependencyVersions` | 只有校验通过才为 ready |
| `Prediction` | `predictionId`、`commitId`、`modelId`、`score`、`explanationStatus`、`createdAt` | 保留模型和特征来源 |
| `Explanation` | `state`、`method`、`methodVersion`、`unit`、`contributions`、`reason` | pending 与 failed 都是正式状态 |
| `RiskItem` | `commitId`、`score`、`committedAt`、`modelId`、`scope` | 列表按 `score` 降序、`commitId` 升序稳定排序 |
| `Error` | `code`、`message`、`details`、`requestId` | 错误码全局统一，接口详情只引用代码 |

对象分层遵循一条原则：任务状态描述“流程是否完成”，业务资源状态描述“数据和模型是否可用”，两者不能互相替代。

### 4.2 状态流转

| 对象 | 状态 | 允许操作 |
|---|---|---|
| Task | `queued → running → ready/failed/cancelled` | failed 可创建新 attempt，不覆盖旧记录 |
| DatasetVersion | `building → ready/failed` | 只有完整快照和计数完成才可 ready |
| ModelVersion | `training → ready/failed/invalid` | 产物哈希或依赖校验失败为 invalid |
| Explanation | `pending → ready/failed` | pending 可查询；failed 返回原因和是否可重试 |

状态必须显式返回，客户端不能通过缺少字段、空数组或零值推断状态。`ready` 仅表示该资源可用于下一业务动作，不表示结果质量已经达到最终验收标准。

### 4.3 全局错误码

错误码由全局表维护，具体接口只引用代码。`requestId` 用于关联日志，错误细节只包含帮助调用方修正请求的信息，不暴露内部凭据、文件路径或第三方响应。

| HTTP | 错误码 | 含义 | 客户端处理 |
|---|---|---|---|
| 400 | `INVALID_ARGUMENT` | 参数格式或组合非法 | 修正请求，不自动重试 |
| 401 | `UNAUTHENTICATED` | 未登录或 Token 无效 | 重新认证 |
| 403 | `FORBIDDEN` | 已认证但无操作权限 | 提示联系管理员 |
| 404 | `RESOURCE_NOT_FOUND` | 仓库、任务、数据集或模型不存在 | 刷新选择，不展示旧详情 |
| 409 | `STATE_CONFLICT` | 状态冲突、幂等键冲突或版本不允许 | 刷新状态后由用户决定 |
| 422 | `ELIGIBILITY_FAILED` | 数据资格、标签或模型兼容性不满足 | 展示计数和失败原因 |
| 429 | `RATE_LIMITED` | 请求过频 | 按 `Retry-After` 退避 |
| 500 | `INTERNAL_ERROR` | 未归类服务错误 | 保留 `requestId`，提示稍后重试 |
| 503 | `DEPENDENCY_UNAVAILABLE` | 数据库、存储或外部来源不可用 | 提示服务不可用，不伪造成功 |

## 5. 接口详细契约

### 5.1 创建类接口

创建类接口先完成输入和资源状态校验，再创建业务记录与任务。校验失败不得留下 queued 任务；重复请求根据幂等键返回原结果或冲突。

| 接口 | 业务逻辑 | 主要校验 | 成功语义 | 主要错误 |
|---|---|---|---|---|
| API-01 接入仓库 | 规范化地址并注册仓库 | URL、分支、重复地址 | 返回仓库资源，不代表已经采集 | `INVALID_ARGUMENT`、`STATE_CONFLICT` |
| API-03 创建采集任务 | 创建 mining run 和异步任务 | 仓库状态、窗口、source ref、规则版本、资源上限 | 返回 task 和 mining run 标识 | `ELIGIBILITY_FAILED`、`STATE_CONFLICT` |
| API-07 创建训练任务 | 校验数据集资格并创建 training run | 有效标签、类别、时间边界、预算 | 返回 task 和 training run 标识 | `ELIGIBILITY_FAILED`、`STATE_CONFLICT` |
| API-12 创建预测 | 读取模型与特征并保存 prediction | 模型 ready、特征完整、版本兼容 | 返回预测分数和解释状态 | `STATE_CONFLICT`、`ELIGIBILITY_FAILED` |

### 5.2 查询与任务接口

查询接口只返回已持久化或可验证的结果。任务状态查询应支持刷新、重试和服务重启后的恢复，不要求客户端保持原请求连接。

| 接口 | 返回重点 | 不可用状态 | 结果边界 |
|---|---|---|---|
| API-02 仓库列表 | 仓库版本、状态、最近任务 | 不存在、存储不可用 | 列表分页稳定，不把采集状态复制成仓库状态 |
| API-04 任务查询 | 当前 attempt、进度、计数、失败原因 | 任务不存在、任务损坏 | failed 不返回 ready，cancelled 有明确原因 |
| API-05 数据集列表 | 仓库、标签策略、资格摘要 | 无数据集、存储不可用 | 只返回调用方可访问的快照版本 |
| API-06 数据集快照 | 来源、哈希、计数、资格 | 构建中、构建失败 | ready 后内容不可覆盖 |
| API-08 训练结果 | 训练状态、结果模型、计数、错误 | 训练中、失败、取消 | failed 不生成可用 modelId |
| API-09 模型列表 | 数据集、状态、指标摘要 | 无模型、存储不可用 | 只返回版本化模型 |
| API-10 模型版本 | 状态、指标、测试清单、产物哈希 | 训练中、失败、invalid | invalid 模型不能预测 |
| API-14 提交详情 | 提交、特征、标签、预测和解释状态 | 无特征、无预测 | 同一提交必须绑定同一 modelId |

### 5.3 比较、风险与趋势接口

| 接口 | 业务逻辑 | 主要校验 | 返回与异常 |
|---|---|---|---|
| API-11 比较模型 | 比较测试清单哈希、标签策略、成本口径和依赖版本 | 至少两个 ready 模型且口径相同 | 可比时返回指标，不可比时返回原因 |
| API-13 查询解释 | 返回 pending、ready 或 failed | prediction 存在且解释归属正确 | ready 必须有方法、单位和贡献；failed 有原因 |
| API-15 查询风险列表 | 在全部匹配结果中排序后分页 | 仓库、模型、分页范围 | 排序稳定；无结果与服务错误分离 |
| API-16 查询趋势 | 按固定标签快照和时间桶聚合 | 快照、时间桶、分母口径 | 零分母返回未定义，unknown 单独计数 |

比较、风险列表和趋势分别回答“模型是否可比”“先检查哪个提交”“质量随时间如何变化”三个问题，不能在页面或接口层面混用同一套排名和数量口径。

## 6. 异步流程与恢复

异步接口采用“创建资源 + 返回 taskId + 查询任务状态”的模式。任务状态和业务资源状态分开保存，使执行器中断、客户端退出和重试不会改变已发布结果。

```text
POST /training-runs
  -> 校验 dataset 与预算
  -> 创建 training_run(status=queued) 和 task_attempt
  -> 返回 202 { taskId, state, resourceType, resourceId }
执行器:
  -> task running
  -> 时间切分、仅训练期拟合、测试评价
  -> 保存模型产物、哈希、指标和版本
  -> task ready, model ready
失败:
  -> task failed, model failed
  -> 保留失败 reason 和 attempt，不登记 ready 模型
```

客户端刷新任务时只读取状态接口。服务重启后不得把 running 自动当作成功；任务重试创建新 attempt；成功发布后的 dataset、model、evaluation 和 explanation 快照不得被重试覆盖。

## 7. 安全、性能与数据保护

| 项 | 首轮本地候选 A0 | 正式候选 A1 |
|---|---|---|
| 鉴权 | 无登录；仅本机和受控网络 | Bearer Token、角色和审计日志 |
| 输入安全 | URL 白名单、路径校验、上传和窗口上限 | 权限校验、限流、敏感信息脱敏 |
| 数据保护 | 本地存储，模型和快照使用哈希 | 加密、备份、保留期和访问审计 |
| 性能 | 预测不等待解释；长任务异步 | 记录 P95、失败率、队列等待和阶段耗时 |
| 缓存 | 可缓存解释和模型元数据 | 缓存键包含模型、特征、方法和背景样本版本 |

性能契约应绑定具体环境和数据版本。预测接口只计算分数，解释通过独立资源查询；采集和训练通过任务状态查询，不能用浏览器长连接作为任务完成机制。缓存只减少读取成本，不改变资源状态和版本语义。

## 8. OpenAPI 草案

[OpenAPI 3.1 草案](api/openapi.yaml)提供机器可读的接口骨架，包括路径、参数、成功响应、公共状态和错误响应。OpenAPI 覆盖不到的异步恢复、业务校验优先级和失败处理由本文档补充。文字契约与 OpenAPI 不一致时，应先停止实现并修正契约，不得只修改其中一份。

## 9. 验收要点

接口验收必须验证行为，而不只检查路径是否存在。每个核心接口至少覆盖正常请求、参数错误、状态冲突、资源不存在和依赖失败。

| 编号 | 检查 | 通过标准 |
|---|---|---|
| API-AC-01 | API清单完整性 | 编号、名称、模块、方法、路径、入参、响应、返回结构、鉴权和调用模块齐全 |
| API-AC-02 | 长任务创建 | 返回任务和业务资源标识，不阻塞请求 |
| API-AC-03 | 任务恢复 | 刷新、重试和服务重启后可判断真实状态 |
| API-AC-04 | 数据与模型追溯 | 数据集、特征、标签、模型和产物哈希可关联 |
| API-AC-05 | 稳定分页 | 全局排序、同分规则和跨页结果一致 |
| API-AC-06 | 错误与状态 | 失败、未知、pending 和不可比不被伪装成成功 |
| API-AC-07 | 鉴权边界 | A0 不用于公网；A1 的权限和审计行为可验证 |
| API-AC-08 | OpenAPI 一致性 | 文字接口、字段和状态与 OpenAPI 草案一致 |
