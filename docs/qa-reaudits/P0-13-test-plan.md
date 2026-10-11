# P0-13 测试方案：Cron context_from 链

> 版本：v1.0 | 状态：Draft — 待评审
> 编制日期：2026-07-08 | 编制人：game-qa（QA）
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0（436 行）
> 原始任务：t_d7ea14bf（Cron context_from 链，v0.18，0.5h）
> 原始验证：t_52ab615e（4/4 PASS）+ t_7ac4eb28（P0-13 实现）

---

## 1. 功能概述

### 1.1 context_from 是什么

Cron jobs 运行在**隔离会话**中——每个 job 没有上一轮运行的内存。`context_from` 参数自动连接它们：当 job B 配置 `context_from=["<job_A_id>"]` 时，job A 的**最近一次输出**在 job B 运行时被注入其 prompt 上下文。

```
┌──────────────┐     context_from      ┌──────────────────┐
│ Job A        │ ─────────────────────→│ Job B            │
│ (上游)       │  上游输出作为 B 的     │ (下游)           │
│              │  prompt 前缀注入       │                  │
└──────────────┘                       └──────────────────┘
```

**关键行为（来自 Hermes 文档）**：
- 支持**单个** job ID（`"a1b2c3d4"`）和**多个** job IDs（`["job_a", "job_b"]`）
- 多个上游按列出的顺序拼接
- 源数据来自 `~/.hermes/cron/output/{job_id}/*.md`
- 注入格式：`## Output from job '<job_id>'` + 代码块包裹的上游完整输出

### 1.2 P0-13 原始验证结果

| # | 检查项 | 结果 | 细节 |
|---|-------|:---:|------|
| 1 | `context_from` 配置正确 | ✅ PASS | job `541553496ddd` 的 `context_from: ["4f05b7c17332"]` |
| 2 | 上游输出注入格式正确 | ✅ PASS | `## Output from job '4f05b7c17332'` + 完整上游输出代码块 |
| 3 | 下游正确解析上游上下文 | ✅ PASS | `"context_received": true, "verification": "success"` |
| 4 | 时序正确 | ✅ PASS | Watchdog 22:30:19 → VA 22:30:35（16s 间隔） |

**验证的 job 链**：
```
Watchdog-Status (4f05b7c17332)
  → 输出：{"source":"watchdog","status":"healthy","active_tasks":4}
  → Verification-Agent (541553496ddd) context_from=["4f05b7c17332"]
  → 输出：{"verification":"success","context_received":true,...}
```

---

## 2. 已有发现

### 2.1 F1：Watchdog 模型自发尝试被阻止的工具调用

| 属性 | 值 |
|------|-----|
| 原始级别 | LOW（观察） |
| 新标准重审级别 | **SUGGESTION** |
| 发现来源 | t_52ab615e（原始 QA 验证） |
| 证据 | agent.log 内部日志中出现 WARNING 级别 tool-call rejection |
| 实际影响 | 无——Watchdog 最终输出正确 JSON，下游 VA 正常接收 |
| 根因 | 模型在 cron 环境下自发尝试 `execute_code` + `kanban` 调用，被 cron 环境正确阻止 |

**判定路径**（按标准 §1.2 五步判定）：

| 步骤 | 检查 | 结果 |
|------|------|:---:|
| 前置 | 安全漏洞？ | ❌ 不是。cron 环境已正确阻止，非安全漏洞 |
| Step 1 | 用户可感知？ | ❌ WARNING 仅出现在 agent.log，终端输出正确 |
| Step 2 | 数据完整性受影响？ | ❌ 输出 JSON 数据正确完整 |
| Step 3 | 系统健康度退化？ | ❌ 这是 cron 环境下的正常访问控制 |
| Step 4 | 纯主观偏好？ | ✅ 优化建议（限制 enabled_toolsets 减少浪费） |

**建议**：为纯文本输出类 cron job 设置 `enabled_toolsets: []` 或在 prompt 中声明「不要调用任何工具」。

### 2.2 链完整性审计

| 发现 | 新标准级别 | 判定 |
|------|:---:|------|
| context_from 链完整 | **PASS** | 审计通过——上游输出成功注入下游，下游正确解析 |

---

## 3. 测试矩阵

### 3.1 测试覆盖维度

| 维度 | 覆盖范围 | 测试用例 |
|------|---------|:---:|
| 功能正确性 | 单链、多上游、深链 | TC-01 ~ TC-03 |
| 容错性 | 上游失败、job 不存在、空输出 | TC-04 ~ TC-07 |
| 边界条件 | 大上下文、循环依赖、并发 | TC-08 ~ TC-10 |
| 安全/隔离 | 工具调用隔离、跨 profile 注入 | TC-11 ~ TC-12 |
| 回归 | 链路完整性、格式稳定性 | TC-13 ~ TC-14 |

### 3.2 功能测试用例

---

#### TC-01：单链 context_from（已通过——验证回归）

```
Given:  两个 cron job：
        - Watchdog-Status（4f05b7c17332）：输出简单 JSON 状态报告
        - Verification-Agent（541553496ddd）：context_from=["4f05b7c17332"]
When:   先运行 Watchdog-Status，完成后运行 Verification-Agent
Then:   a) Verification-Agent 的 prompt 中包含 "## Output from job '4f05b7c17332'"
        b) 包含上游完整输出（代码块包裹）
        c) Verification-Agent 输出中 context_received=true
        d) VA 正确复述上游数据（status/active_tasks 一致）
```

**证据**（2026-07-07 实测）：VA 输出 `"context_received": true, "upstream_data_summary": "Watchdog 报告状态 healthy，4 个活跃任务"` — 与 Watchdog 输出一致。

**回归频率**：每次 cron 功能变更后执行一次。

---

#### TC-02：多上游 context_from 拼接

```
Given:  三个 cron job：
        - Job-A：输出 "DATA_A: 42"
        - Job-B：输出 "DATA_B: hello"
        - Job-C：context_from=["Job-A", "Job-B"]
When:   Job-A → Job-B 依次完成后，Job-C 运行
Then:   a) Job-C 的 prompt 中包含两个 "## Output from job" 区块
        b) 顺序为 Job-A 的输出在前，Job-B 在后
        c) Job-C 能同时访问两个上游的数据
```

**风险点**（来自 v0.18 graft analysis R5.3）：多个 context_from 指定的 job 之间存在循环依赖时需检测。

---

#### TC-03：深链 context_from（A→B→C）

```
Given:  三个 cron job 组成链：
        - Job-A：收集数据（如 kanban 状态）
        - Job-B：context_from=["Job-A"]，对数据进行分类
        - Job-C：context_from=["Job-B"]，生成最终报告
When:   顺序运行 A → B → C
Then:   a) Job-B 能读取 Job-A 的输出
        b) Job-C 能读取 Job-B 的输出
        c) Job-C 无法直接读取 Job-A 的输出（context_from 仅传递直接上游，不递归）
```

**注意**：如果 Job-C 需要 Job-A 的数据，Job-B 必须在自己的输出中保留（或 Job-C 显式列 `context_from=["Job-A", "Job-B"]`）。

---

### 3.3 容错测试用例

---

#### TC-04：上游 job 运行失败

```
Given:  - Job-A：故意设置会导致失败的 prompt（如引用不存在的文件）
        - Job-B：context_from=["Job-A"]
When:   Job-A 运行失败（exit code ≠ 0 或输出为空）
       然后 Job-B 运行
Then:   a) Job-B 仍然正常启动（不因上游失败而跳过）
        b) context_from 注入内容为空，或包含错误标记
        c) Job-B prompt 中不包含有效的上游输出
        d) Job-B 不应静默成功——应标注 "no upstream context available"
```

**风险**（R5.1）：链式故障传播——如果上游失败而下游静默跳过，整条链路失效但无告警。

---

#### TC-05：context_from 指向不存在的 job ID

```
Given:  Job-B 的 context_from=["non_existent_job_id"]
When:   尝试创建 Job-B（cronjob action='create'）
Then:   a) 创建被拒绝，返回明确的错误信息 "job 'non_existent_job_id' not found"
        或
        b) 创建成功但首次运行时注入空上下文 + WARNING 日志
```

**预期行为偏向 (a)**：在创建时就验证 `context_from` 引用的 job 存在，提前失败。

---

#### TC-06：上游 job 输出为空（[SILENT] 返回）

```
Given:  - Job-A：配置为 silent-on-no-data 模式，无变化时输出 "[SILENT]"
        - Job-B：context_from=["Job-A"]
When:   Job-A 运行并返回 "[SILENT]"（不写入输出文件）
       然后 Job-B 运行
Then:   a) context_from 注入内容为上一次有效输出（如果有）
        或
        b) context_from 注入为空
        c) Job-B 不应崩溃或产生幻觉——应标注 context 状态
```

---

#### TC-07：上游输出过大（接近 token 上限）

```
Given:  - Job-A：输出一个 50KB 的 markdown 报告
        - Job-B：context_from=["Job-A"]，prompt 本身体积也不小
When:   Job-B 运行
Then:   a) context_from 注入的上下文被合理截断（truncation marker 明确）
        b) Job-B 不会因 token overflow 而崩溃
        c) 截断时保留上游输出的头部（summary/关键数据）而非尾部
```

**风险**（R5.2）：Context 膨胀——上游输出累积过大时下游被截断。

---

### 3.4 边界条件测试用例

---

#### TC-08：循环依赖检测

```
Given:  - Job-A：context_from=["Job-B"]
        - Job-B：context_from=["Job-A"]
When:   创建或运行这两个 job
Then:   a) 创建时检测到循环依赖 → 拒绝创建
        或
        b) 运行时最多传递一次后检测到循环 → WARNING + 终止链传递
```

**严重度**（R5.3）：CRITICAL——无限循环导致 token 消耗无限增长。

---

#### TC-09：并发上游完成时序

```
Given:  - Job-A：schedule="0 * * * *"（每小时整点）
        - Job-B：schedule="30 * * * *"（每小时半点）
        - Job-C：schedule="45 * * * *"（每小时 45 分）
        context_from=["Job-A", "Job-B"]
When:   所有 job 在同一小时窗口内依次完成
Then:   a) Job-C 获取的是 Job-A 和 Job-B **各自最近一次**输出
        b) 如果 Job-A 在整点失败，Job-C 拿到的是上一次成功的 Job-A 输出
        c) 注入的 Job-A 和 Job-B 输出按时间排序（上游最近的优先）

**风险**（R5.4）：时间语义不明确——"最近一次"可能不是用户期望的"本次周期"。
```

---

#### TC-10：跨 profile 的 context_from

```
Given:  - game-engine profile 创建 Job-A
        - verifier profile 创建 Job-B：context_from=["Job-A"]
When:   Job-B 运行
Then:   a) context_from 能否跨 profile 读取输出？
        或
        b) context_from 仅在同一 profile 内有效
        c) 如果允许跨 profile → 需确认输出文件权限不泄露敏感信息

**风险**（R5.5）：隐私/安全边界——审计类 job 的输出可能包含敏感信息。
```

---

### 3.5 安全与隔离测试用例

---

#### TC-11：工具调用隔离（F1 验证）

```
Given:  - Job-A：prompt 包含「调用 execute_code 读取系统信息」
        - Job-A 的 enabled_toolsets 故意设为 []（无工具）
When:   Job-A 尝试工具调用
Then:   a) 工具调用被 cron 环境阻止
        b) 阻止后模型应**降级输出**（如用静态 JSON 代替）而非崩溃
        c) WARNING 日志记录被阻止的调用但不影响输出正确性
```

**此用例直接验证 F1 的修复建议效果**。

---

#### TC-12：context_from 注入内容不包含敏感信息

```
Given:  Job-A 的输出中包含环境变量泄露（如 API key 片段）
       Job-B：context_from=["Job-A"]
When:   Job-B 运行
Then:   a) 敏感信息不应通过 context_from 传播
        或
        b) 如果无法自动过滤 → doc 中明确警告：上游不输出 credential
```

---

### 3.6 回归测试用例

---

#### TC-13：链路完整性回归

```
Given:  P0-13 已验证的链（Watchdog-Status → Verification-Agent）
       context_from 功能代码变更后
When:   重新触发同一条链
Then:   a) 注入格式不变（"## Output from job '<id>'" + 代码块）
        b) context_received=true
        c) 上游数据被正确复述
```

**执行时机**：每次 Hermes cron 子系统变更后。

---

#### TC-14：context_from 输出格式稳定性

```
Given:  任何 context_from 链
When:   读取下游 job 输出文件（~/.hermes/cron/output/{job_id}/*.md）
Then:   a) 输出文件结构稳定：Prompt 段 → Response 段
        b) context_from 注入的内容出现在 Prompt 段中（非 Response 段中）
        c) 注入标记占一行完整标题，不与其他内容混合
```

---

## 4. 测试环境要求

| 需求 | 理由 |
|------|------|
| 至少 2 个可用的 cron job slot | 用于创建上下游测试 job |
| cron scheduler 运行中 | 非 oneshot 测试需要 scheduler 触发 |
| 至少 2 个 profile（game-engine, verifier） | 跨 profile context_from 测试（TC-10） |
| 大于 50KB 的测试输出文件 | TC-07（上下文截断测试） |

---

## 5. 与新版 QA 标准的对照

| 标准条款 | 适用性 | 说明 |
|---------|:---:|------|
| §1.2 判定公式 | ✅ | F1 按五步判定归入 SUGGESTION |
| §1.3 判定原则 | ✅ | F1 不满足「用户可感知」门槛 |
| §2 安全漏洞 | N/A | 无 OWASP Top 10 范畴的安全发现 |
| §3 性能阈值 | N/A | context_from 注入本身不涉及运行时性能 |
| §4 数据敏感度 | ⚠️ | TC-10/TC-12 涉及跨 profile 数据传输 → 需关注 A 级数据（权限） |
| §6 论证流程 | ✅ | F1 为 SUGGESTION，无驳回/申诉路径 |
| §8 SLA | N/A | SUGGESTION 不触发 SLA |
| §10 发布门禁 | ✅ | SUGGESTION=0 不在门禁公式中，不阻塞发版 |
| §11 产品红线 | N/A | 无触发条件 |

---

## 6. 测试执行优先级

| 优先级 | 用例 | 理由 |
|:---:|------|------|
| **P0** | TC-13（回归） | 每次变更后必跑 |
| **P1** | TC-01（基础链）、TC-04（上游失败）、TC-05（不存在 job） | 核心功能 + 最常见容错场景 |
| **P2** | TC-02（多上游）、TC-03（深链）、TC-07（大输出） | 扩展功能 + 高频边界 |
| **P3** | TC-06（SILENT）、TC-08（循环）、TC-09（并发）、TC-10（跨 profile） | 中低边界 |
| **P4** | TC-11（工具隔离）、TC-12（敏感信息） | 安全/隔离验证 |

---

## 7. 预期产出

### 7.1 测试报告格式

每个用例执行后记录：

```
| TC-NN | 用例名 | 结果 | 实际输出摘要 | 证据文件路径 |
```

### 7.2 发现分级

发现的 bug 按 §1.2 标准分级，分级后填入 QA 发现表格：

```
| 发现 ID | 关联 TC | 描述 | 级别 | 判定路径 | 证据 |
```

---

## 8. 风险登记册

| # | 风险 | 来源 | 严重度 | 概率 | 缓解措施 |
|---|------|------|:---:|:---:|---------|
| R1 | 链式故障传播：上游失败→整链失效 | 嫁接分析 R5.1 | HIGH | MEDIUM | TC-04 验证失败降级行为 |
| R2 | Context 膨胀：大输出→下游截断 | 嫁接分析 R5.2 | MEDIUM | MEDIUM | TC-07 验证截断行为 |
| R3 | 循环依赖：A→B→A 无限 ping-pong | 嫁接分析 R5.3 | CRITICAL | LOW | TC-08 验证检测机制 |
| R4 | 时间语义：下游拿到过期上游数据 | 嫁接分析 R5.4 | MEDIUM | HIGH | TC-09 验证"最近一次"语义 |
| R5 | 隐私边界：跨 profile 上下文泄露 | 嫁接分析 R5.5 | LOW | LOW | TC-10/TC-12 验证隔离 |
| R6 | 工具调用违规：模型在 cron 中尝试非授权工具 | F1 原始发现 | LOW | MEDIUM | TC-11 验证 enabled_toolsets 效果 |

---

## 9. 评审与批准

| 角色 | 签名 | 日期 |
|------|------|------|
| QA（方案编制） | game-qa | 2026-07-08 |
| 研发（技术可行性） | — | — |
| 产品（用户影响） | — | — |
| 架构（系统风险） | — | — |

---

## 附录 A：参考数据

### A.1 已验证的 job 链输出文件

| 文件 | 大小 | 关键内容 |
|------|------|---------|
| `cron/output/4f05b7c17332/2026-07-07_22-30-19.md` | 1172B | Watchdog JSON：`{"source":"watchdog","status":"healthy","active_tasks":4}` |
| `cron/output/541553496ddd/2026-07-07_22-30-35.md` | 2911B | VA JSON：`{"verification":"success","context_received":true}` |
| `cron/output/8e2de5faba3d/2026-07-07_22-28-51.md` | 2374B | Kanban Watchdog 完整看板报告（含 4 个运行中任务） |

### A.2 相关文档

- `docs/standards/qa-finding-classification.md` v1.0 — QA 分级标准
- `~/.hermes/profiles/orchestrator/qa_v018_graft_analysis.md` — 嫁接分析（上下文链风险）
- `hermes-agent.nousresearch.com/docs` — context_from 官方文档
