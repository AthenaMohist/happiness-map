# Watchdog v3.0 — 架构评估报告

> 作者：高见远（架构师） | 日期：2026-07-10 | 议题：B 类头脑风暴 → 架构评估
> 任务：t_badfe4eb

---

## 1. 改动量评估：修 bug 还是重写？

### 结论：**重写**。核心数据模型变更，不是增量修补。

### 差异矩阵

| 维度 | v2.0 (现状) | v3.0 (Frank 要求) | 差异性质 |
|------|-------------|-------------------|----------|
| **数据源** | kanban.db 单一数据源 | kanban.db + OC session 状态 + cron 调度状态 | **新增 2 个数据源** |
| **触发机制** | 手动 resume/pause cron job | OC 生命周期自动触发 | **从手动到自动** |
| **状态模型** | 三态 FSM (ACTIVE→QUIET→SILENT) | 二元：OC 在跑 / OC 不在跑 | **简化但语义不同** |
| **输出格式** | 逐条列出 task | 聚合统计 + OC 会话状态 | **格式重写** |
| **间隔** | 2 min | 1 min | 参数调整 |
| **运行方式** | no_agent Python 脚本 | 待定（见 §4 分析） | 架构选择 |

v2.0 的核心抽象是"有没有 kanban task 在跑"。
v3.0 的核心抽象是"OC 会话是否活跃 + 该会话的任务统计"。

**这两个抽象不兼容。** v2.0 没有 OC 会话概念——它不知道是谁创建了任务、当前 OC 是否还活着。强行在 203 行脚本上打补丁会导致「if-OC-session-else-old-path」的分叉地狱。

**估算**：新脚本 250-400 行，新增 2 个数据读源（session DB / session state file），约 3-5 人天工作量。

---

## 2. 会话感知：Watchdog 如何感知 OC 会话？

### 数据流分析

Frank 要求的三个信息维度：

```
┌─────────────────────────────────────────────┐
│            Watchdog v3.0 需要感知            │
├─────────────────────────────────────────────┤
│ A. OC 会话是否活跃？                         │
│    → 知道该不该播报                          │
│                                             │
│ B. OC 会话的 kanban 任务统计？               │
│    → 生成 📋N|✅N|🔄N|⏳N 格式              │
│                                             │
│ C. OC 会话的时间信息？                       │
│    → 当前会话何时结束、下个 one-shot 何时启动 │
└─────────────────────────────────────────────┘
```

### 数据源分析与选型

#### A. OC 会话是否活跃？

| 方案 | 实现 | 优点 | 缺点 |
|------|------|------|------|
| **S1: Session state file** | OC 启动时写 `.oc_session.json`，结束时删除 | 简单、类似现有 `.kanban_resume` 模式 | OC 崩溃则文件残留 |
| **S2: Session DB 轮询** | 读 `~/.hermes/profiles/orchestrator/state.db` | 无需 OC 配合 | messages 表无限增长；解析 tool-call JSON 脆弱 |
| **S3: Cron job 检测** | 检查 OC 的 one-shot cron 是否 still running | 原生 cron API | OC 不一定是 cron 触发的（手动/roundtable） |

**选型：S1（Session state file）为主，S2 为辅。**

S1 作为存在性检测（OC 在不在），S2 只在需要"当前会话何时结束"时补充读取。

Session state file 格式（提议）：
```json
{
  "session_id": "abc123",
  "started_at": "2026-07-10T14:30:00",
  "role": "orchestrating",           // orchestrating | executing | debating
  "expected_children": 4,            // OC 派发了多少子任务
  "completed_children": 2,           // 已完成的子任务数
  "next_one_shot_at": "2026-07-10T15:00:00"  // 下一轮 OC cron 启动时间（如有）
}
```

#### B. 任务统计（📋安排/✅跑完/🔄在跑/⏳未跑）

v2.0 已能读 kanban.db。v3.0 需要增加的是**归属关系**：
- 哪些任务是本次 OC 会话创建的？
- 「跑完」「在跑」「未跑」怎么定义？

**定义依赖产品澄清，我先给技术方案**：
- **安排**：OC 创建的所有非 done/archived 任务
- **跑完**：本次 OC 会话期间变为 done 的任务
- **在跑**：status=running 的任务（不限谁创建）
- **未跑**：status=ready 的任务（不限谁创建）

替代方案（如果 Frank 想只看 OC 创建的）：kanban DB 记录了 `created_by` 字段，但 OC 是通过 hermestools 调用的，`created_by` 值是 "hermes" 而非 "orchestrator"。需要 OC 在创建任务时打标记。

#### C. OC 时间信息

读取 OC profile 的 cron.db 中的 one-shot cron job 记录，获取 `next_run_at`。
如果 OC 是手动启动的一次性 session（非 cron），则通过 session state file 的 `next_one_shot_at` 字段传递。

---

## 3. OC 生命周期绑定：触发机制

### 架构图

```
┌──────────────┐     write/delete      ┌──────────────────┐
│  OC Session  │ ──── .oc_session.json ─→│  Watchdog Cron   │
│              │                        │  (LLM-driven,1min)│
│  kanban_     │                        │                  │
│  create ─────┼──→ kanban.db ─────────→│  读 kanban.db    │
│              │                        │  读 session file │
│  cronjob     │                        │  读 cron.db      │
│  create ─────┼──→ cron.db ───────────→│  格式化输出      │
└──────────────┘                        └──────────────────┘
```

### 触发链路

```
OC 启动
  ├── 1. 创建 .oc_session.json（原子写：写 .tmp → mv）
  ├── 2. cronjob(action='resume', job_id='<watchdog>') 或 watchdog 自行检测
  └── 3. 正常派发 kanban 任务

OC 运行中
  ├── 每派发/完成子任务 → 更新 .oc_session.json 的 children 计数
  └── watchdog 每分钟读 session file + kanban.db → 输出统计

OC 即将停止
  ├── 所有子任务完成 → 更新 .oc_session.json (completed_children == expected_children)
  ├── watchdog 检测到 0 活跃任务 → 输出 "无任务在跑，即将静默"
  ├── OC 删除 .oc_session.json
  └── watchdog 下次 tick 检测到无 session file → 停止播报（真正静默）
```

### 与其他方案的对比

| 方案 | 实现 | 评价 |
|------|------|------|
| **kanban-event-hooks** | 假设 Hermes 内核支持事件回调 | ❌ Hermes 无此能力，需平台级改动，不现实 |
| **OC 主动 create/destroy cron** | OC 启动时创建临时 watchdog cron，结束时删除 | ⚠️ 可行但 cron.db 高频 churn，出错时泄漏僵尸 cron |
| **Shared state file** (推荐) | 一个持久 watchdog cron + session file 存在性驱动播报 | ✅ 最简、和现有 `.kanban_resume` 模式一致 |

---

## 4. 风险与架构约束

### R1: Stale session file（OC 崩溃残留）

**场景**：OC 进程被 kill -9，`.oc_session.json` 未删除 → watchdog 误以为 OC 还在跑，永久播报。

**缓解**：
- Session file 内加 TTL（max_age_seconds=600，10 分钟）
- Watchdog 读文件时检查 `now - updated_at > TTL` → 视为无效，删除
- OC 每完成一个子任务时 `touch` 更新 `updated_at`

### R2: 格式语义模糊

**Frank 的格式**：`📋 安排N个 | ✅ 跑完N个 | 🔄 在跑N个 | ⏳ 未跑N个`

当前未明确：
- 「安排」= OC 创建的所有任务？还是包括手动创建的？
- 「跑完」= 本次 OC 会话期间 done 的？还是历史所有 done？
- 四个数字是全局还是仅 OC 创建的？

**需要产品 @许清楚 澄清后才能锁死实现。**

### R3: no_agent vs LLM-driven 路线选择

这是 v2.0 最痛的遗留问题：

- `no_agent` 脚本：**送达不可靠**（v2 实战教训），但零 token 消耗，格式化输出简单
- `LLM-driven` cron：**送达可靠**，但每分钟烧 token，且格式化统计是机器擅长的活

**推荐架构**：两层分离

```
Layer 1: data-collector (no_agent script, 30s cron)
  → 读 kanban.db + session file → 输出纯文本统计字符串
  → stdout: "📋 安排4个 | ✅ 跑完2个 | 🔄 在跑1个 | ⏳ 未跑1个"
  → 无 session file 时 stdout 为空

Layer 2: reporter (LLM-driven cron, 1min)
  → context_from: [collector job]
  → prompt: "以下是看板统计。非空就直接输出原文字符串到聊天；空则回复'无任务在跑，即将静默'然后停止。"
  → 工具集: 无（纯格式转发，不需要 kanban 工具）
```

这样：
- Layer 1 可单独测试（纯脚本，不依赖 agent 管道）
- Layer 2 负责可靠送达（走完整 agent 消息通道）
- Layer 1 的输出本身就是最终格式，LLM 不需要重新组织

### R4: 多 OC 会话并存

当前 OC 是单会话模型（orchestrator profile 同时只跑一个 session）。如果未来支持并行 OC，session state file 需要变成 directory of files：
```
.oc_sessions/
  abc123.json
  def456.json
```
Watchdog 遍历目录，合并统计。目前不需要，但 file 命名应预留扩展性（用 session_id 命名而非固定名）。

### R5: Kanban DB 锁竞争

v2.0 的 SQLite 读没有 WAL 模式，高频率（1min）读 + OC 写可能触发 `database is locked`。
当前 kanban.db 似乎没有高频锁竞争问题，但增加到 1min 后注意监控。加 `PRAGMA journal_mode=WAL` 即可彻底解决。

### R6: session DB 隐私边界

读 `state.db` 获取 OC 会话状态意味着 watchdog 可以读到 OC 的全部对话历史。这是一个隐私边界——watchdog 只应读"结构化元数据"（session 状态），不应读"对话内容"。

**约束**：如果必须走 S2（session DB 轮询），只查 session 表（session_id, status, started_at），不查 messages 表。

---

## 5. 推荐架构总览

```
                    ┌─────────────────────┐
                    │    OC Session        │
                    │  (orchestrator)      │
                    │                     │
                    │  启动时写:           │
                    │  .oc_session.json   │
                    │  结束时删            │
                    └──────┬──────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        .oc_session    kanban.db     cron.db
        .json          (tasks)       (one-shot)
              │            │            │
              └────────────┼────────────┘
                           │
                           ▼
              ┌──────────────────────┐
              │  Layer 1: Collector  │
              │  (no_agent, 30s)     │
              │  → 纯文本统计字符串   │
              └──────────┬───────────┘
                         │ stdout
                         ▼
              ┌──────────────────────┐
              │  Layer 2: Reporter   │
              │  (LLM cron, 1min)    │
              │  context_from: coll. │
              │  → 原文转发/静默      │
              └──────────────────────┘
```

### 与 v2.0 的 diff

| v2.0 | v3.0 |
|------|------|
| 1 层 no_agent 脚本 | 2 层：collector (no_agent) + reporter (LLM) |
| 手动 resume/pause | 自动：session file 存在→播报，不存在→静默 |
| 三态 FSM | 二元：session file 存在/不存在 |
| 逐条列表 | 聚合统计 🤖\n📋N\|✅N\|🔄N\|⏳N |
| 无 OC 感知 | OC session file + cron timing |
| 2 min 间隔 | 1 min (collector 30s 采集，reporter 1min 发送) |

### 文件变更清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `~/.hermes/profiles/orchestrator/scripts/kanban_collector.py` | **新建** | Layer 1: 纯数据采集 |
| `~/.hermes/profiles/orchestrator/scripts/.oc_session.json` | **运行时** | OC 写入，collector 读取 |
| `~/.hermes/profiles/orchestrator/scripts/kanban_watchdog.py` | **废弃/替换** | v2.0 不再使用 |
| `~/.hermes/profiles/orchestrator/scripts/.kanban_resume` | **废弃** | 由 session file 替代 |
| `~/.hermes/profiles/orchestrator/scripts/.kanban_watchdog_meta.json` | **废弃** | 三态状态机消除 |
| cron job `bbe75923ac55` (LLM watchdog) | **修改** | 改为 context_from collector |
| cron job (new, collector) | **新建** | 30s no_agent collector |
| OC orchestrator skill | **修改** | 增加 session file 生命周期管理 |

---

## 6. 需要产品澄清的问题（@许清楚）

在进入实现前，以下问题需要产品确认：

1. **「安排」「跑完」「在跑」「未跑」的精确定义**
   - 范围：仅 OC 创建的任务？还是看板上所有任务？
   - 「跑完」的时间窗口：本次 OC 会话期间？过去 N 分钟？

2. **OC 会话结束后的行为**
   - "无任务在跑，即将静默"之后，watchdog cron 是 pause 还是 keep running but silent？
   - 如果 keep running：下次 OC 启动时如何重新激活？用 session file 检测（推荐）还是 OC 主动 resume？

3. **「下个 one-shot cron 何时启动」的显示位置**
   - 在心跳消息里内联？还是单独一行？

---

> **结论**：v3.0 是重写，不是修 bug。推荐两层架构（collector + reporter），session file 驱动生命周期，消除三态状态机。核心风险是 stale session file 和格式语义模糊——前者有 TTL 缓解，后者需要产品澄清。
