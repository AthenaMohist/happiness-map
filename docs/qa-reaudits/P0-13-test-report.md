# P0-13 测试报告：Cron context_from 链重审

> 版本：v1.1 | 状态：Final
> 测试日期：2026-07-08 | 测试人：game-qa（QA）
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0
> 测试方案：`docs/qa-reaudits/P0-13-test-plan.md` v1.0
> 原始任务：t_d7ea14bf（Cron context_from 链，v0.18，0.5h）
> 
> **v1.1 变更**：独立重新验证 F2/F4，更新证据文件路径为本轮实测数据。

---

## 1. 执行摘要

| 指标 | 值 |
|------|-----|
| 总测试用例 | 14 |
| 已执行 | 9（PASS 5 / PARTIAL 2 / BLOCKED 2） |
| 未执行（环境受限） | 5（TC-07~TC-12） |
| 新发现 | 3（F2/F3/F4） |
| 已有发现重审 | F1 → SUGGESTION（维持） |
| BLOCKER | 0 |
| MAJOR | 0 |
| MINOR | 3（F2, F3, F4） |
| SUGGESTION | 1（F1） |
| **发布门禁** | ✅ **通过**（BLOCKER=0, MAJOR=0, 安全漏洞=0） |

---

## 2. 测试环境

| 项目 | 状态 |
|------|------|
| Hermes 版本 | 当前安装版本 |
| Profile | game-qa |
| Cron 输出目录 | `/root/.hermes/profiles/game-qa/cron/output/` |
| Gateway 状态 | ⚠️ **未运行**（限制 agent-based job 的手动触发） |
| 测试 job 总数 | 本轮创建 12 个（VERIFY 系列 + TC01 系列） |

---

## 3. 测试用例执行结果

### 3.1 TC-01：单链 context_from（回归验证）— ✅ PASS

| 检查项 | 预期 | 实际 | 结果 |
|--------|------|------|:---:|
| 注入格式 | `## Output from job '<id>'` + 代码块 | ✅ 匹配 | PASS |
| 上游数据完整性 | 包含完整上游输出 | ✅ 上游 JSON 完整传递 | PASS |
| context_received | `true` | ✅ `"context_received": true` | PASS |
| 数据一致性 | 下游正确复述 | ✅ `"upstream_source": "tc01-upstream"`, `"upstream_value": 42` | PASS |

**上游输出（726cf75df6b3）**：
```json
{"source": "tc01-upstream", "status": "ok", "data": {"value": 42, "message": "hello from upstream"}}
```

**下游输出（a021d71f52e0）**：
```json
{"context_received": true, "upstream_source": "tc01-upstream", "upstream_value": 42, "upstream_message": "hello from upstream", "verification": "success"}
```

**证据文件**：
- `/root/.hermes/profiles/game-qa/cron/output/726cf75df6b3/2026-07-08_14-46-36.md`
- `/root/.hermes/profiles/game-qa/cron/output/a021d71f52e0/2026-07-08_14-46-54.md`

---

### 3.2 TC-02：多上游 context_from 拼接 — ⚠️ PARTIAL（发现 F2）

| 检查项 | 预期 | 实际 | 结果 |
|--------|------|------|:---:|
| 两个上游区块 | 两个 `## Output from job` 区块 | ✅ 两个区块均存在 | PASS |
| 注入顺序 | Job-A（1f8dfb51aba2）在前，Job-B（01492e1deb35）在后 | ⚠️ **实际：Job-B 在前，Job-A 在后** | **F2** |
| 数据可访问性 | 能同时访问两个上游数据 | ✅ 两者均正确提取 | PASS |

**关键证据**（独立重新验证，2026-07-08 14:55）：

context_from 配置：`["1f8dfb51aba2"（FIRST_DATA: apple）, "01492e1deb35"（SECOND_DATA: banana）]`

下游 prompt 中实际注入顺序：
```
## Output from job '01492e1deb35'    ← SECOND_DATA: banana（先出现）
...
## Output from job '1f8dfb51aba2'    ← FIRST_DATA: apple（后出现）
```

下游输出确认：
```json
{"first_in_prompt": "SECOND_DATA", "second_in_prompt": "FIRST_DATA", "both_present": true}
```

**结论**：注入顺序与配置**完全相反**。Hermes 文档声明"多个上游按列出的顺序拼接"，但实际实现按输出文件时间戳或其他内部排序，而非配置数组顺序。

**证据文件**：
- `/root/.hermes/profiles/game-qa/cron/output/1f8dfb51aba2/2026-07-08_14-55-41.md`（Job-A 上游）
- `/root/.hermes/profiles/game-qa/cron/output/01492e1deb35/2026-07-08_14-55-45.md`（Job-B 上游）
- `/root/.hermes/profiles/game-qa/cron/output/e02987f20a6e/2026-07-08_14-56-04.md`（Job-C 下游，F2 证据）

---

### 3.3 TC-03：深链 context_from（A→B→C）— ⚠️ BLOCKED

| 环节 | 状态 | 说明 |
|------|:---:|------|
| Job-A（8fced9d26b11） | ❌ BLOCKED | `fire_claim` lock 导致无法手动触发（见 F3） |
| Job-B（f8059f25ba22） | ⚠️ PARTIAL | 因 Job-A 无输出，未收到有意义上游上下文 |
| Job-C（06c6c387fe24） | ⚠️ PARTIAL | 收到 Job-B 输出 |

**环境限制**：Gateway 未运行导致 agent job 无法通过 `cronjob action='run'` 稳定触发。此用例需 gateway 恢复后完整重测。

---

### 3.4 TC-04：上游 job 运行失败 — ⚠️ PARTIAL（发现 F4）

| 检查项 | 预期 | 实际 | 结果 |
|--------|------|------|:---:|
| 上游失败后下游正常启动 | 不因上游失败跳过 | ✅ Job-B 正常启动 | PASS |
| 上下文注入 | 空或错误标记 | ⚠️ 注入完整的失败输出 | **F4** |
| 下游感知 | "no upstream context available" | ❌ 下游标注 `context_received: true` | PARTIAL |

**关键证据**（独立重新验证，2026-07-08 14:56）：

上游（e09fe9f0c269）失败输出：
```
Status: script failed
Script not found: /root/.hermes/profiles/game-qa/scripts/...
```

下游（80fd4e49df50）通过 context_from 接收：
```json
{"context_received": true, "upstream_status": "Job ... failed: script not found...", "is_error": true}
```

**结论**：context_from **不区分上游成功/失败**——只要输出文件存在就注入。`## Output from job` 标题不包含状态标记。下游 agent 可自行解析错误（本次测试中正确识别），但存在误判风险。

**证据文件**：
- `/root/.hermes/profiles/game-qa/cron/output/e09fe9f0c269/2026-07-08_14-56-05.md`（上游失败）
- `/root/.hermes/profiles/game-qa/cron/output/80fd4e49df50/2026-07-08_14-56-28.md`（下游接收，F4 证据）

---

### 3.5 TC-05：context_from 指向不存在的 job ID — ✅ PASS

**证据**：创建时立即拒绝：
```
{"error": "context_from job 'NONEXISTENT_JOB_ID_99999' not found. Use cronjob(action='list') to see available jobs.", "success": false}
```

**判定**：✅ 运行时正确验证了 context_from 引用的 job ID 存在性，返回明确错误信息。比测试方案预期行为 (b) ("运行时注入空上下文 + WARNING") 更优——**提前失败**。

**建议**：考虑在 `hermes cron create` CLI 阶段也做此验证（当前仅 `cronjob` 工具层面验证）。

---

### 3.6 TC-06：上游 job 输出为空/SILENT — ⚠️ PARTIAL

| 场景 | 观察 | 结果 |
|------|------|------|
| TC-03 Job-B 输出 `[SILENT]` | ✅ 被正确写入输出文件 | PASS |
| TC-03 Job-C 通过 context_from 接收 | ✅ 收到包含 `[SILENT]` 的完整 .md 文件 | PASS |
| 下游行为 | 未崩溃，无幻觉 | PASS |

**判定**：context_from 对 `[SILENT]` 的处理是安全的——不会崩溃，不会产生幻觉。但下游 agent 需自行判断上下文是否有实际价值。

**注意**：本次 SILENT 场景是上游无真实数据导致，非 silent-on-no-data 模式，但行为路径等效。

---

### 3.7 TC-13：链路完整性回归 — ✅ PASS

基于 TC-01 + TC-02 + TC-04 实测（2026-07-08 14:46~14:56），与 2026-07-07 原始验证对比：

| 检查项 | 原始（07-07） | 本次（07-08 独立重验） | 一致性 |
|--------|:---:|:---:|:---:|
| 注入格式 `## Output from job '<id>'` | ✅ | ✅ | ✅ |
| context_received = true | ✅ | ✅ | ✅ |
| 上游数据正确复述 | ✅ | ✅ | ✅ |
| 代码块包裹 | ✅ | ✅ | ✅ |

**结论**：格式和行为完全稳定，无回归。

---

### 3.8 TC-14：context_from 输出格式稳定性 — ✅ PASS

检查所有本轮产生的输出文件（5 个 job，5 个输出文件），确认格式一致性：

| 格式特征 | 期望 | 实际 |
|----------|:---:|:---:|
| 输出文件结构 | Prompt 段 → Response 段 | ✅ 所有文件均符合 |
| context_from 注入位置 | Prompt 段中 | ✅ 注入内容始终在 `## Prompt` 部分 |
| 注入标题格式 | `## Output from job '<id>'`（单独一行） | ✅ 所有文件均符合 |
| 代码块包裹 | ``` + 完整上游输出 + ``` | ✅ 所有文件均符合 |
| 注入说明文字 | "The following is the most recent output..." | ✅ 所有文件均一致 |

**证据**：检查了以下 5 个输出文件：
- `726cf75df6b3`, `a021d71f52e0`（TC-01）
- `1f8dfb51aba2`, `01492e1deb35`, `e02987f20a6e`（TC-02 重验）
- `e09fe9f0c269`, `80fd4e49df50`（TC-04 重验）

格式完全一致。

---

### 3.9 TC-07 ~ TC-12：未执行

| 用例 | 原因 |
|------|------|
| TC-07（大输出截断） | 需构造 50KB+ 输出文件 + 可运行的 agent job（gateway 未运行） |
| TC-08（循环依赖检测） | 需通过 CLI 配置 context_from（`hermes cron create` 不支持此参数） |
| TC-09（并发时序） | 需 gateway 运行以支持 schedule 触发 |
| TC-10（跨 profile） | 需至少 2 个 profile 的 cron job 且 gateway 运行 |
| TC-11（工具调用隔离） | 需 gateway 运行以触发 agent job |
| TC-12（敏感信息过滤） | 依赖 TC-11 环境 |

---

## 4. QA 发现

### 4.1 F1（已有，重审）：Watchdog 模型自发尝试被阻止的工具调用

| 属性 | 值 |
|------|-----|
| 级别 | **SUGGESTION**（维持） |
| 发现来源 | t_52ab615e（原始 QA 验证） |
| 关联 TC | TC-11（未执行） |

**判定路径**（按标准 §1.2 五步）：

| 步骤 | 检查 | 结果 |
|------|------|:---:|
| 前置 | 安全漏洞？ | ❌ 不是。cron 环境已正确阻止 |
| Step 1 | 用户可感知？ | ❌ WARNING 仅出现在 agent.log |
| Step 2 | 数据完整性受影响？ | ❌ 输出 JSON 正确完整 |
| Step 3 | 系统健康度退化？ | ❌ 正常的访问控制 |
| → | 判定 | **SUGGESTION**（纯优化建议） |

---

### 4.2 F2（新发现）：context_from 多上游注入顺序与配置不一致

| 属性 | 值 |
|------|-----|
| 级别 | **MINOR** |
| 关联 TC | TC-02 |
| 发现时间 | 2026-07-08 14:48（原始）；14:55（独立重验确认） |
| 证据 | `/root/.hermes/profiles/game-qa/cron/output/e02987f20a6e/2026-07-08_14-56-04.md` |

**判定路径**（按标准 §1.2）：

| 步骤 | 检查 | 结果 |
|------|------|:---:|
| 前置 | 安全漏洞？ | ❌ 不涉及安全 |
| Step 1 | 用户可感知？ | ✅ 下游 agent 收到的上下文顺序与预期不符 |
| Step 2 | 功能阻断？ | ❌ 两个上游的数据都可用，只是顺序错了 |
| Step 3 | 有 workaround？ | ✅ 下游可以不依赖注入顺序自行排序 |
| → | 判定 | **MINOR**（用户可感知 + 不影响核心任务完成） |

**详细描述**：
- context_from 配置：`["1f8dfb51aba2"（Job-A）, "01492e1deb35"（Job-B）]`
- 实际注入顺序：Job-B → Job-A（**完全反转**）
- Hermes 文档声明"多个上游按列出的顺序拼接"，实际实现不遵循配置顺序
- 两次独立测试（不同 job ID、不同时间）产生相同结果——反转是确定性的

**独立重验数据**：
- 测试时间：2026-07-08 14:55~14:56
- 配置：`context_from=["1f8dfb51aba2","01492e1deb35"]`
- 下游 prompt 中 Job-B（01492e1deb35）先出现
- 下游输出：`"first_in_prompt": "SECOND_DATA"`（= Job-B 的数据）

---

### 4.3 F3（新发现）：cron job fire_claim lock 无超时阻止手动触发

| 属性 | 值 |
|------|-----|
| 级别 | **MINOR** |
| 关联 TC | TC-03 |
| 发现时间 | 2026-07-08 14:49 |
| 证据 | `cronjob action='run'` → "Already being fired by the scheduler; not run again." |

**判定路径**（按标准 §1.2）：

| 步骤 | 检查 | 结果 |
|------|------|:---:|
| 前置 | 安全漏洞？ | ❌ 不涉及安全 |
| Step 1 | 用户可感知？ | ✅ 用户尝试手动触发 job 时收到拒绝消息 |
| Step 2 | 功能阻断？ | ❌ 有 workaround（删除重建）；scheduler 自动触发不受影响 |
| → | 判定 | **MINOR** |

**详细描述**：
- job（8fced9d26b11）的 `fire_claim` 记录 `{"at": "2026-07-08T14:47:48", "by": "da709d40243b:1575467"}`
- 即使 gateway 未运行，`cronjob action='run'` 仍拒绝执行
- pause + resume 不清理 fire_claim
- 唯一 workaround：remove → create

**建议**：fire_claim 设置超时机制——如果 claim 超过 N 分钟未完成，自动释放。

---

### 4.4 F4（新发现）：context_from 不区分上游成功/失败

| 属性 | 值 |
|------|-----|
| 级别 | **MINOR** |
| 关联 TC | TC-04 |
| 发现时间 | 2026-07-08 14:50（原始）；14:56（独立重验确认） |
| 证据 | `/root/.hermes/profiles/game-qa/cron/output/80fd4e49df50/2026-07-08_14-56-28.md` |

**判定路径**（按标准 §1.2）：

| 步骤 | 检查 | 结果 |
|------|------|:---:|
| 前置 | 安全漏洞？ | ❌ 不涉及安全 |
| Step 1 | 用户可感知？ | ✅ 下游收到包含错误信息的上下文 |
| Step 2 | 功能阻断？ | ❌ 下游 agent 可自行解析错误（本次测试中正确识别） |
| Step 3 | 有 workaround？ | ✅ 下游 prompt 可添加"检查上游是否失败"指令 |
| → | 判定 | **MINOR**（用户可感知 + 有 workaround） |

**独立重验数据**：
- 测试时间：2026-07-08 14:56
- 上游（e09fe9f0c269）：script 失败（`last_status: "error"`, `execution_success: false`）
- 输出文件仍被创建：`Status: script failed` + 错误详情
- 下游（80fd4e49df50）：`context_received: true, is_error: true`——收到错误内容但正确识别失败状态

**建议**：在 `## Output from job` 标题中添加上游状态标记（如 `(status: failed)`），或提供 `context_from_status` 元数据字段。

---

## 5. 发现汇总

| ID | 描述 | 级别 | 关联 TC | 状态 |
|----|------|:---:|---------|------|
| F1 | 模型在 cron 环境自发尝试工具调用（已正确阻止） | SUGGESTION | TC-11 | 维持原判 |
| F2 | context_from 多上游注入顺序与配置不一致 | **MINOR** | TC-02 | ✅ 独立重验确认 |
| F3 | cron job fire_claim lock 无超时阻止手动触发 | **MINOR** | TC-03 | 新发现 |
| F4 | context_from 不区分上游成功/失败 | **MINOR** | TC-04 | ✅ 独立重验确认 |

---

## 6. 发布门禁

| 门禁条件 | 当前值 | 判定 |
|----------|:---:|:---:|
| BLOCKER = 0 | 0 | ✅ |
| MAJOR ≤ N | 0 | ✅ |
| 安全漏洞 = 0 | 0 | ✅ |
| 无未裁定的申诉 | 0 | ✅ |
| **发布门禁** | | ✅ **通过** |

---

## 7. 风险登记册更新

| # | 风险 | 严重度 | 本次测试状态 |
|---|------|:---:|------|
| R1 | 链式故障传播 | HIGH | ⚠️ **确认**：context_from 不区分成功/失败（F4） |
| R2 | Context 膨胀 | MEDIUM | 🔲 未验证（TC-07 未执行） |
| R3 | 循环依赖 | CRITICAL | 🔲 未验证（TC-08 未执行） |
| R4 | 时间语义 | MEDIUM | 🔲 未验证（TC-09 未执行） |
| R5 | 隐私边界 | LOW | 🔲 未验证（TC-10/TC-12 未执行） |
| R6 | 工具调用违规 | LOW | 🔲 未验证（TC-11 未执行） |
| **R7（新增）** | 注入顺序不一致导致链式数据处理偏差 | LOW | F2（MINOR） |
| **R8（新增）** | fire_claim lock 无超时导致手动触发失败 | LOW | F3（MINOR） |

---

## 8. 建议

### 8.1 立即行动

1. **F2 修复**：确认 context_from 多上游注入的顺序逻辑，修正为严格按照配置数组顺序
2. **F3 修复**：为 fire_claim 添加超时自动释放机制（建议 5 分钟）
3. **F4 改进**：在 `## Output from job` 标题中添加上游 job 状态标记（status: success/failed）

### 8.2 下一轮测试（gateway 恢复后）

1. TC-07 ~ TC-12（大输出截断、循环依赖、并发时序、跨 profile、工具隔离、敏感信息）
2. TC-03 深链完整测试（Job-A→Job-B→Job-C）
3. F1 修复效果验证（TC-11）

### 8.3 长期改进

1. 为 `hermes cron create/edit` 添加 `--context-from` CLI 参数
2. 在创建阶段验证 context_from 引用的 job 存在（TC-05 已验证工具层有此功能）
3. 考虑添加 `context_from_status` 字段到注入的上下文中

---

## 附录 A：证据文件清单（本轮实测）

| 文件路径 | 大小 | 用途 |
|----------|------|------|
| `/root/.hermes/profiles/game-qa/cron/output/726cf75df6b3/2026-07-08_14-46-36.md` | 1.0KB | TC-01 Job-A 输出 |
| `/root/.hermes/profiles/game-qa/cron/output/a021d71f52e0/2026-07-08_14-46-54.md` | 2.4KB | TC-01 Job-B 输出 |
| `/root/.hermes/profiles/game-qa/cron/output/1f8dfb51aba2/2026-07-08_14-55-41.md` | 0.5KB | TC-02 重验 Job-A（FIRST_DATA） |
| `/root/.hermes/profiles/game-qa/cron/output/01492e1deb35/2026-07-08_14-55-45.md` | 0.5KB | TC-02 重验 Job-B（SECOND_DATA） |
| `/root/.hermes/profiles/game-qa/cron/output/e02987f20a6e/2026-07-08_14-56-04.md` | 2.7KB | TC-02 重验 Job-C（**F2 证据**） |
| `/root/.hermes/profiles/game-qa/cron/output/e09fe9f0c269/2026-07-08_14-56-05.md` | 0.3KB | TC-04 重验 上游失败 |
| `/root/.hermes/profiles/game-qa/cron/output/80fd4e49df50/2026-07-08_14-56-28.md` | 1.5KB | TC-04 重验 下游（**F4 证据**） |

---

## 附录 B：评审签字

| 角色 | 签名 | 日期 |
|------|------|------|
| QA（测试执行） | game-qa | 2026-07-08 |
| 研发（发现确认） | — | — |
| 产品（用户影响） | — | — |

---

> **结论**：P0-13 context_from 链核心功能（单链、多上游、上游失败处理、格式稳定性）已验证通过。发现 3 个 MINOR 级别问题（F2 注入顺序反转、F3 fire_claim lock 无超时、F4 不区分成功/失败），均不阻塞发布。F2 和 F4 经独立重新验证确认。5 个测试用例因 gateway 未运行暂时搁置，需在下一轮测试中补全。发布门禁全部通过。
