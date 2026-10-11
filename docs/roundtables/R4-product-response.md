# R4 统一工作流 — Product 发言（首轮）：对照 + 修正 + 标准

> 发言人：许清楚（产品负责人） | 日期：2026-07-30 | 版本：v1.0
> 目标：看完全部 R3 报告 + Frank 7 条反馈后，从产品视角统一修正、输出可执行标准
> 规则：kanban_complete 后传给 architect

---

## 0. 三份 R3 独立卷对照

先回答第一个任务：Product 的 R3 理解和 Architect、Engineer 的 R3 理解对比，哪些一致、哪些不一致。

### 0.1 高度一致的部分（三方共识，不需要讨论）

| 主题 | Architect 说 | Engineer 说 | Product 说 | 结论 |
|------|------------|------------|-----------|------|
| **管线主流程** | dev → qa → verify → merge → close | dev → qa → verify → merge → close | dev → qa → va → merge → close | ✅ 一致 |
| **OpenSpec 位置** | 阶段 0，OC 调用 | 阶段 0，OC 调用 | 阶段 0，OC 调用 | ✅ 一致 |
| **checkpoint 存储** | `/workspace/devPPL/pipeline_state.db`，SQLite WAL | 同，一张 `pipeline_steps` 表 | 同 | ✅ 一致 |
| **autopilot 触发** | cron 轮询 kanban，约 2min 间隔 | cron 每 2min | cron 每 2min | ✅ 一致 |
| **DPL-011 实现路径** | `.hermes.md` 增强 + boot_context cron | `.hermes.md` 两段式 + boot_context cron | `.hermes.md` 双重角色 + cron | ✅ 一致 |
| **close.sh 闭环** | 6 步强制闭环 | 6 步强制闭环 | 6 步不可裁剪 | ✅ 一致 |
| **kanban 为 SSOT** | kanban.db 是任务状态 SSOT | kanban.db 是 source of truth | kanban 是单一事实来源 | ✅ 一致 |
| **SOUL.md 铁律优先级** | 铁律 > OpenSpec spec | （未明确说但隐含） | 铁律 > spec | ✅ 一致 |

**Product 判断**：三方在路径选择和架构边界上高度一致。这意味着「做什么、按什么顺序做」已经没有争议。剩下的分歧集中在细节——步骤内部怎么设计、怎么处理异常。

### 0.2 不一致的部分（需要 R4 统一）

| 主题 | Architect | Engineer | Product（R3 时） | Product（R4 修正后） |
|------|----------|----------|-------------------|---------------------|
| **boot_context 刷新频率** | 每 5min 或 session 启动 | 每 5min | **每 30min（偏慢）** | → 修正为 **每 5min**，与 Engineer 对齐 |
| **QA 嵌入方式** | 仅提及 QA agent 步骤，无 D1/D2 | 仅提及 QA 步骤，无 D1/D2 | 仅提及 QA 步骤，无 D1/D2 | → **三方都漏了 D1/D2**（见 §2） |
| **失败分支处理** | §6 故障模式有结构分析，但未嵌入主流程图 | §2.2 文件级失败处理，但未嵌入主流程 | §2.4 条件路由提到但未细化 | → **三方都画了 happy path**（见 §1） |
| **Autopilot vs Watchdog** | 未专门对比 | §6.1 有对比表 | 未提及 | → 需补充（见 §4） |
| **Frank 视角的红绿灯** | 未覆盖 | 未覆盖 | §6 有 Frank 视角但粒度不够 | → 需细化（见 §5） |
| **Product 在 Engineer 报告里的位置** | — | **完全缺失** — Engineer 的角色列表没有 Product | — | → 需修正（见 §6） |

**Product R4 核心修正方向**（自我纠错）：
1. Boot context 频率从 30min → 5min。30min 太慢——意味着上一个 session 结束后最快 30 分钟才能让下一个 session 看到上下文，不可接受。
2. QA 环节从「一个 QA 步骤」→「D1 测试方案评审 + QA 测试执行 + D2 测试报告评审」，三个子阶段。

---

## 1. Frank 反馈 #1：失败分支处理 — 每个节点的 if 条件

> 「流程都是单线，没有分支情况或 if 失败情况的处理方案。需要落实到纸面：每个节点的 if 条件 + 失败时跳转到哪」

**承认**：三方 R3 都画了 happy path。Product R3 提了「条件路由」但没有嵌入到主流程的每一跳。

### 1.1 修正后的完整分支流程图（每个节点带 if）

```
Frank 说"做 X"
    │
    ▼
[Node 0: OC 理解 + 规范生成]
    │── 产出: OpenSpec spec.md + validate 通过
    │
    │ IF spec validate 不通过:
    │   → OC 修正 spec → 重新 validate（最多 3 次）
    │   → 3 次仍失败 → block, 通知 Frank "spec 无法通过验证"
    │
    │ IF spec 与 SOUL.md 铁律冲突:
    │   → OC 标记冲突 → block → 创建 D 类 roundtable
    │   → Frank 裁定: (a) 修改 spec, 继续 / (b) 铁律例外（需 Frank 签字）
    │
    ▼
[Node 1: kanban 创建 + 分发]
    │── 产出: kanban task t_xxx, status=ready, assignee=game-engine
    │
    │ IF kanban_create 失败（API 不可用 / 格式错误）:
    │   → 重试 3 次（间隔 10s）
    │   → 3 次仍失败 → block, 通知 OC "kanban 创建失败"
    │
    ▼
[Node 2: 研发 dev]
    │── 产出: 分支 + 代码改动 + engine 自测通过
    │
    │ IF engine 超时（> 60min 未产出）:
    │   → autopilot 检测到超时 → kanban comment [AUTOPILOT: dev timeout]
    │   → 重试一次（重新 dispatch engine）
    │   → 仍超时 → block, 通知 Frank "P0-XX dev 超时，需要介入"
    │
    │ IF engine 自测失败:
    │   → engine 自行修复（不离开 dev 步骤）
    │   → 3 次修复仍失败 → 标记 dev blocked → OC 介入
    │
    │ IF engine 忘记 commit（产物不存在）:
    │   → state.py 合约校验: requires ["branch","code_changes"] 失败
    │   → 检测方式: 检查 repo 是否有 engine 的分支 + 文件改动非空
    │   → autopilot 写 comment [CONTRACT_VIOLATION: dev produces 缺失]
    │   → 不创建 QA 卡片 → 等待 engine 补交产物
    │   → 超时 30min → block, 通知 OC
    │
    ▼
[Node 3: QA D1 — 测试方案生成 + 评审]           ← 新增
    │── 产出: test_plan.md
    │
    │ IF QA 无法生成测试方案（需求理解不清）:
    │   → 升为 D 类 roundtable → block
    │
    │ IF test_plan.md 未覆盖 spec.md 中所有 requires:
    │   → D1 评审不通过 → QA 补充 → 重新 D1（最多 2 次）
    │   → 2 次仍不通过 → block, 通知 Product "测试方案未覆盖关键路径"
    │
    ▼
[Node 4: QA 测试执行]
    │── 产出: test_report.md（含分级判定）
    │
    │ IF QA 执行中发现 BLOCKER:
    │   → autopilot 写 [GATE: D 类 roundtable, BLOCKER found]
    │   → 阻塞当前管线，通知 Frank + Product
    │   → Frank 裁定后: (a) 继续（BLOCKER 转 MAJOR）/ (b) 回退 dev
    │
    │ IF QA 执行中发现 MAJOR（非 BLOCKER）:
    │   → autopilot 判定: MAJOR ≤ 3 → 继续（记录到 kanban comment）
    │   → MAJOR > 3 → 等同于 BLOCKER 处理
    │
    │ IF D2 roundtable 发现 MAJOR（Frank 具体提到的场景）:
    │   → 走 MAJOR 判定流程
    │   → IF MAJOR > 3 或涉及安全漏洞 → block + roundtable
    │   → IF MAJOR ≤ 3 → 记录 + 继续推进
    │
    ▼
[Node 5: QA D2 — 测试报告评审]                   ← 新增
    │── 产出: D2 评审结论（pass / conditional pass / fail）
    │
    │ IF D2 评审 fail:
    │   → 回退到 dev 或 QA 重测（根据失败原因）
    │   → 写 kanban comment [D2_FAIL: 回退到 {step}]
    │
    │ IF D2 评审 conditional pass:
    │   → 记录 pending items → 继续推进（不阻塞管线）
    │   → pending items 加入 kanban follow-up task
    │
    ▼
[Node 6: VA 验证]
    │── 产出: VA report（claims 证伪/证实结论）
    │
    │ IF VA FALSIFIED:
    │   → autopilot 写 [VA: FALSIFIED] → block
    │   → 回退到 dev — engine 重新修复
    │   → 回退路径: pipeline_state.db 设置 dev=restart, qa/va=pending
    │   → checkpoint 记录回退原因 + 链路
    │   → 修复后重新走 dev → qa D1 → qa → qa D2 → va
    │
    │ IF VA 无法判定（信息不足）:
    │   → block → 请求补充信息 → OC 介入
    │
    ▼
[Node 7: 合并 merge]
    │── 产出: merge_commit
    │
    │ IF merge conflict:
    │   → autopilot 检测到冲突 → block
    │   → engine 解决冲突 → 重新触发 merge 检查
    │
    │ IF merge 需要 Frank 最终确认:
    │   → OC 通知 Frank "P0-XX 全部通过，可以 merge"
    │   → Frank 回复: 确认 / 暂缓
    │
    ▼
[Node 8: 闭环 close.sh]
    │── 产出: 6 步全部通过 → 飞书通知 "P0-XX 闭环完成"
    │
    │ IF close.sh 任一步失败:
    │   → 停止后续步骤（不继续执行第 N+1 步）
    │   → kanban comment [CLOSE_FAIL: step N={reason}]
    │   → 下次 cron tick 重试剩余步骤
    │   → 3 次重试仍失败 → block, 通知 Frank "close 失败，需手动检查"
    │
    │ IF GAI 更新失败 / manifest 更新失败:
    │   → 不发送"完成"通知（铁律: close.sh 不全绿不发通知）
    │   → block → OC 手动修复
    │
    ▼
[DONE] Frank 收到飞书 "P0-XX 闭环完成"
```

### 1.2 分支规则总结（可自动化判定）

| 节点 | if 条件 | 判定方式 | 失败去向 |
|------|--------|---------|---------|
| OpenSpec validate | validate --strict 不通过 | 命令行退出码 ≠ 0 | 修正 spec（最多 3 次）→ block |
| 铁律冲突 | spec 要求事项 ∈ 铁律禁止事项 | autopilot 启动时交叉检查 | D 类 roundtable |
| engine 忘 commit | produces 中的 branch 不存在或 diff 为空 | state.py 合约校验 | 阻塞 → 等待补交 → 超时 block |
| QA BLOCKER | QA report §1.2 判定 = BLOCKER | 读 QA report 分级字段 | D 类 roundtable → 回退 dev |
| MAJOR > 3 | QA report MAJOR 计数 > 3 | 读 QA report 分级字段 | 等同于 BLOCKER |
| VA FALSIFIED | VA report conclusion = FALSIFIED | 读 VA report conclusion | 回退 dev（全链回退） |
| merge 冲突 | git merge 非 0 退出 | git merge --no-commit --no-ff | engine 解决 → 重新 merge |
| close.sh 不完整 | 任一步 exit ≠ 0 | close.sh 内部各步骤返回值 | 重试 → block → OC 介入 |

---

## 2. Frank 反馈 #2：QA 测试方案 + D1/D2 评审

> 「产品出 spec 后，下一步应该是研发写代码，同步 QA 出测试方案，然后测试方案要拉回评审。完整的 QA D1/D2 环节缺失了。」

### 2.1 修正后的 QA 三阶段

在原有「dev → qa → va → merge → close」管线中，将 QA 拆为三个子阶段：

```
spec.md 就绪
    │
    ├───→ [engine] 研发写代码                     ← 并行
    │
    └───→ [QA-D1] 出测试方案                      ← 并行
              │
              ▼
         test_plan.md 拉回 D1 评审
              │
              │ 评审方: Product(许清楚) + Architect(高见远)
              │ 评审依据: spec.md 的 requires 字段是否全部覆盖
              │
              ├── PASS → QA 执行测试
              │
              └── FAIL → QA 补充方案 → 重新 D1
              │
              ▼
         [QA] 执行测试 → test_report.md
              │
              ▼
         测试方案评审 D2
              │
              │ 评审方: Architect(高见远) + Product(许清楚)
              │ 评审内容: 覆盖率、分级判定是否正确、误报率
              │
              ├── PASS → 推进到 VA
              │
              ├── CONDITIONAL PASS → 记录 pending → 继续推进
              │
              └── FAIL → 回退 dev 或 QA 重测
```

### 2.2 谁评审、评什么

| 环节 | 评审方 | 评审内容 | 评审标准 |
|------|--------|---------|---------|
| **D1（测试方案）** | Product + Architect | test_plan.md 是否覆盖 spec.md 的所有 requires；测试用例是否有效 | 覆盖率 100% → pass；< 100% → fail |
| **D2（测试报告）** | Architect + Product | 分级判定是否正确（按 `.hermes.md` §1.2）；MAJOR 是否合理；有没有漏报 BLOCKER | 分级判定无错误 → pass；有争议 → 升级 |

### 2.3 D1/D2 在 autopilot 中的嵌入

- autopilot 检测到 spec.md 就绪 → **同时**创建两个 kanban card：`dev`（assignee=game-engine）和 `qa-d1`（assignee=game-qa）
- `qa-d1` done → autopilot 创建 `roundtable-d1` review card（assignee=game-director，即 Product）— 这是 D1 评审
- D1 评审 pass → autopilot 检查 dev 是否也 done：
  - 如果 dev 已 done → 推进到 QA 测试执行
  - 如果 dev 未 done → 等待 dev done（两个条件都满足才推进）
- QA 测试执行 done → autopilot 创建 `roundtable-d2` review card — D2 评审

---

## 3. Frank 反馈 #3：DPL-011 四个具体问题

> 从产品视角给出标准回答。

### 3.1 (a) `.hermes.md` 跨 profile 共享机制

**问题**：OC 写的 boot context 如何被 engine/QA/VA 读到？各自读同一个文件还是各自有副本？

**产品标准**：

```
.hermes.md 位于 repo root (/workspace/devPPL/.hermes.md)
    │
    │ Hermes 引擎行为 (经三方验证):
    │   - 任何 agent 在该 repo 下启动 session 时
    │   - 自动扫描 workdir → repo root 路径上的 .hermes.md
    │   - 加载到 system prompt（在 SOUL.md 之前）
    │
    ▼
┌──────────────────────────────────────────────┐
│ 所有 profile 读同一个 .hermes.md              │
│ (engine/QA/VA/OC/product/architect)           │
│ 不存在副本——只存在一份。                       │
│                                               │
│ 写入者: boot_context cron（唯一写入源）        │
│ 写入方式: 原子覆写（.tmp → os.rename）        │
│ 读取者: 所有 profile（启动时自动加载）         │
└──────────────────────────────────────────────┘
```

**为什么不需要副本**：
- `.hermes.md` 是项目级文件——一个项目一套规范、一套上下文
- 所有 profile 在同一个 repo 下工作 → 自然共享同一个 `.hermes.md`
- 如果未来有多项目场景（`/workspace/project-a` 和 `/workspace/project-b`），各自有各自的 `.hermes.md`，互不干扰

**内容区分（静态 vs 动态）**：

| 区块 | 内容 | 写入者 | 读者 | 修改频率 |
|------|------|--------|------|---------|
| `## 项目规范` | QA 标准、申诉机制、管线规则 | 人工（Product/Architect） | 所有 agent | 手动，低频 |
| `## 当前活跃上下文` | 活跃任务、最近决策、最近纠正 | boot_context cron | 所有 agent，**特别是 OC** | cron 每 5min |

**Product 立场**：静态规范（QA 标准等）由 Product 和 Architect 手动维护。动态上下文由 cron 自动生成——任何 agent 都不应该手动编辑这一区块（防止写入错误误导后续会话）。

### 3.2 (b) checkpoint/autopilot/pipeline_state.db 是统一存储还是项目级

**产品标准**：**项目级**。每个 repo 一个 `pipeline_state.db`。

理由：
1. **不同项目管线完全独立**——项目 A 的步骤进度和项目 B 无关。统一存储会导致 task_id 冲突、artifact 路径混淆。
2. **隔离性**——如果一个项目的 pipeline_state.db 损坏，不影响其他项目。
3. **可移植性**——`pipeline_state.db` 在 repo 内，可以跟着 git 管理（通过 `.gitignore` 排除实际 DB 文件但保留 schema 模板）。

存储路径：`/workspace/<project>/pipeline_state.db`

对于 devPPL 项目：`/workspace/devPPL/pipeline_state.db`（与 Architect 和 Engineer 一致）。

### 3.3 (c) 成员输入输出标准化

**产品标准**：每个角色的产物清单（注意：Agent 执行 = 消耗管线上游输出，Agent 完成 = 产出供下游消费的文件）

| 角色 | 输入（从哪读） | 输出（写到哪） | 文件 | 被谁接着读 |
|------|--------------|--------------|------|-----------|
| **OC** | Frank 飞书消息 → session_search → memory | 理解 → OpenSpec → kanban | `openspec/changes/{id}/spec.md`, `kanban task t_xxx` | engine, QA, VA, autopilot |
| **Product**（许清楚） | spec.md, roundtable 讨论 | 功能优先级裁定、D1/D2 评审结论、redline 例外签字 | kanban comment | OC, engine, QA |
| **Architect**（高见远） | spec.md, roundtable 讨论 | 架构设计、D 类 roundtable 裁定 | `docs/arch-{id}.md`, kanban comment | engine, QA, autopilot |
| **Engine**（寇豆码） | kanban body → spec.md → arch doc | 代码改动 + 自测 | 分支 `feat/{id}`, `docs/eng-notes-{id}.md`（可选） | state.py（合约校验）, QA |
| **QA**（game-qa） | spec.md → engine 分支 → `docs/standards/qa-finding-classification.md` | 测试方案 + 测试报告 | `docs/qa/test-plan-{id}.md`, `docs/qa/test-report-{id}.md` | D1/D2 评审方, VA |
| **VA**（verifier） | engine claims → QA report → spec.md | VA 证伪/证实报告 | `docs/va/va-report-{id}.md`（含 [VERIFIED] 或 [FALSIFIED]） | autopilot, OC |
| **autopilot** | kanban.db + pipeline_state.db + spec.md | 步骤推进决策 + checkpoint 写入 | `pipeline_state.db` 新记录, kanban comment [AUTOPILOT:...] | resume.sh, dashboard |

**路径约定**（所有产物必须落在约定路径，否则合约校验看不到）：
- `docs/qa/`：QA 所有产出
- `docs/va/`：VA 所有产出
- `docs/arch-*.md`：架构设计
- `openspec/changes/{id}/`：规范文件
- `pipeline_state.db`：项目根目录

### 3.4 (d) OpenSpec specs 是项目级还是全局

**产品标准**：**项目级**。`openspec/` 目录在项目根目录下。

理由：
1. 每个项目的 spec 和 task 独立——项目 A 的 `spec.md` 对项目 B 无意义
2. OpenSpec CLI 的 propose/apply/archive 工作流天然绑定项目
3. 跨项目 spec 共享 → 未来如果需要，通过跨项目引用（spec 中写 `ref: ../other-project/openspec/changes/...`），而不是合并目录

当前 devPPL 项目中：`/workspace/devPPL/openspec/changes/{id}/`

---

## 4. Frank 反馈 #4：Autopilot vs Watchdog 职责边界

> 「有了 autopilot，是不是就不需要 watchdog 了？」

**产品回答**：不是。两者职责完全不同，不存在替代关系。

### 4.1 职责表

| | Autopilot | Watchdog |
|---|----------|----------|
| **管什么** | 管「任务流」——从上一步到下一步的状态转移 | 管「系统呼吸」——进程还活着吗、任务积压了吗 |
| **核心问题** | "dev 做完了，下一步是 QA 吗？" | "autopilot 自己还活着吗？" |
| **数据源** | kanban.db + pipeline_state.db + OpenSpec spec.md | kanban.db + cron.db + session file + autopilot 心跳文件 |
| **触发方式** | cron 每 2min（主动轮询） | cron 每 30min + 心跳超时检测 |
| **写什么** | pipeline_state.db + kanban comment | 飞书播报 / kanban comment [WATCHDOG:...] |
| **失败后果** | 管线停摆（下一个步骤不会自动触发） | 管线停摆没人知道 |
| **可替代对方？** | ❌ 不能监控自己是否活着 | ❌ 不能推进步骤 |

### 4.2 互相依赖关系

```
Watchdog 监控 Autopilot 是否活着
    │
    │ 监控方式: autopilot 每 tick 写心跳文件
    │          /.pipeline/heartbeat
    │          watchdog 检查心跳文件 mtime
    │
    │ IF 心跳 > 2×cron_interval 未更新:
    │   → [WATCHDOG] autopilot 可能宕了 → 飞书告警 Frank
    │
    ▼
如果 Autopilot 宕了:
    ├─ 管线停摆（2min 内会体现）
    └─ Watchdog 在 4min 后检测到 + 告警
```

### 4.3 Product 立场

- **Watchdog 是必需的基础设施**——不是"和 autopilot 二选一"，是"autopilot 的上层保险"
- autopilot 负责"推动"，watchdog 负责"autopilot 还在呼吸"
- 两者有唯一交集：watchdog 的监控列表中加入 `pipeline-autopilot` cron job（Engineer §6.1 已正确指出）

---

## 5. Frank 反馈 #5：Frank 视角的红绿灯 + 持续状态

### 5.1 每个节点的红绿灯判定

| 节点 | 绿灯条件 | 红灯条件 | 判定方 | 判定依据 |
|------|---------|---------|--------|---------|
| OpenSpec validate | `validate --strict` 退出码 0 | 退出码 ≠ 0 | autopilot | CLI 返回值 |
| 铁律冲突 | spec 不违反 SOUL.md 铁律 | spec 违反铁律 | autopilot（启动时交叉检查） | SOUL.md 铁律规则集 vs spec.md requires |
| dev 合约校验 | produces 全部存在（分支存在 + 文件改动非空） | 任一项缺失 | state.py | 合约 JSONL + 文件系统检查 |
| QA D1 评审 | test_plan.md 覆盖所有 spec requires | 覆盖率 < 100% | Product + Architect | test_plan.md vs spec.md |
| QA 测试执行 | 0 BLOCKER AND MAJOR ≤ 3 AND 安全漏洞 = 0 | BLOCKER > 0 OR MAJOR > 3 OR 安全漏洞 > 0 | state.py 读 QA report 分级字段 | QA report 的分级结果 |
| QA D2 评审 | 分级判定无误、无漏报 | 分级错误或漏报 BLOCKER | Architect + Product | QA report vs `.hermes.md` §1.2 |
| VA 验证 | all_claims pass → [VERIFIED] | FALSIFIED | state.py 读 VA report | VA report conclusion |
| merge | 无冲突、人工闸门确认 | 冲突或未确认 | autopilot | git merge 返回值 + kanban comment |
| close.sh | 6 步全部 pass | 任一步 fail | close.sh 内部返回值 | 每步执行结果 |

### 5.2 红绿灯如何展示给 Frank

**Product 推荐方案**：使用 `dashboard.py` CLI 输出（Frank 可以随时运行），格式如下：

```
┌─ Pipeline: devPPL ───────────────────────────────────────────────┐
│                                                                  │
│  P0-21 URL 修复 [t_abc123]                                       │
│  ├── ✅ OpenSpec validate          (pass, 2026-07-30 14:32)      │
│  ├── ✅ dev 合约校验               (pass, feat/p0-21-url-fix)    │
│  ├── ✅ QA D1 测试方案评审         (pass, 覆盖率 100%)            │
│  ├── 🔄 QA 测试执行                (running, 00:12:45 elapsed)   │
│  ├── ⬜ QA D2 测试报告评审         (waiting)                      │
│  ├── ⬜ VA 验证                    (waiting)                      │
│  ├── ⬜ merge                      (waiting)                      │
│  └── ⬜ close.sh                   (waiting)                      │
│                                                                  │
│  P1-07 Schema 审计 [t_def456]                                    │
│  ├── ✅ OpenSpec validate          (pass)                        │
│  ├── 🔴 dev 合约校验               (FAIL: branch 不存在)          │
│  ├── ⬜ QA D1                      (blocked: 等待 dev 补交)      │
│  └── ...                                                        │
│                                                                  │
│  ═══════════════════════════════════════════════════════════════ │
│  系统状态: 🟢 autopilot 正常 (last tick: 0.3s ago)               │
│  阻塞: 1 个任务 (t_def456: dev 合约失败)                         │
│  3 个任务正常推进中                                               │
└──────────────────────────────────────────────────────────────────┘
```

**符号约定**：
- ✅ = 绿灯（pass）
- 🔴 = 红灯（fail / blocked）
- 🔄 = 运行中
- ⬜ = 等待中

**Frank 不需要记住去看**：close.sh 闭环后发飞书通知。红绿灯面板是"Frank 想看的时候可以看"，不是"Frank 必须定期检查"。管线正常运行时 Frank 不需要看。

### 5.3 持续状态报告

**Product 补充**：Frank 说的「是还在跑还是停掉了」——需要两个层面的信息：

1. **autopilot 心跳**（分钟级）：
   - 心跳文件 `/.pipeline/heartbeat`，autopilot 每个 cron tick 更新 mtime
   - Watchdog 检测心跳超时 → 告警
   - 如果没有告警 = autopilot 在跑

2. **管线是否真的在推进**（任务级）：
   - 看 pipeline_state.db 中活跃任务的 `started_at` 时间
   - 如果某 step 的 `started_at` > max_timeout 且 status 仍是 running → step 卡住了
   - autopilot 在推进 = 有新任务进入 running 状态或完成 done 状态

### 5.4 唤醒机制

Frank 说：「即使所有 profile 都结束了，但能通过脚本唤醒来继续执行下一步，我也认可」。

**Product 方案**：autopilot cron 不依赖任何 profile 是否活跃。
- autopilot 是 cron job，每 2min 自动运行一次——不需要 OC 或其他 agent 在线
- 当 autopilot 检测到某个已完成的 step → 它创建下一个 kanban card → kanban dispatcher 自动 spawn agent
- 如果 dispatcher 一时没响应（所有 slot 满）→ task 在 `ready` 队列中 → dispatcher 下次有空了就派发

**不需要"唤醒"操作**——cron + dispatcher 天然是拉取模型。autopilot 只管创建需求（kanban card），dispatcher 只管满足需求（派发 agent）。两者解耦，互不等。

---

## 6. Frank 反馈 #6：OC 与 Product 的角色划分

### 6.1 修正：各角色定位表

Frank 明确指出 Engineer 报告中漏掉了 Product 的位置，且可能存在"OC = Product"的认知错误。以下是修订后的标准角色表，**写入 SOUL.md 作为每个新 agent 的启动上下文**：

| 角色 | 是谁 | 职责 | 不是 |
|------|------|------|------|
| **Frank** | 老板 | 产品方向最终裁决、BLOCKER 暂缓签字、铁律例外签字 | — |
| **OC**（orchestrator） | Frank 的指挥官/秘书 | 接收 Frank 指令 → 理解 → 编排流程 → 创建 kanban → 协调 agent | 不是产品经理；不做功能决策；不代替 Frank 拒绝需求 |
| **Product**（许清楚） | 产品负责人 | 功能优先级裁定、D1/D2 评审、QA 分级争议最终裁定、BLOCKER 暂缓评估、产品红线维护 | 不负责编排流程（那是 OC 的事）；不做架构设计（那是 Architect 的事） |
| **Architect**（高见远） | 架构师 | 架构设计、技术方案评审、D 类 roundtable 裁定、管线组件设计 | 不做产品功能决策 |
| **Engineer**（寇豆码） | 研发工程师 | 代码实现、bug 修复、自测、PR 提交 | 不做 QA 测试、不做 VA 验证 |
| **QA**（game-qa） | 测试 | 测试方案、测试执行、分级判定 | 不做代码修改、不做架构设计 |
| **VA**（verifier） | 独立验证 | 逐条证伪/证实 engine 的 claims | 不修复 bug、不重新测试 |

### 6.2 Product 在工作流中的具体嵌入点

Product（许清楚）在以下节点介入管线：

| 介入点 | 时机 | 做什么 |
|--------|------|--------|
| **spec 评审**（可选） | OC 生成 OpenSpec spec.md 后 | 确认 spec 正确反映了产品意图（Frank 不在时替代 Frank 确认） |
| **D1 测试方案评审** | QA 产出 test_plan.md 后 | 与 Architect 联合评审测试覆盖率 |
| **D2 测试报告评审** | QA 产出 test_report.md 后 | 与 Architect 联合评审分级判定 |
| **D 类 roundtable** | autopilot 遇到闸门时（BLOCKER、铁律例外、产品方向争议） | 裁定：是否继续 / 回退 / 暂缓 |
| **BLOCKER 暂缓** | QA 发现 BLOCKER 但研发认为可暂缓 | 评估风险 → 推荐 → Frank 最终签字 |
| **OpenSpec 归档前**（可选） | close.sh 闭环后 | 确认 spec.md 可以归档 |

### 6.3 对 Engineer 报告的修正请求

Engineer（寇豆码）的 R3 报告中角色列表（§1.1）缺失了 Product 和 Architect 两个关键角色。OC 不等于 Product。

**申请在下一次 Engineer 报告中修正**：角色速览表应增加 Product 和 Architect，共 7 个角色。

---

## 7. Frank 反馈 #7：Engineer 的错误引用

### 7.1 问题描述

Engineer R3 报告第 226 行：
> 「当前 `.hermes.md` 只有 30 行，全是 QA 规范引用。Frank 说『只保留 QA 标准，boot context 另走 cron』。」

Frank 明确表示**不记得说过这句话**。这给 Engineer 增加了一个不存在的约束，可能导致 Engineer 基于错误前提做了设计取舍。

### 7.2 影响评估

回顾 Engineer 的 R3 设计，这个"约束"实际造成的影响：

**好消息：Engineer 的设计结果反而是正确的。** 无论 Frank 是否说过这句话，Engineer 的输出是：
- `.hermes.md` 两段式：静态规范（含 QA 标准） + 动态上下文（boot context cron 生成）
- 动态上下文由 cron 独立生成，使用 `no_agent=true` 确定性脚本
- 静态规范从 `docs/hermes-static.md` 模板读取，cron 拼接

这个设计与 Product 和 Architect 的独立方案完全对齐（三方都选择了同样的两段式结构）。**即使 Engineer 被一条不存在的约束驱动，他的推导结论是正确的。**

**需要消除的潜在误导**：未来如果 Engineer 遇到「Frank 说过的约束」和「工程最佳实践」冲突，应优先找 OC 或 Product 确认，而不是在可能不存在的约束下做取舍。

### 7.3 约束澄清

正确的约束应该是：

> `.hermes.md` 的静态部分（项目规范）由人工维护（Product/Architect）。动态部分（活跃上下文）由 boot_context cron 自动生成——任何 agent 都不应该手动编辑动态区块。

这与「只保留 QA 标准」完全不同——静态规范不限于 QA 标准，还包括管线规则、角色表、申诉机制等。**QA 标准是最优先的，但不是唯一的。**

---

## 8. Product R4 决定清单（可执行）

以下是本次 R4 中 Product 做出的最终决定，写入项目标准：

| # | 决定 | 类型 | 执行方 |
|---|------|------|--------|
| D-001 | QA 拆为三阶段：D1 测试方案评审 → 测试执行 → D2 测试报告评审 | 流程变更 | OC + autopilot + QA |
| D-002 | boot_context 刷新频率固定为 5min（修正 Product R3 的 30min） | 参数修正 | boot_context cron |
| D-003 | 每个管线节点必须有显式 if 分支（见 §1.2 表），写入合约 JSONL | 流程标准 | autopilot + state.py |
| D-004 | Autopilot 和 Watchdog 并行存在，互不替代。Watchdog 监控 Autopilot 心跳 | 架构裁定 | Watchdog + autopilot |
| D-005 | dashboard.py CLI 面板使用 ✅/🔴/🔄/⬜ 符号表示红绿灯 | UI 标准 | dashboard.py |
| D-006 | `.hermes.md` 动态区块由 cron 唯一写入；agent 不可手动编辑 | 写入权限 | boot_context cron |
| D-007 | 成员输入输出标准化使用 §3.3 表，产物路径使用约定目录 | 路径标准 | 所有 agent |
| D-008 | OpenSpec specs 为项目级，存储于 `openspec/changes/{id}/` | 架构裁定 | OC + OpenSpec CLI |
| D-009 | checkpoint/autopilot/pipeline_state.db 为项目级，每 repo 一个 | 架构裁定 | autopilot + checkpoint.py |
| D-010 | Engineer 报告需修正角色表（加入 Product + Architect） | 文档修正 | Engineer（下次报告） |

---

## 9. 总结

三份 R3 独立卷的核心路径高度一致——管线结构、组件选择、数据流方向没有争议。这就是我们之前独立出卷的价值所在：**如果三个角色在互不参考的情况下画出同样的路径，说明架构方向是对的。**

Frank 的 7 条反馈指出的问题集中在一个方向：**我们画了骨架，缺了血肉。** Happy path 画清楚了，但引擎忘记 commit 怎么办、VA 证伪了怎么回退、QA D1/D2 的评审环节在哪——这些都是用户（Frank）真正关心的部分。漂亮的路不一定能到目的地，带岔路标的路才能。

Product R4 核心修正：
1. 每个节点加了 if 条件 + 失败去向（§1）
2. QA 从"一个步骤"扩展为 D1 → 测试执行 → D2 三个阶段（§2）
3. DPL-011 四个问题全部给出产品标准答案（§3）
4. Autopilot 和 Watchdog 是监视器与被监视者的关系，不是二选一（§4）
5. Frank 视角的红绿灯用 dashboard.py 的可视化表情符号展示（§5）
6. OC ≠ Product——角色表修正并写入 SOUL.md 标准（§6）
7. Engineer 的错误引用约束应澄清——静态规范不限于 QA 标准（§7）

**下一步**：将 Product 的 D-001 ~ D-010 决定注入到管线设计中，由 Architect 更新架构设计、Engineer 更新实现方案、OC 更新编排流程。

---

> 产品发言完毕。三份独立卷的一致性给了我们信心——方向选对了。Frank 的 7 条反馈给了我们细节——把每个节点的 if 分叉、QA 的 D1/D2 评审、不看门狗不行的道理，全部落到纸面，不留模糊地带。
> 
> 这条路不漂亮，但能走到底。
