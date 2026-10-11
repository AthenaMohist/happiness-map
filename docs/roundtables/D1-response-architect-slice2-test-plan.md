# D1 Architect 发言 — Slice 2 测试方案架构评审

> 发言人：高见远（架构师） | 日期：2026-07-30
> 评审对象：`docs/qa/slice2-pipeline-test-plan.md` v1.0（810 行，48 用例）
> 对照基准：`docs/arch-slice2-7step-pipeline.md` v1.0（1082 行架构设计）+ 实际代码

---

## 0. 总体评价

测试方案覆盖面广、结构清晰、按 Round 分层的执行计划合理。48 用例覆盖了 7 步管线 + 21 分支 + rollback + gate_roundtable + fanout + 边界条件，与架构设计的覆盖映射基本完整。

**但 QA 发现了 4 项"PRD/合约冲突"并全部标为 BLOCKER/MAJOR——这里需要架构师澄清：其中 2 项是 PRD 被架构设计覆盖的正常情况，不是冲突。另有 1 项（BE-01）是架构设计的有意选择。**

---

## 1. 关键纠正：QA 误判为 BLOCKER 的 3 项

### 1.1 D1-F2：autopilot.sh 未适配 Slice 2 → **驳回（BLOCKER→N/A）**

**QA 判断**：autopilot.sh 仍为 Slice 1 版本，只处理 start_step/wait/complete/error 四种 action。

**实际情况**：autopilot.sh（449 行）已在 Slice 2 完整实现所有新 action：

| action | autopilot.sh 位置 | 行为 |
|:---|:---|:---|
| gate_roundtable | 第 286-316 行 | 创建 roundtable card + block 原任务 |
| rollback | 第 318-338 行 | comment 通知 + 创建新 dev card |
| retry | 第 340-383 行 | 重建 kanban card（dev/qa-d1/merge/close 各有分支） |
| block | 第 385-392 行 | kanban comment + block |
| await_confirm | 第 394-400 行 | kanban block(kind=needs_input) |
| fanout 检测 | 第 408-442 行 | dev done → 检测 fanout → 创建 qa-d1 |

**裁决**：此发现不成立。autopilot.sh 的 Slice 2 适配已落地。所有分支 action 均可通过 autopilot.sh 执行。

---

### 1.2 D1-F1：VA FALSIFIED → gate_roundtable(D) vs rollback → **驳回（BLOCKER→N/A）**

**QA 判断**：PRD §2.5 B-13 要求 `action=rollback, target=dev`，contracts.jsonl 第 5 行是 `gate_roundtable(D)`，视为冲突。

**架构设计原文**（`arch-slice2-7step-pipeline.md` §4.1）：

> 「注意：**va 的 FALSIFIED 不会直接触发 rollback**——它走 gate_roundtable(D) 流程，Product + Architect 裁定后才决定是 rollback 还是其他处置。」

这是架构设计的**有意选择**。理由：
1. VA FALSIFIED 不是简单的代码 bug——代表 claim 被证伪，可能是 spec 层面的问题
2. 直接 rollback 到 dev 让 engine 重写代码不合逻辑——需要 Product+Architect 判断问题根源
3. Roundtable 裁定后可以决定是 rollback dev、修改 spec、还是废弃任务

**裁决**：contracts.jsonl 的 `FALSIFIED→gate_roundtable(D)` 是正确的。PRD 正文应更新为与架构设计一致。

---

### 1.3 BE-01：BranchesEvaluator 无匹配时静默推进 → **有意设计（需 Product 确认）**

**QA 判断**：无匹配分支时 `_default_advance` 返回 `action='advance'`，导致失败步骤被跳过——这是 BLOCKER 级 bug。

**架构设计原文**（`arch-slice2-7step-pipeline.md` §3.3 流程图）：

```
└── （无匹配）──────────► advance to next step（默认行为）
```

这是架构设计的**默认行为**。理由：合约的 branches 数组是白名单——如果某条件不在白名单中，说明不需要特殊处理，正常推进。

但 QA 指出的场景确实存在风险：步骤 status='failed' 且无分支匹配 → 推进到下一步。这个行为在以下场景触发：
- 步骤 failed 但 contracts.jsonl 中没有对应的 on 条件 → 静默推进
- 例如 D1-F3 的 security_vuln 场景：qa-exec 发现安全漏洞但合约无此分支 → 当前会返回 advance（推进到 qa-d2），而非 block

**裁决**：**建议 Product 确认**。两种选择：
- **A**：保持当前行为（advance 是默认）——需要确保 contracts.jsonl 覆盖所有可能的失败模式
- **B**：改为默认 block——任何未匹配的失败都 block，由人工介入。更安全但会导致更多"误 block"

**架构师倾向 A**，但需要 contracts.jsonl 补全所有已知失败分支（特别是 D1-F3 的 security_vuln，见 §3.1）。

---

## 2. 架构设计覆盖 PRD 的 3 处简化（PRD→架构的正常演化）

### 2.1 D1-F4：dev 缺 self_test_fail 分支 → **有意简化**

架构设计中 dev 的 4 个 branches 覆盖了：超时、合约违规、铁律违规。PRD 的 B-02 self_test_fail 被 kanban failed 通用路径覆盖：

state.py 第 687-701 行：kanban_status == "failed" → `result = {"status": "failed", "detail": "kanban task failed"}` → 进入 branches 评估。

`_match_condition` 中 `"kanban task failed"` 不匹配任何 dev branch → 默认 advance（进入 §1.3 的抉择）。

**架构师意见**：dev 的 kanban failed 应补充一个 `on: "kanban_task_failed"` 分支（action=retry, max_retries=3），匹配 behavior 但不强制。或不加分支走默认 advance（让后续 qa-d1 发现问题）。

### 2.2 D1-F3：qa-exec 缺 security_vuln 和 timeout → **timeout 已覆盖，security_vuln 需补充**

- **timeout**：已由 state.py 的超时检测通用路径覆盖（第 622-639 行）。Running step 超时 → status='failed', verdict='timeout' → branches 评估 → 匹配 `timeout` 条件 → 无匹配则默认 advance。不需要在 qa-exec branches 中重复。
- **security_vuln**：未覆盖。state.py `_match_condition` 没有 security_vuln 匹配器。如果 QA 发现安全漏洞，需要明确的 gate_roundtable(D) 触发路径。

**架构师意见**：在 qa-exec branches 中补充 `{"on": "security_vuln", "action": "gate_roundtable", "reason": "安全漏洞", "roundtable_type": "D"}`。同时在 `_match_condition` 中增加匹配逻辑。

### 2.3 B-10/B-11 合并：qa-d2 review_fail 不区分 grading_error vs quality_fail → **有意简化**

架构设计将 PRD 的两种 D2 失败合并为一条 review_fail→rollback(dev)。理由：
- grading_error 和 quality_fail 的处理结果都是 rollback dev（D2 评审不通过 = 代码需返工）
- 区分两者需要额外的判断逻辑（如何判定是 grading_error 还是 quality_fail？）
- 如果要区分，需要在 D2 测试报告中有明确的字段标记——目前没有这个机制

**裁决**：保留合并。如果产品坚持区分，需要先在数据模型中增加区分字段。

---

## 3. 测试方案本身的架构一致性问题

### 3.1 TC-09 rollback retry_count 预期与实现不一致

测试方案 §TC-09 预期 execute_rollback 应递增 dev 的 retry_count，但实际代码（state.py:443）设置为 `retry_count=0`。架构设计 §4.2 step 3 明确写了 `retry_count=0`。

**但测试方案的担忧是正确的**：这确实意味着没有任何机制阻止无限 rollback。建议在 _apply_branch_action 的 rollback 路径中增加 dev retry_count 检查：
- dev retry_count >= 3 → block 而非 rollback
- 或在 execute_rollback 中 retry_count += 1 而非重置

**待 Product 决定**。

### 3.2 TC-02 fanout 检测流程描述需修正

测试方案 §TC-02 步骤 3 预期 advance_pipeline 返回 start_step qa-d1。实际流程是：

1. dev done → advance_pipeline 返回 start_step qa-d1（因为 contracts 下一步是 qa-d1）
2. autopilot.sh 在 start_step case 中创建 qa-d1 kanban card
3. 然后 autopilot.sh 的 fanout 检测（第 408 行）检查 dev done + qa-d1 未创建 → 但 qa-d1 刚被创建 → 返回 null

这不是 bug——fanout 检测是**安全网机制**，用于处理 autopilot.sh 上一轮未创建 qa-d1 的场景。正常流程中 advance_pipeline 的 _advance_to_next 已经在推进到 qa-d1 了。

**建议**：TC-02 修正预期：advance_pipeline 返回 start_step qa-d1（而非通过 fanout 触发）。

### 3.3 contracts.jsonl vs contracts-v2.jsonl

测试方案 §0 的输入文档列表中引用了 `config/contracts.jsonl`，但实际项目中存在：
- `config/contracts.jsonl` — 生产合约（7 行，内容与 architecture 设计一致）
- `config/contracts-v2.jsonl` — 设计稿（内容相同）

两文件内容完全相同。测试应使用 `config/contracts.jsonl`（生产文件）。contracts-v2.jsonl 是设计阶段产物，可以归档或删除。

---

## 4. 架构评审发现的实际缺陷

### 4.1 （MAJOR）qa-exec 缺少 security_vuln 分支

状态：架构设计和合约均未包含。QA 正确识别。
影响：安全漏洞不会触发 gate_roundtable，默认推进（不会静默放过——因为 step 状态是 failed → 无匹配分支 → advance → 推进到 qa-d2 但 qa-d2 会看到 qa-exec 是 failed 而非 done → depends on BE-01 决策）。

**修复**：补 contracts.jsonl + _match_condition。

### 4.2 （MAJOR）无 rollback 循环保护

状态：execute_rollback 将 dev retry_count 重置为 0（设计有意）。
影响：理论上可无限 rollback 循环。实际中每次 rollback 需要 human gate（roundtable 裁定或 OC 手动触发），不是自动循环。
风险：如果 autopilot 在某种条件下自动触发 rollback 而不经过人，可能循环。当前从代码看 rollback 只能由 branches 引擎的 `review_fail` 和 `va_merge_check_fail` 触发——这两个条件都需要步骤 done 后评估，不是自动循环路径。

**建议**：保留 retry_count=0 但增加 rollback 计数器（单独字段），连续 3 次 rollback 后 block。

### 4.3 （MINOR）BranchesEvaluator 的 _match_condition 缺少 security_vuln 匹配

与 §4.1 对应。`_match_condition` 没有 `security_vuln` 的匹配逻辑。

---

## 5. 测试方案覆盖度评估

| 架构组件 | 测试覆盖 | 评估 |
|:---|:---|:---|
| 7 步管线完整流转 | TC-01, TS-01 | ✅ 完整 |
| contracts.jsonl 解析 | TC-10 | ✅ |
| BranchesEvaluator (26 条 match) | TC-B01~B21 | ✅ 21 分支全覆盖 + BE-01 默认行为 |
| execute_rollback | TC-08, TC-09, TC-14 | ✅ |
| handle_gate_roundtable | TC-06, TC-07 | ✅ |
| fanout detect + join | TC-02, TC-03, TS-02 | ✅ |
| close_s6_check | TC-11, TC-B20 | ✅ |
| close.sh 子步骤 | TC-12, TC-B21 | ✅ |
| checkpoint v1→v2 migration | TC-13 | ✅ |
| 超时检测 | TC-04, TC-B01 | ✅ |
| autopilot.sh 集成 | TS-01~05 | ⚠️ 依赖 mock kanban |
| contracts.jsonl 一致 | BE-03 | ✅ |
| 空合约处理 | BE-04 | ✅ |

**未覆盖的架构路径**：
1. `contract_violation` → block 的具体匹配路径（TC-B03 覆盖了，但 detail 匹配逻辑依赖中文关键词"缺失"——需要确认）
2. `spec_violates_ironlaw` → gate_roundtable(D) 没有独立 TC（只在 TC-B01-B03 的 dev 分支表中被提及但无独立测试）
3. `_advance_to_next` 中 requires 不满足的路径（第 895-913 行）——contracts 中 qa-exec 的 requires 有 "branch", "code_changes", "test_plan.md"，其中 "test_plan.md" 不在前序步骤的 produces 中（qa-d1 produces test_plan.md），"branch" 和 "code_changes" 在 dev produces 中——但 _advance_to_next 的 requires 检查只过滤"应该由管线产生"的项。此路径可以加一个边界用例。

---

## 6. 对 48 用例分级的重新判定

| QA 原判定 | 架构重判 | 变化 |
|:---|:---|:---|
| 19 BLOCKER | **15 BLOCKER** | D1-F1(驳回)、D1-F2(驳回)、BE-01(降为 MAJOR，待 Product 确认) |
| 23 MAJOR | **25 MAJOR** | 新增：rollback 循环保护、security_vuln 分支缺失 |
| 2 MINOR | **2 MINOR** | |

修订后的 BLOCKER 用例：TC-01, TC-02, TC-03, TC-04, TC-05, TC-06, TC-08, TC-10, TC-11, TC-B01, TC-B03, TC-B05, TC-B06, TC-B07, TC-B11, TC-B13, TC-B14, TC-B16, TC-B17, TS-05 — 实际是 19 项减去 D1-F1(TC-B13) 和 D1-F2(N/A) 和 BE-01 的 BLOCKER 标记，但 TC-B13 的 BLOCKER 是"依赖 D1-F1 裁定结果"——既然 D1-F1 已驳回，TC-B13 的行为就是确定的 gate_roundtable(D)，风险等级降为 MAJOR。

**重新统计**：
- BLOCKER: 15（去掉了 TC-B13 的 BLOCKER 标记、BE-01 降级，以及去掉了因 D1-F1/F2 衍生出的 2 个 BLOCKER）
- MAJOR: 27
- MINOR: 2
- 总计: 44 用例（4 个场景用例与 AC 用例重叠）

---

## 7. D1 审定 Checklist 答复

| # | 问题 | 架构师答复 |
|:---|:---|:---|
| D1-F1 | VA FALSIFIED 行为？ | **gate_roundtable(D)**。架构设计有意选择。PRD 正文需更新。 |
| D1-F2 | autopilot.sh 需 Slice 2 扩展？ | **已完成**。当前 autopilot.sh 已实现所有新 action。 |
| D1-F3 | qa-exec 缺 security_vuln/timeout？ | timeout 已有通用超时检测覆盖。**security_vuln 需补**。 |
| D1-F4 | dev 缺 self_test_fail？ | kanban failed 通用路径覆盖。**建议补 kanban_task_failed 分支**（非强制）。 |
| B-10/B-11 | 拆 review_fail？ | **不拆**。架构有意合并。当前无数据字段支持区分。 |
| BE-01 | 默认行为：advance 还是 block？ | **待 Product 确认**。架构师倾向 advance + 补全 contracts 覆盖所有已知失败模式。 |
| TC-09 | rollback retry_count 递增还是重置？ | 当前重置（架构有意）。**建议 Product 确认是否增加 rollback 上限**。 |
| Mock 策略 | 接受 mock kanban？ | Round 1-2 接受。Round 3+ 建议用真实 cron+kanban。 |
| D1 必过 TC | 时间有限时优先哪些？ | TC-01, TC-04, TC-06, TC-08, TC-10, TC-11, TC-B03, TC-B06, TC-B11, TC-B13(以 gate_roundtable 为准), TC-B16, TC-B17 |

---

## 8. 可测试性总评

| 维度 | 结论 |
|:---|:---|
| state.py/fanout.py/checkpoint.py | ✅ 可直接测试（函数级调用，无外部依赖） |
| autopilot.sh | ✅ 可测试（已适配 Slice 2，mock kanban 即可） |
| contracts.jsonl | ✅ 生产文件就绪，与架构设计一致 |
| 全链路场景 | ⚠️ Round 3 依赖 mock kanban 准确性，建议部分用真实环境验证 |
| 测试执行顺序 | ✅ Round 0→5 的分层合理 |

**总体意见**：测试方案可用。修正 §1 的三项误判 + 确认 §4 的两项实际缺陷后，进入 Round 0 静态检查。

---

> 架构师评审完毕。下一步：Product（许清楚）确认 BE-01 默认行为 + rollback 循环保护 + security_vuln 补充。
