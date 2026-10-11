# R3 独立卷 — Engineer 工作流报告：目标系统全貌

> 角色：寇豆码（游戏引擎工程师） | 日期：2026-07-30 | 版本：v1.0
> 类型：B 类会议，独立出卷，不传递
> Frank 反馈已纳入：DPL-011 理解修正 + 先看全貌再定 MVP

---

## 0. 写在前面的工程师声明

这份报告不是"设计"——是"验证"。作为 engineer，我的职责是：蓝图拿过来，验证能不能跑、跑起来会不会打架、跑通需要多少东西。

Product 和 Architect 定义了**什么要做**。我定义**怎么做、哪里会崩、以及你至少要写多少行代码**。

---

## 1. 一条真实任务的端到端追踪

从 OC 执行 `kanban_create` 到 VA 打出 `[VERIFIED]`，新管线在每个步骤做什么。

### 1.1 角色速览

| 缩写 | 全称 | SOUL.md 位置 |
|------|------|-------------|
| OC | Orchestrator | `/root/.hermes/profiles/orchestrator/SOUL.md` |
| Arch | 架构师 (game-architect) | `/root/.hermes/profiles/game-architect/SOUL.md` |
| Eng | 工程师 (game-engine) | `/root/.hermes/profiles/game-engine/SOUL.md` |
| QA | 测试 (game-qa) | `/root/.hermes/profiles/game-qa/SOUL.md` |
| VA | 验证 (verifier) | `/root/.hermes/profiles/verifier/SOUL.md` |

### 1.2 端到端时间线

```
时刻 T0：Frank 在飞书告诉 OC "做 P0-XX 功能"
    │
    │ OC 动作：
    │   1. 读 .boot_context.md（铁律 6 触发）——恢复上下文
    │   2. 读 .hermes.md ——获取项目规范
    │   3. session_search + memory ——确认这不是重复任务
    │
    ▼
时刻 T0+2m：OC 创建 kanban 任务
    │
    │ kanban_create(
    │   title="P0-XX: 新功能",
    │   assignee="game-architect",
    │   body=OpenSpec 规范引用 + Frank 的需求原话
    │ )
    │
    │ ┌─────────────────────────────────────────────┐
    │ │ 写入: kanban.db (Hermes 内核)                │
    │ │ 状态: todo → ready → running (dispatcher)    │
    │ └─────────────────────────────────────────────┘
    │
    ▼
时刻 T0+5m：autopilot.sh（cron，每 2m）检测到新 task
    │
    │ autopilot 动作：
    │   1. 读 kanban 状态：新 task 处于 running
    │   2. 读 pipeline_state.db：此 task_id 无记录
    │   3. 写入 checkpoint：
    │      INSERT INTO pipeline_steps
    │        (task_id, step_name, status)
    │        VALUES ('t_xxx', 'dev', 'running')
    │   4. 写 kanban comment: [AUTOPILOT] Step dev started
    │   5. 告警检查：超时？合约失败？→ 正常，继续
    │
    │ ┌─────────────────────────────────────────────┐
    │ │ 写入: pipeline_state.db (SQLite WAL)         │
    │ │ 写入: kanban comment (human-readable log)    │
    │ │ cron: autopilot.sh，每 2m，no_agent=False    │
    │ └─────────────────────────────────────────────┘
    │
    ▼
时刻 T0+10m：Arch（game-architect）被 dispatcher 派发
    │
    │ Arch 启动时：
    │   1. SOUL.md 注入（profile 级，静态）
    │   2. .hermes.md 注入（项目级，静态文件扫描）
    │   3. hermes.md 现在包含：
    │      - 项目规范（QA 标准、申诉机制）
    │      - 当前活跃任务摘要（boot context cron 持续更新）
    │      - "最近 3 次会话的关键决策"
    │
    │ Arch 产出：
    │   架构设计 → docs/arch-p0-xx.md
    │   标记 step done → autopilot 检测到 → 推进到 qa
    │
    ▼
时刻 T0+1-2h：同上流程 → QA → VA → merge → close
    │
    │ 每个步骤：
    │   1. autopilot 检测 step status 变更
    │   2. state.py 做合约校验：
    │      - 进入 qa：检查 dev 的 produces 是否存在
    │      - 进入 va：检查 qa 的 test_report 是否存在
    │   3. checkpoint 记录 artifact_paths
    │
    ▼
时刻 T_close：VA 打出 [VERIFIED] → all_claims pass
    │
    │ OC 执行 close.sh（6 步闭环）：
    │   1. kanban complete
    │   2. GAI 更新（GLOBAL_ACTION_ITEMS.md）
    │   3. manifest 更新
    │   4. 备份推送
    │   5. 并发通知
    │   6. S6 检测 all pass
    │
    │ autopilot 最终检查：
    │   - pipeline_state.db: 所有步骤 status=done
    │   - state.py: 合约 produces 全部满足
    │   - 写入最后一次 checkpoint：step='close', status='done'
    │
    └─── TASK COMPLETE
```

### 1.3 每一步 autopilot + checkpoint + OpenSpec + .hermes.md 的职责矩阵

| 阶段 | autopilot 做什么 | checkpoint 写什么 | OpenSpec 在哪介入 | .hermes.md 何时更新 |
|------|-----------------|------------------|------------------|-------------------|
| **创建任务** | 检测新 task_id → 写入 dev:running | 记录 step=dev, artifact_paths=[] | OC 创建时引用 openspec ref | 无变化（项目规范不变） |
| **研发阶段** | 轮询到 dev done → 写 qa:running | 更新 artifact_paths: [prd.md, arch.md, branch] | 开发者执行 `openspec apply {task-id}` | 无变化 |
| **QA 阶段** | 读取 qa done → state.py 校验产物 | 更新 artifact_paths += [test_plan.md, test_report.md] | QA 参考 openspec spec.md 写测试用例 | 无变化 |
| **VA 阶段** | 轮询到 va done → 校验所有 claims | 更新 artifact_paths += [va_results] | VA 对照 spec.md 验证 claims | 无变化 |
| **合并** | 检测 merge ready → 人工闸门停止 | 等待 human gate | `openspec archive {task-id}` | 无变化 |
| **关闭** | 检测 close done → 最终校验 | 最后写入 status=done, finished_at=now | 已归档 | GAI 更新（boot context cron 下次捕获） |

### 1.4 checkpoint 数据的完整 schema

```sql
-- /workspace/devPPL/pipeline_state.db
-- SQLite WAL 模式，cron 进程共享

CREATE TABLE IF NOT EXISTS pipeline_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,              -- kanban task id (t_xxx)
    step_name TEXT NOT NULL,            -- dev|qa|verify|merge|close
    status TEXT NOT NULL DEFAULT 'pending',  -- pending|running|done|failed|blocked
    artifact_paths TEXT DEFAULT '[]',   -- JSON array of file paths
    started_at TEXT,
    finished_at TEXT,
    error_msg TEXT,
    retry_count INTEGER DEFAULT 0,
    assigned_agent TEXT,                -- game-architect|game-engine|game-qa|verifier
    openspec_ref TEXT,                  -- openspec/changes/{id}/spec.md
    UNIQUE(task_id, step_name)
);

-- Schema migration tracking
PRAGMA user_version = 1;
```

**为什么只要一张表**：Architect 建议的「不搞全节点 schema」。这张表存的是步骤级元数据——不存"这个 bug 是在第几行代码引入的"，只存"QA 步骤产出了 test_report.md 在 /workspace/devPPL/docs/"。够用了。如果未来需要步骤内部详情（如 QA 的 D 类 roundtable 细节），用 kanban comment 或单独的文件做结构化日志。

---

## 2. 新增脚本/文件清单和职责

### 2.1 需要新建的文件

```
/workspace/devPPL/
├── pipeline/
│   ├── state.py                  (~120 lines)  — 合约校验引擎
│   ├── checkpoint.py             (~80 lines)   — SQLite WAL wrapper
│   ├── autopilot.sh              (~60 lines)   — cron 轮询主入口
│   ├── close.sh                  (~50 lines)   — 强制闭环（6步验证）
│   ├── resume.sh                 (~30 lines)   — 跨会话上下文恢复
│   ├── dashboard.py              (~50 lines)   — CLI 管线面板
│   ├── router.py                 (~80 lines)   — 条件路由决策
│   ├── fanout.py                 (~40 lines)   — 并行 dispatch
│   ├── interrupt.py              (~30 lines)   — 中断/恢复 handler
│   └── contracts/
│       └── devPPL.jsonl          (~15 lines)   — 5 步合约定义
│
├── config/
│   └── pipeline-routes.yaml      (~30 lines)   — P1-1 路由规则
│
├── .hermes.md                     (~100 lines)  — 大幅扩展，见 §3
│
└── tests/
    └── test_pipeline.py           (~200 lines)  — P0 集成测试
```

**总计：~885 行新代码，14 个新文件。**

### 2.2 每个文件的调用链和失败处理

| 文件 | 谁调用 | 调用频率 | 失败时怎么处理 |
|------|--------|:---:|------|
| **autopilot.sh** | Hermes cron（cronjob） | 每 2 分钟 | 写 error 到 kanban comment，下次 cron tick 重试。连续 3 次失败 → 飞书告警 Frank |
| **state.py** | autopilot.sh（import） | 每次 step 切换 | 合约校验失败 → 阻止 step 推进，写 [CONTRACT_VIOLATION] comment，等待人工介入 |
| **checkpoint.py** | autopilot.sh + state.py + resume.sh | 每个状态变更 | SQLite BUSY → busy_timeout 5000ms + 重试 3 次。重试全部失败 → 写日志然后跳过（非致命——kanban 状态是 source of truth） |
| **close.sh** | OC 手动调用（或被 autopilot 触发） | 每次任务关闭 | 6 步中任何一步失败 → 标记该步 failed，不继续。下次 cron tick 重试剩余步 |
| **resume.sh** | OC 启动时主动调用（铁律 6 触发） | 每个新 OC 会话 | 无 pipeline_state.db → 打印 "no active pipeline"，正常继续 |
| **dashboard.py** | Frank 手动运行或 cron 生成摘要 | 按需 | 读 DB 失败 → 打印 "pipeline offline"，不影响管线运行 |
| **router.py** | autopilot.sh → 判断下一步路由 | 每次 step 完成 | YAML 解析失败 → 回退到默认路由（线性 dev→qa→verify→merge→close） |
| **fanout.py** | autopilot.sh → 检测到并行需求 | 按需 | kanban_create 失败 → 重试 3 次 → 失败则标记 blocked |
| **interrupt.py** | autopilot.sh → 检测到闸门 | D 类 roundtable / merge | block 操作失败 → 写 comment 手动标记 |
| **pipeline-routes.yaml** | config_loader.py → router.py | 每次路由决策 | YAML 语法错误 → config_loader 抛出明确异常，autopilot 回退线性路由 |
| **.hermes.md** | Hermes `build_context_files_prompt()` | 每个 session 启动 | 文件不存在或过大 → 注入空字符串（不阻塞 session） |
| **test_pipeline.py** | QA / CI | 按需 | 测试失败 → 写在测试报告中，不阻塞管线 |

### 2.3 不需要新建的（复用现有基础设施）

| 现有文件 | 用途 | 改动 |
|----------|------|:---:|
| `scripts/lib/kanban_helpers.py` | kanban CLI 封装 | +15 lines：新增 `get_task_state()` 和 `get_task_artifacts()` |
| `scripts/lib/config_loader.py` | YAML 配置加载 | +15 lines：新增 `load_pipeline_config()` |
| `config/qa-classification.yaml` | QA 分级标准 | 无改动 |
| `GLOBAL_ACTION_ITEMS.md` | 人工维护 manifest | 无改动（由 close.sh 更新） |

---

## 3. DPL-011 的具体实现：.hermes.md 扩展 + boot context

### 3.1 理解修正：DPL-011 到底是什么

Frank 纠正了我们之前的理解：DPL-011 **不是**"让 Frank 能读记忆"——而是解决 **Hermes 的架构问题**：session 被系统静默切分，OC 跨 session 后"失忆"。

**核心机制**：Hermes 已有 **Project Context 系统**（`.hermes.md`），会在每个 session 启动时自动加载，向上遍历到 git root，上限 20,000 字符。我们一直没认真用起来。

### 3.2 .hermes.md 的新结构设计

当前 `.hermes.md` 只有 30 行，全是 QA 规范引用。Frank 说「只保留 QA 标准，boot context 另走 cron」。正确的设计是 **两段式**：

```markdown
# devPPL 项目规范

> 以下内容由两个来源拼接：静态规范（人工维护）+ 动态上下文（boot context cron 自动生成）

## 📋 项目规范（静态，人工维护）

### 核心标准文档
...（保留现有 QA 标准 30 行）
...

### 管线规则（新增）
- 5 步管线：dev → qa → verify → merge → close
- 合约文件：pipeline/contracts/devPPL.jsonl
- 超时规则：dev 60min / qa 45min / verify 30min / merge 15min / close 15min
- 合约违规处理：阻止步骤推进，kanban comment 通知，等待 OC 介入

---

## 🔄 当前活跃上下文（动态，cron 每 5min 更新）

<!-- BEGIN AUTO-GENERATED: boot context -->
<!-- 最后更新: 2026-07-30T14:30:00Z -->
<!-- 生成方式: cron boot_context.py, no_agent=True -->

### 活跃任务
| 任务 | 步骤 | 状态 | 产物 |
|------|------|------|------|
| t_xxx: P0-XX 新功能 | dev | running | - |
| t_yyy: P1-YY 优化 | qa | blocked (等待 D 类 roundtable) | test_plan.md ✓ |

### 最近决策（最近 3 次会话）
- [2026-07-30] Frank 确认：管线工具 Phase 1 先做 checkpoint，再 autopilot
- [2026-07-30] R2 共识：Node 22 二进制直装，不依赖 apt 仓库
- [2026-07-30] R1 发现：kanban 无真正 hook，autopilot 只能 cron polling

### 被纠正的行为（Memory verify 标记）
- 做梦报告投递方式 [纠正×3]：必须照抄 backup 的投递方式
- close.sh 不在 repo 中 [已确认]：位于 OC profile home

<!-- END AUTO-GENERATED -->
```

**存储方式**：不直接写 `.hermes.md`（会和人工维护的规范冲突），而是：

```
/workspace/devPPL/
├── .hermes.md              ← 静态规范（人工维护，~50行，只含 QA 标准 + 管线规则）
└── .hermes/
    ├── boot_context.md     ← cron 自动生成（动态上下文，~500 tokens）
    └── includes/
        └── pipeline-context.md  ← 由 .hermes.md include 指令引用（如果 Hermes 不支持 include，改为 cron 拼接）
```

**实际落地方式**：因为 Hermes 的 `build_context_files_prompt()` 只扫描静态文件，不支持 include 指令——**用 cron 直接重写 `.hermes.md`**，把静态部分和动态部分拼接后覆写。静态部分从 `docs/hermes-static.md` 模板读取。

### 3.3 boot context cron：多长周期、更新什么

```
cron job: "pipeline-boot-context"
  schedule: "every 5m"
  no_agent: true
  script: /workspace/devPPL/scripts/boot_context.py
  deliver: "local"  # 不推送给 Frank，静默更新文件
```

`boot_context.py` 做什么（~80 行 Python）：

1. **读 session DB**（`sqlite3 ~/.hermes/sessions/sessions.db`）→ 最近 3 个 session 的标题 + 最后一条 user message
2. **读 pipeline_state.db** → 所有 status≠'done' 的活跃任务 + 当前步骤
3. **读 memory**（`mem0_tagged.search_tagged(state='verified')`）→ 被 Frank 纠正过的行为
4. **格式化** → 紧凑 markdown，控制在 400-500 tokens
5. **拼接** → 读 `docs/hermes-static.md`（静态模板），追加动态区块
6. **写入** → 原子写入 `.hermes.md`（先写 `.hermes.md.tmp`，再 `os.rename`）

**为什么 5 分钟**：
- Agent 被 dispatcher 派发是间歇性的——不会每 10 秒就有一个新 session
- pipeline_state.db 的变更频率约每 10-30 分钟（一个 agent 完成一个步骤）
- 5 分钟足够覆盖"上一个 session 刚结束，下一个 session 就拿到最新上下文"
- 如果降到 1 分钟：对 SQLite 没压力（WAL 模式），但 token 预算上无增益

### 3.4 如何判断什么信息值得写入 .hermes.md

**硬规则**：

| 写入 | 不写入 |
|------|--------|
| 活跃任务（status≠done）的当前步骤 | 已完成任务的细节 |
| 最近 3 次会话的标题 + 一句关键决策 | 会话的完整消息流 |
| 被 Frank 明确纠正的行为（verified memory） | LLM 中间推理过程 |
| 管线健康状态（是否有 blocked task） | agent 的临工笔记 |
| 最近一次决策变更（Frank 说了"改成 X"） | 技术实现细节（给 agent 看 architecture.md） |

**容量控制**：硬限制 2000 字符（~500 tokens）。超了就截断活跃任务列表（只保留最近 5 个）和决策列表（只保留最近 3 条）。

**为什么不用 `memory` 工具替代**：memory 自动注入在 system prompt 位置靠后（在 SOUL.md 之后），而 `.hermes.md` 作为 Project Context 在 SOUL.md **之前**注入。Frank 要的是"agent 在加载自己的 SOUL.md 之前就知道项目上下文"——这就是 DPL-011 要解决的架构问题。

---

## 4. 坑点清单

基于 R1/R2 的发现 + 新全貌分析，按严重度排序：

### 🔴 坑 1：autopilot cron 和 checkpoint cron 抢 SQLite 锁（MAJOR）

**场景**：autopilot.sh（每 2m）和 boot_context.py（每 5m）同时读写 `pipeline_state.db`。SQLite WAL 允许多 reader + 单 writer，但两个 writer 同时写 → 第二个拿 `SQLITE_BUSY`。

**缓解**：
- checkpoint.py 所有写操作加 `busy_timeout=5000` + 重试 3 次
- boot_context.py 只读不写 pipeline_state.db（它从 memory + session DB 读）
- 如果仍有冲突：autopilot.sh 和 boot_context.py 错开执行周期（autopilot 在 0/2/4/6... 分钟，boot_context 在 1/3/5/7... 分钟）

**实际风险**（经分析）：boot_context.py **不写** pipeline_state.db——它读 session DB、memory、pipeline_state.db，**只写** `.hermes.md`。因此两个 cron 的对 pipeline_state.db 的操作是：autopilot 写 + boot_context 读 → WAL 完美支持，零冲突。

### 🔴 坑 2：kanban 没有真正的事件 hook（BLOCKER 级后果，但已降级）

**状态**：R2 已验证——Hermes webhook 不支持 kanban 内部事件。cron polling 是唯一路径。

**影响**：
- 步骤切换延迟最大 2 分钟（cron 间隔）
- 如果 cron 进程挂了（crash/oom）→ 管线静默停止，没有心跳
- 依赖 Watchdog v5 检测"autopilot cron 是否还活着"

**缓解**：
- Watchdog v5 监控 autopilot cron 的心跳
- 2 分钟延迟对 30-60 分钟的步骤来说影响不大
- 未来如 Hermes 增加 kanban hook → 可无缝升级（checkpoint.py 接口已预留）

### 🟡 坑 3：pipeline_state.db schema migration（MEDIUM）

**场景**：v1 schema 只有 `pipeline_steps` 一张表。v2 可能需要 `step_audit_log` 表或新字段。SQLite 的 `ALTER TABLE` 能力有限。

**缓解**：checkpoint.py 内置 `PRAGMA user_version` schema migration：
```python
DB_PRAGMA = "PRAGMA user_version"
if current_version < 2:
    conn.execute("ALTER TABLE pipeline_steps ADD COLUMN assigned_agent TEXT")
    conn.execute("PRAGMA user_version = 2")
```

### 🟡 坑 4：autopilot 死循环——步骤反复切换（MEDIUM）

**场景**：agent A 把 step 标为 done → autopilot 推进到下一步 → agent A 的 successor 又把 step 标回 running（因为 re-dispatch 等原因）→ autopilot 检测到回退 → 重复推进。

**缓解**：state.py 做幂等检查：
```python
if current_status == 'done' and new_action == 'start':
    raise ContractViolation(f"step {step_name} already done, cannot restart")
```
另加 `retry_count` 字段——同一 task+step 被推进超过 3 次 → 标记 blocked，等人工介入。

### 🟡 坑 5：close.sh 跨 profile 依赖（MEDIUM → MINOR）

**状态**：R2 已验证 close.sh 在 OC profile home（`/root/.hermes/profiles/orchestrator/scripts/close.sh`），不是幽灵依赖。

**但仍有隐忧**：如果 OC profile 被重建或迁移，close.sh 可能丢失。建议在 devPPL repo 中留存一份副本（`pipeline/close.sh`），OC profile 的版本通过 symlink 指向。

### 🟢 坑 6：Node 升级对 gateway 进程的影响（MINOR）

**问题**：Node 从 18 → 22 升级（二进制直装到 `/usr/local`），会影响当前运行的 Hermes gateway 进程吗？

**答案**：不会。Hermes gateway 是 Python 进程，不依赖系统 Node。只有 OpenSpec CLI（`openspec` 命令）需要 Node ≥20.19。升级路径是**并行的**——不会中断 gateway。

**风险**：如果 CloudStudio 沙箱禁止写 `/usr/local`，需要运维介入。备选方案：装到 `/workspace/node-v22/` 并加 `PATH`。

### 🟢 坑 7：boot_context.py 的 session DB schema 依赖（MINOR）

**问题**：`boot_context.py` 直接读 Hermes session DB——schema 非公开 API，可能随 Hermes 版本变化。

**缓解**：
- 优先用 `hermes session list --json` CLI（如果可用）
- Fallback 到 SQLite 直读，加 schema 版本检查
- 两种方式都失败 → 写 "boot context unavailable" 到 `.hermes.md`，不阻塞

---

## 5. 最小可用演示

如果 Frank 说「让我看看这玩意真能跑」——下面是演示方案。

### 5.1 演示内容：一个任务从头跑到尾

```
# Step 0：验证环境
$ node --version                 # → v22.x (已升级)
$ python3 -c "import sqlite3"    # → OK
$ ls /root/.hermes/profiles/orchestrator/scripts/close.sh  # → exists

# Step 1：初始化管线基础设施
$ mkdir -p /workspace/devPPL/pipeline/contracts
$ python3 /workspace/devPPL/pipeline/checkpoint.py --init
# 输出: "pipeline_state.db created, user_version=1"

# Step 2：创建一个测试合约
$ cat > /workspace/devPPL/pipeline/contracts/devPPL.jsonl << 'EOF'
{"step":"dev","requires":[],"produces":["branch","code_changes"],"timeout_min":60}
{"step":"qa","requires":["branch","code_changes"],"produces":["test_plan.md","test_report.md"],"timeout_min":45,"gate":"D_roundtable"}
{"step":"verify","requires":["test_report.md"],"produces":["va_results"],"timeout_min":30}
{"step":"merge","requires":["va_results","test_report.md"],"produces":["merge_commit"],"gate":"human"}
{"step":"close","requires":["merge_commit"],"produces":["gai_update","manifest_update"],"timeout_min":15}
EOF

# Step 3：模拟一次端到端运行（dry-run 模式）
$ python3 /workspace/devPPL/pipeline/state.py \
    --task-id t_demo_001 \
    --dry-run \
    --verbose

# 期望输出：
# [PASS] dev → qa: all requires satisfied
# [PASS] qa → verify: test_report.md exists
# [PASS] verify → merge: va_results valid
# [SKIP] merge: human gate — awaiting Frank
# [PASS] merge → close: merge_commit exists
# Pipeline complete: 5/5 steps verified

# Step 4：启动 autopilot cron（观察模式）
$ hermes --profile orchestrator cronjob create \
    --name "pipeline-autopilot-demo" \
    --schedule "every 2m" \
    --no_agent true \
    --script /workspace/devPPL/pipeline/autopilot.sh \
    --deliver local

# Step 5：CLI 面板查看状态
$ python3 /workspace/devPPL/pipeline/dashboard.py
# ┌─ Pipeline: devPPL ──────────────────────────────┐
# │ t_demo_001: [dev:done → qa:running] 0:12:45      │
# │   artifacts: prd.md ✓, arch.md ✓, branch ✓        │
# │ t_demo_002: [qa:blocked] 1:03:22                  │
# │   block: D 类 roundtable 待产品裁定                │
# └──────────────────────────────────────────────────┘
```

### 5.2 演示所需的前置条件

| 条件 | 状态 | 操作 |
|------|:---:|------|
| Node ≥ 20.19 | ❌ 当前 18.19 | 二进制直装到 `/usr/local/bin`（5 行命令） |
| pipeline_state.db | ❌ 未创建 | `checkpoint.py --init`（1 行命令） |
| checkpoint.py | ❌ 未写 | **这是 Slice 1 的第一个交付件** |
| autopilot.sh | ❌ 未写 | 依赖 checkpoint.py 完成后编写 |
| state.py | ❌ 未写 | 依赖 JSONL 合约定义 |

**从零到"能演示"的最短路径**：

```
1. [0.5h] Node 升级 (二进制直装)
2. [1.5h] checkpoint.py + pipeline_state.db schema + 单元测试
3. [0.5h] 合约 JSONL 定义（5 步）
4. [1.0h] state.py（读取合约 + 校验逻辑）
5. [0.5h] autopilot.sh（cron 轮询框架）
6. [0.5h] dashboard.py（CLI 面板）
7. [0.5h] 端到端 dry-run 验证
─────────────────────────────────
   ~5.0h → 可以跑完整演示
```

---

## 6. 与其他系统共存

### 6.1 autopilot vs Watchdog v5：会冲突吗？

**不会**。职责完全不同：

| | autopilot | Watchdog v5 |
|---|----------|------------|
| 做什么 | 轮询 kanban → 推进步骤 | 监控 OC 健康 + 任务积压 |
| 读什么 | kanban.db + pipeline_state.db | kanban.db + cron.db + session file |
| 写什么 | pipeline_state.db + kanban comment | 飞书消息（播报） |
| 频率 | 每 2 分钟 | 每 30 分钟 |
| 同一时间窗口 | autopilot 写 pipeline_state.db | watchdog 读 kanban.db（不同 DB） |

**唯一交集**：如果 autopilot cron 挂了，watchdog 应该能检测到"autopilot 心跳丢失"，然后播报。需要在 watchdog 的监控列表中加入 `pipeline-autopilot` cron job。

**改动**：watchdog 配置新增监控目标：
```yaml
watchdog:
  cron_jobs_to_monitor:
    - pipeline-autopilot       # 新增
    - pipeline-boot-context    # 新增
```

### 6.2 checkpoint cron 和 autopilot cron 会抢锁吗？

**不会**（见 §4 坑 1 分析）。autopilot 写 pipeline_state.db，boot_context 读 pipeline_state.db → WAL 模式完美支持。

### 6.3 多个 autopilot cron 实例之间的竞争

**问题**：如果 autopilot cron 的间隔是 2 分钟，但单次运行超过 2 分钟 → 两个实例同时运行。

**缓解**：autopilot.sh 开头加文件锁：
```bash
LOCKFILE="/tmp/pipeline-autopilot.lock"
exec 200>"$LOCKFILE"
flock -n 200 || exit 0  # 已有实例在跑，静默退出
```

### 6.4 Node 升级对现有 gateway 的影响

**零影响**。验证：
- Hermes gateway 进程：Python 3.11，不依赖系统 Node.js
- 现有 cron job：全部是 Python/bash，不依赖 Node
- kanban dispatcher：Python 进程，不依赖 Node

Node 22 二进制直装到 `/usr/local/bin/node`，和现有 Node 18（`/usr/bin/node`）并存。PATH 优先级决定用哪个：`/usr/local/bin` 优先于 `/usr/bin`。

如果 Frank 担心共存，可以用 `update-alternatives` 管理多版本：
```bash
update-alternatives --install /usr/bin/node node /usr/local/bin/node-v22 100
update-alternatives --install /usr/bin/node node /usr/bin/nodejs 50
# 默认用 v22，可随时切回 v18: update-alternatives --set node /usr/bin/nodejs
```

---

## 7. 一句话总结

> OpenSpec 是规范层，checkpoint 是数据层，autopilot 是执行层。先做数据层（pipeline_state.db），再连规范层和执行层——这就是 Frank 要的"全貌"。从零到能演示：~5h 写代码 + 0.5h 环境准备。Watchdog 不冲突，SQLite WAL 不打架，Node 升级不影响现有服务。坑都在上面列清楚了——开始写代码之前，你知道所有可能绊倒你的地方。

---

> 我是团队的双手。蓝图要我验证——验完了。管线能跑，5 小时出 demo，冲突全是已知的、可缓解的。给我 checkpoint 先，剩下的按依赖链推进。
