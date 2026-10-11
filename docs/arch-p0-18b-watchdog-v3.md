# Watchdog v3.0 — 架构设计文档

> 作者：高见远（架构师） | 日期：2026-07-10 | 版本：v1.2
> 来源：B 类 Roundtable 架构评估 → 正式设计
> 前置评估：`docs/arch-p0-18-watchdog-v3-evaluation.md` (t_badfe4eb)
> 产品评估：`docs/roundtables/watchdog-v3-product-evaluation.md`
> 对应 PRD：`docs/prd-p0-18-watchdog.md`

---

## Changelog

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-10 | 初始版本，814 行，14 章节 |
| v1.1 | 2026-07-10 | 架构修正：路径常量 / 「安排」过滤 |
| **v1.2** | **2026-07-10** | **Frank 裁定 R-D1：project_board → project_boards（支持跨 board 项目）** |

### v1.1 修正详情（t_f703074d）

**BLOCKER 修复**：
- 所有路径常量从 `~/.hermes/...` 改为绝对路径 `/root/.hermes/...`
- 移除伪代码中的 `.expanduser()` 调用（绝对路径不需要展开）
- 根因：orchestrator profile 下 `~` 展开为 `/root/.hermes/profiles/orchestrator/home`，导致 collector 扫不到 kanban.db / cron.db / session file

**「安排」计数优化**：
- 「安排」= `ready + running`（**排除 blocked**）
- Blocked 任务往往是僵尸卡片，纳入「安排」会虚增工作量计数
- 同时仅扫描 OC 当前项目的看板（通过 `.oc_session.json` 的 `project_boards` 字段识别，支持跨 board 项目），避免跨项目干扰

**Session file 扩展**：
- 新增 `project_boards` 字段（§5.2/§5.3），collector 据此过滤扫描范围（支持多 board）

**影响范围**：§3.3, §3.4, §3.5, §5.2, §5.3, §7.2, §12.3, §14.C

### v1.2 修正详情（t_c253b9e5）— Frank 裁定 R-D1

**Frank 裁定**：「安排」不是全局所有任务，是 OC 当前项目相关任务。跨 board 的项目需汇总所有相关 board。

**设计变更**：
- `.oc_session.json`: `project_board`（string）→ `project_boards`（list[string]）
- Collector: `project_board not in` → `project_boards not in`（支持多 board 过滤）
- Root DB: 仅在 `project_boards` 未指定时扫描（有项目过滤时不纳入 root DB）
- 四维（📋✅🔄⏳）统一范围：仅限 project_boards 列出的 board

**向后兼容**：当 `project_boards` 未指定时，行为与 v1.1 一致（扫描所有 board + root DB）。

**影响范围**：§3.3, §5.2, §5.3, 伪代码, 测试 TC-12/TC-13

---

## 目录

1. [设计目标与原则](#1-设计目标与原则)
2. [总体架构](#2-总体架构)
3. [Layer 1：Data Collector](#3-layer-1data-collector)
4. [Layer 2：LLM Reporter](#4-layer-2llm-reporter)
5. [OC Session State File 协议](#5-oc-session-state-file-协议)
6. [OC 生命周期绑定](#6-oc-生命周期绑定)
7. [会话感知：时间线汇报](#7-会话感知时间线汇报)
8. [状态机：极简二元模型](#8-状态机极简二元模型)
9. [数据流](#9-数据流)
10. [边缘场景矩阵](#10-边缘场景矩阵)
11. [风险与缓解](#11-风险与缓解)
12. [实施计划](#12-实施计划)
13. [与 v2.0 的差异对照](#13-与-v20-的差异对照)
14. [附录](#14-附录)

---

## 1. 设计目标与原则

### 1.1 Frank 的四项需求

| # | 需求 | 来源 |
|---|------|------|
| F1 | 每分钟心跳，格式 `📋 安排N个 | ✅ 跑完N个 | 🔄 在跑N个 | ⏳ 未跑N个` | Frank |
| F2 | 与 OC 生命周期绑定：OC 启动 → watchdog 激活；OC 停止 → "无任务在跑，即将静默" → watchdog 停 | Frank |
| F3 | 汇报 OC 会话情况：当前会话何时结束、下个 one-shot cron 何时启动 | Frank |
| F4 | 不要复杂的 SILENT 状态机 | Frank |

### 1.2 设计原则

1. **两层分离**：数据采集与消息投递解耦。Layer 1（collector）纯脚本、零 token；Layer 2（reporter）走 agent 管道、可靠送达。
2. **会话驱动**：watchdog 的生命周期由 OC 会话状态决定，不做独立状态机。
3. **Profile 对等**：watchdog 在 orchestrator profile 下运行，复用 Feishu 凭证。
4. **失败友好**：所有错误模式都有降级路径，不静默吞错。
5. **v2 教训**：no_agent 脚本 cron 送达不可靠（v3-v5 实战教训）→ 用 LLM reporter 层保底。

---

## 2. 总体架构

### 2.1 架构图

```
                         ┌──────────────────────┐
                         │    OC Session         │
                         │   (orchestrator)      │
                         │                      │
                         │  启动时:              │
                         │  • 写 .oc_session.json│
                         │  • 创建/恢复 watchdog │
                         │     cron              │
                         │  • fan-out kanban 任务│
                         │                      │
                         │  运行中:              │
                         │  • touch heartbeat   │
                         │  • 更新 children 计数 │
                         │                      │
                         │  结束前:              │
                         │  • 写 status=draining │
                         │  • 等 reporter 告别   │
                         │  • 删 .oc_session.json│
                         └──────┬───────────────┘
                                │
               ┌────────────────┼────────────────┐
               │                │                │
               ▼                ▼                ▼
         .oc_session       kanban.db         cron.db
         .json             (tasks)           (one-shot)
               │                │                │
               └────────────────┼────────────────┘
                                │
                                ▼
               ┌─────────────────────────────────┐
               │  Layer 1: Data Collector        │
               │  (no_agent cron, 30s)            │
               │                                 │
               │  读 .oc_session.json → 会话状态  │
               │  读 kanban.db → 任务四维统计     │
               │  读 cron.db → 下一轮启动时间     │
               │                                 │
               │  输出：纯文本统计字符串           │
               │  无 session → stdout 为空        │
               └──────────────┬──────────────────┘
                              │ stdout
                              ▼
               ┌─────────────────────────────────┐
               │  Layer 2: LLM Reporter           │
               │  (LLM cron, 1min)                │
               │  context_from: [collector job]   │
               │                                 │
               │  collector 非空 → 原文转发       │
               │  collector 为空 → "即将静默"     │
               │                 → 暂停自己       │
               └──────────────┬──────────────────┘
                              │ hermes send
                              ▼
               ┌─────────────────────────────────┐
               │  Feishu API                      │
               │  → Frank 的飞书消息               │
               └─────────────────────────────────┘
```

### 2.2 两层理由

| 维度 | 纯 no_agent | 纯 LLM | 两层（本方案） |
|------|:----------:|:------:|:------------:|
| 送达可靠性 | ❌ 不可靠（v2 教训） | ✅ agent 管道可靠 | ✅ Layer 2 走 agent |
| Token 成本 | ✅ 零 | ❌ 每分钟烧 token | ✅ 零（Layer 1）+ 微小（Layer 2 只转发） |
| 逻辑复杂度 | ✅ 脚本可控 | ❌ LLM 不稳定 | ✅ 逻辑在脚本，LLM 仅转发 |
| 可测试性 | ✅ 脚本可单测 | ❌ 需 mock agent | ✅ Layer 1 独立可测 |

---

## 3. Layer 1：Data Collector

### 3.1 概述

- **文件**：`/root/.hermes/profiles/orchestrator/scripts/kanban_collector.py`
- **运行方式**：`no_agent` cron job，30s 间隔
- **职责**：从三个数据源采集原始数据，输出纯文本统计字符串
- **不负责**：消息投递、格式美化、生命周期决策

### 3.2 数据源

| 数据源 | 路径/来源 | 读取内容 | 用途 |
|--------|----------|---------|------|
| kanban.db | `/root/.hermes/kanban/boards/*/kanban.db` | 所有 board 的任务状态 | 四维统计 (📋/✅/🔄/⏳) |
| .oc_session.json | `/root/.hermes/profiles/orchestrator/scripts/.oc_session.json` | 会话状态、session_id | 判断是否播报 |
| cron.db | `/root/.hermes/profiles/orchestrator/cron.db` | OC 的 one-shot cron jobs | 下一轮启动时间 |

### 3.3 四维统计定义

产品已确认（见产品评估文档）：

```
📋 安排 = ready + running（排除 blocked，过滤僵尸任务）
✅ 跑完 = 本次 OC 会话启动后 status 变为 'done' 的任务（通过 completed_at >= session.started_at 判定）
🔄 在跑 = status = 'running' 的任务
⏳ 未跑 = status = 'ready' 且未被任何 agent claim 的任务
```

> **注意**：「安排」= ready + running，**不包含 blocked**。
> Blocked 任务往往是僵尸卡片（无人处理、长期阻塞），纳入「安排」会虚增工作量计数。
> 「跑完」通过 session 启动时间过滤，只显示本次会话期间完成的任务。
> 同时仅扫描 OC 当前项目的看板（通过 `.oc_session.json` 的 `project_boards` 字段识别，支持跨 board 项目），避免跨项目干扰。

### 3.4 输出格式

```
=== kanban_collector stdout ===
📋 安排8个 | ✅ 跑完5个 | 🔄 在跑3个 | ⏳ 未跑5个
🕐 OC 会话: abc123 | 已运行 23min | 下一轮: 15:00 启动
```

> 「安排」不包含 blocked 任务。如 3 个 blocked 僵尸任务，则不纳入计数。

无 session file 时：**stdout 为空（零输出）**。

### 3.5 伪代码

```python
#!/usr/bin/env python3
"""kanban_collector.py — Layer 1 of Watchdog v3.0"""

import json
import os
import sqlite3
import time
from pathlib import Path

# === 常量 ===
SESSION_FILE = Path("/root/.hermes/profiles/orchestrator/scripts/.oc_session.json")
KANBAN_DIR  = Path("/root/.hermes/kanban/boards")
CRON_DB     = Path("/root/.hermes/profiles/orchestrator/cron.db")

def read_session_state():
    """Read .oc_session.json. Returns dict or None if absent/stale."""
    if not SESSION_FILE.exists():
        return None
    try:
        with open(SESSION_FILE) as f:
            state = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

    # Stale 检测：超过 TTL（10 分钟无更新）视为无效
    ttl = state.get("max_age_seconds", 600)
    updated_at = state.get("updated_at", 0)
    if time.time() - updated_at > ttl:
        return None
    return state

def scan_all_boards(session=None):
    """Scan OC's current project kanban board, return aggregated task counts.

    仅扫描 OC 当前项目对应的 boards（通过 session state 中的 project_boards 字段识别）。
    未指定时回退到扫描所有 board。
    """
    stats = {"ready": 0, "running": 0, "blocked": 0, "done": 0, "archived": 0}
    session_started_at = 0
    project_boards = None

    if session:
        session_started_at = session.get("started_at", 0)
        project_boards = session.get("project_boards")

    for board_dir in KANBAN_DIR.iterdir():
        if not board_dir.is_dir():
            continue
        # 项目过滤：仅扫描 project_boards 中列出的 board
        if project_boards and board_dir.name not in project_boards:
            continue
        db_path = board_dir / "kanban.db"
        if not db_path.exists():
            continue
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            # 全局状态计数
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM tasks "
                "WHERE archived = 0 GROUP BY status"
            ).fetchall()
            for row in rows:
                key = row["status"]
                if key in stats:
                    stats[key] += row["cnt"]

            # 本次会话完成的计数
            if session_started_at > 0:
                done_in_session = conn.execute(
                    "SELECT COUNT(*) FROM tasks "
                    "WHERE status = 'done' AND completed_at >= ?",
                    (session_started_at,)
                ).fetchone()
                if done_in_session:
                    stats["_done_in_session"] = done_in_session[0]

        except sqlite3.Error:
            continue
        finally:
            if conn:
                conn.close()

    return stats

def read_next_cron():
    """Read OC profile's one-shot cron jobs for next run time."""
    if not CRON_DB.exists():
        return None
    try:
        conn = sqlite3.connect(str(CRON_DB))
        rows = conn.execute(
            "SELECT next_run_at FROM jobs "
            "WHERE repeat = 1 AND status = 'active' ORDER BY next_run_at LIMIT 1"
        ).fetchall()
        conn.close()
        if rows:
            return rows[0][0]
    except sqlite3.Error:
        pass
    return None

def build_output(stats, session, next_cron):
    """Format the four-dimension statistics string.

    「安排」= ready + running（排除 blocked，过滤僵尸任务）
    「跑完」= 本次会话启动后完成的
    「在跑」= running
    「未跑」= ready（未被 claim）
    """
    scheduled = stats.get("ready", 0) + stats.get("running", 0)
    done      = stats.get("_done_in_session", stats.get("done", 0))
    running   = stats.get("running", 0)
    pending   = stats.get("ready", 0)

    lines = []
    lines.append(f"📋 安排{scheduled}个 | ✅ 跑完{done}个 | 🔄 在跑{running}个 | ⏳ 未跑{pending}个")

    if session:
        session_id = session["session_id"]
        elapsed    = int((time.time() - session["started_at"]) / 60)
        lines.append(f"🕐 OC 会话: {session_id} | 已运行 {elapsed}min", end="")
        if next_cron:
            lines.append(f" | 下一轮: {next_cron} 启动")
        else:
            lines.append("")
    return "\n".join(lines)

def main():
    session = read_session_state()
    if not session:
        # 无活跃 OC 会话 → 空输出（触发 Layer 2 的静默逻辑）
        return

    stats     = scan_all_boards(session)
    next_cron = read_next_cron()
    output    = build_output(stats, session, next_cron)
    print(output)

if __name__ == "__main__":
    main()
```

---

## 4. Layer 2：LLM Reporter

### 4.1 概述

- **运行方式**：LLM-driven cron job，1min 间隔
- **context_from**：[collector job id] — 读取 Layer 1 的 stdout
- **职责**：判断是否有输出 → 转发或静默

### 4.2 行为逻辑

```
collector stdout 非空 → 直接输出原文到聊天（不修改、不总结）
collector stdout 为空:
    → 输出 "👋 无任务在跑，即将静默"
    → 调用 cronjob(action='remove', job_id='<self>') 删除自己
```

### 4.3 Prompt 设计

```
你是 watchdog reporter。读取 collector 的统计输出：

- 如果统计字符串非空：直接发送原文字符串到聊天（不要修改格式）
- 如果统计字符串为空：发送 "👋 无任务在跑，即将静默"，然后删除你自己的 cron job（job_id=<self>）
```

### 4.4 工具集

- 仅需 `send_message` 和 `cronjob` 工具
- **不需要** kanban 工具（数据已由 Layer 1 提供）

### 4.5 配置

```bash
# Layer 1: Collector cron (30s no_agent)
hermes --profile orchestrator cronjob create \
  --schedule "30s" \
  --script "kanban_collector.py" \
  --no_agent \
  --name "Watchdog Collector (30s)"

# Layer 2: Reporter cron (1min LLM, context_from collector)
hermes --profile orchestrator cronjob create \
  --schedule "1m" \
  --prompt "<reporter prompt>" \
  --context_from "<collector_job_id>" \
  --deliver "feishu:ou_c96ec83837f5d62e87f6b94289d1fdb8" \
  --enabled_toolsets ["messaging", "cron"] \
  --name "Watchdog Reporter (1min)"
```

---

## 5. OC Session State File 协议

### 5.1 文件规范

**路径**：`/root/.hermes/profiles/orchestrator/scripts/.oc_session.json`

**写入者**：OC（orchestrator profile，通过 SOUL.md 规则或 skill）
**读取者**：kanban_collector.py

### 5.2 格式

```json
{
  "session_id": "oc_20260710_143000",
  "started_at": 1750600200,
  "updated_at": 1750600260,
  "status": "active",
  "role": "orchestrating",
  "max_age_seconds": 600,
  "expected_children": 4,
  "completed_children": 2,
  "next_one_shot_at": 1750600800,
  "board_summary": "devPPL P0-15 修复",
  "project_boards": ["devPPL", "devPPL-infra"]
}
```

### 5.3 字段说明

| 字段 | 类型 | 必须 | 说明 |
|------|------|:---:|------|
| `session_id` | string | ✅ | 唯一会话标识符，格式 `oc_YYYYMMDD_HHMMSS` |
| `started_at` | int | ✅ | Unix timestamp，会话启动时间 |
| `updated_at` | int | ✅ | Unix timestamp，最后心跳时间（每次 touch 更新） |
| `status` | enum | ✅ | `active`/`draining`/`stopped` |
| `role` | string | 否 | `orchestrating`/`executing` |
| `max_age_seconds` | int | 否 | TTL，默认 600 |
| `expected_children` | int | 否 | 计划派发的子任务数 |
| `completed_children` | int | 否 | 已完成的子任务数 |
| `next_one_shot_at` | int | 否 | 下一个 OC one-shot cron 的启动时间 |
| `board_summary` | string | 否 | 当前工作内容简述 |
| `project_boards` | list[string] | 否 | OC 当前项目对应的 kanban board 名称列表（collector 仅扫描这些 board，支持跨 board 项目） |

### 5.4 生命周期

```
OC 启动
  ├── 原子写 .oc_session.json（写 .tmp → mv）
  │   status = "active", updated_at = now
  │
OC 运行中（每次子任务完成时）
  ├── touch: 更新 updated_at, completed_children
  │
OC 即将停止（所有子任务完成）
  ├── status = "draining", updated_at = now
  ├── 等待 1-2 个 reporter tick（让告别消息发出）
  ├── 删除 .oc_session.json
  │
异常：OC 崩溃
  ├── .oc_session.json 残留
  ├── collector 检测到 updated_at > TTL → 视为无效
  └── Layer 2 reporter 检测到 collector 空输出 → 告别 + 停止
```

### 5.5 TTL 策略

| 阶段 | TTL 值 | 原因 |
|------|:------:|------|
| 正常心跳 | OC 每 30s touch 一次 | updated_at 始终新鲜 |
| OC 崩溃 | > 10min 无 touch | collector 判定 session stale |
| OC draining | 2-3min | 最后一次 touch 足够 reporter 送别 |

---

## 6. OC 生命周期绑定

### 6.1 绑定模型

Watchdog 不自己决定何时启动/停止。生命周期完全由 OC 管理。

```
┌──────────────────────────────────────────────────────────┐
│                       OC Session                         │
│                                                          │
│  启动阶段：                                               │
│    1. 生成 session_id                                    │
│    2. 写 .oc_session.json（status=active）               │
│    3. 检查 watchdog reporter cron 是否存在               │
│       - 不存在 → 创建（幂等：用 idempotency_key）        │
│       - 存在但未运行 → 恢复（resume）                     │
│       - 存在且在运行 → 跳过                               │
│    4. 确保 watchdog collector cron 存在                  │
│                                                          │
│  运行阶段：                                               │
│    • 每次 fan-out/收集子任务 → touch .oc_session.json     │
│    • Collector 自行读取，Reporter 自行转发                │
│    • OC 不主动调用 watchdog                               │
│                                                          │
│  结束阶段：                                               │
│    1. 所有子任务 done/archived                            │
│    2. status = "draining" → touch                        │
│    3. 等待 2 个 collector tick（60s）                     │
│    4. 删除 .oc_session.json                              │
│    → Collector 下次 tick 输出为空                         │
│    → Reporter 检测到空 → 告别 → 删除自己                  │
│                                                          │
│  异常恢复（OC 重启）：                                     │
│    1. 检测到残留 .oc_session.json                         │
│       - 如果 status=draining → 直接清理                   │
│       - 如果 status=active 且 TTL 未过期 → 续用          │
│       - 如果 TTL 过期 → 清理 + 重新开始                   │
│    2. 检测到残留 watchdog reporter cron                  │
│       - 删除 + 重建（fresh start）                        │
└──────────────────────────────────────────────────────────┘
```

### 6.2 OC SOUL.md 集成规则（提议）

在 orchestrator 的 SOUL.md 中增加以下规则（或作为 `kanban-event-hooks` skill）：

```
### 6.2a Watchdog 生命周期规则（SOUL.md 集成）

### 会话启动
在开始分配 kanban 任务前：
1. 生成 session_id = "oc_" + 当前时间戳
2. 创建 .oc_session.json，status=active
3. 检查 watchdog reporter cron 是否存在
   - 不存在：创建（idempotency_key="watchdog-reporter-v3"）
4. 检查 watchdog collector cron 是否存在
   - 不存在：创建（idempotency_key="watchdog-collector-v3"）

### 任务分配后
每次 fan-out 或收集子任务结果后：
- 更新 .oc_session.json 的 updated_at, completed_children

### 会话结束
当所有子任务状态为 done 或 archived：
1. 更新 .oc_session.json: status="draining"
2. 等待 60 秒
3. 删除 .oc_session.json
```

### 6.3 幂等性保证

- Watchdog cron 创建使用 `idempotency_key="watchdog-reporter-v3"` / `"watchdog-collector-v3"`
- OC 每次启动做"存在性检查"而非无条件创建
- 避免 OC 多次重启产生僵尸 cron

---

## 7. 会话感知：时间线汇报

### 7.1 三个维度

Watchdog v3.0 汇报 OC 会话的三个信息维度：

```
A. OC 是否活跃？           → 通过 .oc_session.json 存在性 + TTL
B. OC 的任务统计           → 通过 kanban.db 四维统计
C. OC 的时间信息           → 通过 session started_at + cron.db next_run_at
```

### 7.2 输出示例

```
有活跃会话 + 有任务：
  📋 安排8个 | ✅ 跑完5个 | 🔄 在跑3个 | ⏳ 未跑5个
  （12 任务中 3 个 blocked → 不纳入「安排」）
  🕐 OC 会话: oc_20260710_143000 | 已运行 23min | 下一轮: 15:00 启动

有活跃会话 + 无任务（罕见，可能刚开始）：
  📋 安排0个 | ✅ 跑完0个 | 🔄 在跑0个 | ⏳ 未跑0个
  🕐 OC 会话: oc_20260710_143000 | 已运行 1min

无活跃会话 → collector 空输出 → reporter 发告别：
  👋 无任务在跑，即将静默

OC 心跳超时（stale session file）：
  📋 安排3个 | ✅ 跑完1个 | 🔄 在跑2个 | ⏳ 未跑1个
  ⚠️ OC 最后活动: 12 分钟前 — 可能已静默
```

### 7.3 下一轮启动时间

来源优先级：
1. `.oc_session.json` 的 `next_one_shot_at` 字段（OC 主动声明）
2. `cron.db` 的 one-shot jobs 的 `next_run_at`（collector 自行查询）
3. 如果两者都没有 → 不显示"下一轮"行

---

## 8. 状态机：极简二元模型

### 8.1 v2.0 状态机（将被删除）

```
ACTIVE → QUIET → SILENT → ACTIVE (via .kanban_resume)
   ▲       │        │          │
   └───────┴────────┴──────────┘
```

问题：v2.0 三态 FSM 维护复杂，且 watchdog 自己无法准确判断"何时应该静默"——
因为 watchdog 不知道任务创建者是 OC 还是 Frank。

### 8.2 v3.0 "状态机"（极简）

```
      有 session file    无 session file
      ─────────────      ──────────────
         REPORT              SILENT
         (播报)              (不播报)


没有中间过渡态。没有计数。
session file 存不存在 — OC 决定。watchdog 只读取。
```

### 8.3 等价关系

| v2.0 状态 | v3.0 等价 | 说明 |
|-----------|----------|------|
| ACTIVE | session file 存在 | OC 在跑 → 播报 |
| QUIET | ❌ 删除 | 不必要——session file 存在就报，不管有没有任务 |
| SILENT | session file 不存在 | OC 不在 → collector 空输出 → reporter 告别 + 停 |

### 8.4 清理的旧文件

| 文件 | 动作 |
|------|------|
| `.kanban_resume` | **删除** — session file 替代 |
| `.kanban_watchdog_meta.json` | **删除** — silent_ticks 不再需要 |
| `.kanban_state.json` | **删除** — 不再追踪逐任务状态变化 |
| `kanban_watchdog.py` | **废弃** — 由 kanban_collector.py 替代 |

---

## 9. 数据流

### 9.1 完整数据流

```
 OC writes            OC creates tasks          OC schedules
     │                      │                      │
     ▼                      ▼                      ▼
.oc_session.json        kanban.db              cron.db
     │                      │                      │
     └──────────────────────┼──────────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │  Collector (30s)        │
              │  read 3 sources          │
              │  → stats string          │
              └────────────┬────────────┘
                           │ stdout
                           ▼
              ┌─────────────────────────┐
              │  Reporter (1min)         │
              │  context_from: collector │
              │  → forward or goodbye    │
              └────────────┬────────────┘
                           │ hermes send
                           ▼
              ┌─────────────────────────┐
              │  Feishu                  │
              │  Frank 收到消息           │
              └─────────────────────────┘
```

### 9.2 时序图（正常流程）

```
Time    OC              Collector(30s)    Reporter(1min)     Frank
──────────────────────────────────────────────────────────────────
T+0     写 session
        创建 cron jobs
        fan-out tasks
T+30s                   读 → 有输出 ──────────────────→ "📋..."
T+60s                   读 → 有输出 ──────────────────→ "📋..."
T+90s                   读 → 有输出 ──────────────────→ "📋..."
...
T+N     OC 完成最后一个
        子任务
        status=draining
T+N+30s                 读 → 有输出 ──────────────────→ "📋..."
T+N+60s OC 删 session
T+N+90s                 读 → 空输出 ──────────────────→ "👋 静默"
                                                         (reporter 删自己)
T+N+120s                 (collector 仍运行但空输出)
                         (reporter 已不存在 → 无投递)
```

### 9.3 时序图（OC 崩溃恢复）

```
Time    OC              Collector(30s)    Reporter(1min)     Frank
──────────────────────────────────────────────────────────────────
T+0     写 session
T+30s                   读 → 有输出 ──────────────────→ "📋..."
T+60s                                                 ──→ "📋..."
T+70s   💥 OC 崩溃
        (session file 残留)
T+90s                   读 → 有输出 ──────────────────→ "📋..."
...
T+600s                  读 → TTL 过期              ──→ "📋..."
                        视为无效 → 空输出           ──→ "⚠️ OC 无响应"
...
T+900s  OC 重启
        清理残留 session
        写新 session
        删旧 cron + 重建
T+930s                  读 → 有输出 ──────────────────→ "📋..."
```

---

## 10. 边缘场景矩阵

| # | 场景 | 预期行为 | 保障机制 |
|---|------|---------|---------|
| E1 | OC 正常启动，有任务 | 1min 内 Frank 收到心跳 | Collector 30s 采集 + Reporter 1min 投递 |
| E2 | OC 正常停止 | Frank 收到 "即将静默" → 之后无消息 | OC draining → 删 session → collector 空 → reporter 告别 + 自删 |
| E3 | OC 崩溃（残留 session file） | TTL 过期后 → Frank 收到 "OC 无响应"，不再有心跳 | TTL + collector 检测 + reporter 告别 |
| E4 | OC 重启（清理旧状态） | 无缝恢复心跳，无重复 cron | OC 启动时清理 + 幂等创建 |
| E5 | 所有任务在 30s 内完成 | Collector 可能捕获不到 running 状态 | 可接受——Frank 看到的是趋势，不需要逐帧 |
| E6 | kanban.db 被锁 | 跳过本次 tick | try/except，下次 tick 重试 |
| E7 | cron.db 不可读 | 不显示 "下一轮" 行，其余正常 | 降级，不阻塞 |
| E8 | .oc_session.json 损坏 | 视为无 session → 空输出 → 告别 | json decode 异常捕获 |
| E9 | OC 忘记更新 session file | updated_at 过期 → TTL 触发 | 被动检测 |
| E10 | OC 忘记删除 cron jobs | Reporter 自删（告别消息中删除自己） | OC 启动时也会清理 |
| E11 | Frank 手动创建任务（非 OC） | 心跳中可见 📋 计数增长 | 全局扫描不区分创建者 |
| E12 | OC session file 不存在但 kanban 有任务 | collector 空输出 → reporter 静默 | 按设计：无 OC 会话 = 不播报 |

---

## 11. 风险与缓解

| # | 风险 | 概率 | 影响 | 缓解 |
|---|------|:---:|:---:|------|
| R1 | **OC 行为不可靠**：LLM agent 可能忘记创建/清理 session file 和 cron | 中 | 高 | Session file TTL 自动过期；Reporter 自删机制；OC SOUL.md 明确规则；启动时主动清理 |
| R2 | **Stale session file**：OC 崩溃后残留，watchdog 误报 OC 活跃 | 中 | 高 | TTL（max_age_seconds=600）；collector 检测超时 → 空输出；reporter 标注 "OC 无响应" |
| R3 | **僵尸 cron**：OC 重启未清理旧 cron | 中 | 中 | 幂等 idempotency_key；OC 启动时 list + remove；Reporter 自删 |
| R4 | **30s cron 粒度**：cron scheduler 可能跳过 tick | 低 | 低 | Reporter 1min 粒度保底；两个 tick 之间的差距对 Frank 不可见 |
| R5 | **SQLite 锁竞争**：30s 读 + OC 写同时 | 低 | 低 | try/except + 下次重试；可加 `PRAGMA journal_mode=WAL` |
| R6 | **多 OC 会话并存**（未来） | 极低 | 中 | 预留扩展：session state file 命名用 session_id 而非固定名 |

---

## 12. 实施计划

### 12.1 分阶段交付

产品建议 MVP + 完整版两步走，以下为完整版计划：

| 阶段 | 内容 | 工作量 | 产物 |
|------|------|:---:|------|
| **Phase 1: MVP** | Layer 1 collector 脚本 + Layer 2 reporter cron + 新输出格式 + 1min 间隔 | 0.5 人天 | `kanban_collector.py`、reporter cron |
| **Phase 2: OC 集成** | OC SOUL.md 规则 / skill + session state file 管理 | 0.3 人天 | OC 规则、集成测试 |
| **Phase 3: 会话感知** | cron.db 读取 + 下一轮时间显示 + TTL 逻辑 | 0.2 人天 | collector 增强 |
| **Phase 4: 清理 v2** | 删除旧脚本、旧状态文件、旧 cron jobs | 0.1 人天 | 清理脚本 |
| **Phase 5: 测试** | 集成测试 + 异常场景测试 | 0.3 人天 | 测试报告 |
| **合计** | | **1.4 人天** | |

### 12.2 MVP 最小可用版本

如果优先交付 MVP（Phase 1 only，不做生命周期绑定）：

- collector 一直运行（不依赖 session file）
- Frank 手动创建/删除 reporter cron
- 无 session 感知 → 不显示 "OC 会话: xxx" 行
- 输出格式同完整版

MVP 风险：Frank 需要手动管理 cron，体验不如完整版。

### 12.3 文件变更清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `/root/.hermes/profiles/orchestrator/scripts/kanban_collector.py` | **新建** | Layer 1 数据采集 |
| `/root/.hermes/profiles/orchestrator/scripts/.oc_session.json` | **运行时** | OC 写入，collector 读取 |
| `/root/.hermes/profiles/orchestrator/scripts/kanban_watchdog.py` | **废弃** | v2.0 脚本不再使用 |
| `/root/.hermes/profiles/orchestrator/scripts/.kanban_resume` | **删除** | 由 session file 替代 |
| `/root/.hermes/profiles/orchestrator/scripts/.kanban_watchdog_meta.json` | **删除** | silent_ticks 消除 |
| `/root/.hermes/profiles/orchestrator/scripts/.kanban_state.json` | **删除** | 逐任务追踪消除 |
| `/root/.hermes/profiles/orchestrator/SOUL.md` | **修改** | 增加 watchdog 生命周期规则 |
| `/root/.hermes/profiles/orchestrator/skills/kanban-event-hooks/SKILL.md` | **修改** | 增加 session state file 管理 |
| `tests/test_watchdog_smoke.py` | **重写** | 适配 v3.0 架构 |

---

## 13. 与 v2.0 的差异对照

| 维度 | v2.0 | v3.0 |
|------|------|------|
| **架构** | 1 层 no_agent 脚本 | 2 层：collector (no_agent) + reporter (LLM) |
| **数据源** | kanban.db 单一数据源 | kanban.db + .oc_session.json + cron.db |
| **触发** | 手动 resume/pause cron | 自动：session file 存在→播报，不存在→静默 |
| **状态机** | 三态 FSM (ACTIVE→QUIET→SILENT) | 二元：session 存在/不存在 |
| **输出** | 逐条任务列表 + 汇总行 | 四维聚合 `📋N|✅N|🔄N|⏳N` |
| **OC 感知** | 无 | OC session file + cron timing |
| **间隔** | 2 min | 1 min (collector 30s + reporter 1min) |
| **送达** | 不可靠（v2 教训） | 可靠（走 agent 管道） |
| **投递渠道** | 飞书 DM | 飞书 DM（不变） |
| **脚本行数** | ~203 行 | ~150 行 (collector) + prompt (reporter) |
| **状态文件** | 3 个 (.kanban_resume, .kanban_watchdog_meta, .kanban_state) | 1 个 (.oc_session.json) |
| **Token 成本** | 零 | 近乎零（LLM 仅转发 10-20 token） |
| **静默机制** | 脚本内部不输出 | OC 删 session → collector 空 → reporter 自停 |
| **测试复杂度** | 需模拟状态机转换 | 仅需测试 collector 输出正确性 |

---

## 14. 附录

### A. 需要产品确认的问题

以下问题在产品评估中已提出但尚未收到正式回复，需在实现前确认：

1. **「安排」「跑完」「在跑」「未跑」的精确定义**
   - 范围：仅 OC 创建的任务？还是看板上所有任务？
   - 「跑完」的时间窗口：本次 OC 会话期间？过去 N 分钟？
   - **当前设计假设**：全局范围（非仅 OC）；「跑完」= 会话启动后的 done

2. **OC 会话结束后的行为**
   - "无任务在跑，即将静默"之后，watchdog cron 是 pause 还是 deleted？
   - **当前设计假设**：reporter 自删（cronjob remove self）

3. **「下个 one-shot cron 何时启动」的显示位置**
   - 在心跳消息里内联？还是单独一行？
   - **当前设计假设**：内联在 OC 会话行

### B. 参考文档

| 文档 | 路径 | 角色 |
|------|------|------|
| v3 架构评估 | `docs/arch-p0-18-watchdog-v3-evaluation.md` | 前置分析 |
| v3 产品评估 | `docs/roundtables/watchdog-v3-product-evaluation.md` | 产品裁决 |
| v2 架构设计 | `tasks_watchdog/docs/architecture.md` | 旧版参考 |
| Watchdog PRD | `docs/prd-p0-18-watchdog.md` | 需求来源 |
| 项目上下文 | `tasks_watchdog/docs/context.md` | 历史背景 |
| v2 冒烟测试 | `tests/test_watchdog_smoke.py` | 需重写 |

### C. 关键配置

```yaml
# orchestrator profile
platforms:
  feishu:
    enabled: true

# Frank 的飞书 open_id
feishu_target: "ou_c96ec83837f5d62e87f6b94289d1fdb8"

# watchdog 文件位置
collector_script: "/root/.hermes/profiles/orchestrator/scripts/kanban_collector.py"
session_state:    "/root/.hermes/profiles/orchestrator/scripts/.oc_session.json"
kanban_db_glob:   "/root/.hermes/kanban/boards/*/kanban.db"
cron_db:          "/root/.hermes/profiles/orchestrator/cron.db"
```

---

> **结论**：v3.0 核心变化是架构范式转移——从「独立守护进程 + 三态状态机」变为「OC 会话驱动 + 两层数据管道」。架构更简洁，责任边界更清晰，但依赖 OC 行为可靠性。建议 MVP 先行验证核心管道，完整版再引入生命周期绑定。
