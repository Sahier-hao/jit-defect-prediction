# ActiveMQ历史数据可行性核查

2026-10-04。类型：**真实公开来源的小规模案例核查**，用于解除数据方案的不确定性。已取得4个历史issue、4份真实提交patch、提交／PR页面及修复前后文件快照，共15份来源，1,181,609字节。没有执行Git、SZZ、仓库全量采集或训练；不形成正式缺陷标签或效果结论。

## 1. 对项目的直接结论

保留`apache/activemq`作为首轮数据工作的候选，优先验证2024年的历史Jira AMQ记录和固定main分支。样本证明**可以取得真实修复候选、issue类型／状态变化、父提交、diff及文件快照**，足以开始细化解析和标签契约；还没有证明能获得正式训练所需样本量、完整历史或可靠SZZ标签。

数据方案需立即补四项约束：区分历史Jira与当前GitHub Issues；先限定分支再处理修复；读取issue类型而非仅看Fixed；标签可得时间包含主分支集成及所需证据，不能只用提交自身时间。

这次选择是有限技术核查的工作默认值，可逆，未替团队批准最终仓库、技术栈或范围。真实访谈可独立推进，不要求等待采集开发完成。

## 2. 已获取的真实证据

四个issue是为检验不同边界主动挑选的案例，**不是随机抽样**。数量和成功访问不能用于计算全仓库覆盖率、误标率或Bug比例。以下状态是保存响应中的状态。

| 来源 | 可核对事实 | 对设计的影响 |
|---|---|---|
| [AMQ-9481](https://issues.apache.org/jira/browse/AMQ-9481) | Bug／Resolved／Fixed，完整返回6条评论、7条历史事件，关联修复、合并和回补提交 | 可作为已核对修复候选；没有回溯证据仍不能给引入提交赋buggy |
| [AMQ-9330](https://issues.apache.org/jira/browse/AMQ-9330) | Bug／Resolved／Fixed，8条评论、10条历史事件，另一组真实修复与回补记录 | 与后续修复代码有关联，但不能据文本相似就认定是缺陷引入点 |
| [AMQ-9461](https://issues.apache.org/jira/browse/AMQ-9461) | Task／Resolved／Fixed，是版权年份更新 | Fixed不等于Bug；排除出Bug-only修复候选，不代表对应提交是clean |
| [AMQ-9482](https://issues.apache.org/jira/browse/AMQ-9482) | Bug／Open／无resolution，8条评论、2条历史事件，无已提取修复提交证据 | 未解决Bug不产生已确认修复；没有修复关系不能自动变成负例 |

当前[ActiveMQ官方issue入口](https://activemq.apache.org/issues)指向GitHub Issues；保存的Jira页面标示ActiveMQ为Read-Only。历史窗口可以继续核查AMQ键，最新数据不能默认全在Jira。采集接口须保存`tracker_kind + issue_key_or_number + source_url`，GitHub里的数字PR编号也不能直接当Bug issue。

GitHub公开REST元数据探测返回403，响应说明rate limit exceeded；只尝试一次，没有读取本机凭据或反复重试。后续使用公开网页、固定SHA的patch／raw文件和Jira REST，15份来源均HTTP 200。未测量仓库克隆体积，不能把这些小文件的大小或抓取时间当全仓库采集成本。[GitHub官方提交接口说明](https://docs.github.com/en/rest/commits/commits)提供匿名公开读取及分页参数；实际采集应保存分页完整性和限制原因。

## 3. 同一次修复的三种提交

| 对象 | SHA | 本次核对 |
|---|---|---|
| 原始修复 | `72befc14fbb69c24bdec0c7d4a1002da8874380d` | 单父提交，Subject关联AMQ-9481；父提交`6084867b26619ab614bc117667a32649def5887a` |
| 合并提交 | `6e6caf7c6060efadc1ba524147e71d9720fcd935` | 两个父提交，第二父是上述修复；PR-1206将其合入main |
| 回补提交 | `827ad1012b934ca4fff749a5da1a9c1e070a0ee1` | patch消息注明cherry picked from上述原始修复；Jira通知指向5.18.x分支 |

来源为[修复页面](https://github.com/apache/activemq/commit/72befc14fbb69c24bdec0c7d4a1002da8874380d)、[合并页面](https://github.com/apache/activemq/commit/6e6caf7c6060efadc1ba524147e71d9720fcd935)、[PR-1206](https://github.com/apache/activemq/pull/1206)与AMQ-9481原始评论。

首轮提议：用固定main上的单父变更作归因输入；merge负责记录集成事件，不再对同一修复重复归因；其它分支backport保留来源关系但不混入main训练清单。实际采集仍须验证可达性、完整历史及复杂合并边界。这里没有运行blame，也没有找出完整缺陷引入提交。

issue引用先从提交消息解析。AMQ-9481修复patch的测试代码还提到AMQ-9330和AMQ-9418；若扫描整个diff提取issue键，会把这些历史背景误当额外修复关联。

## 4. 标签时间：真实反例

| 事件 | 真实时间，UTC | 来源 |
|---|---|---|
| 原始修复author／committer时间 | 2024-04-21 16:42:20 | 固定提交页面与patch邮件头一致 |
| PR合入main | 2024-04-22 15:01:36 | PR-1206 merge事件 |
| issue状态变成Resolved／Fixed | 2024-04-22 15:07:37.766 | Jira字段与完整changelog |

若训练截止为`2024-04-22T00:00:00Z`，仅比较修复提交时间会误认为修复已可用；实际它还未合入本次限定的main，issue也尚未达到本方案要求的Fixed证据。

**工程提议**：当规则要求“目标分支已集成＋历史可核验Bug/Fixed”时，`label_available_at = max(integrated_at, qualifying_issue_evidence_at)`；本例为`2024-04-22T15:07:37.766Z`。具体规则须版本化，不声称这是论文的统一标准；若改为更早的人工核验，应保留当时核验事件与证据。

现在下载到旧issue不等于在2024年实际观察过它。已重构的历史事件与本次`retrieved_at`分开；历史事件缺失或分页不完整时，不能用当前状态反推所有历史时点。复用老patch、backport或修改author时间也不能回写更早的标签可得性。

## 5. diff与特征边界

AMQ-9481原始修复的全路径diff包含2个Java文件、17行增加、8行删除；其中一个是测试文件，一个是生产文件。已核对hunk中的旧／新行数，并将生产文件的patch作用于独立下载的父文件，结果与独立下载的修复后文件逐行一致。

生产文件`activemq-web/src/main/java/org/apache/activemq/web/async/AsyncServletRequest.java`的旧118行条件和旧121行调用被修改；旧119、120行是注释。这个人工案例可为未来SZZ提供旧118／121行的归因输入，并保留排除注释和测试文件的计数。注释过滤这里只对已人工核对的案例成立，不声称一个简单字符串规则足以解析所有Java语法。

**特征采集与SZZ文件过滤分开**：本例的全路径原始NF/LA/LD为2/17/8；只拿SZZ生产文件范围会变成1/4/4。二者不能使用相同schema名称混训。Kamei特征的Java、测试、生成文件等范围需明确规则版本；SZZ排除测试行不自动意味着Kamei也排除它们。

没有祖先历史，就无法真实计算AGE、NDEV、NUC、EXP等特征；FIX还需预测时可得的消息／issue信息规则。**没有制作用默认零值补满14维的“真实训练CSV”。** 本次所有引入提交标签都保持`unknown_szz_not_executed`。

## 6. 可直接复用的产物

- [来源台账](activemq-2024-sample-20261004/sources.json)：15份原始响应的URL、HTTP状态、获取时间、字节数、SHA-256。
- [结构化案例与8个核对场景](activemq-2024-sample-20261004/case-study.json)：类型反例、分支关系、时间可得性、diff过滤和不完整特征。
- [离线复核脚本](../../scripts/verify_data_sources.py)：独立比较真实修复前后文件、验证来源哈希、issue状态和时间事件，不发网络请求。

在项目根目录执行：

```powershell
python scripts/verify_data_sources.py
```

实际结果：PASS；15份来源哈希及字节数一致；4个issue、8个案例记录；生产文件旧118／121行和真实修复后快照核对一致。它只证明保存的证据和案例整理可复核，不证明SZZ、14维采集、训练或产品已完成。

下一步实现的最小单元已经明确：先做固定分支与窗口的提交清单、候选修复消息及issue核对，保留失败／缺页状态；用这8个场景验收输入契约，再接SZZ与完整历史特征。真实仓库规模、有效正例量、成熟率和训练资源仍须后续实测。

原始源码／patch来自Apache ActiveMQ，只用于课程核查，保留上游头部和来源；[固定SHA的上游源码](https://raw.githubusercontent.com/apache/activemq/72befc14fbb69c24bdec0c7d4a1002da8874380d/activemq-web/src/main/java/org/apache/activemq/web/async/AsyncServletRequest.java)头部注明Apache License 2.0。核查没有联系上游维护者或团队成员、没有写入远端工具。
