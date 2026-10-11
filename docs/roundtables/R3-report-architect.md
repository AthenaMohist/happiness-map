# R3 独立卷 — Architect 工作流报告：目标系统全貌

> 发言人：高见远（架构师） | 日期：2026-07-30 | 版本：v1.0
> 类型：B 类会议 — 不产生行动任务
> 规则：独立完成，不参考 Engineer/Product/QA 的卷

---

## 0. 约束前提（架构师看到的现实）

在画完整数据流之前，先声明当前环境约束——这些是地基，不可绕过：

| 约束 | 现状 | 影响 |
|------|------|------|
| **Hermes 引擎** | cron + SQLite polling 驱动 kanban dispatcher，非事件驱动 | 无法做 webhook 级实时触发；step 推进最小粒度为 cron interval（默认 2min） |
| **kanban.db** | SQLite @ `/root/.hermes/kanban.db`，WAL 模式 | 单写者、多读者；短事务安全；不支持跨 DB JOIN |
| **profile 隔离** | 每个 profile 独立 `state.db` + prompt + skills | agent 之间不共享上下文，通过 kanban task body 传数据 |
| **工作区模型** | `dir` workspace（持久化）和 `scratch` workspace（临时） | 管线产物需要写到可跨 session 访问的路径 |
| **Node 版本** | v18.19.1，OpenSpec 要求 ≥20.19 | 升级后才能装 OpenSpec CLI（R2 已评估，风险低） |
| **`.hermes.md`** | 薄壳（30 行，仅 QA 标准引用） | 未承载跨会话上下文；是 DPL-011 的注入锚点 |
| **SOUL.md** | 已拆分为 SOUL+PIPELINE（P0-20 done）；profile 级加载 | 铁律 1-5 已存在；铁律 6（跨会话启动协议）待加入 |

---

## 1. 完整数据流图

### 1.1 端到端拓扑（Frank 需求 → 最终交付）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Phase 0: 需求捕获与规范化                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐    ┌───────────────┐    ┌───────────────────────────────────┐ │
│  │ Frank 的  │───▶│ OC 对话/飞书   │───▶│ OpenSpec propose                  │ │
│  │ 自然语言   │    │ （澄清+细化）   │    │ openspec/changes/{id}/spec.md     │ │
│  │ 需求      │    │               │    │ openspec/changes/{id}/tasks.md     │ │
│  └──────────┘    └───────────────┘    └───────────────┬───────────────────┘ │
│                                                        │                     │
│  Frank "我要一个"  ──▶  OC 白板讨论  ──▶  结构化 spec  │                     │
│                                                        │                     │
│                         输入: NL 需求文本                │                     │
│                         输出: spec.md (Markdown)         │                     │
│                               tasks.md (分解任务清单)     │                     │
│                         验证: openspec validate --strict │                     │
│                         存储: openspec/changes/{id}/     │                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                                      │
                                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Phase 1: 任务分发（kanban 创建 + 调度）                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  spec.md ──────▶ Orchestrator ──────▶ kanban_create(                         │
│  tasks.md         分解为 kanban cards     title=...,                         │
│                                        assignee=<profile>,                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ kanban.db (SQLite)                                                   │   │
│  │   tasks(id, title, body, assignee, status, priority,                │   │
│  │         current_run_id, workspace_path, ...)                         │   │
│  │   状态流转: ready → running → done / blocked / failed               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  输入: OpenSpec spec.md + tasks.md                                          │
│  输出: N 个 kanban tasks, 每个带 assignee + parent 依赖                      │
│  存储: kanban.db (已存在，SQLite WAL)                                        │
│  写者: orchestrator profile (手动或 autopilot 自动)                          │
│  读者: kanban dispatcher (自动), autopilot (轮询)                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                                      │
                                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Phase 2: 执行引擎（autopilot + OC）                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  autopilot.sh (cron, ~2min interval)                                        │
│  ┌───────────────────────────────────────────────────────────────┐         │
│  │ 1. 轮询 kanban.db → 检测 status 变更                          │         │
│  │ 2. 读 task.body → 提取 OpenSpec ref                          │         │
│  │ 3. 读 openspec/changes/{id}/spec.md → 解析 requires/produces  │         │
│  │ 4. 读 pipeline_state.db → 确定当前 checkpoint                 │         │
│  │ 5. 判定下一步: 推进 / 等待 / 告警                              │         │
│  │ 6. 写 kanban comment [AUTOPILOT: ...]                        │         │
│  │ 7. 写 pipeline_state.db (step 完成 → checkpoint)              │         │
│  └───────────────────────────────────────────────────────────────┘         │
│                                                                             │
│  kanban dispatcher                                                          │
│  ┌───────────────────────────────────────────────────────────────┐         │
│  │ ready task → spawn OC/agent → 执行 task.body 中的指令          │         │
│  │ 产出的文件 / 变更 → 落地到 workspace                           │         │
│  │ 完成后 → kanban_complete                                      │         │
│  └───────────────────────────────────────────────────────────────┘         │
│                                                                             │
│  输入: kanban task (从 Phase 1)                                             │
│         OpenSpec spec.md (规范)                                              │
│         pipeline_state.db (断点信息)                                         │
│  输出: 产物 (代码/文档/artifacts)                                            │
│         kanban_complete (done/failed)                                        │
│         pipeline_state.db 更新 (step 进度)                                   │
│                                                                             │
│  调度者: autopilot.sh (cron 轮询，推进步骤)                                  │
│  执行者: OC/agent (kanban dispatcher 派发)                                   │
│  验证者: autopilot (步骤合约校验，P0-1)                                      │
│  记录者: checkpoint (pipeline_state.db，P0-3)                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                                      │
                                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Phase 3: 检查点与恢复                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  pipeline_state.db (SQLite, 独立 DB)                                        │
│  ┌───────────────────────────────────────────────────────────────┐         │
│  │ task_steps(task_id, step_name, status, started_at, finished_at, │         │
│  │            attempt, error, artifacts_json)                     │         │
│  │                                                                 │         │
│  │ ── 断点恢复: resume.sh 读 pipeline_state.db                    │         │
│  │     → 找到最后 completed step → 派发下一个 step                │         │
│  │ ── 超时检测: autopilot 检查 running 超过 TTL 的 step           │         │
│  │ ── 产物追踪: artifacts_json 记录每个 step 的输出文件路径       │         │
│  └───────────────────────────────────────────────────────────────┘         │
│                                                                             │
│  输入: autopilot 步骤完成通知                                                │
│  输出: 可查询的管线状态 (step ↔ status ↔ artifacts)                          │
│  存储: /workspace/devPPL/pipeline_state.db                                   │
│  写者: autopilot (每 step 完成时)                                            │
│  读者: autopilot (启动时), resume.sh (恢复时), dashboard (可视化)             │
└─────────────────────────────────────────────────────────────────────────────┘
                                                      │
                                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Phase 4: 闭环与可视化                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  close.sh (P0-19 done)                                                      │
│  ┌───────────────────────────────────────────────────────────────┐         │
│  │ 6 步强制闭环:                                                  │         │
│  │   1. 确认所有 child tasks 完成                                 │         │
│  │   2. 验证 GAI 条目状态                                         │         │
│  │   3. 验证 manifest 一致性                                      │         │
│  │   4. 验证 artifacts 产物存在                                   │         │
│  │   5. 写完成摘要到 task comment                                 │         │
│  │   6. 触发下游通知 (如有)                                       │         │
│  └───────────────────────────────────────────────────────────────┘         │
│                                                                             │
│  dashboard (CLI 原型, P1-2)                                                  │
│  ┌───────────────────────────────────────────────────────────────┐         │
│  │ 输入: kanban.db + pipeline_state.db + OpenSpec specs           │         │
│  │ 展示: 管线全局状态 / 每个 task 的 step 进度 / 阻塞项 / SLA     │         │
│  └───────────────────────────────────────────────────────────────┘         │
│                                                                             │
│  输入: autopilot + OC 执行结果                                              │
│  输出: GAI 更新 + manifest 更新 + 可选飞书通知                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 每个节点的输入/输出 schema

| 节点 | 输入 Schema | 输出 Schema | 存储位置 |
|------|------------|-------------|---------|
| **OpenSpec** | NL 需求文本 (Frank) | `spec.md` (Markdown, 含 requires/produces), `tasks.md` (checklist) | `openspec/changes/{id}/` (Git 追踪) |
| **kanban** | task_id, title, body(含 OpenSpec ref), assignee, parents[] | task row in kanban.db; status 变更 | `/root/.hermes/kanban.db` |
| **autopilot** | kanban task (status变更), spec.md, pipeline_state.db | kanban comment [AUTOPILOT:...]; checkpoint write | kanban.db + pipeline_state.db |
| **checkpoint** | task_id, step_name, status, artifacts | row in task_steps table | `/workspace/devPPL/pipeline_state.db` |
| **close.sh** | task_id (从 env) | GAI 更新 + manifest 更新 + task comment | GAI + manifest + kanban.db |
| **dashboard** | kanban.db + pipeline_state.db + OpenSpec specs | 终端输出 / JSON | 纯读，不写 |

---

## 2. 新组件的技术边界

### 2.1 边界矩阵

```
                     ┌──────────────┐
                     │   OpenSpec    │  「定义要做什么」
                     │   (规范层)     │
                     │  写 spec.md   │
                     │  写 tasks.md  │
                     └──────┬───────┘
                            │ spec.md (Markdown)
                            ▼
              ┌─────────────────────────┐
              │       autopilot          │  「管过程怎么走」
              │       (编排层)            │
              │  读 spec.md              │
              │  读 pipeline_state.db    │
              │  判下一步                 │
              │  写 checkpoint            │
              │  写 kanban comment        │
              └──────┬──────────────────┘
                     │ step 指令 (kanban comment/status)
                     ▼
              ┌─────────────────────────┐
              │    OC / agent (执行层)    │  「具体干活」
              │   读 task.body            │
              │   执行指令                 │
              │   写产物到 workspace       │
              │   完成后 kanban_complete   │
              └──────────────────────────┘
```

### 2.2 详细边界定义

| 组件 | 职 责 | 不 做 什 么 | 调 用 关 系 |
|------|-------|------------|------------|
| **OpenSpec** (§ 规范层) | 1. 接收 Frank 需求 → 生成结构化 spec.md、tasks.md<br>2. 提供 `openspec validate --strict --json` 确定性校验<br>3. 管理 spec 生命周期 (propose→apply→archive) | 不执行代码<br>不操作 kanban<br>不写 pipeline 状态 | → 输出 spec.md 给 Orchestrator/autopilot 读<br>← 被 OC 调用 (propose) / autopilot 读取 (apply 时) |
| **autopilot** (§ 编排层) | 1. cron 轮询 kanban 状态变更<br>2. 读 spec.md → 解析步骤依赖<br>3. 判定下一步 (推进/等待/告警)<br>4. 写 checkpoint 到 pipeline_state.db<br>5. 步骤合约校验 (P0-1) | 不执行具体任务<br>不修改 OpenSpec specs<br>不操作 kanban (除写 comment) | → 读 kanban.db (轮询)<br>→ 读 pipeline_state.db (checkpoint)<br>→ 写 pipeline_state.db (step done)<br>→ 写 kanban comment [AUTOPILOT: ...] |
| **checkpoint** (§ 持久层) | 1. 记录 task_id → step → status 映射<br>2. 记录 artifacts (产物路径)<br>3. 提供断点恢复查询 (resume.sh) | 不推进步骤<br>不做决策<br>不校验  | → 被 autopilot 写入<br>→ 被 resume.sh 读取<br>→ 被 dashboard 读取 |
| **OC (OC)** (§ 执行层) | 1. 被 kanban dispatcher 派发<br>2. 读 task.body → 执行具体操作<br>3. 产生产物 (代码/文档/配置)<br>4. kanban_complete / block | 不做跨 task 编排<br>不做步骤判定<br>不操作 pipeline_state.db | → kanban_complete 触发 status 变更<br>→ autopilot 检测到变更后推进 |

### 2.3 调用链（完整路径）

```
OpenSpec propose (OC 调用)
  → openspec/changes/{id}/spec.md 落地
  → Orchestrator 读 spec.md, 创建 kanban tasks
    → kanban dispatcher 派发 OC 执行
      → OC 完成后 kanban_complete
        → autopilot cron 检测到 status=done
          → autopilot 读 spec.md → 判定下一步
            → autopilot 写 checkpoint (pipeline_state.db)
              → autopilot 触发下一个 task 或等待
                → 全部 done 后
                  → close.sh 闭环验证
                    → GAI + manifest 更新
```

**关键路径延迟**：
- OC 完成 → autopilot 检测到 (cron interval, ~2min)
- checkpoint 写入 → 可查询 (即时，SQLite 写入)
- autopilot 判定下一步 → 新 kanban task 创建 → OC 派发 (~2-3min)

---

## 3. DPL-011 的架构实现

### 3.1 Frank 的纠偏：DPL-011 不是让人读的，是让 OC 懂的

Frank 明确指出：DPL-011 解决的是 **Hermes 的架构问题**——OC session 之间上下文不互通。Frank 在飞书对话是连续的，但在 Hermes 里被分割为多个 session。OC 切会话后「失忆」是系统级缺陷。

### 3.2 三层跨会话上下文架构

```
┌───────────────────────────────────────────────────────────┐
│                     Layer 1: 确定层                         │
│                   (系统自动注入，零 LLM)                     │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────────┐    ┌─────────────────────────────┐   │
│  │ memory 工具       │    │ .hermes.md 增强版            │   │
│  │ 已保存事实         │    │ (DPL-011 注入锚点)           │   │
│  │ 每轮自动注入      │    │                             │   │
│  │ 覆盖: 100%       │    │ 写入者: boot_context cron    │   │
│  │ 成本: 0 LLM token│    │ 内容:                       │   │
│  └─────────────────┘    │   - 最近 N 个 session 摘要   │   │
│                         │   - 最近的 kanban task 状态   │   │
│  DREAM-003 过滤:        │   - 关键决策 (verified 记忆)  │   │
│  search_tagged(         │   - 活跃的纠偏记录            │   │
│    state='verified',    │                             │   │
│    exclude_expired=True)│  格式: ~300 tokens 摘要       │   │
│                         │  刷新: cron 定时生成          │   │
│                         │          (每 5min 或                   │   │
│                         │           session 启动时)      │   │
│                         └─────────────────────────────┘   │
│                                                           │
│  覆盖: 100%   |   成本: ~300 tokens/session               │
│  可靠性: 100% (确定性脚本，非 LLM 路径)                     │
└───────────────────────────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────────┐
│                     Layer 2: 铁律层                         │
│                    (SOUL.md 注入，概率性)                    │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  铁律 6（待加入 SOUL.md）:                                  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ 在新会话首次回复 Frank 之前:                          │  │
│  │   1. 查 memory — 了解已保存的事实和偏好               │  │
│  │   2. 如话题涉及过往工作 → session_search 深入查       │  │
│  │   3. 显式告知 Frank 查到了什么（或确认未找到）         │  │
│  │                                                     │  │
│  │ 禁止: 不查前情就直接从零提议                          │  │
│  │       假定"不知道就等于没做过"                        │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  覆盖: ~70-80% (LLM 可能跳过，尤其在任务紧迫时)            │
│  成本: session_search 的 token 开销                       │
└───────────────────────────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────────┐
│                     Layer 3: 摘要层                         │
│              (会话结束时生成，作为 Layer 1 的数据源)         │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  会话结束 → OC 生成结构化摘要:                              │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ session_id: xxx                                     │  │
│  │ key_decisions: [决策1, 决策2, ...]                   │  │
│  │ corrections: [纠错1, ...]                            │  │
│  │ active_tasks: [t_xxx, ...]                          │  │
│  │ unfinished: "XXX 讨论到方案 C，待 Frank 决策"          │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  → boot_context cron 读取最新摘要                           │
│  → 注入到 .hermes.md（Layer 1 的部分数据源）                │
│                                                           │
│  成本: LLM 生成摘要(~200 tokens) + 写入开销                 │
└───────────────────────────────────────────────────────────┘
```

### 3.3 `.hermes.md` 应存什么（导航摘要，不是全部 history）

| 应存 | 格式 | 写入时机 | 写入者 | 读者 |
|------|------|---------|--------|------|
| 最近 3 个 session 摘要 | 标题 + 关键决策 + 进行中任务 | 每次 session 结束 | OC (Layer 3 摘要) / boot_context cron | OC 新 session 启动 |
| 活跃 kanban task 状态 | task_id → status → last_step | boot_context cron 生成时 | boot_context cron | OC |
| 最近纠偏记录 | `[纠偏] 话题: 正确做法` | Frank 纠错后 | OC 写入 memory，boot_context cron 摘要化 | OC |
| 项目级规则 | 静态（类似当前 QA 标准引用） | 手动维护 | 架构师 | 所有 profile |
| 关键决策日志 | decision_id → 结论 → 日期 | Roundtable 裁定后 | Orchestrator | 所有 profile |

| 不应存 | 理由 |
|--------|------|
| 全量对话历史 | token 杀手；100M 上限压力巨大 |
| 中间推理过程 | 单次会话级，跨会话无用 |
| 已完成的临时操作序列 | 噪声 |
| 所有 memory 条目正文 | memory 工具已自动注入，不需要 `.hermes.md` 重复 |

### 3.4 boot_context cron 和 OpenSpec specs 如何共存

**不冲突——它们是不同维度的信息。**

```
.hermes.md
  ├─ 静态部分: 项目规范 (手动维护)
  │    └─ 当前: QA 标准、申诉机制
  ├─ 动态部分: 导航摘要 (boot_context cron 自动更新)
  │    └─ 最近 session 摘要 / kanban 状态 / 纠偏记录
  └─ 不长存 OpenSpec specs 正文
       (specs 在 openspec/changes/{id}/，独立文件树)

OpenSpec specs
  ├─ openspec/changes/{id}/spec.md     ← 单一 task 的规范
  ├─ openspec/changes/{id}/tasks.md    ← 任务分解
  └─ openspec/changes/{id}/design.md   ← 技术设计 (optional)

两者关系:
  .hermes.md = 导航地图 (去哪、从哪开始)
  OpenSpec specs = 目的地详情 (做什么、怎么做)
  OC 启动 → 读 .hermes.md → 知道「在做 t_xxx」→ 去 openspec/changes/{t_xxx}/spec.md 看详情
```

**boot_context cron 的实现位置**：

```
cronjob (profile: orchestrator/game-architect)
  ├─ script: scripts/boot_context.py
  │   ├─ 读 session_search(limit=3, sort='newest')
  │   ├─ 读 kanban.db (活跃 task)
  │   ├─ 读 mem0_tagged.search_tagged(state='verified')
  │   ├─ 格式化为 ~300 tokens 摘要
  │   └─ 写 .hermes.md 的动态部分 (<!-- BOOT_CONTEXT_START --> ... <!-- BOOT_CONTEXT_END -->)
  │
  └─ schedule: every 5min / 或 session 启动时触发
```

---

## 4. 冲突处理机制

### 4.1 核心冲突场景

> OpenSpec specs 说「需要 D2 roundtable」，但 autopilot 判断「MAJOR=0 应跳过」
> → 谁说了算？

### 4.2 冲突裁决链

```
                     冲突发生
                        │
                        ▼
               ┌───────────────┐
               │ Step 1: 自动   │  autopilot 读 OpenSpec spec.md 的 requires 字段
               │    解析        │  → 发现 spec 要求 roundtable D2
               │               │  → 同时检查 QA findings: MAJOR=0
               └───────┬───────┘
                       │
            ┌──────────┼──────────┐
            ▼                     ▼
    spec 要求 fulfilled?     MAJOR=0 跳过了?
    NO → 继续               YES
            │                     │
            └──────────┬──────────┘
                       │ 冲突: spec 要求 roundtable，
                       │       autopilot 判定不需要
                       ▼
               ┌───────────────┐
               │ Step 2: 升级   │  autopilot 不能自行裁决
               │    到 kanban   │  → 创建 D 类 roundtable task
               │               │  → assignee=game-architect (架构裁决)
               │               │  → 当前管线 task block
               └───────┬───────┘
                       │
                       ▼
               ┌───────────────┐
               │ Step 3: 架构   │  架构师 (我) 判定
               │    裁决        │  → 如果 spec 是旧规范 (过时) → openspec archive 或更新
               │               │  → 如果 spec 仍有效 → 强制推进 roundtable，忽略 autopilot
               │               │  → 裁定结果写入 spec.md 的 decisions 块
               └───────┬───────┘
                       │
                       ▼
               ┌───────────────┐
               │ Step 4: 产品   │  如果架构裁决仍有争议 → Product 介入
               │    最终裁定    │  → Frank 级别的裁决
               └───────────────┘
```

### 4.3 SOUL.md 铁律 vs OpenSpec validate --strict 不一致时

**规则**：**SOUL.md 铁律 胜出，OpenSpec validate 作为验证工具服从铁律。**

理由：
1. SOUL.md 代表 Frank 的最高意志（经由 Product 声明）
2. OpenSpec validate 是语法/结构化校验——它验证 spec 写对了，不验证 spec 的内容是否与铁律一致
3. 如果 OpenSpec validate --strict 输出与 SOUL.md 铁律冲突 → 视为 spec 内容错误 → 修正 spec，然后重新 validate

**实现**：
```
autopilot 启动时:
  1. 读 SOUL.md 铁律 → 提取规则集 R (不可变的约束)
  2. 读 OpenSpec spec.md → 提取 requires 集 S
  3. 对每个 s ∈ S: 检查 s 是否违反任何 r ∈ R
     → 如违反 → 告警 + block task → 创建 D 类 roundtable
     → 如不违反 → 正常推进
```

### 4.4 常规冲突类型及裁决方

| 冲突类型 | 例 | 裁决方 | 机制 |
|---------|----|--------|------|
| **spec ↔ autopilot 判定** | spec 要求 roundtable，autopilot 认为跳过 | 架构师 | 升级为 D 类 roundtable |
| **spec ↔ SOUL.md 铁律** | spec 要求 LLM 做决定 vs 铁律「OC 不做决定」 | 铁律胜出 | autopilot 启动时检查 → block |
| **autopilot ↔ OC 执行** | autopilot 说下一步是 review，OC 完成了但产物不符合 spec | autopilot 步骤合约校验 | 合约引擎 P0-1 拦截 → failed → 回退 |
| **checkpoint ↔ 实际状态** | pipeline_state.db 说 step 3 done，但产物文件不存在 | checkpoint 数据为主 | close.sh 闭环验证 → failed |
| **两个 profile 的判定** | Game-architect 说 skip，game-engineer 说 need | 升级到 Product | Roundtable B 类 |

---

## 5. 数据一致性问题

### 5.1 四套数据源——谁说了算？

| 数据源 | 存储 | 内容 | 角色 | Single Source of Truth? |
|--------|------|------|------|------------------------|
| **kanban.db** | `/root/.hermes/kanban.db` | task 生命周期 (status, assignee, priority, run history) | **运行态的主记录** | ✅ **SSOT for 任务状态** |
| **pipeline_state.db** | `/workspace/devPPL/pipeline_state.db` | step 级别的细粒度进度 + artifacts 追踪 | **管线视角的衍生数据** | ❌ 从 kanban 状态 + autopilot 日志派生 |
| **OpenSpec specs** | `openspec/changes/{id}/` (Git 追踪) | 规范和任务分解 (spec.md, tasks.md) | **规范的 SSOT** | ✅ **SSOT for 需求规范** |
| **`.hermes.md`** | repo root | 导航摘要 + 项目规则 | **缓存的上下文视图** | ❌ 从其他三套数据源编译 |

### 5.2 SSOT 层级

```
         OpenSpec specs           ← SSOT for 「应该做什么」
         (spec.md + tasks.md)
                │
                ▼
         kanban.db                ← SSOT for 「正在做什么」
         (task status + history)
                │
                ▼
         pipeline_state.db        ← 衍生数据
         (step 进度 + artifacts)     「做完了什么、在哪」
                │
                ▼
         .hermes.md               ← 缓存视图
         (导航摘要)                  「快速了解当前状态」
```

### 5.3 对账机制

当 pipeline_state.db 和 kanban.db 不一致时（例如：kanban status=done 但 pipeline 某 step 仍是 running）：

```
对账触发:
  1. autopilot 每次轮询时: 读 kanban status → 对比管道 pipeline 最后一个 step status
  2. close.sh 执行时: 6 步验证中包含一致性检查
  3. dashboard 展示时: 对比两套数据

对账规则:
  - kanban.completed_at 存在 且 pipeline.task_steps 有未完成 step
    → pipeline_state.db 落后 → autopilot 补写 checkpoint
  - pipeline.task_steps 全部 done 但 kanban.status 不是 done
    → kanban 落后 → autopilot 写 comment 提示
  - 两者不一致且无法判定 → 创建 D 类 roundtable task → 人工裁决
```

### 5.4 窗口期问题

| 窗口 | 场景 | 持续时间 | 影响 |
|------|------|---------|------|
| kanban done → autopilot 检测 | OC 完成一个 task，autopilot cron 还没轮询到 | ≤2min (cron interval) | 管线暂停，下一个 step 等待。**可接受** |
| autopilot 写 checkpoint → dashboard 读到 | checkpoint 写入 SQLite，dashboard 下次查询时可见 | SQLite 写入延迟 (ms 级) | **无影响**——dashboard 是轮询读取 |
| OpenSpec archive → kanban 仍引用旧 spec | spec 被 archive 但 autopilot 已读取了旧 spec.md | 取决于 autopilot 缓存策略 | autopilot 应每次读取 spec.md 文件内容（不缓存），避免此窗口 |

---

## 6. 故障模式

### 6.1 checkpoint 恢复后 autopilot 重复执行了一个步骤

**场景**：autopilot 在 step 3 完成后崩溃。重启后 resume.sh 从 pipeline_state.db 读最后 completed step → 判定是 step 3 → 重新执行 step 3。但 step 3 在崩溃前已经完成了（产物已写入，只是 checkpoint 没来得及记）。

**架构分析**：

```
autopilot step 3 执行:
  1. 写产物到 workspace            ← 幂等? 可能覆盖已有文件
  2. 写 kanban comment             ← 幂等? 追加，会产生重复 comment
  3. 写 pipeline_state.db          ← 有 attempt 计数器

恢复后:
  resume.sh 读 pipeline_state.db
  → 找到 step 2 completed, step 3 missing
  → 判定: step 3 未完成 → 重新执行
  → 问题: step 3 的产物已经存在 → 可能被覆盖
```

**方案**：

1. **鉴权 before 写**（推荐）：step 3 开始前检查产物是否已存在且有正确的 checksum
   ```
   if artifacts_exist and checksum_matches:
       → 跳过执行，直接写 checkpoint
   else:
       → 执行 step 3
   ```
2. **attempt 计数器**：pipeline_state.db 的 task_steps 记录 `attempt`。恢复时看到 attempt 增量 → 使用不同的产物输出路径（如 `step-3-attempt-2/`）
3. **二阶段写**：先写临时文件 → 完成验证 → 原子 rename 到最终路径

### 6.2 OpenSpec archive 和 kanban done 之间存在窗口期

**场景**：OC 对一个 task 做了 kanban_complete，但对应的 OpenSpec spec 还没 archive。如果此时有人读 spec，看到的仍是「活跃的规范」→ 实际任务已结束。

```
时间线:
  t0: OC kanban_complete (task done)
  t1: autopilot 检测到 done, 推进下一步
  t2: [某人 读 openspec/changes/{id}/spec.md → 看到活跃状态]
  t3: openspec archive (spec 标记为 archived)
  
  窗口: t0 → t3，可能数分钟
```

**方案**：

1. **kanban_complete 的 close.sh 中集成 `openspec archive`**：完成 → archive 原子化
2. **spec.md 的 header 加状态字段**：`status: active | archived`，autopilot 读之前检查
3. **autopilot 在 step 0（启动）时校验**：如果 spec 是 archived，跳过该 task

### 6.3 autopilot cron 静默失败

**场景**：cron 进程死了但没人知道。管线停摆。

**现有机制**：P0-18 watchdog v4 已落地——session_watchdog.py + Collector + Reporter。但它是针对 OC session 的，不是针对 autopilot cron 的。

**需要补充**：
- autopilot cron 的 healthcheck（类似 `.oc_relay.json` 的心跳文件）
- 如果 2×cron_interval 内 autopilot 未更新心跳 → watchdog 告警

### 6.4 kanban dispatcher 派发失败

**场景**：kanban dispatcher 尝试 spawn OC 但失败（模型不可用、profile 不存在等）。

**现有机制**：kanban.db 已有 `consecutive_failures` 字段 + max_retries。失败达到上限后 task 进入 failed 状态。

**对管线的影响**：autopilot 检测到 task failed → 写 pipeline_state.db (step=failed) → 触发告警 → 等待人工介入。

### 6.5 故障模式总览

| 故障 | 影响 | 检测方式 | 恢复方式 | 预防 |
|------|------|---------|---------|------|
| autopilot crash + restart | 步骤可能重复执行 | attempt 计数器 | 鉴权 before 写 | 二阶段写 |
| checkpoint 数据丢失 | 管线认为从未执行过某 step | close.sh 产物存在性检查 | 从 kanban comment 历史重建 | pipeline_state.db 定期备份 |
| spec 腐化（写了不维护） | autopilot 按过时规范执行 | `openspec validate --strict` + autopilot 对比 kanban status | archive + 更新 | 定期 CI 检查 |
| cron silenced | 管线停摆 | autopilot heartbeat 文件 | watchdog 告警 → 重启 | P0-18 的扩展 |
| dispatcher 派发失败 | task stuck in ready | consecutive_failures 递增 | 达到上限后 failed → 人工 | max_retries 限制 |

---

## 7. 架构建议（不产生行动任务，BCLASS）

### 7.1 推进顺序确认

```
Phase 0: 前置条件
  └─ Node 升级到 ≥20.19 + OpenSpec CLI 安装  [0.4h]

Phase 1: 数据基座
  └─ P0-3: checkpoint (pipeline_state.db + resume.sh)  [1.0h]
     ← 先做 checkpoint，因为合约引擎的入口需要知道「上一步产出了什么」

Phase 2: 合约 + 编排
  ├─ P0-1: 步骤合约引擎 (state.py + JSONL 合约)  [2.5h]
  └─ P0-2: autopilot.sh (cron + kanban 轮询 + 步骤推进)  [集成在 P0-1 中]

Phase 3: 可视化
  └─ P1-2: CLI dashboard  [0.5h]

Phase 4: 跨会话
  ├─ DPL-011 Layer 2: SOUL.md 铁律 6  [0.1h]
  ├─ DPL-011 Layer 1: boot_context.py cron  [0.5h]
  └─ DPL-011 Layer 3: 会话摘要  [0.2h]
```

### 7.2 不做的事

- 不引入 webhook 替代 cron polling（Hermes webhook 大概率不支持 kanban 事件，R2 已评估）
- 不 fork LangGraph（借鉴 checkpoint/interrupt/resume 数据模型，不引入框架）
- 不在 `.hermes.md` 存全量历史（只存导航摘要 ~300 tokens）
- 不修改 Hermes 引擎层（管线在脚本层实现）

---

> 我是地基。今天把「从 Frank 一句话到 pipeline_state.db 一行记录」的全链路画清楚，明天 Code 照着写就不用猜了。中间那 4 套数据源的 SSOT 层级如果没理清——验收那天对账的时候全是坑。
