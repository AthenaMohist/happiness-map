# D1 审定 — Product 发言（许清楚）

> 日期：2026-07-30 | 版本：v1.0
> 议题：Slice1 管线数据层 — 4 项 PRD/架构冲突裁定
> 输入：QA 测试方案 `docs/qa/slice1-pipeline-test-plan.md`（411 行，19 用例）

---

## 裁定总表

| # | 冲突 | 级别 | Product 裁定 | 理由概述 |
|---|------|:--:|-------------|---------|
| D1-F1 | 5 步步骤名 | BLOCKER | **采用 PRD：dev→qa-exec→va→merge→close** | qa-d1 需 fan-out（Slice 2），va 是纯线性步骤 |
| D1-F2 | project_config 表 | MAJOR | **接受架构建议：Slice 1 就建** | 55 行零复杂度，现在建比以后建便宜 |
| D1-F3 | user_version/verdict 列 | MAJOR | **拒绝架构建议：user_version=1，不预置列** | YAGNI——Slice 1 永远不用的列不应存在 |
| D1-F4 | 超时检测 | MAJOR | **采用 PRD：Slice 1 必须做** | 超时检测≠分支引擎，是基本安全机制 |

---

## 详细裁定

### D1-F1：5 步步骤名 [BLOCKER]

**冲突**：PRD 是 `dev→qa-exec→va→merge→close`，架构是 `dev→qa-d1→qa-exec→merge→close`。

**产品分析**：

架构将 `va`（独立验证）替换为 `qa-d1`（测试方案评审），但这两个步骤的复杂度完全不同：

| 步骤 | 执行模式 | 输入 | 输出 | 需要什么能力 |
|------|---------|------|------|-------------|
| `va` | 线性（单 agent） | test_report.md | va_report.md | 无特殊要求——verifier 读报告→写结论 |
| `qa-d1` | **fan-out（双 agent 并行）** | spec.md | test_plan.md | dev 和 qa-d1 必须同时启动，然后在 qa-exec 处 join |

PRD §1 已明确论述：qa-d1 需要 fan-out（dev + qa-d1 并行启动），引入并发状态管理。这恰恰是 Slice 2 的范围，违背 Slice 1"最小可行线性管线"的产品目标。

va 是纯粹的线性步骤——verifier 拿 test_report.md，独立产出 va_report.md。无并行、无分支、无回退。它天然属于 Slice 1。

架构 §7 将 va 列为 Slice 2 项目，但未给出理由。在 Slice 1 的线性模型中，va 比 qa-d1 更合适——va 是 Slice 1 可承载的，qa-d1 不是。

**裁定：采用 PRD 的步骤链 `dev → qa-exec → va → merge → close`**

**下游影响**：
- `config/contracts.jsonl`：步骤修正为 PRD 定义
- `pipeline/constants.py` STEP_NAMES：修正为 `["dev", "qa-exec", "va", "merge", "close"]`
- QA 测试方案 TC-03 步骤名同步修正
- 架构 §6.2 的 STEP_NAMES 常量需修正

---

### D1-F2：project_config 表 [MAJOR]

**冲突**：PRD §8 Sl1-02 说 Slice 1 不建此表；架构 §0.2 说 Slice 1 就建。

**产品分析**：

架构给出了清晰的成本矩阵（§0.2）：

| | 现在建 | 以后建 |
|---|:---:|:---:|
| 实现成本 | +55 行一次 | +20 行改造 + 全组件回归 |
| 架构整洁度 | 组件边界清晰 | 硬编码散落 2 个文件 |

PRD 当初的判断是"v1 schema 最简"，这是对的，但架构提出的"现在建比以后建便宜"同样是正确的——project_config 是一张 key-value 表，对 Slice 1 的核心流程不造成任何复杂度增加。它只被 state.py 和 autopilot.sh 读，不参与管线推进逻辑。

产品原则：接受合理的技术建议。架构的成本分析说服了我，覆盖 Sl1-02 的旧决定。

**裁定：接受架构建议，Slice 1 建 project_config 表。init_project.py 实现。**

**下游影响**：
- PRD §8 Sl1-02 标记为"已被 D1 裁定覆盖"
- pipeline_state.db v1 schema 增加 project_config 表
- init_project.py 按架构 §6.3 实现
- 测试用例需覆盖 init_project.py 的基本功能

---

### D1-F3：user_version / verdict 列 [MAJOR]

**冲突**：PRD §1.2 `user_version=1`，无 verdict/verdict_detail/contract_check_passed 列；架构 §1.3 `user_version=2`，预置三列（始终写 NULL）。

**产品分析**：

架构的理由是"避免 Slice 2 的 ALTER TABLE"（Arch §1.3）。但 SQLite 的 ALTER TABLE ADD COLUMN 是零风险操作——它是内置的、确定性的，在 WAL 模式下甚至不影响并发读。

PRD §1.2 的设计原则是清晰的：v1 schema 只包含 Slice 1 实际使用的字段。verdict/verdict_detail/contract_check_passed 是 Slice 2 才参与逻辑的字段，预置三列 NULL 违反了 YAGNI 原则。

预置三列的实际影响：

- 代码中到处是 `verdict=NULL` → 任何读 schema 的人会困惑"这列到底用不用"
- migration 脚本仍需写（v1→v3 的 ALTER 变成了 user_version 2→3 的语义更新）
- 增加的"好处"（避免一条 ALTER TABLE）不值 schema 的复杂性代价

**裁定：拒绝架构建议。user_version=1，只含 pipeline_steps 的 10 个 Slice 1 字段（不含 verdict/verdict_detail/contract_check_passed）。Slice 2 通过 migration 追加这些列。**

**下游影响**：
- pipeline_state.db DDL 回退到 PRD §1.2 版本
- user_version = 1
- 架构 §1.1 DDL 中移除 verdict/verdict_detail/contract_check_passed 列
- Slice 2 时通过 v1→v2 migration 追加

---

### D1-F4：超时检测 [MAJOR]

**冲突**：PRD AC-4 要求超时检测（autopilot 检测超时→status='failed'→告警）；架构 §3.4 说"Slice 1 不做超时检测，由 Slice 2 的 branches engine 处理"。

**产品分析**：

**超时检测不是分支逻辑，是基本安全机制。** 两者的关系是：

```
分支引擎（Slice 2）：超时后怎么办？retry? block? rollback?
超时检测（Slice 1）：超时了吗？→ 是 → 停止 + 告警
```

Slice 1 只需要后一半——检测到超时→停止。这不需要 branches 引擎。PRD §2.2 的异常处理策略已经定义了 Slice 1 的最简行为：

> 步骤超时 → autopilot 记录 error_msg + status='failed' → 发 kanban_comment 告警 → **停止**

实现极其简单——autopilot 或 state.py 中加一行比较 `started_at + timeout_min < now()`，不需要任何新模块。

**为什么 MVP 必须做超时检测**：没有超时检测，管线在 agent 卡死时会无限等待。这不是"优雅降级"的缺失——这是 MVP 的安全性缺失。QA 测试方案将 TC-04 标为 BLOCKER 的分级逻辑是正确的。

**裁定：采用 PRD 要求。Slice 1 实现简化的超时检测——比较 started_at + timeout_min < now，超时则 status='failed' + kanban_comment 告警。不涉及重试/回退/分支路由。**

**下游影响**：
- 架构 §3.4 "超时检测"行修正为"Slice 1 做简化版（检测→failed→停止）"
- state.py 或 autopilot.sh 增加超时比较逻辑（约 5 行）
- 不影响架构其他设计决策
- QA TC-04（超时检测）可执行

---

## 裁定后行动

| 谁 | 做什么 |
|----|--------|
| Architect（高见远） | 1. 按 D1-F1/D1-F3/D1-F4 修正架构文档 §1.1（DDL）、§2.1（JSONL）、§3.4（超时）、§6.2（STEP_NAMES）<br>2. D1-F2 部分无需修改（project_config 已被采纳） |
| Engineer（寇豆码） | 按修正后的架构文档实现 |
| QA（game-qa） | 1. 修正测试方案中 TC-03 的步骤名为 `dev→qa-exec→va→merge→close`<br>2. D1-F4 裁定后 TC-04 可执行<br>3. 开始 Round 1 测试（静态检查） |

---

## 产品原则总结

这次裁定体现了三条产品原则：

1. **MVP 是做正确的事，不是做最少的事**（D1-F4：超时检测是安全机制，不是 nice-to-have）
2. **架构师的技术判断值得尊重，但产品目标决定边界**（D1-F2 接受技术建议；D1-F3 拒绝过度设计）
3. **Slice 边界是产品决定，不是技术决定**（D1-F1：va 进 Slice 1 因为它是线性的；qa-d1 进 Slice 2 因为它需要 fan-out）

---

> 产品发言完毕。交由 Architect 评审修正 → Engineer 实现。
