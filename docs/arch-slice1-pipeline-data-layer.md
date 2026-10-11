# Slice 1 架构设计 — 管线数据层（checkpoint + 合约引擎）

> 发言人：高见远（架构师） | 日期：2026-07-30 | 版本：v1.0
> 目标：产出 Slice 1 完整技术方案——pipeline_state.db v1 / 合约 JSONL v1 / state.py / autopilot.sh
> 输入：R5 三方统一报告（Product 613 行 / Architect 762 行 / Engineer 590 行）+ R4 Slice 分拆
> 规则：不含 branches 分支逻辑、不含 gate_roundtable、不含 fanout、不含错误回退（均属 Slice 2）

---

## 0. Slice 1 范围定义

### 0.1 做什么

```
checkpoint.py v1 + contracts JSONL(5步) + state.py(简化) + autopilot.sh(简化)
→ 演示: 一个任务从 dev → qa-exec → va → merge → close 线性跑通
```

| 组件 | 范围 | 不含（→Slice 2） |
|------|------|------------------|
| `pipeline/checkpoint.py` | pipeline_state.db 读写 + v1 schema | v2+ migration、verdict 字段 |
| `config/contracts.jsonl` | 5 步线性定义（dev/qa-exec/va/merge/close） | branches 数组、roundtable_type |
| `pipeline/state.py` | kanban→合约→checkpoint→下一 步判定 | 分支 engine、gate_roundtable、close 子步骤 |
| `scripts/autopilot.sh` | cron 2min 轮询 → 调 state.py → 转换 | 错误处理、回退、备份命令 |
| `pipeline/constants.py` | ProjectType 枚举 + 步骤名常量 | ROUNDTABLE 映射表 |
| `pipeline/config.py` | project_config 只读接口 | backup 策略查询 |
| `pipeline/init_project.py` | 一次性项目初始化 | — |

### 0.2 关键架构决策：project_config 放 Slice 1 还是 Slice 2？

**裁决：放 Slice 1。**

理由矩阵：

| 维度 | Slice 1 就建 | Slice 2 再建 |
|------|:-----------:|:-----------:|
| 实现成本 | +55 行（constants 20 + config 30 + init 15，checkpoint migration 已有） | 0 行（暂时硬编码） |
| 未来改造成本 | 0 | 需 v1→v2 migration + 改所有引用点（state.py / autopilot.sh / checkpoint.py），约 +20 行改造 |
| 数据依赖 | 无——checkpoint.py / state.py 都引用它 | 需要在所有调用点加 fallback 默认值 → 改完后删 fallback |
| 测试覆盖 | 可以在 Slice 1 就测 project_config 的读/初始化 | 推迟测试到 Slice 2，但影响面扩散到所有已写模块 |
| 架构整洁度 | 组件边界清晰：config.py 是单一数据源 | 硬编码散落 2 个文件（state.py + autopilot.sh），后续统一切换容易遗漏 |

**结论**：project_config 是一张 key-value 表，复杂度为零。现在建是 55 行一次性开销+0 未来改造成本；Slice 2 再建是 0 行现在+20 行改造+全组件回归风险。这是典型的「现在不建以后更贵」。

对于 Slice 1 线性流程，project_config 的实际作用仅限于：
- `state.py` 启动时读 `project_type` 确认自己在正确环境运行
- `autopilot.sh` 启动时读 `project_name` 写日志头

这两个调用在 Slice 1 即可实现，不需要等 Slice 2 的备份策略查询。

---

## 1. pipeline_state.db v1 schema

### 1.1 完整 DDL

```sql
PRAGMA journal_mode = WAL;
PRAGMA user_version = 1;  -- Slice 1 只含实际使用的字段

CREATE TABLE IF NOT EXISTS pipeline_steps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT NOT NULL,              -- kanban task ID (如 t_721e24b0)
    step_name       TEXT NOT NULL,              -- dev|qa-exec|va|merge|close
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending|running|done|failed|blocked
    artifact_paths  TEXT NOT NULL DEFAULT '[]', -- JSON array: ["spec.md", "branch"]
    started_at      TEXT,                       -- ISO 8601
    finished_at     TEXT,                       -- ISO 8601
    error_msg       TEXT,                       -- 失败原因（NULL = 无错误）
    retry_count     INTEGER NOT NULL DEFAULT 0,
    assigned_agent  TEXT,                       -- 执行者 profile name
    openspec_ref    TEXT,                       -- openspec 引用（如 AG-004）
    UNIQUE(task_id, step_name)
);

CREATE TABLE IF NOT EXISTS project_config (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
```

### 1.2 字段说明

| 字段 | 类型 | Slice 1 使用 | 说明 |
|------|------|:-----------:|------|
| `task_id` | TEXT | ✅ | 来自 kanban.db 的 task ID |
| `step_name` | TEXT | ✅ | 5 个枚举值之一 |
| `status` | TEXT | ✅ | `pending`→`running`→`done`/`failed` |
| `artifact_paths` | TEXT | ✅ | JSON array，存放每步产物路径 |
| `started_at` | TEXT | ✅ | ISO 8601，step 开始时写入 |
| `finished_at` | TEXT | ✅ | ISO 8601，step 完成时写入 |
| `error_msg` | TEXT | ✅ | 失败时记录原因 |
| `retry_count` | INTEGER | ✅ | 失败重试计数 |
| `assigned_agent` | TEXT | ✅ | 执行 agent 的 profile name |
| `openspec_ref` | TEXT | ✅ | openspec 引用 |

### 1.3 为什么 user_version = 1

遵循 YAGNI 原则：v1 schema 只包含 Slice 1 实际使用的 10 个字段。verdict/verdict_detail/contract_check_passed 在 Slice 1 中不参与任何逻辑，不应存在于 v1 表中。

SQLite 的 ALTER TABLE ADD COLUMN 是零风险操作——不重写表、不阻塞读（WAL 模式下）、不改变已有行的物理存储。到 Slice 2 时通过 `ALTER TABLE pipeline_steps ADD COLUMN verdict TEXT` 追加这三列，migration 脚本从 `user_version=1` 迁到 `user_version=2`。

保留三列为 NULL 的代价是 schema 清晰度下降——任何读 DDL 的人会困惑「verdict 这列到底用不用」。产品裁定「schema 的清晰度 > 省一条 ALTER 语句」，架构上同意这个判断。

### 1.4 project_config 表的预定义 key

```sql
-- 由 init_project.py 一次性写入：
INSERT OR REPLACE INTO project_config VALUES ('project_type', 'system_mechanism');
INSERT OR REPLACE INTO project_config VALUES ('project_name', 'devPPL');
INSERT OR REPLACE INTO project_config VALUES ('backup_script', '/workspace/hermes_backup_push.sh');
INSERT OR REPLACE INTO project_config VALUES ('notify_script', '/workspace/hermes_backup_notify.sh');
```

| key | value 枚举 | Slice 1 使用 |
|-----|----------|:-----------:|
| `project_type` | `system_mechanism` / `pure_product` / `hybrid` | ✅ 启动时验证 |
| `project_name` | 自由文本 | ✅ 日志标识 |
| `backup_script` | 文件路径 | — Slice 2 |
| `notify_script` | 文件路径 | — Slice 2 |

---

## 2. 合约 JSONL v1 schema

### 2.1 完整 JSONL（5 步，无 branches）

```jsonl
{"step":"dev","requires":[],"produces":["branch","code_changes"],"timeout_min":60,"pass_condition":"code changes committed to branch"}
{"step":"qa-exec","requires":["branch","code_changes"],"produces":["test_report.md"],"timeout_min":45,"pass_condition":"test_report.md 无 BLOCKER 发现"}
{"step":"va","requires":["test_report.md"],"produces":["va_report.md"],"timeout_min":20,"pass_condition":"va_report.md validates test_report.md meets all AC requirements"}
{"step":"merge","requires":["test_report.md"],"produces":["merge_commit"],"timeout_min":20,"pass_condition":"git merge 成功 + 无冲突"}
{"step":"close","requires":["merge_commit"],"produces":["gai_update"],"timeout_min":15,"pass_condition":"kanban complete + GAI 标记 done"}
```

### 2.2 字段定义（v1 子集）

| 字段 | 类型 | 必填 | 说明 | Slice 2 扩展 |
|------|------|:----:|------|-------------|
| `step` | string | ✅ | 步骤名（dev/qa-exec/va/merge/close） | +qa-d2, +qa-d1 |
| `requires` | [string] | ✅ | 前置 artifact 列表（空数组 = 无依赖） | 同 |
| `produces` | [string] | ✅ | 产出 artifact 列表 | 同 |
| `timeout_min` | int | ✅ | 超时（分钟），state.py 用于超时检测 | 同 |
| `pass_condition` | string | ✅ | 通过条件的自然语言描述（Slice 1 用于日志/注释） | branches 数组替代 |

### 2.3 与 R5 JSONL v2 的差异

| 维度 | v1 (Slice 1) | v2 (Slice 2, R5) |
|------|-------------|------------------|
| 步骤数 | 5 | 7 (+qa-d1, +qa-d2) |
| 分支逻辑 | 无（失败 → `failed` 状态停止） | 完整 branches 数组 engine |
| `branches` 字段 | 不存在 | 每步 2-7 个分支条件 |
| `pass_condition` | 字符串（人类可读） | 被 `branches[].on` 条件替代 |
| roundtable 触发 | 无 | gate_roundtable(type, reason) |

### 2.4 v1 中 pass_condition 的实际作用

在 Slice 1 中，`pass_condition` 是**文档性字段**——不在代码中做语义解析。state.py 的判定逻辑是二元的：步骤完成（`status='done'`）→ 推进到下一步；步骤失败（`status='failed'`）→ 停止管线。

pass_condition 写入日志和 checkpoint 的 verdict_detail 原样透传，供人类阅读和 Slice 2 的自动化校验参考。

---

## 3. state.py 核心逻辑

### 3.1 数据流图

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│  kanban.db    │────▶│  state.py    │────▶│ pipeline_state.db │
│ (task 状态)   │     │              │     │ (checkpoint 读写)  │
└──────────────┘     │  ① 读 kanban │     └──────────────────┘
                     │  ② 比对合约   │
┌──────────────┐     │  ③ 写 checkpoint│  ┌──────────────┐
│ contracts.   │────▶│  ④ 判定下一步  │──▶│ autopilot.sh  │
│ jsonl        │     │              │     │ (下一步指令)   │
└──────────────┘     └──────────────┘     └──────────────┘
```

### 3.2 函数接口

```python
# pipeline/state.py — Slice 1 核心逻辑 (~120 行)

import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pipeline.constants import ProjectType, STEP_NAMES, STEP_ORDER
from pipeline.config import get_project_config
from pipeline.checkpoint import CheckpointDB


def get_kanban_task_state(task_id: str) -> dict:
    """
    读 kanban.db，返回任务当前状态。
    
    Returns: {
        'task_id': 't_721e24b0',
        'status': 'running',       # kanban 状态
        'assignee': 'game-engine',
        'title': '...',
        'body': '...',
    }
    
    实现：调用 hermes kanban show --json <task_id>
    """
    ...


def load_contract(contract_path: str = "config/contracts.jsonl") -> list[dict]:
    """
    加载合约 JSONL，返回有序步骤列表。
    
    Returns: [
        {'step': 'dev', 'requires': [], 'produces': [...], ...},
        {'step': 'qa-d1', 'requires': [...], ...},
        ...
    ]
    """
    ...


def get_current_step(task_id: str, db: CheckpointDB) -> str | None:
    """
    查询 pipeline_state.db，返回当前进行中的步骤名。
    
    逻辑：
    1. SELECT * FROM pipeline_steps WHERE task_id=? ORDER BY id DESC
    2. 找到最后一个 status='done' 的步骤 → 下一步是合约中的下一个 step
    3. 如果最后一步 status='running' → 当前步骤就是它
    4. 如果无记录 → 当前步骤是合约中的第一个 step
    5. 如果所有步骤都 done → 返回 None（管线已完成）
    
    Returns: step_name | None
    """
    ...


def determine_next_step(
    current_step: str | None,
    contract: list[dict],
    kanban_state: dict,
) -> str | None:
    """
    根据当前步骤和 kanban 状态，判定下一步做什么。
    
    Slice 1 逻辑（简化版）：
    - current_step == None → 返回 contract[0].step（第一步）
    - current_step 的 status == 'done' → 返回 contract 中的下一个 step
    - current_step 的 status == 'running' → 返回 None（等待中）
    - current_step 的 status == 'failed' → 返回 None（停止，等人工介入）
    - 所有步骤 done → 返回 None（完成）
    
    Returns: next_step_name | None
    """
    ...


def write_checkpoint(
    task_id: str,
    step_name: str,
    status: str,
    db: CheckpointDB,
    artifact_paths: list[str] | None = None,
    error_msg: str | None = None,
    assigned_agent: str | None = None,
) -> None:
    """
    写入 checkpoint 到 pipeline_state.db。
    
    - 如果该 task_id + step_name 行已存在 → UPDATE
    - 如果不存在 → INSERT
    - status='running' 时自动写入 started_at
    - status='done'/'failed' 时自动写入 finished_at
    """
    ...


def advance_pipeline(task_id: str, db_path: str = "pipeline_state.db") -> dict:
    """
    autopilot 的主入口：推进管线一步。
    
    完整流程：
    1. 读合约 JSONL
    2. 读 pipeline_state.db 当前状态
    3. 读 kanban.db 任务状态
    4. 判定当前步骤 + 下一步
    5. 如果需要开始新步骤 → write_checkpoint(status='running')
    6. 如果最后一步 done → write_checkpoint(status='done') 并标记完成
    7. 返回 {action: 'start_step'|'wait'|'complete', step: ..., task_id: ...}
    
    Returns: {
        'action': 'start_step' | 'wait' | 'complete' | 'error',
        'step': 'dev' | None,
        'task_id': 't_721e24b0',
        'detail': '...'  # 人类可读描述
    }
    """
    ...
```

### 3.3 判定逻辑状态机（Slice 1 简化版）

```
                 ┌─────────┐
                 │  START  │
                 └────┬────┘
                      │
                      ▼
              ┌───────────────┐
              │ 读合约 JSONL    │
              │ 读 kanban 状态  │
              │ 读 checkpoint   │
              └───────┬───────┘
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ 第一步    │ │ 中间步   │ │ 末尾步   │
    │ (无记录)  │ │ status=  │ │ 全部done │
    │          │ │ running/ │ │          │
    │          │ │ done     │ │          │
    └────┬─────┘ └────┬─────┘ └────┬─────┘
         │            │            │
         ▼            ▼            ▼
    start_step    wait/         complete
    (dev)         advance       (管线结束)
```

### 3.4 关键设计决策

| 决策 | 方案 | 理由 |
|------|------|------|
| 超时检测 | Slice 1 做简化版：检测→failed→停止 | 不涉及 retry/block/rollback——那是 Slice 2 branches engine 的职责。实现为只读检查 `finished_at - started_at > timeout_min` |
| 并发安全 | 依赖 autopilot.sh 的 flock 锁 | state.py 不自己做锁——单一 cron 进程保证不并发 |
| 状态写入 | UPSERT（INSERT OR REPLACE） | UNIQUE(task_id, step_name) 约束保证幂等 |
| 合约加载 | 每次调用都读 JSONL 文件 | 文件小（~1KB），不需要缓存；保证合约热更新 |
| kanban 查询 | `hermes kanban show --json` | 通过 subprocess 调用 CLI（已由 kanban_helpers.py 验证可用） |

---

## 4. autopilot.sh 核心逻辑

### 4.1 整体结构

```bash
#!/bin/bash
# scripts/autopilot.sh — Slice 1 核心轮询脚本
#
# 用法（由 cron 每 2 分钟调用）:
#   */2 * * * * /workspace/devPPL/scripts/autopilot.sh
#
# Slice 1 逻辑:
#   1. flock 获取互斥锁
#   2. 加载项目配置
#   3. 扫描活跃的 kanban 任务
#   4. 对每个任务调 state.py advance_pipeline
#   5. 根据 state.py 返回的 action 决定下一步
#   6. 释放锁

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCKFILE="/tmp/autopilot.lock"
LOG_TAG="[autopilot]"

# ── 互斥锁 ──
exec 200>"$LOCKFILE"
if ! flock -n 200; then
    echo "$LOG_TAG 另一 autopilot 实例正在运行，跳过本轮" >&2
    exit 0
fi

# ── 项目配置 ──
PROJECT_TYPE=$(python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT')
from pipeline.config import get_project_config
print(get_project_config()['project_type'])
")
PROJECT_NAME=$(python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT')
from pipeline.config import get_project_config
print(get_project_config()['project_name'])
")

echo "$LOG_TAG === 开始轮询: $PROJECT_NAME ($PROJECT_TYPE) ==="

# ── 扫描活跃任务 ──
# 从 pipeline_state.db 找出有 pending/running 步骤的任务
ACTIVE_TASKS=$(python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT')
from pipeline.checkpoint import CheckpointDB
db = CheckpointDB('$REPO_ROOT/pipeline_state.db')
tasks = db.get_active_tasks()
for t in tasks:
    print(t)
")

# ── 对每个活跃任务推进 ──
for TASK_ID in $ACTIVE_TASKS; do
    echo "$LOG_TAG 处理任务: $TASK_ID"
    
    RESULT=$(python3 -c "
import sys, json; sys.path.insert(0, '$REPO_ROOT')
from pipeline.state import advance_pipeline
result = advance_pipeline('$TASK_ID', '$REPO_ROOT/pipeline_state.db')
print(json.dumps(result))
")
    
    ACTION=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['action'])")
    STEP=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('step',''))")
    
    case "$ACTION" in
        start_step)
            echo "$LOG_TAG $TASK_ID: 开始步骤 $STEP"
            ;;
        wait)
            echo "$LOG_TAG $TASK_ID: 等待中（步骤 $STEP）"
            ;;
        complete)
            echo "$LOG_TAG $TASK_ID: 管线全部完成 ✅"
            ;;
        error)
            echo "$LOG_TAG $TASK_ID: 错误，停止推进 ❌"
            ;;
    esac
done

echo "$LOG_TAG === 轮询结束 ==="

# ── 释放锁（脚本退出时自动）──
flock -u 200
```

### 4.2 Cron 配置

```cron
# devPPL 管线 autopilot — 每 2 分钟轮询一次
# 部署命令：
#   crontab -e  # 添加下行
*/2 * * * * cd /workspace/devPPL && bash scripts/autopilot.sh >> logs/autopilot.log 2>&1
```

### 4.3 关键设计决策

| 决策 | 方案 | 理由 |
|------|------|------|
| 锁机制 | `flock` 文件锁 | 内核级，进程退出自动释放，比 PID 文件可靠 |
| 配置读取 | `python3 -c` 内联 import | 避免 shell 层复制 Python 逻辑；autopilot.sh 保持薄层 |
| 任务发现 | 通过 checkpoint.py `get_active_tasks()` | 而非遍历 kanban.db——管线状态在 pipeline_state.db |
| 错误处理 | Slice 1 记录日志后继续下一个任务 | Slice 2 加 retry + block 逻辑 |
| Cron 频率 | 2 分钟 | 与 R4 Engineer §3.1 一致；够快但不浪费 |

---

## 5. 组件间接口契约

### 5.1 文件间依赖图

```
pipeline/constants.py          ← 零依赖（纯枚举常量）
       │
       ▼
pipeline/checkpoint.py         ← 依赖 sqlite3（标准库）
       │
       ▼
pipeline/config.py             ← 依赖 checkpoint.py（读 pipeline_state.db）
       │
       ▼
pipeline/state.py              ← 依赖 constants + config + checkpoint
       │                           + subprocess（调 hermes kanban）
       ▼
scripts/autopilot.sh           ← 依赖 state.py + config.py（通过 python3 -c）
                                    + flock（系统工具）

pipeline/init_project.py       ← 依赖 checkpoint.py（写 pipeline_state.db）
                                    + constants.py（枚举值）
                                    → 由 OC 手动调用一次，不在 cron 中
```

### 5.2 数据流向

```
初始部署:
  OC 手动执行 → init_project.py → pipeline_state.db (project_config 表已填充)

日常运行:
  cron → autopilot.sh → state.py.advance_pipeline()
                            │
                            ├── 读: config/contracts.jsonl
                            ├── 读: pipeline_state.db (checkpoint)
                            ├── 读: kanban.db (via hermes kanban show)
                            └── 写: pipeline_state.db (checkpoint)
```

### 5.3 外部系统交互

| 外部系统 | 交互方式 | 读/写 | 说明 |
|---------|---------|:----:|------|
| `kanban.db` | `hermes kanban show --json` | 只读 | 获取任务状态、assignee |
| `hermes kanban` CLI | subprocess | 只读 | 通过 kanban_helpers.py 的 `_run_hermes` 模式 |
| `.hermes.md` | 文件系统 | 不交互 | Slice 1 不修改 .hermes.md（那是 DPL-011 / Slice 3） |
| `close.sh` | 文件系统 | 不交互 | Slice 1 的 close 步骤仅做 kanban complete，不调 close.sh |
| `hermes_backup_push.sh` | 文件系统 | 不交互 | Slice 2（merge/close 备份） |

---

## 6. pipeline/ 目录结构

```
pipeline/
├── __init__.py           # 空文件，使 pipeline/ 成为 Python package
├── constants.py          # ~25 行：ProjectType 枚举 + STEP_NAMES/STEP_ORDER
├── checkpoint.py         # ~120 行：CheckpointDB 类 + schema 创建 + CRUD
├── config.py             # ~30 行：get_project_config() 只读接口
├── state.py              # ~120 行：advance_pipeline() + 辅助函数
└── init_project.py       # ~25 行：argparse CLI，初始化 pipeline_state.db
```

**约 320 行 Python**（非精确，含文档字符串和空行）。

### 6.1 __init__.py

```python
# pipeline/__init__.py
# 使 pipeline/ 成为 Python package，支持 from pipeline.xxx import yyy
```

### 6.2 constants.py（~25 行）

```python
"""pipeline/constants.py — 枚举与常量"""

from enum import StrEnum

class ProjectType(StrEnum):
    SYSTEM_MECHANISM = "system_mechanism"
    PURE_PRODUCT     = "pure_product"
    HYBRID           = "hybrid"

# 5 步管线顺序（Slice 1）
STEP_NAMES = ["dev", "qa-exec", "va", "merge", "close"]
STEP_ORDER = {name: i for i, name in enumerate(STEP_NAMES)}
```

### 6.3 init_project.py（~25 行）

```python
"""pipeline/init_project.py — 一次性项目初始化

用法：
    python3 pipeline/init_project.py --project-type system_mechanism [--project-name devPPL]

由 OC 在项目创建后手动执行一次，写入 pipeline_state.db 的 project_config 表。
autopilot 不调用此脚本——它只读 project_config。
"""

import argparse
import sys
from pathlib import Path

from pipeline.checkpoint import CheckpointDB
from pipeline.constants import ProjectType


def main():
    parser = argparse.ArgumentParser(description="初始化 pipeline_state.db")
    parser.add_argument("--project-type", required=True,
                        choices=[t.value for t in ProjectType],
                        help="项目类型")
    parser.add_argument("--project-name", default="devPPL",
                        help="项目名称")
    parser.add_argument("--backup-script", default="/workspace/hermes_backup_push.sh")
    parser.add_argument("--notify-script", default="/workspace/hermes_backup_notify.sh")
    parser.add_argument("--db-path", default="pipeline_state.db")
    args = parser.parse_args()

    db = CheckpointDB(args.db_path)
    db.ensure_schema()
    config = {
        "project_type": args.project_type,
        "project_name": args.project_name,
        "backup_script": args.backup_script,
        "notify_script": args.notify_script,
    }
    db.write_project_config(config)
    print(f"[init_project] pipeline_state.db 已初始化")
    print(f"  project_type: {args.project_type}")
    print(f"  project_name: {args.project_name}")


if __name__ == "__main__":
    main()
```

---

## 7. 不做的事（架构边界）

| 项目 | 归属 | 理由 |
|------|:----:|------|
| branches 分支 engine | Slice 2 | 需要 JSONL v2 的 branches 数组 + state.py 的分支判定器 |
| gate_roundtable 分发 | Slice 2 | 需要 ROUNDTABLE_ASSIGNEES/WORKFLOWS 映射表 + kanban_create/block |
| fanout 并行执行 | Slice 2 | 需要 fanout.py + join-point 检测 |
| rollback / retry 逻辑 | Slice 2 | Slice 1 的失败策略是「停止，等待人工」 |
| close 子步骤展开 | Slice 2 | Slice 1 的 close = kanban complete（单步原子操作） |
| 备份推送 | Slice 2 | 需要 backup_strategy 查询 + hermes_backup_push.sh 调用 |
| close.sh 最终验证 | Slice 2 | close.sh 的调用点在 close-6 之后，不在 Slice 1 范围 |
| DPL-011 boot_context | Slice 3 | .hermes.md 动态段的生成和注入 |
| dashboard 红绿灯 | Slice 3 | 读 pipeline_state.db 的可视化面板 |
| qa-d1 / va 步骤 | Slice 2 | qa-d1 需 fan-out（Slice 2）；va 已在 Slice 1 实现 |

---

## 8. 增量工作量估算

| 文件 | 类型 | 行数 | 时间 | 说明 |
|------|------|:----:|:----:|------|
| `pipeline/__init__.py` | 新增 | ~2 | 0.05h | 空文件 |
| `pipeline/constants.py` | 新增 | ~25 | 0.3h | ProjectType + STEP_NAMES/STEP_ORDER |
| `pipeline/checkpoint.py` | 新增 | ~120 | 2.0h | SQLite schema + CRUD + get_active_tasks |
| `pipeline/config.py` | 新增 | ~30 | 0.5h | get_project_config() 只读接口 |
| `pipeline/state.py` | 新增 | ~120 | 2.0h | advance_pipeline() + kanban 状态读取 + 合约加载 |
| `pipeline/init_project.py` | 新增 | ~25 | 0.3h | argparse CLI + 写 project_config |
| `config/contracts.jsonl` | 新增 | ~5 | 0.2h | 5 步线性定义 |
| `scripts/autopilot.sh` | 新增 | ~60 | 1.0h | flock + cron 轮询 + 调用 state.py |
| `scripts/lib/kanban_helpers.py` | 修改 | +5 | 0.1h | 确认 `_run_hermes()` 可在 pipeline/ 中被 import |
| **Slice 1 总计** | | **~392 行** | **~6.5h** | |

**与 R4 Engineer §3 的 Slice 1 估算（3.5h）的差异**：R4 估算不含 project_config 三件套（constants + config + init_project ≈ 80 行 / 1.1h），也不含 autopilot.sh 的 flock 锁逻辑和项目配置读取（+~20 行 / 0.3h）。加上 project_config 后，Slice 1 从 3.5h → ~6.5h 是合理的。

**但**：checkpoint.py 和 state.py 是我从架构角度估算的上界（含完整错误检查和边界条件）。Engineer 实际编码可能更紧凑，实际工作量的下限约为 4.5h。

---

## 9. 技术风险点

| # | 风险 | 级别 | 缓解 |
|---|------|:----:|------|
| 1 | `hermes kanban show --json` 的实际输出格式可能与预期不符 | MINOR | 先在终端验证输出格式，再写解析逻辑 |
| 2 | autopilot.sh 中 `python3 -c` 内联 import 的路径问题 | MINOR | `sys.path.insert(0, repo_root)` 保证可靠 |
| 3 | pipeline_state.db 的 WAL 模式在 cron 环境下可能不生效 | MINOR | PRAGMA journal_mode=WAL 在 ensure_schema() 中显式设置 |
| 4 | 合约 JSONL 变更后的热加载 | — | 每次调用都读文件（~1KB），天然支持热更新 |
| 5 | kanban_helpers.py 的 `_run_hermes()` 是模块私有函数 | MINOR | 在 kanban_helpers.py 中添加 `run_hermes()` 公开函数，或 state.py 自己调 subprocess |

---

## 10. 一句话总结

> Slice 1 做的是「把管线跑起来」——5 步线性流程 + checkpoint 记录 + autopilot 自动推进。没有分支、没有回退、没有 roundtable。project_config 现在建比以后建便宜，所以建在 Slice 1。约 390 行 Python+Shell+JSONL，4.5-6.5 小时。每个函数的输入输出和边界条件都明确了，Engineer 可以直接按 §3（state.py）+ §4（autopilot.sh）+ §1（schema）+ §6（目录结构）写代码。

---

> 架构师发言完毕。下一站：engineer（寇豆码），请按 Slice 1 Step 2 开始编码实现。
