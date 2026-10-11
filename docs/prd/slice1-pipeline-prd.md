# Slice 1 PRD — 管线数据层：checkpoint + 合约引擎 + 简化 autopilot

|> 作者：许清楚（产品负责人） | 日期：2026-07-30 | 版本：v1.1
|> 来源：DPL-012 R5 最终统一工作流 → Slice 1（3.5h）
|> 修订 v1.1：D1 裁定后——project_config 表纳入 Slice 1（采纳架构建议），其余 3 项冲突消除（架构已自行与 PRD 对齐）

---

## 0. Slice 1 在整体架构中的定位

DPL-012 最终按三 Slice 分批交付：

```
Slice 1 (3.5h): checkpoint + 5 步合约 + 简化 autopilot    ← 本 PRD
Slice 2 (3.5h): 完整 7 步 + 21 分支 + 回退
Slice 3 (~10h):  DPL-011 + dashboard + watchdog + ABCD 类型 + 备份 + S6 闭环
```

**Slice 1 的产品目标**：建立最小可行管线——能追踪 5 个步骤的状态，能用合约定义每步的输入输出，能用 cron 驱动的 autopilot 在步骤间自动推进。不包含分支路由、不包含回退、不包含 fan-out。这些在 Slice 2/3 中逐步叠加。

**为什么先做 5 步而不是 7 步**：qa-d1（测试方案评审）和 qa-d2（测试报告评审）需要与 fan-out + 条件路由联动（dev 和 qa-d1 并行启动，qa-d2 失败需 rollback 到 dev）。在 Slice 1 引入这两个步骤会把整个分支引擎拖进来，违背"最小可行"原则。qa-exec（测试执行）是纯粹的线性步骤，适合 Slice 1。

---

## 1. Checkpoint：pipeline_state.db v1

### 1.1 什么任务需要 checkpoint

**所有通过管线流转的 kanban 开发任务**都需要 checkpoint。具体判定：

| 触发特征 | 需要 checkpoint？ | 理由 |
|---------|:---:|------|
| Frank 说"做 X"（明确开发任务） | ✅ | 走标准管线 |
| OC 创建 kanban card（含 spec） | ✅ | 同上 |
| Roundtable 任务（A/B/C/D 类） | ❌ | 不走管线流转，autopilot 不推进 |
| 手动运维任务 | ❌ | 不在管线范围内 |

**一句话**：autopilot 看到新的 kanban card 时，先查 pipeline_state.db——如果 task_id 不在库中，插入初始行（step='dev', status='pending'）；如果已在库中，按状态推进。

### 1.2 状态存什么

**pipeline_steps 表（v1 schema）**：

```sql
-- pipeline/checkpoint.py 创建（首次运行时自动 migration）
PRAGMA user_version = 1;

CREATE TABLE IF NOT EXISTS pipeline_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,          -- kanban task id（如 t_3831c640）
    step_name TEXT NOT NULL,         -- dev | qa-exec | va | merge | close
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | running | done | failed
    artifact_paths TEXT DEFAULT '[]',   -- JSON array，每步产出的文件路径
    started_at TEXT,                    -- ISO 8601
    finished_at TEXT,                   -- ISO 8601
    error_msg TEXT,                     -- 失败原因
    retry_count INTEGER DEFAULT 0,      -- 本步重试次数
    assigned_agent TEXT,                -- 执行此步骤的 agent profile
    UNIQUE(task_id, step_name)
);
```

**字段设计理由**：

| 字段 | 为什么需要 | 谁写 | 谁读 |
|------|-----------|---|-----|
| task_id + step_name（唯一约束） | 一个 task 在每个步骤只有一条记录 | autopilot（插入） | autopilot, dashboard |
| status | autopilot 判定"当前在哪一步、下一步是什么"的核心字段 | autopilot（更新） | autopilot |
| artifact_paths | 合约校验的依据——下一步 requires 的前一步 produces 是否在磁盘上存在 | autopilot/checkpoint | state.py（合约校验） |
| started_at / finished_at | 超时检测 + SLA 计算 | autopilot | dashboard, watchdog |
| error_msg | 失败时记录原因，供 OC 和 Frank 查看 | autopilot | dashboard, OC |
| retry_count | 防止无限重试——超过阈值后 block 而非继续重试 | autopilot | autopilot |
| assigned_agent | 记录"谁在执行"，便于排查和角色追踪 | autopilot | OC |

**v1 故意不包含的字段**（在 Slice 2/3 加入）：
- `verdict` — 多值判定（pass/fail/FALSIFIED/conditional_pass 等），Slice 1 只有 pass/fail
- `verdict_detail` — JSON 子步骤详情，Slice 1 不需要
- `contract_check_passed` — 合约校验结果，Slice 1 不做合约校验（只做超时+artifact存在性检查）

>  **D1 裁定修订（v1.1）**：pipeline_state.db v1 新增 `project_config` 表（key-value 结构），由 `init_project.py` 可选初始化。详见架构设计 §1.1。若未初始化 project_config，系统以硬编码默认值降级运行。

### 1.3 谁读谁写

```
pipeline_state.db 的访问矩阵：

  写入者（唯一）：
    autopilot.sh ──调用──→ checkpoint.py ──写──→ pipeline_state.db

  读取者：
    autopilot.sh ──读──→ pipeline_state.db（判定当前步骤）
    dashboard.py ──读──→ pipeline_state.db（未来 Slice 3）
    watchdog ──读──→ pipeline_state.db（未来 Slice 3）

  初始化：
    checkpoint.py 首次运行时自动建表（幂等 migration）
```

**为什么只有 autopilot 写**：pipeline_state.db 是管线推进的唯一权威状态源。如果有多个写入者（OC、QA、autopilot 都可以直接写），会出现竞态——OC 标记 step done 的同时 autopilot 启动下一步，状态不一致。单一写入者消除这个风险。

### 1.4 状态转移图

```
         OC 创建 kanban task
                │
                ▼
         ┌──────────┐
         │  pending  │  ← 初始状态（autopilot 检测到新 task 后插入）
         └────┬─────┘
              │ autopilot 创建 kanban card → 分配给 agent
              ▼
         ┌──────────┐
         │  running  │  ← agent 执行中
         └────┬─────┘
              │ agent 完成（kanban task 变为 done）
              ▼
         ┌──────────┐
         │   done    │  ← autopilot 验证 produces 存在 → 推进下一步
         └──────────┘

         异常路径：
         ┌──────────┐
    ┌───→│  failed  │  ← agent 失败 / 超时
    │    └────┬─────┘
    │         │ retry（retry_count < max）
    │         ▼
    │    ┌──────────┐
    └────│  running  │  ← 重新分配
         └──────────┘
              │ retry 耗尽（retry_count >= max）
              ▼
         ┌──────────┐
         │  failed   │  → autopilot 发 kanban_comment 告警 → 停止
         └──────────┘
```

---

## 2. 5 步合约 JSONL

### 2.1 哪 5 步

```
dev → qa-exec → va → merge → close
 1      2       3      4       5
```

| 步骤 | 执行者 | 做什么 | 输入（requires） | 输出（produces） |
|------|--------|--------|-----------------|-----------------|
| **dev** | game-engine profile | 根据 spec 写代码 | `spec.md`（从 kanban card body 或 OpenSpec 获取） | `branch` + `code_changes` |
| **qa-exec** | game-qa profile | 执行测试 | `branch` + `code_changes`（dev 的 produces） | `test_report.md` |
| **va** | verifier agent | 独立验证 | `test_report.md` | `va_report.md` |
| **merge** | autopilot / OC | 合并分支 | `va_report.md` + `test_report.md` | `merge_commit` |
| **close** | autopilot | 关闭任务 | `merge_commit` | `gai_update` + `kanban_closed` |

**qa-exec 不拆成 qa-d1 + qa-exec + qa-d2**：qa-d1（测试方案评审）和 qa-d2（测试报告评审）需要条件路由和 rollback（Sl 2）。Slice 1 的 qa-exec 是原子操作——QA 拿到代码 → 执行测试 → 产出报告。测试方案的审核和报告的评审在 Slice 2 中通过条件路由自然引入。

**close 不展开为 7 个子步骤**：close 在 Slice 1 是原子操作——autopilot 执行 `hermes kanban complete` → 标记 step='close', status='done'。7 个子步骤（S6 检测、GAI 更新、manifest 更新、备份推送、通知、归档）在 Slice 3 中引入。

### 2.2 每步的合约：输入 / 输出 / 通过条件

```jsonl
{"step":"dev","requires":["spec.md"],"produces":["branch","code_changes"],"timeout_min":60}
{"step":"qa-exec","requires":["branch","code_changes"],"produces":["test_report.md"],"timeout_min":45}
{"step":"va","requires":["test_report.md"],"produces":["va_report.md"],"timeout_min":30}
{"step":"merge","requires":["va_report.md","test_report.md"],"produces":["merge_commit"],"timeout_min":20}
{"step":"close","requires":["merge_commit"],"produces":["gai_update","kanban_closed"],"timeout_min":10}
```

**合约字段说明（Sl 1 精简版）**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `step` | string | ✅ | 步骤名 |
| `requires` | [string] | ✅ | 前置 artifact（前一步 produces 的子集） |
| `produces` | [string] | ✅ | 本步骤产出的 artifact |
| `timeout_min` | int | ✅ | 超时（分钟） |

**Slice 1 故意不包含 `branches` 字段**。分支路由（retry/block/rollback/gate_roundtable）在 Slice 2 引入。Sl 1 的异常处理遵循简化规则：

| 场景 | Slice 1 行为 |
|------|-------------|
| 步骤超时 | autopilot 记录 error_msg + status='failed' → 发 kanban_comment 告警 → **停止**（不重试） |
| requires 缺失 | autopilot 检查 produces 文件是否存在 → 不存在则停止，记录 error_msg |
| kanban task 失败 | autopilot 检测到 kanban task status 为 failed → 标记 checkpoint status='failed' → 停止 |

### 2.3 JSONL 文件位置与格式规范

- **位置**：`config/contracts.jsonl`
- **格式**：每行一个 JSON 对象，无尾逗号，UTF-8 编码
- **读取方式**：`state.py` 或 `autopilot.sh`（通过 `python3 -c` 或 import）按行读取，以 `step` 字段为 key 建立索引
- **扩展性**：Slice 2 会在每行追加 `branches` 字段，但不改变已有字段的结构

### 2.4 合约校验（Slice 1 简化版）

autopilot 在推进下一步前做最小校验：

```
推进前检查逻辑（伪代码）：
  1. 读当前步骤的合约（contracts.jsonl）
  2. 检查 produces 列表中的文件是否在磁盘上存在
     → 不存在：status='failed', error_msg="missing produces: {file}"
     → 存在：推进到下一步，更新 checkpoint
  3. 不检查超时（超时由 cron 轮询自然检测——started_at + timeout_min < now）
```

**Slice 1 不做**：
- 不检查 contract_violation（如 dev 产出的代码不符合 spec——那是 Slice 2 QA 的职责）
- 不检查 artifact 内容（如 test_report.md 是否包含必要章节——那是 Slice 2 qa-d1/d2 的职责）
- 不做 rollback（Slice 2）

---

## 3. 简化 autopilot.sh

### 3.1 核心循环

```
cron 每 2 分钟触发一次：

  1. flock 获取锁（防止同一 cron tick 并发执行）
  2. 读 kanban 状态（kanban_helpers.py 提供接口）
     → 找出所有 status=running 的任务
  3. 对每个 running 任务：
     a. 读 pipeline_state.db → 当前在哪一步？status 是什么？
     b. IF 当前步 status='done' → 推进到下一步
        - 验证下一步的 requires 是否满足
        - 创建新的 kanban card（分配给 agent）或跳过 close 步（autopilot 自己执行）
        - 更新 pipeline_state.db：插入新步骤行（status='pending' or 'running'）
     c. IF 当前步 status='running' → 检查 kanban task 是否完成
        - 已完成 → 验证 produces 文件 → status='done', finished_at=now
        - 失败 → status='failed', error_msg=kanban 返回的错误
        - 超时 → status='failed', error_msg="timeout: {timeout_min} min"
     d. IF 当前步 status='failed' → 跳过（不重试），发 kanban_comment 告警
  4. 释放锁
```

### 3.2 步骤推进的线性逻辑

```
dev done?
  ↓ YES → 推进到 qa-exec
qa-exec done?
  ↓ YES → 推进到 va
va done?
  ↓ YES → 推进到 merge
merge done?
  ↓ YES → 推进到 close
close done?
  ↓ YES → 全部完成 ✅
```

**没有条件分支**：dev 成功后一定进入 qa-exec，不跳步，不并行，不回退。每一步的"推进到下一步"是自动的——autopilot 检测到当前步 done 后立即创建下一步的 kanban card。

### 3.3 各步骤的 autopilot 行为

| 步骤 | autopilot 做什么 | 创建什么 |
|------|-----------------|---------|
| **dev** | 检测到新 task → 创建 kanban card（assignee=game-engine） | `hermes kanban create --assignee game-engine` |
| **qa-exec** | dev done → 创建 kanban card（assignee=game-qa） | `hermes kanban create --assignee game-qa` |
| **va** | qa-exec done → 创建 kanban card（assignee=verifier agent） | `hermes kanban create --assignee <va-profile>` |
| **merge** | va done → 执行 git merge | 不创建 kanban card（autopilot 自己执行） |
| **close** | merge done → `hermes kanban complete` | 不创建 kanban card（autopilot 自己执行） |

**merge 和 close 不创建 kanban card**：这两个步骤是 autopilot 的自动化操作，不需要 agent 介入。merge 由 autopilot 直接执行 `git merge`；close 由 autopilot 直接调用 `hermes kanban complete`。

### 3.4 autopilot.sh 伪代码

```bash
#!/bin/bash
# scripts/autopilot.sh — Slice 1 简化版
# cron: */2 * * * * cd /workspace/devPPL && bash scripts/autopilot.sh

set -euo pipefail
LOCKFILE="/tmp/autopilot.lock"
DB="pipeline_state.db"

# ── 获取锁 ──
exec 200>"$LOCKFILE"
if ! flock -n 200; then
    echo "[autopilot] 上一轮未完成，跳过"
    exit 0
fi

# ── 读合约 ──
CONTRACTS=$(python3 -c "
import json
contracts = {}
with open('config/contracts.jsonl') as f:
    for line in f:
        c = json.loads(line.strip())
        contracts[c['step']] = c
print(json.dumps(contracts))
")

# ── 获取 running 任务 ──
TASKS=$(python3 -c "
import sys
sys.path.insert(0, 'scripts/lib')
from kanban_helpers import get_running_tasks
tasks = get_running_tasks()
for t in tasks:
    print(t['id'])
")

if [ -z "$TASKS" ]; then
    echo "[autopilot] 无 running 任务"
    exit 0
fi

# ── 主循环 ──
STEP_ORDER=("dev" "qa-exec" "va" "merge" "close")
NEXT_STEP_INDEX_AFTER=("qa-exec" "va" "merge" "close" "")  # 最后一步之后是空

for TASK_ID in $TASKS; do
    # 查当前步骤
    CURRENT=$(python3 -c "
import sqlite3, json
conn = sqlite3.connect('$DB')
cur = conn.execute(
    'SELECT step_name, status FROM pipeline_steps WHERE task_id=? ORDER BY id DESC LIMIT 1',
    ('$TASK_ID',)
)
row = cur.fetchone()
print(json.dumps({'step': row[0], 'status': row[1]}) if row else 'null')
")

    if [ "$CURRENT" = "null" ]; then
        # 新任务 → 初始化 step=dev
        echo "[autopilot] 新任务 $TASK_ID → 初始化 dev"
        python3 -c "
import sqlite3
conn = sqlite3.connect('$DB')
conn.execute(
    'INSERT INTO pipeline_steps (task_id, step_name, status, started_at) VALUES (?,?,?,datetime(\"now\"))',
    ('$TASK_ID', 'dev', 'pending')
)
conn.commit()
"
        # 创建 dev kanban card
        hermes kanban create --title "dev: $TASK_ID" --assignee game-engine
        continue
    fi

    STEP=$(echo "$CURRENT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['step'])")
    STATUS=$(echo "$CURRENT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['status'])")

    case "$STATUS" in
        done)
            # → 推进到下一步
            NEXT_STEP=$(python3 -c "
order = ['dev','qa-exec','va','merge','close']
idx = order.index('$STEP') + 1
print(order[idx] if idx < len(order) else '')
")
            if [ -z "$NEXT_STEP" ]; then
                echo "[autopilot] $TASK_ID: 全部完成 ✅"
                continue
            fi
            echo "[autopilot] $TASK_ID: $STEP done → 推进到 $NEXT_STEP"

            # 验证 requires
            python3 pipeline/state.py --check-requires --step "$NEXT_STEP" --task "$TASK_ID" || {
                echo "[autopilot] ERROR: requires 不满足"
                continue
            }

            # 根据步骤决定下一步动作
            case "$NEXT_STEP" in
                dev|qa-exec|va)
                    # 创建 kanban card 分配给 agent
                    ASSIGNEE="game-engine"  # 根据步骤映射
                    hermes kanban create --title "$NEXT_STEP: $TASK_ID" --assignee "$ASSIGNEE"
                    ;;
                merge)
                    # autopilot 自己执行 merge
                    git merge --no-ff "feat/$TASK_ID"
                    ;;
                close)
                    # autopilot 自己执行 close
                    hermes kanban complete "$TASK_ID"
                    ;;
            esac

            # 更新 checkpoint
            python3 -c "
import sqlite3
conn = sqlite3.connect('$DB')
conn.execute(
    'INSERT INTO pipeline_steps (task_id, step_name, status, started_at) VALUES (?,?,?,datetime(\"now\"))',
    ('$TASK_ID', '$NEXT_STEP', 'running')
)
conn.commit()
"
            ;;
        running)
            # 检查 kanban task 状态
            KANBAN_STATUS=$(hermes kanban show "$TASK_ID" 2>/dev/null | grep 'status' || echo "unknown")
            if echo "$KANBAN_STATUS" | grep -q "done"; then
                # 验证 produces
                python3 pipeline/state.py --check-produces --step "$STEP" --task "$TASK_ID" && {
                    python3 -c "
import sqlite3
conn = sqlite3.connect('$DB')
conn.execute(
    'UPDATE pipeline_steps SET status=\"done\", finished_at=datetime(\"now\") WHERE task_id=? AND step_name=?',
    ('$TASK_ID', '$STEP')
)
conn.commit()
"
                }
            fi
            ;;
        failed)
            echo "[autopilot] $TASK_ID: $STEP 失败，跳过"
            hermes kanban comment "$TASK_ID" "[AUTOPILOT] 步骤 $STEP 失败，停止推进"
            ;;
    esac
done
```

### 3.5 与 Slice 2/3 的扩展点

autopilot.sh 的架构预留了以下扩展接口（不实现，只留位置）：

| 预留点 | 当前行为 | Slice 2/3 扩展 |
|--------|---------|---------------|
| `--handle-branch` | 不存在 | Slice 2：读取 JSONL branches 字段，按 action 分发 |
| `--close-s6-check` | 不存在 | Slice 3：close-0 S6 检测 |
| `--close-gai` | 不存在 | Slice 3：更新 GAI |
| `--close-backup` | 不存在 | Slice 3：按项目类型执行备份 |
| `fanout` | 不存在 | Slice 2：并行 dev + qa-d1 |
| `state.py gate_roundtable` | 不存在 | Slice 2：触发 D 类 roundtable |

---

## 4. 验收标准

### 4.1 功能验收

| # | 验收项 | 验证方式 | 通过标准 |
|---|--------|---------|---------|
| AC-1 | **checkpoint 初始化** | 删除 pipeline_state.db → 运行 autopilot.sh → 检查 db 是否存在 | db 文件创建，含 pipeline_steps 表 |
| AC-2 | **断点续跑** | 模拟中途 kill autopilot → 重新启动 | 从上次中断的步骤继续，不重复创建 kanban card |
| AC-3 | **5 步线形推进** | 手动创建 kanban task → 观察 autopilot 日志 | dev→qa-exec→va→merge→close 全部完成，pipeline_state.db 中 5 行记录 |
| AC-4 | **超时检测** | 设置 timeout_min=1 → dev 步骤运行超过 1 分钟 | autopilot 检测超时 → status='failed' → 发 kanban_comment 告警 |
| AC-5 | **produces 验证** | dev 完成后不生成代码文件 | autopilot 检测 produces 缺失 → status='failed' |
| AC-6 | **flock 锁** | 同时触发两个 autopilot.sh 实例 | 第二个实例输出"上一轮未完成，跳过"并退出 |
| AC-7 | **JSONL 合约可解析** | `python3 -c "import json; [json.loads(l) for l in open('config/contracts.jsonl')]"` | 无异常，每行可解析 |

### 4.2 非功能验收

| # | 验收项 | 标准 |
|---|--------|------|
| AC-8 | **SQLite WAL 模式** | pipeline_state.db 启用 WAL（允许并发读） |
| AC-9 | **幂等建表** | checkpoint.py 重复调用不报错 |
| AC-10 | **日志可读** | autopilot 每步输出带时间戳的 `[autopilot]` 标记 |

### 4.3 测试场景

| 场景 | 操作 | 预期结果 |
|------|------|---------|
| 正常流转 | 创建 kanban task → 各 agent 依次完成 | 5 步全部 done，close 执行 kanban_complete |
| 无任务时 | cron 触发 autopilot，kanban 无 running 任务 | 输出"无 running 任务"，立即退出 |
| 新任务首次检测 | autopilot 发现 task_id 不在 pipeline_state.db 中 | 插入 step='dev', status='pending'，创建 dev kanban card |
| 步骤失败 | agent 返回失败 | pipeline_state.db status='failed'，kanban_comment 告警，不继续推进 |
| 超时 | 某步运行时间 > timeout_min | status='failed', error_msg="timeout: N min" |

---

## 5. 不做的事（Slice 2/3 才做）

### 5.1 Slice 2 才做（完整 7 步 + 分支 + 回退）

| 项目 | 为什么不现在做 | 影响 |
|------|--------------|------|
| **qa-d1（测试方案评审）** | 需要 fan-out（dev + qa-d1 并行），引入并发状态管理 | Slice 1 管线少 1 步，但不影响核心流转 |
| **qa-d2（测试报告评审）** | 需要 rollback（评审 fail → 回退到 dev），引入条件路由引擎 | Slice 1 不做测试评审的质量把关 |
| **21 分支条件** | 需要完整的 branches 解析引擎 + action 分发器（retry/block/rollback/continue/gate_roundtable） | Slice 1 的异常处理等价于"失败即停止" |
| **gate_roundtable(type, reason)** | D 类 roundtable 需要 kanban_create + kanban_block 的组合操作 | Slice 1 不做铁律冲突/QA 发现 BLOCKER 的自动化裁定 |
| **rollback 机制** | 需要回退到目标步骤 + 清除中间状态，涉及 pipeline_state.db 多行更新 | Slice 1 没有回退，失败后需要人工介入 |
| **fan-out** | dev + qa-d1 并行启动需要 join 点检测 + 多 kanban card 管理 | Slice 1 所有步骤都是串行的 |

### 5.2 Slice 3 才做（架构增强 + 运维闭环）

| 项目 | 为什么不现在做 | 影响 |
|------|--------------|------|
|| **verdict / verdict_detail 字段** | 需要多值判定逻辑（pass/fail/FALSIFIED/conditional_pass/VERIFIED） | Slice 1 只有 status（pass/fail 二元） |
| **三重备份（merge-1/merge-4/close-4）** | 备份脚本调用依赖 project_type + 错误处理策略 | Slice 1 的 merge 只是 git merge，close 只是 kanban_complete |
| **close 7 个子步骤** | S6 检测/GAI 更新/manifest 更新/备份推送/通知/归档都是独立的执行逻辑 | Slice 1 的 close 是单一步骤 |
| **DPL-011 boot_context** | session DB 查询 + .hermes.md 动态段写入是独立子系统 | 不影响 Slice 1 的核心流转 |
| **dashboard.py** | 红绿灯面板依赖 verdict 字段 + 多维度展示 | Slice 1 通过 SQLite 命令行直接查状态 |
| **ABCD 类型 roundtable** | OC 判定 + state.py 分发 + kanban_block 逻辑是完整子系统 | Slice 1 遇到异常直接停止，不做 roundtable |
| **D-015（close.sh 角色裁定）** | Product 和 Architect 对此有冲突，需 Slice 3 前裁定 | Slice 1 的 close 不调用 close.sh |

### 5.3 永远不做

- **不修改 close.sh**（104 行）——它保持为验证脚本，Sl 1 不调用它
- **不让 autopilot 写 kanban 系统表**——autopilot 只通过 hermes CLI 操作 kanban
- **不引入新语言/新框架**——Python 3.11 + SQLite + Bash，零依赖膨胀
- **不在 pipeline_state.db 中存储 agent 输出内容**——只存文件路径（artifact_paths）

---

## 6. 数据流全景（Slice 1 视角）

```
  Frank "做 P0-XX"
       │
       ▼
  OC 创建 kanban task (id = t_xxx)
       │
       ▼
  ┌──────────────────────────────────────────────┐
  │ autopilot.sh (cron 2min)                     │
  │                                              │
  │ 1. 读 kanban → 发现新 task t_xxx             │
  │ 2. 初始化 checkpoint: step=dev, status=pending│
  │ 3. 创建 kanban card → game-engine            │
  │                                              │
  │ ┌─────────┐    ┌──────────┐    ┌──────────┐  │
  │ │  dev    │ →  │ qa-exec  │ →  │   va     │  │
  │ │ engine  │    │   qa     │    │ verifier │  │
  │ └────┬────┘    └────┬─────┘    └────┬─────┘  │
  │      │              │               │        │
  │      ▼              ▼               ▼        │
  │ ┌─────────┐    ┌──────────┐                  │
  │ │  merge  │ →  │  close   │                  │
  │ │autopilot│    │autopilot │                  │
  │ └─────────┘    └──────────┘                  │
  │                                              │
  │ 每一步完成 → 写 pipeline_state.db            │
  └──────────────────────────────────────────────┘
       │
       ▼
  pipeline_state.db:
    t_xxx | dev      | done
    t_xxx | qa-exec  | done
    t_xxx | va       | done
    t_xxx | merge    | done
    t_xxx | close    | done
       │
       ▼
  kanban task = done ✅
```

---

## 7. 交付物清单

| # | 文件 | 行数（估） | 说明 |
|---|------|:---:|------|
| 1 | `pipeline/checkpoint.py` | ~80 | pipeline_state.db v1 schema + 幂等建表 + 读写接口 |
| 2 | `pipeline/state.py` | ~120 | 合约读取 + requires/produces 校验 + 步骤状态更新 |
| 3 | `config/contracts.jsonl` | ~5 | 5 步合约定义 |
| 4 | `scripts/autopilot.sh` | ~100 | cron 主循环 + 步骤推进 + 锁 |
| **总计** | | **~305 行** | |

---

## 8. 产品决定

| ID | 决定 | 裁定 |
|----|------|:----:|
| **Sl1-01** | Slice 1 用 5 步（dev → qa-exec → va → merge → close），不用 7 步 | ✅ |
| **Sl1-02** | pipeline_state.db v1 含 pipeline_steps + project_config 两张表，不含 verdict 三列。init_project.py 为可选——缺少 project_config 时系统降级运行 | ✅ |
| **Sl1-03** | Slice 1 不做分支路由——失败即停止，不重试不回退 | ✅ |
| **Sl1-04** | merge 和 close 由 autopilot 自己执行，不创建 kanban card | ✅ |
| **Sl1-05** | autopilot cron 频率 = 2 分钟（与 Slice 2/3 一致，方便后续叠加） | ✅ |
| **Sl1-06** | contracts.jsonl 不包含 branches 字段（Slice 2 追加） | ✅ |

---

> Slice 1 是管线的最小可行骨架——能跑通 5 步流转就是成功。不追求完美，追求可运行。每一步的完整性和健壮性在 Slice 2/3 中逐步加固。
>
> 产品发言完毕。交由 Architect 评审 → Engineer 实现。
