# Slice 3 架构设计 — 收尾层（DPL-011 + dashboard + backup + close 展开 + 三 cron 共存）

> 发言人：高见远（架构师） | 日期：2026-07-30 | 版本：v1.0
> 目标：在 Slice 2 的 7 步管线之上，补齐收尾层全部能力——跨会话上下文注入、CLI 仪表盘、备份策略、close 展开、三 cron 共存
> 输入：Slice 1/2 架构设计 + R3 architect 报告 + R4 product 裁决 + contracts-v2.jsonl
> 规则：扩展 pipeline/ 包，不重写 Slice 1/2 代码；.hermes.md ≤20000 字符；boot_context ≤2000 字符

---

## 0. Slice 3 范围定义

### 0.1 做什么

```
Slice 1: 5 步线性管线 + 数据层
Slice 2: 7 步管线 + 分支引擎 + rollback + fanout
Slice 3: DPL-011 跨会话上下文 + dashboard + 备份策略 + close 7 子步展开 + 三 cron 共存
```

### 0.2 新增/修改组件一览

| 组件 | 文件 | 类型 | 核心变更 |
|------|------|:----:|---------|
| `boot_context.py` | `pipeline/boot_context.py` | **新增** | DPL-011 Layer 1: 读 session DB + kanban + pipeline → 写 .hermes.md 动态段 |
| `backup.py` | `pipeline/backup.py` | **新增** | 三类备份策略自动判定 + backup_step 字段支持 (pre/post/close) |
| `dashboard.py` | `scripts/dashboard.py` | **新增** | CLI 红绿灯仪表盘，读 pipeline_state.db，彩色终端输出 |
| `pipeline/state.py` | `pipeline/state.py` | 扩展 | 实现 close 5 个 stub 函数（GAI/manifest/backup/notify/archive） |
| `pipeline/constants.py` | `pipeline/constants.py` | 扩展 | 加 BACKUP_STRATEGIES 常量 + BOOT_CONTEXT 模板常量 |
| `.hermes.md` | `.hermes.md` | 修改 | 加静态结构 + `<!-- BOOT_CONTEXT_START -->` 动态段锚点 |
| `scripts/autopilot.sh` | `scripts/autopilot.sh` | 扩展 | close 子步骤调用 backup.py 集成 |

### 0.3 不改的组件

| 文件 | 理由 |
|------|------|
| `pipeline/checkpoint.py` | user_version=2 已稳定，Slice 3 无 schema 变更 |
| `pipeline/config.py` | 只读接口已完备 |
| `pipeline/init_project.py` | 新增备份脚本路径通过 project_config 传递，init_project 已有 --backup-script / --notify-script 参数 |
| `pipeline/fanout.py` | 不涉及 |
| `pipeline/discover.py` | 任务发现已实现，Slice 3 只加 boot_context 对已发现任务的摘要 |
| `config/contracts.jsonl` | v2 合约不变（close 步骤的 backup_step 已在 merge 合约中定义） |
| `pipeline_state.db` schema | 无新增列，no migration needed |

---

## 1. DPL-011: boot_context cron + .hermes.md 写入规范

### 1.1 设计目标

解决 Hermes 架构问题：OC 跨 session 后「失忆」。boot_context 在 OC 每次新 session 启动前，将最近上下文摘要写入 `.hermes.md` 动态段。Hermes 引擎在 SOUL.md 之前加载 `.hermes.md`（Project Context），确保 agent 在认知自己角色前就已获得项目状态。

### 1.2 .hermes.md 结构（两段式）

```
# devPPL 项目规范                                        ← 静态段（手动维护）

> 所有在此 workspace 中执行的 kanban 任务自动加载此文件。

## 核心标准文档
... (QA 标准、申诉机制等)

## 关键规则
... (管线规则等)

<!-- BOOT_CONTEXT_START -->                              ← 动态段锚点（注释标记）
<!-- 由 boot_context cron 每 5min 自动生成，禁止手动编辑 -->

## 当前活跃上下文
(最近 3 个 session 摘要、活跃 kanban task、关键决策等)

<!-- BOOT_CONTEXT_END -->                                ← 动态段结束标记
```

**约束**：
- 动态段总大小 ≤2000 字符（含标记注释）
- `.hermes.md` 总文件大小 ≤20000 字符
- 写入方式：原子覆写（写 .tmp → os.rename），防止并发读脏数据
- 动态段为纯文本，不依赖 markdown 渲染（OC 在 terminal 中阅读）

### 1.3 boot_context.py 模块设计

```python
# pipeline/boot_context.py — DPL-011 Layer 1（确定层，零 LLM）

def generate_boot_context(
    pipeline_db_path: str = "pipeline_state.db",
    kanban_db_path: str = "~/.hermes/kanban.db",
    session_limit: int = 3,
) -> str:
    """生成 boot_context 动态段内容（≤2000 字符）。

    数据源优先级：
      1. pipeline_state.db — 当前活跃步骤（最高优先级，必须）
      2. kanban.db — 活跃任务标题（高优先级）
      3. session_search — 最近 session 摘要（中优先级，可能无数据）
      4. memory — 关键决策 / 纠偏记录（低优先级，补充）

    Returns:
        ≤2000 字符的 markdown 摘要文本（不含锚点标记，由调用方包裹）。
    """

def write_boot_context(
    content: str,
    hermes_md_path: str = ".hermes.md",
) -> bool:
    """将 boot_context 内容原子写入 .hermes.md 动态段。

    操作：
      1. 读取当前 .hermes.md
      2. 定位 <!-- BOOT_CONTEXT_START --> ... <!-- BOOT_CONTEXT_END -->
      3. 替换中间内容为新的 boot_context
      4. 原子覆写（写 .hermes.md.tmp → os.rename）

    Returns:
        True 成功，False 失败（文件不存在 / 无锚点 / IO 错误）。
    """
```

### 1.4 数据源与优先级

```
优先级 1（必须，零成本）:
  pipeline_state.db → 查询所有活跃 task_id → 当前步骤 + 状态
  格式: "活跃任务: t_xxx(dev:running), t_yyy(qa-exec:done)"

优先级 2（高优先级，零成本）:
  kanban.db → 对应 task_id 的 title
  格式: "  t_xxx: [Slice3-Step1] 架构设计 — 收尾层"

优先级 3（中优先级，可能有数据）:
  session_search(query="关键决策 OR roundtable", sort="newest", limit=3)
  → 提取每个 session 的 title 和关键消息
  格式: "最近决策: [2026-07-30] Slice2 管线通过 roundtable D 类裁定"

优先级 4（低优先级，补充）:
  memory 工具已验证的事实（通过 session DB 获取）
  格式: "纠偏记录: OC 不应跳过 D2 roundtable"
```

**容错设计**：每个数据源读取失败不阻塞整体生成。pipeline_state.db 不可读 → 生成「pipeline 状态不可用」摘要。

### 1.5 输出格式示例（~350 tokens）

```markdown
## 当前活跃上下文
> boot_context @ 2026-07-30T14:35:00Z

### 活跃管线任务
- t_0e926cad(close:running) — [Slice3-Step1] 架构设计 — 收尾层
- t_8dbdcfb2(qa-d2:done)   — [D1] Architect — Slice2 测试方案架构评审

### 最近决策
- 0730: D1-F1 VA FALSIFIED 是架构有意选择 gate_roundtable，非 bug
- 0730: Slice 1 代码 5 处不一致（3 BLOCKER + 2 MAJOR）已在 R5 修正

### 纠偏
- OC 不应跳过 D2 roundtable（即使 MAJOR=0），需 Product 裁定
```

### 1.6 cron 调度

```
cron: 每 5min
脚本: python3 pipeline/boot_context.py --write
lockfile: /tmp/boot_context.lock (flock)
```

---

## 2. dashboard.py — CLI 红绿灯仪表盘

### 2.1 设计目标

提供一行命令查看整个管线健康状态：`python3 scripts/dashboard.py`。终端输出，ANSI 颜色，不需要浏览器。

### 2.2 输出设计

```
 ─────────────────────────────────────────────────────────
  devPPL Pipeline Dashboard                   14:35:00 UTC
 ─────────────────────────────────────────────────────────
  t_0e926cad [Slice3-Step1] 架构设计
    dev       ✅ done     (0730 12:05)
    qa-d1     ✅ done     (0730 13:20)
    qa-exec   ✅ done     (0730 14:00)
    qa-d2     ✅ done     (0730 14:15)
    va        ✅ done     (0730 14:30)
    merge     ✅ done     (0730 14:45)
    close     🔄 running  (0730 14:50)
  ─────────────────────────────────────────────────────────
  t_8dbdcfb2 [D1] Architect — Slice2 测试方案架构评审
    dev       ✅ done     (0730 10:00)
    qa-d1     ✅ done     (0730 11:00)
    qa-exec   ✅ done     (0730 11:45)
    qa-d2     🔄 running  (0730 12:00)
    va        ⬜ pending
    merge     ⬜ pending
    close     ⬜ pending
  ─────────────────────────────────────────────────────────
  汇总: 2 active | 0 blocked | 0 failed | 0 timed out
 ─────────────────────────────────────────────────────────
```

### 2.3 颜色编码

| 状态 | 图标 | ANSI | 含义 |
|------|:----:|------|------|
| `done` | ✅ | 绿 | 步骤已完成 |
| `running` | 🔄 | 黄 | 步骤进行中 |
| `pending` | ⬜ | 灰 | 等待启动 |
| `failed` | ❌ | 红 | 步骤失败 |
| `blocked` | 🚫 | 品红 | 被阻塞（等待 roundtable/人工） |
| `cancelled` | ↩️ | 灰 | 因 rollback 取消 |
| `timeout` | ⏰ | 红 | 超时 |

### 2.4 命令行接口

```
python3 scripts/dashboard.py                  # 全量
python3 scripts/dashboard.py --brief          # 只看汇总行
python3 scripts/dashboard.py --task t_xxx     # 单个 task
python3 scripts/dashboard.py --failed-only    # 只看异常
```

### 2.5 数据源

只读 pipeline_state.db（CheckpointDB 的 `get_all_steps` + `get_active_tasks`），不写任何数据。

### 2.6 实现概要

```python
# scripts/dashboard.py
# 依赖: pipeline.checkpoint.CheckpointDB, pipeline.constants.STEP_NAMES
# 纯 Python，无外部依赖（ANSI 颜色码内联）
```

---

## 3. 三类备份策略自动判定 + backup_step 字段

### 3.1 设计目标

合并步骤（merge）需要在合并前/后执行备份，关闭步骤（close）需要最终备份。不同项目类型可能需要不同的备份脚本。backup_step 字段（pre/post）区分同一步骤中的多次备份。

### 3.2 三类备份策略

| 策略 | backup_step | 触发时机 | 失败影响 | 重试 |
|------|:-----------:|---------|:--------:|:----:|
| **pre-merge** | `pre` | merge 步骤开始前 | 阻塞 merge（必须成功） | 1 次（合约定义） |
| **post-merge** | `post` | merge 步骤成功后 | 不阻塞管线，告警 | 2 次（合约定义） |
| **close-final** | `close` | close 子步骤 close-4 | 不阻塞管线，告警 | 3 次（合约定义） |

### 3.3 备份脚本判定逻辑

```
backup.py::determine_backup_script(project_type, backup_step, db) → script_path

判定规则（优先级从高到低）:
  1. project_config 中的 backup_script_<step> 键（如有显式配置）
     - backup_script_pre    → pre-merge 备份脚本
     - backup_script_post   → post-merge 备份脚本
     - backup_script_close  → close 备份脚本
  2. project_config 中的 backup_script（全局默认）
  3. 内置默认（项目类型相关）:
     - system_mechanism → /workspace/hermes_backup_push.sh (git push)
     - pure_product     → /workspace/hermes_backup_tarball.sh (归档)
     - hybrid           → /workspace/hermes_backup_push.sh (优先 git)
```

### 3.4 backup.py 模块设计

```python
# pipeline/backup.py — 备份策略判定 + 执行

def determine_backup_script(
    project_type: str,
    backup_step: str,  # "pre" | "post" | "close"
    db: CheckpointDB,
) -> str:
    """返回备份脚本的绝对路径。"""

def run_backup(
    script_path: str,
    task_id: str,
    backup_step: str,
    timeout_seconds: int = 120,
) -> tuple[bool, str]:
    """执行备份脚本。
    
    Returns:
        (success: bool, output_or_error: str)
        成功: (True, stdout)
        失败: (False, stderr)
    """

def run_backup_for_step(
    task_id: str,
    backup_step: str,
    db_path: str = "pipeline_state.db",
) -> tuple[bool, str]:
    """一站式接口：判定 → 执行 → 返回结果。
    由 autopilot.sh 和 state.py 调用。
    """
```

### 3.5 与现有合约的对接

`contracts-v2.jsonl` 中 merge 步骤的 branches 已包含 `backup_step` 字段：

```json
// merge step branches 中:
{"on":"pre_merge_backup_fail",  "action":"retry", "backup_step":"pre",  ...}
{"on":"post_merge_backup_fail", "action":"retry", "backup_step":"post", ...}
```

Slice 3 的 `backup.py` 使 `backup_step` 字段从「合约定义」变成「可执行动作」——BranchesEvaluator 已将 backup_step 传递到 action dict，autopilot.sh 现在可以消费它。

### 3.6 merge 步骤中备份的执行位置

```
merge 步骤被触发 (autopilot.sh):
  1. 运行 backup.py::run_backup_for_step(task_id, "pre")
     → 失败: state.py 记录 failed + "pre_merge_backup_fail"
     → 合约分支引擎触发 retry
  2. git merge 执行
  3. 运行 backup.py::run_backup_for_step(task_id, "post")
     → 失败: state.py 记录 failed + "post_merge_backup_fail"
     → 合约分支引擎触发 retry
```

---

## 4. close 7 子步骤展开（state.py + autopilot）

### 4.1 当前状态（Slice 2 stub）

Slice 2 中 `state.py` 已有 close 的 5 个 stub 函数（全部 `pass`），autopilot.sh 的 `close_pipeline_step()` 已按 7 子步调用它们。Slice 3 将 stub 替换为实际实现。

### 4.2 close-0: S6 检测（已实现，不动）

`pipeline/state.py::close_s6_check(task_id, db)` — 已实现，Slice 2 完成。检查前 6 步（dev/qa-d1/qa-exec/qa-d2/va/merge）必须全部 done。Slice 3 不修改此逻辑。

### 4.3 close-1: 关闭 kanban（已实现，不动）

autopilot.sh 中 `hermes kanban complete "$TASK_ID"` — 已实现。

### 4.4 close-2: GAI 更新（Slice 3 实现）

```python
def _close_gai_update(task_id: str, db: CheckpointDB) -> None:
    """close-2: 更新 GAI 跟踪信息。

    操作：
      1. 读取 task 所有步骤的 verdict/verdict_detail 汇总
      2. 写入 GAI 跟踪文件: .pipeline/gai/{task_id}.json
         {
           "task_id": "...",
           "completed_at": "ISO8601",
           "steps": {step: {"verdict": ..., "status": "done"}, ...},
           "aggregate_verdict": "pass" | "fail" | "conditional_pass"
         }
      3. 如果所有步骤 verdict 均为 pass/VERIFIED → aggregate_verdict = "pass"
         否则 → aggregate_verdict = "conditional_pass" 或 "fail"
    """
```

### 4.5 close-3: manifest 更新（Slice 3 实现）

```python
def _close_manifest_update(task_id: str, db: CheckpointDB) -> None:
    """close-3: 更新项目 manifest（发布日志）。

    操作：
      1. 读取 task 的 artifact_paths 汇总
      2. 追加到 .pipeline/manifest.jsonl:
         {"task_id": "...", "completed_at": "ISO8601",
          "steps": ["dev", "qa-d1", "qa-exec", "qa-d2", "va", "merge", "close"],
          "artifacts": ["docs/qa/test-report-t_xxx.md", ...],
          "verdict_summary": "pass" | "conditional_pass" | "fail"}
    """
```

### 4.6 close-4: 备份推送（Slice 3 实现）

```python
def _close_backup(task_id: str, db: CheckpointDB) -> None:
    """close-4: 执行最终备份（备份策略 = close）。

    操作：
      1. 调用 backup.py::run_backup_for_step(task_id, "close")
      2. 如果失败 → 记录 error_msg 但继续（不阻塞 close 流程）
      3. 写入 backup_snapshot 路径到 artifact_paths
    """
```

### 4.7 close-5: 通知（Slice 3 实现）

```python
def _close_notify(task_id: str, db: CheckpointDB) -> None:
    """close-5: 通知相关方（失败不阻塞 close 流程）。

    操作：
      1. 读取 project_config 中的 notify_script（默认 /workspace/hermes_backup_notify.sh）
      2. 调用通知脚本，传入 task_id 和 aggregate_verdict
      3. 失败静默忽略（写日志但不抛异常）
    """
```

### 4.8 close-6: 归档（Slice 3 实现）

```python
def _close_archive(task_id: str, db: CheckpointDB) -> None:
    """close-6: 归档产物 + 最终验证。

    操作：
      1. 收集所有步骤的 artifact_paths → 复制到 .pipeline/archive/{task_id}/
      2. 调用 close.sh（如果存在）做最终验证
      3. 写入归档清单 .pipeline/archive/{task_id}/manifest.json
    """
```

### 4.9 close 子步骤错误处理

```
close-0: S6 检测           → 失败: block 任务（S6 不满足）
close-1: kanban complete   → 失败: retry 1 次 → block
close-2: GAI 更新           → 失败: retry 1 次 → 继续（记录 warning）
close-3: manifest 更新      → 失败: retry 1 次 → 继续（记录 warning）
close-4: 备份推送           → 失败: retry 3 次 → 继续（记录 warning）
close-5: 通知              → 失败: 静默忽略
close-6: 归档              → 失败: 静默忽略 + 记录 warning
```

这与 `contracts-v2.jsonl` 中 close 步骤的 branches 定义一致。

---

## 5. autopilot 任务发现

### 5.1 当前状态

`pipeline/discover.py` + autopilot.sh 中的 `DISCOVERED_TASKS` 段落已实现扫描 kanban.db 自动注册。Slice 3 不修改此逻辑。

### 5.2 Slice 3 增强：boot_context 集成

`boot_context.py` 在生成摘要时，同时读取 pipeline_state.db 和 kanban.db，使 boot_context 反映最新的任务发现状态。这是一个「只读消费」增强，不改变 discover.py 的写入逻辑。

---

## 6. 三 cron 共存：flock 防冲突

### 6.1 三个 cron 任务

| cron | 间隔 | lockfile | 职责 | 互斥范围 |
|------|:----:|---------|------|---------|
| autopilot | 2min | `/tmp/autopilot.lock` | 管线推进 | 自身（同一脚本不可并发） |
| watchdog | 30min | `/tmp/watchdog.lock` | 系统健康检查 | 自身 |
| boot_context | 5min | `/tmp/boot_context.lock` | .hermes.md 动态段更新 | 自身 + autopilot（写入 .hermes.md 时） |

### 6.2 为什么不需要跨脚本互斥

- autopilot 只写 `pipeline_state.db`（SQLite WAL 天然并发安全）和 kanban（CLI 调用，每次独立进程）
- boot_context 读 pipeline_state.db + 写 `.hermes.md`（原子覆写，不会读脏数据）
- watchdog 只读 kanban.db + 飞书播报，无共享写入

**唯一潜在冲突**：boot_context 写 `.hermes.md` 时，如果 autopilot 恰好也在操作——但 autopilot 不写 `.hermes.md`，所以不需要跨脚本锁。

### 6.3 flock 最佳实践

```bash
# 每个脚本的模式:
LOCKFILE="/tmp/<script>.lock"
exec 200>"$LOCKFILE"
if ! flock -n 200; then
    echo "[$(date)] 另一实例运行中，跳过本轮" >&2
    exit 0
fi
trap 'flock -u 200' EXIT
# ... 主逻辑 ...
```

---

## 7. 组件间接口契约

### 7.1 文件依赖图（Slice 3 更新版）

```
pipeline/constants.py          ← 零依赖（加 BACKUP_STRATEGIES + BOOT_CONTEXT 模板）
       │
       ▼
pipeline/checkpoint.py         ← 依赖 sqlite3（不变，v2 schema）
       │
       ├──────────────┬──────────────┬──────────────┐
       ▼              ▼              ▼              ▼
pipeline/config.py  pipeline/fanout.py  pipeline/discover.py  pipeline/backup.py  ← 新增
       │              │              │              │
       │              │              │              ▼
       │              │              │       pipeline/boot_context.py  ← 新增
       │              │              │              │
       ▼              ▼              ▼              ▼
pipeline/state.py              ← 依赖 constants + config + fanout + checkpoint + backup
       │                            + 实现 close stub 函数
       │
       ├──────────────────────────────┐
       ▼                              ▼
scripts/autopilot.sh           scripts/dashboard.py    ← 新增
  + 集成 backup.py                + 只读 CheckpointDB
  + close 子步骤调用 backup       + ANSI 颜色输出
```

### 7.2 数据流（Slice 3 新增路径）

```
三 cron 并行运行:
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │ autopilot    │  │ watchdog     │  │ boot_context │
  │ 每 2min      │  │ 每 30min     │  │ 每 5min      │
  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
         │                 │                  │
         ▼                 ▼                  ▼
  pipeline_state.db    kanban.db         session DB
  (读写)               (只读)            (只读)
         │                                  │
         │                                  ▼
         │                          pipeline/boot_context.py
         │                             │
         │                             ▼
         │                          .hermes.md
         │                          (原子覆写动态段)
         │
         ▼
  scripts/dashboard.py
  (只读 pipeline_state.db → CLI 红绿灯)

close 子步骤:
  autopilot.sh → close_pipeline_step()
    close-0: S6 检测     → state.py::close_s6_check (已有)
    close-1: kanban done  → hermes kanban complete
    close-2: GAI 更新     → state.py::_close_gai_update (Slice 3 实现)
    close-3: manifest     → state.py::_close_manifest_update (Slice 3 实现)
    close-4: 备份推送     → backup.py::run_backup_for_step(task_id, "close")
    close-5: 通知         → state.py::_close_notify (调用 notify_script)
    close-6: 归档         → state.py::_close_archive + close.sh
```

---

## 8. pipeline/ 目录结构（Slice 3 更新版）

```
pipeline/
├── __init__.py           # 空文件（不变）
├── constants.py          # ~65 行（+15）：BACKUP_STRATEGIES + BOOT_CONTEXT 模板常量
├── checkpoint.py         # ~300 行（不变）
├── config.py             # ~40 行（不变）
├── state.py              # ~1100 行（+50）：close stub → 完整实现
├── fanout.py             # ~55 行（不变）
├── discover.py           # ~137 行（不变）
├── init_project.py       # ~58 行（不变）
├── backup.py             # ~80 行（新增）：三类备份策略判定 + 执行
└── boot_context.py       # ~120 行（新增）：DPL-011 跨会话上下文生成 + 写入

scripts/
├── autopilot.sh          # ~500 行（+20）：close 子步骤集成 backup.py
├── dashboard.py          # ~100 行（新增）：CLI 红绿灯仪表盘
└── ...

config/
└── contracts.jsonl       # v2（不变）

.pipeline/
├── gai/{task_id}.json    # GAI 跟踪文件（新增）
├── manifest.jsonl        # 发布清单（新增）
└── archive/{task_id}/    # 归档目录（新增）
```

---

## 9. 增量工作量估算

| 文件 | 类型 | 行数 | 说明 |
|------|------|:----:|------|
| `pipeline/boot_context.py` | **新增** | ~120 | DPL-011: session DB + kanban + pipeline → .hermes.md |
| `pipeline/backup.py` | **新增** | ~80 | 三类备份策略判定 + subprocess 执行 |
| `scripts/dashboard.py` | **新增** | ~100 | 读 pipeline_state.db，ANSI 彩色输出 |
| `pipeline/state.py` | 修改 | +50 | close 5 个 stub → 完整实现 |
| `pipeline/constants.py` | 修改 | +15 | BACKUP_STRATEGIES + BOOT_CONTEXT 模板常量 |
| `.hermes.md` | 修改 | +40 | 静态结构 + BOOT_CONTEXT 锚点 |
| `scripts/autopilot.sh` | 修改 | +20 | close 子步骤集成 backup.py |
| **Slice 3 总计** | | **~425 行** | 含 Python + Shell + Markdown |

---

## 10. 技术约束验证

| 约束 | 验证 |
|------|------|
| 扩展 pipeline/ 包，不重写 Slice1/2 代码 | ✅ 所有修改都是加新文件或实现已有 stub，不改现有接口 |
| .hermes.md ≤20000 字符 | ✅ 动态段 ≤2000 字符 + 静态段 ~1400 字符 = 3400，远低于上限 |
| boot_context ≤2000 字符 | ✅ generate_boot_context() 有字符预算强制截断 |
| 不修改 contracts.jsonl | ✅ v2 合约中 backup_step 字段已存在，Slice 3 只消费它 |
| 不修改 checkpoint.py | ✅ 无 schema 变更，user_version 保持 2 |

---

## 11. 不做的事（架构边界）

| 项目 | 归属 | 理由 |
|------|:----:|------|
| Layer 2 SOUL.md 铁律 6 | 跨架构/产品 | 属于 profile 配置变更，不属于 pipeline 代码 |
| Layer 3 会话摘要 LLM 生成 | Future | 需要 OC 在 session 结束时产出，暂不属于 Slice 3 |
| dashboard Web UI | Future | 当前只需 CLI |
| boot_context 含 LLM 摘要 | Future | Slice 3 只做确定性数据拼接（零 LLM token 成本） |
| B-brainstorming 自动恢复 | — | 永远等待人工 |
| watchdog 修改 | — | 已有独立 cron，不属 Slice 3 |

---

## 12. 技术风险点

| # | 风险 | 级别 | 缓解 |
|---|------|:----:|------|
| 1 | session DB 在 cron 环境中不可访问（路径/权限） | MINOR | boot_context 每个数据源独立 try/except，失败降级输出 |
| 2 | .hermes.md 原子覆写与 OC 正在读取并发 | MINOR | os.rename 在 POSIX 上原子，读方要么看到旧版要么新版 |
| 3 | backup 脚本路径不可执行 | MINOR | run_backup 检查 os.access(X_OK)，失败返回明确错误 |
| 4 | dashboard 输出在窄终端上换行混乱 | MINOR | --brief 模式作为回退 |
| 5 | close 子步骤 GAI/manifest/archive 写入 .pipeline/ 目录，首次运行需 mkdir | 低 | 每个函数内 os.makedirs(exist_ok=True) |

---

## 13. 一句话总结

> Slice 3 在 Slice 2 的 7 步管线之上补齐收尾层：boot_context cron 实现 DPL-011 跨会话上下文注入（.hermes.md 动态段，零 LLM 成本）、dashboard.py 提供 CLI 红绿灯仪表盘、backup.py 实现三类备份策略自动判定（pre/post/close）、state.py close stub 全部展开为实际逻辑、三 cron（autopilot/watchdog/boot_context）通过独立 flock 共存。不重写 Slice 1/2 代码，约 425 行增量（Python + Shell + Markdown）。

---

> 架构师发言完毕。下一站：engineer（寇豆码），请按 Slice 3 Step 2 开始编码实现。
