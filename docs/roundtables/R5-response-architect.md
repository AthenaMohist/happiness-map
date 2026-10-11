# R5 最终修复 — Architect 发言：统一架构设计

> 发言人：高见远（架构师） | 日期：2026-07-30 | 版本：v1.0
> 目标：读 Product R5（613 行，D-011~D-018）后，逐项给出架构设计，产出可直接交给 Engineer 实现的 schema + 逻辑规格
> 规则：kanban_complete 后传给 engineer

---

## 0. 总体判断：8 项全部可落地，2 处需架构修正

读完 Product R5 的 8 项新增决定（D-011~D-018），架构判断：

| 决定 | 状态 | 说明 |
|------|:----:|------|
| D-011 | ✅ 支持，补设计 | merge 三步备份的备份点+失败策略设计 |
| D-012 | ✅ 支持，补表结构 | project_config 表 schema + 初始写入流程 |
| D-013 | ✅ 支持 | autopilot 按 project_type 决定备份命令 |
| D-014 | ✅ 支持 | OC 判定 + state.py 分发 |
| D-015 | ⚠️ 架构修正 | close.sh 是验证脚本，不能被 autopilot 直接调用执行 close-1~5 |
| D-016 | ✅ 支持，补分支逻辑 | gate_roundtable(type,reason) 的完整分支 + B-brainstorming 特殊处理 |
| D-017 | ✅ 支持 | 飞书通知含 commit hash |
| D-018 | ✅ 支持 | 24 untracked 文件归档，close-3 扩展检查 |

**核心修正 D-015**：close.sh（104 行）是**事后验证脚本**（检查→fix），不是**执行脚本**。autopilot 不能直接调它做 close-1~close-5 的执行，因为 close.sh 的 S1 是"检查 kanban 是否 done"——在 autopilot 调用时 kanban 还没 close，必然失败。解决方案见 §3。

---

## 1. D-012: project_config 表设计

### 1.1 表结构

```sql
-- pipeline_state.db user_version=2 migration 中追加
CREATE TABLE IF NOT EXISTS project_config (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
```

预定义 key 及取值：

| key | value 枚举 | 说明 |
|-----|----------|------|
| `project_type` | `system_mechanism` / `pure_product` / `hybrid` | 项目分类，决定备份策略 |
| `project_name` | 自由文本 | 项目名（如 `"devPPL"`） |
| `backup_script` | 文件路径 | 备份脚本的绝对路径 |
| `notify_script` | 文件路径 | 通知脚本的绝对路径（可 NULL） |

### 1.2 枚举值语义与代码常量

```python
# pipeline/constants.py（新增文件，所有组件导入）
from enum import StrEnum

class ProjectType(StrEnum):
    SYSTEM_MECHANISM = "system_mechanism"  # 无独立 repo，如 devPPL
    PURE_PRODUCT     = "pure_product"      # 独立 repo，如 Threes
    HYBRID           = "hybrid"            # 独立 repo + Hermes 依赖

# 项目类型判定特征：
# - system_mechanism: /workspace/ 下没有独立 .git（或者 .git 就是 /workspace/.git）
# - pure_product:    /workspace/<project>/.git 存在，且不含 Hermes 配置依赖
# - hybrid:          /workspace/<project>/.git 存在，但依赖 Hermes 本体（SOUL.md 等）
```

### 1.3 初始化：谁写入、何时写入

```
首次部署流程:
  1. OC 创建项目 workspace
  2. OC 调用 pipeline/init_project.py（新增脚本，~15行）
     $ python3 pipeline/init_project.py --project-type system_mechanism
  3. init_project.py:
     a. 创建 pipeline_state.db + 执行 migration (user_version=2)
     b. INSERT OR REPLACE INTO project_config ...
     c. 回显 "project_config 已初始化: devPPL (system_mechanism)"
  4. 后续 autopilot 启动时只读 project_config，不写入
```

**为什么不让 autopilot 自动检测**：系统机制类和混合类的边界需要 Frank 的语义判断（"这个项目是否依赖 Hermes 本体"），无法通过文件系统特征 100% 准确判定。人工一次性写入，autopilot 只读，避免误判。

### 1.4 读取接口

```python
# pipeline/config.py（checkpoint.py 同目录，state.py + autopilot 引用）
import sqlite3

def get_project_config(db_path: str = "pipeline_state.db") -> dict:
    """返回 {'project_type': 'system_mechanism', 'project_name': 'devPPL', ...}"""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT key, value FROM project_config").fetchall()
    conn.close()
    config = dict(rows)
    config.setdefault("project_type", "system_mechanism")  # 默认值
    return config

def get_backup_strategy(project_type: str) -> dict:
    """返回三个备份点的命令"""
    STRATEGIES = {
        "system_mechanism": {
            "pre_merge":   "bash /workspace/hermes_backup_push.sh",
            "post_merge":  "bash /workspace/hermes_backup_push.sh",
            "close_backup": "bash /workspace/hermes_backup_push.sh",
            "notify":      "bash /workspace/hermes_backup_notify.sh",
        },
        "pure_product": {
            "pre_merge":   "cd {repo} && git add . && git commit -m 'backup: pre-merge'",
            "post_merge":  "cd {repo} && git add . && git commit -m 'backup: post-merge'",
            "close_backup": "cd {repo} && git push",
            "notify":      None,
        },
        "hybrid": {
            "pre_merge":   "cd {repo} && git add . && git commit -m 'backup: pre-merge' && git push && bash /workspace/hermes_backup_push.sh",
            "post_merge":  "cd {repo} && git add . && git commit -m 'backup: post-merge' && git push && bash /workspace/hermes_backup_push.sh",
            "close_backup": "bash /workspace/hermes_backup_push.sh",
            "notify":      "bash /workspace/hermes_backup_notify.sh",
        },
    }
    return STRATEGIES[project_type]
```

**给 Engineer 的信息**：`pipeline/config.py` 是新增文件（~30 行），被 `state.py` 和 `autopilot.sh`（通过 `python3 -c` 或直接 import）引用。不在 state.py 中内联，因为 autopilot.sh 的 shell 层也需要读项目类型来决定备份命令。

---

## 2. D-016: gate_roundtable(type, reason) 统一分发

### 2.1 JSONL 合约变更

```jsonl
# R4 旧格式（变更前）:
{"on":"BLOCKER_found","action":"gate_D_roundtable","reason":"QA 发现 BLOCKER"}

# R5 新格式（变更后）:
{"on":"BLOCKER_found","action":"gate_roundtable","reason":"QA 发现 BLOCKER","roundtable_type":"D"}
```

`branches[].action` 的值从 6 种扩展为 **仍 6 种**，但 `gate_roundtable` 取代了 `gate_D_roundtable`：

| action | roundtable_type 字段 | 说明 |
|--------|---------------------|------|
| `gate_roundtable` | 必填 | 指定类型 A/B/C/D，由 state.py 分发给对应 handler |

### 2.2 state.py 分发逻辑

```python
# pipeline/state.py 中的 roundtable 分支执行

ROUNDTABLE_ASSIGNEES = {
    "A": ["game-director", "game-architect", "game-engine", "game-qa"],
    "B": ["game-director", "game-architect", "game-engine", "game-qa"],
    "C": ["game-director", "game-architect", "game-engine"],
    "D": ["game-director", "game-architect"],
}

ROUNDTABLE_WORKFLOWS = {
    "A": "vote",         # 各角色投票 → approve/reject/conditional
    "B": "brainstorm",   # 不产生 kanban 开发任务 → 报告提交 Frank
    "C": "risk_matrix",  # 输出风险矩阵 → 记录决策
    "D": "review",       # D1/D2 评审 → 3 个强制议题
}

def handle_gate_roundtable(roundtable_type: str, reason: str, context: dict) -> str:
    """
    创建对应类型的 roundtable kanban task，block 当前管线任务。
    返回 roundtable task_id。
    """
    assignees = ROUNDTABLE_ASSIGNEES[roundtable_type]
    workflow  = ROUNDTABLE_WORKFLOWS[roundtable_type]

    mandatory_topics = []
    if roundtable_type == "D":
        mandatory_topics = [
            "分级判定是否正确",
            "处置方式是否合理",
            "修复难度评估",
        ]

    # B 类特殊规则：不产生 kanban 开发任务
    creates_dev_tasks = (roundtable_type != "B")

    task_id = kanban_create(
        title=f"[ROUNDTABLE-{roundtable_type}] {reason}",
        assignee=assignees[0],  # 主 assignee
        body=f"类型: {roundtable_type} ({workflow})\n"
             f"原因: {reason}\n"
             f"参与者: {', '.join(assignees)}\n"
             + (f"强制议题:\n" + "\n".join(f"  - {t}" for t in mandatory_topics) if mandatory_topics else ""),
        priority=50,  # roundtable 优先于普通开发
    )

    kanban_comment(
        task_id=context["current_task_id"],
        body=f"[AUTOPILOT: GATE] {roundtable_type} 类 roundtable 已创建: {task_id}"
    )
    kanban_block(
        task_id=context["current_task_id"],
        reason=f"等待 {roundtable_type} 类 roundtable ({task_id}) 裁定",
    )
    return task_id
```

### 2.3 完整触发场景矩阵

| 触发条件 | 判定节点 | 触发方 | roundtable_type | 参与者 |
|---------|---------|--------|:---------------:|--------|
| spec 违反 SOUL.md 铁律 | dev 进入前 | state.py | D | Product + Architect |
| QA 发现 BLOCKER | qa-exec done | state.py | D | Product + Architect |
| MAJOR > 3 | qa-exec done | state.py | D | Product + Architect |
| D1 评审 fail（2 次重试后） | qa-d1 done | state.py | D | Product + Architect |
| D2 评审 fail | qa-d2 done | state.py | D | Product + Architect |
| VA FALSIFIED | va done | state.py | D | Product + Architect |
| Frank 说"评估/讨论" | 阶段 -1 | OC | B | 全员 |
| Frank 说"做决定/选方案" | 阶段 -1 | OC | A | 全员 |
| Frank 说"有风险吗" | 阶段 -1 | OC | C | Product + Architect + Engineer |

### 2.4 B-brainstorming 的特殊处理

B 类 roundtable 的架构差异：

- **不产生 kanban 开发 card**：B 类 roundtable 完成后，OC 将结论报告 Frank，Frank 决定 → OC 手动创建后续任务。不走 autopilot 自动推进。
- **autopilot 不等待 B 类**：B 类 roundtable 的 block 在 roundtable 完成后由 OC 手动 unblock（或 Frank 的指令触发下一个动作），autopilot 不会自动检测 B 类 roundtable 的完成。

**实现**：`kanban_block` 时对 B 类型使用 `kind="needs_input"`（等待人工），而非 `kind="dependency"`（等待子任务完成自动恢复）。

---

## 3. D-015: close 展开为 7 个子步骤 + close.sh 调用修正

### 3.1 核心问题：close.sh 不能被 autopilot 直接调用执行

**现状**：close.sh（104行，`/root/.hermes/profiles/orchestrator/scripts/close.sh`）是**事后验证脚本**：
- S1: 检查 kanban 是否 done → 只是 grep 检查，不是执行 kanban_complete
- S2: 检查 VA 是否通过 → 只是 grep GAI 文件
- S3-S6: 同样只是检查/--fix 修复，不是执行

**问题**：autopilot 在 merge done 后调用 close.sh 时，close-1（kanban close）还没发生 → close.sh S1 必然 FAIL。

**Product 的 §4.3 假定了 close.sh 能执行 close-1~close-5，但 close.sh 只是验证脚本。**

### 3.2 架构修正：autopilot 直接执行各步骤，close.sh 仅做最终验证

```
close 步骤的数据流:
  autopilot 检测 merge done
    │
    ├─ [close-0] S6 检测（autopilot 执行）
    │   谁: autopilot
    │   内容: SELECT COUNT(*) FROM pipeline_steps
    │         WHERE task_id=X AND status='done'
    │         AND verdict IN ('pass','VERIFIED','conditional_pass')
    │         → 必须 = 6
    │   IF 不足 6: → block "S6 检测不通过"
    │
    ├─ [close-1] 关闭 kanban 任务（autopilot 通过 state.py 执行）
    │   谁: state.py（被 autopilot 调用）
    │   命令: hermes kanban complete $TASK_ID
    │   验证: hermes kanban show $TASK_ID | grep -q 'done'
    │   IF 失败: → retry 1 次 → block
    │
    ├─ [close-2] 更新 GAI（state.py 执行）
    │   谁: state.py
    │   操作: sed -i 's/P0-XX.*待办/P0-XX ✅ done/' GLOBAL_ACTION_ITEMS.md
    │   IF GAI 文件不存在: → block "GAI 文件丢失"
    │   IF 更新失败: → retry 1 次 → block
    │
    ├─ [close-3] 更新 Manifest（state.py 执行）
    │   谁: state.py
    │   操作: git diff HEAD~1 --name-only | while read f; do
    │         grep -q "$f" config/manifest.yaml || echo "MISSING: $f"
    │         done
    │   IF 有未注册文件: → autopilot 自动注册（追加到 manifest.yaml）或 block
    │   D-018 扩展: 检查 untracked roundtable 文件
    │
    ├─ [close-4] 备份推送（autopilot.sh 执行，按项目类型）
    │   谁: autopilot.sh（shell 层）
    │   策略: 读取 project_config → get_backup_strategy() → 执行对应命令
    │   IF 失败: → retry 2 次 → block "close-4 备份推送失败"
    │
    ├─ [close-5] 并发通知（autopilot 执行）
    │   谁: autopilot
    │   内容:
    │     a. 飞书通知 Frank（含 7 步验证摘要 + commit hash）
    │     b. 备份通知（如果配置了 notify_script）
    │   IF 通知发送失败: → retry 1 次 → 记录 warning（不阻塞 close）
    │
    ├─ [close-6] 归档 + 清理（autopilot 执行）
    │   谁: autopilot
    │   内容:
    │     a. openspec archive <task_id>
    │     b. git worktree remove /tmp/<task_id> (if exists)
    │     c. pipeline_state.db: step=close, verdict='pass', status='done'
    │   IF 归档失败: → 记录 warning（不阻塞）
    │
    └─ [最终验证] close.sh 跑一遍确认（可选，--fix 模式）
        目的: 验证 close-1~5 全部成功，作为闭环完整性的最终检查
        调用: bash close.sh $TASK_ID --fix
        失败: → 告警但不撤销已完成的 close
```

### 3.3 autopilot.sh 中的调用方式（修正后）

```bash
# autopilot.sh 的 close 段（修正版）

close_pipeline_step() {
    local TASK_ID="$1"

    # ── close-0: S6 检测 ──
    log "close-0: S6 检测"
    if ! python3 pipeline/state.py --close-s6-check "$TASK_ID"; then
        log "ERROR: close-0 S6 检测失败"
        python3 pipeline/state.py --handle-branch --step close --condition "s6_check_fail" --task "$TASK_ID"
        return 1
    fi
    log "close-0: PASS (6/6 步完成)"

    # ── close-1: 关闭 kanban ──
    log "close-1: 关闭 kanban 任务"
    if ! python3 pipeline/state.py --close-kanban "$TASK_ID"; then
        log "ERROR: close-1 失败"
        python3 pipeline/state.py --handle-branch --step close --condition "step_fail_close_kanban" --task "$TASK_ID"
        return 1
    fi

    # ── close-2: 更新 GAI ──
    log "close-2: 更新 GAI"
    if ! python3 pipeline/state.py --close-gai "$TASK_ID"; then
        python3 pipeline/state.py --handle-branch --step close --condition "step_fail_gai" --task "$TASK_ID"
        return 1
    fi

    # ── close-3: 更新 Manifest ──
    log "close-3: 更新 Manifest"
    if ! python3 pipeline/state.py --close-manifest "$TASK_ID"; then
        python3 pipeline/state.py --handle-branch --step close --condition "step_fail_manifest" --task "$TASK_ID"
        return 1
    fi

    # ── close-4: 备份推送 ──
    log "close-4: 备份推送"
    if ! python3 pipeline/state.py --close-backup "$TASK_ID"; then
        python3 pipeline/state.py --handle-branch --step close --condition "step_fail_backup" --task "$TASK_ID"
        return 1
    fi

    # ── close-5: 通知 ──
    log "close-5: 发送通知"
    python3 pipeline/state.py --close-notify "$TASK_ID" || true  # 通知失败不阻塞

    # ── close-6: 归档 + 清理 ──
    log "close-6: 归档"
    python3 pipeline/state.py --close-archive "$TASK_ID" || true  # 归档失败不阻塞

    # ── 最终验证（可选）──
    log "close: 最终验证"
    if bash /root/.hermes/profiles/orchestrator/scripts/close.sh "$TASK_ID"; then
        log "close: 全部验证通过 ✅"
        python3 pipeline/state.py --write-verdict --step close --verdict pass
    else
        log "WARNING: close.sh 验证有告警项（close 已完成但验证脚本发现异常）"
        python3 pipeline/state.py --write-verdict --step close --verdict conditional_pass
    fi
}
```

### 3.4 步骤执行顺序的架构理由

**为什么 backup (close-4) 在 kanban close (close-1) 之后？**

Product 的 close 顺序是 close-4（备份）在 close-1（kanban close）之后。但 kanban close 是不可逆操作——如果 close-4 备份失败，已经 close 的 kanban 任务无法回退。

**架构权衡**：
- 顺序 A（Product 原意）：close-1→close-2→close-3→close-4→close-5→close-6
  - 风险：如果 close-4 备份失败，close-1 的 kanban close 无法回退
  - 收益：kanban close 后 GAI/manifest 更新基于"任务已完成"的语义

- 顺序 B（风险优先）：close-4→close-1→close-2→close-3→close-5→close-6
  - 风险：close-4 成功但 close-1 失败 → 备份了一个"未完全关闭"的状态
  - 收益：kanban close 是最后的状态变更，之前的步骤失败都可以安全重试

- **架构裁决：采用顺序 A（Product 原意），但 close-4 的 retry 次数提升到 3 次。**
  - 理由：kanban close 对应的实际状态是"任务完成"，GAI/manifest 更新依赖这个语义
  - 缓解：close-4 重试 3 次（与 R4 的 close 总重试次数相同），reduce 备份失败的概率
  - 极端情况：close-4 重试耗尽 → block（此时 kanban 已 close 但备份未完成）→ OC 手动触发备份

---

## 4. D-011: 三重备份点设计与冗余分析

### 4.1 三个备份点

```
merge-1    merge-4    close-4
   │          │          │
   ▼          ▼          ▼
 pre-merge  post-VA    final
  snapshot   snapshot   snapshot
```

| 备份点 | 触发时机 | 备份内容 | 失败策略 |
|--------|---------|---------|---------|
| **merge-1** | merge 前 | 当前 main 的完整快照 | retry 1 次 → block |
| **merge-4** | VA 验证 merge 通过后 | merge 后的完整快照 | retry 2 次 → block |
| **close-4** | close 子步骤中 | 最终的完整快照 | retry 3 次 → block |

### 4.2 是否冗余？

**不冗余。三个备份点捕获三种不同的逻辑状态：**

- merge-1：**安全网**。如果 merge 出错需要 rollback → 从 merge-1 恢复。
- merge-4：**已确认的 merge 状态**。VA 已验证合并结果正确 → 这是"可以交付"的状态。
- close-4：**完全闭合状态**。GAI/manifest 已更新，kanban 已 close → 这是"一个完整任务周期结束"的最终状态。

`git reflog` 不能替代 merge-1 备份：
- reflog 记录的是 git 操作历史（rebase/merge/reset），不记录工作区文件状态
- merge-1 的备份脚本（hermes_backup_push.sh）做 rsync 增量同步 → 完整文件系统快照，比 git 覆盖面更大（含未跟踪文件）

### 4.3 各项目类型的备份行为

| 备份点 | system_mechanism | pure_product | hybrid |
|--------|-----------------|-------------|--------|
| merge-1 | rsync + backup-repo commit | git commit (项目 repo) | git commit + rsync |
| merge-4 | rsync + backup-repo commit | git commit (项目 repo) | git commit + rsync |
| close-4 | rsync + backup-repo commit | git push | rsync |

**存储位置**：
- system_mechanism: 所有备份在 `/workspace/SandboxHermesBackup/` 独立备份仓库
- pure_product: 在项目自己的 git 历史中（正常 commit）
- hybrid: 两份——项目 git 历史 + SandboxHermesBackup

### 4.4 merge 步骤的 JSONL 扩展

```jsonl
{"step":"merge","requires":["va_report.md","test_report.md"],"produces":["merge_commit","backup_snapshot"],"timeout_min":20,"branches":[
  {"on":"pre_merge_backup_fail","action":"retry","target":"merge","max_retries":1,"backup_step":"pre"},
  {"on":"conflict","action":"block","reason":"merge 冲突，engine 需解决"},
  {"on":"va_merge_check_fail","action":"rollback","target":"dev","reason":"VA 合并验证不通过"},
  {"on":"post_merge_backup_fail","action":"retry","target":"merge","max_retries":2,"backup_step":"post"},
  {"on":"human_gate","action":"await_confirm","reason":"等待 Frank 确认 merge"}
]}
```

**`backup_step` 字段**：新增，区分 "合并前备份失败" 和 "合并后备份失败"。state.py 读此字段决定：
- `pre` → 尚未开始 merge，可以直接重试
- `post` → merge 已完成 + VA 已通过，只需重试备份命令（不需要重做 merge）

---

## 5. JSONL v2 合约完整 schema（R5 更新版）

### 5.1 完整 JSONL（7 步）

```jsonl
{"step":"dev","requires":[],"produces":["branch","code_changes"],"timeout_min":60,"branches":[
  {"on":"timeout","action":"retry","target":"dev","max_retries":1},
  {"on":"timeout_after_retry","action":"block","reason":"dev 超时，需 OC 介入"},
  {"on":"contract_violation","action":"block","reason":"dev produces 缺失：{detail}"},
  {"on":"spec_violates_ironlaw","action":"gate_roundtable","reason":"spec 违反 SOUL.md 铁律","roundtable_type":"D"}
]}
{"step":"qa-d1","requires":["spec.md"],"produces":["test_plan.md"],"timeout_min":30,"branches":[
  {"on":"test_plan_incomplete","action":"retry","target":"qa-d1","max_retries":2},
  {"on":"test_plan_incomplete_after_retry","action":"block","reason":"测试方案未覆盖关键路径"}
]}
{"step":"qa-exec","requires":["branch","code_changes","test_plan.md"],"produces":["test_report.md"],"timeout_min":45,"branches":[
  {"on":"BLOCKER_found","action":"gate_roundtable","reason":"QA 发现 BLOCKER","roundtable_type":"D"},
  {"on":"MAJOR_gt_3","action":"gate_roundtable","reason":"MAJOR > 3，等同于 BLOCKER","roundtable_type":"D"},
  {"on":"MAJOR_le_3","action":"continue","reason":"记录后继续推进"}
]}
{"step":"qa-d2","requires":["test_report.md"],"produces":["review_conclusion"],"timeout_min":20,"branches":[
  {"on":"review_fail","action":"rollback","target":"dev","reason":"D2 评审不通过：{detail}"},
  {"on":"review_conditional","action":"continue","reason":"记录 pending items → 继续推进"},
  {"on":"requirement_unclear","action":"gate_roundtable","reason":"需求理解不清","roundtable_type":"D"}
]}
{"step":"va","requires":["test_report.md"],"produces":["va_report.md"],"timeout_min":30,"branches":[
  {"on":"FALSIFIED","action":"gate_roundtable","reason":"VA 证伪：{detail}","roundtable_type":"D"},
  {"on":"undetermined","action":"block","reason":"VA 信息不足，需 OC 介入"}
]}
{"step":"merge","requires":["va_report.md","test_report.md"],"produces":["merge_commit","backup_snapshot"],"timeout_min":20,"branches":[
  {"on":"pre_merge_backup_fail","action":"retry","target":"merge","max_retries":1,"backup_step":"pre"},
  {"on":"conflict","action":"block","reason":"merge 冲突，engine 需解决"},
  {"on":"va_merge_check_fail","action":"rollback","target":"dev","reason":"VA 合并验证不通过"},
  {"on":"post_merge_backup_fail","action":"retry","target":"merge","max_retries":2,"backup_step":"post"},
  {"on":"human_gate","action":"await_confirm","reason":"等待 Frank 确认 merge"}
]}
{"step":"close","requires":["merge_commit"],"produces":["gai_update","manifest_update","backup_snapshot"],"timeout_min":15,"branches":[
  {"on":"s6_check_fail","action":"block","reason":"S6 检测未通过：存在未完成步骤"},
  {"on":"step_fail","action":"retry","target":"close","max_retries":3,"note":"从失败步开始重试"},
  {"on":"step_fail_close_kanban","action":"retry","target":"close","max_retries":1,"note":"kanban 关闭失败"},
  {"on":"step_fail_gai","action":"retry","target":"close","max_retries":1,"note":"GAI 更新失败"},
  {"on":"step_fail_manifest","action":"retry","target":"close","max_retries":1,"note":"manifest 更新失败"},
  {"on":"step_fail_backup","action":"retry","target":"close","max_retries":3,"note":"备份推送失败（最高重试）"},
  {"on":"retry_exhausted","action":"block","reason":"close 重试耗尽，需手动检查"}
]}
```

### 5.2 与 R4 JSONL 的差异对照

| 步骤 | R4 | R5 | 变更 |
|------|-----|-----|------|
| dev | 3 分支 | 4 分支 | +spec_violates_ironlaw → gate_roundtable(type=D) |
| qa-d1 | 2 分支 | 2 分支 | 无变更 |
| qa-exec | 3 分支 | 3 分支 | gate_D_roundtable → gate_roundtable + roundtable_type:D |
| qa-d2 | 2 分支 | 3 分支 | +requirement_unclear → gate_roundtable(type=D) |
| va | 2 分支 | 2 分支 | gate_D_roundtable → gate_roundtable + roundtable_type:D |
| merge | 2 分支 | 5 分支 | +pre/post backup + va_merge_check_fail backup_step 字段 |
| close | 2 分支 | 7 分支 | 展开为每个 sub-step 一个 on 条件 + 各异的 max_retries |

### 5.3 字段总览

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `step` | string | ✅ | 步骤名 |
| `requires` | [string] | ✅ | 前置 artifact |
| `produces` | [string] | ✅ | 产出 artifact |
| `timeout_min` | int | ✅ | 超时（分钟） |
| `branches` | [object] | ✅ | 分支列表 |
| `branches[].on` | string | ✅ | 触发条件标识符 |
| `branches[].action` | string | ✅ | retry/block/rollback/continue/gate_roundtable/await_confirm |
| `branches[].target` | string | * | retry/rollback 时必填 |
| `branches[].max_retries` | int | * | retry 时必填 |
| `branches[].reason` | string | ✅ | 失败原因模板 |
| `branches[].roundtable_type` | string | * | gate_roundtable 时必填 (A/B/C/D) |
| `branches[].backup_step` | string | * | merge step 备份失败时区分 pre/post |
| `branches[].note` | string | — | 附注 |

---

## 6. pipeline_state.db schema v2 → v3

### 6.1 user_version 演进

| version | 变更 |
|---------|------|
| v1 | 初始 schema（Engineer 已预留） |
| v2 | R4：新增 verdict/verdict_detail/contract_check_passed |
| v3 | R5：新增 project_config 表 + close_step 字段 |

### 6.2 v3 完整 schema

```sql
PRAGMA user_version = 3;

-- ============================================================
-- 主表：pipeline_steps（v2 字段全部保留 + v3 新增 close_step）
-- ============================================================
CREATE TABLE IF NOT EXISTS pipeline_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    step_name TEXT NOT NULL,              -- dev|qa-d1|qa-exec|qa-d2|va|merge|close
    status TEXT NOT NULL DEFAULT 'pending',  -- pending|running|done|failed|blocked|restart
    artifact_paths TEXT DEFAULT '[]',     -- JSON array
    started_at TEXT,
    finished_at TEXT,
    error_msg TEXT,
    retry_count INTEGER DEFAULT 0,
    assigned_agent TEXT,
    openspec_ref TEXT,
    -- v2 字段
    verdict TEXT,                         -- pass|fail|conditional_pass|FALSIFIED|VERIFIED|blocked|timeout
    verdict_detail TEXT,
    contract_check_passed INTEGER,        -- NULL(未校验)|0(不适用)|1(通过)|2(失败)
    UNIQUE(task_id, step_name)
);

-- ============================================================
-- R5 新增表：project_config
-- ============================================================
CREATE TABLE IF NOT EXISTS project_config (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);

-- 初始数据（由 init_project.py 写入）:
-- INSERT OR REPLACE INTO project_config VALUES ('project_type', 'system_mechanism');
-- INSERT OR REPLACE INTO project_config VALUES ('project_name', 'devPPL');
-- INSERT OR REPLACE INTO project_config VALUES ('backup_script', '/workspace/hermes_backup_push.sh');
-- INSERT OR REPLACE INTO project_config VALUES ('notify_script', '/workspace/hermes_backup_notify.sh');

-- ============================================================
-- v3 migration（从 v2 升级）
-- ============================================================
-- ALTER TABLE pipeline_steps 不需要变更（v2 字段已足够，close 子步骤状态写入 verdict_detail）
-- CREATE TABLE IF NOT EXISTS project_config (...);
```

### 6.3 close 子步骤状态追踪

**设计决策：不在 pipeline_steps 表中为每个 close 子步骤新增独立行。**

理由：
- close 是 7 步管线中的最后一步（`step_name='close'`），子步骤是 close 的内部展开
- 如果为 close-0~close-6 各建一行，主表会从 7 行/任务膨胀到 14 行/任务，且 close 子步骤的重试逻辑与主步骤不同
- 折中方案：`verdict_detail` 字段（TEXT）存储 JSON，记录每个 close 子步骤的状态

```python
# close 子步骤状态写入示例
verdict_detail = json.dumps({
    "close_substeps": {
        "close_0_s6_check":         {"status": "pass"},
        "close_1_kanban_close":     {"status": "pass", "kanban_task_id": "t_xxx"},
        "close_2_gai_update":       {"status": "pass"},
        "close_3_manifest_update":  {"status": "pass"},
        "close_4_backup":           {"status": "pass", "commit_hash": "abc1234"},
        "close_5_notify":           {"status": "pass"},
        "close_6_archive":          {"status": "warning", "detail": "openspec archive skipped: no openspec dir"},
    }
})
```

这样 dashboard.py 可以解析 verdict_detail JSON 展示 close 子步骤的详细状态，但主表的 `verdict` 字段保持为 'pass'/'fail'/'conditional_pass' 作为整体判定。

### 6.4 checkpoint.py 需要新增的 migration 逻辑

```python
# pipeline/checkpoint.py v3 migration

def migrate_v2_to_v3(conn: sqlite3.Connection):
    """v2 → v3: 新增 project_config 表"""
    cursor = conn.cursor()
    cursor.execute("PRAGMA user_version")
    current = cursor.fetchone()[0]

    if current < 3:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_config (
                key    TEXT PRIMARY KEY,
                value  TEXT NOT NULL
            )
        """)
        cursor.execute("PRAGMA user_version = 3")
        conn.commit()
```

**不需要 ALTER TABLE pipeline_steps**：v2 的 verd/verdict_detail/contract_check_passed 字段已足够。

---

## 7. D-018: 24 个 untracked roundtable 文件处理

### 7.1 影响

`docs/roundtables/` 下有 24 个未被 git track 的 roundtable 文件。这是系统缺陷 DPL-012。

### 7.2 close-3（manifest 更新）的扩展

close-3 的 manifest 检查逻辑扩展为：

```python
# pipeline/state.py close-3 逻辑

import subprocess, os

def close_manifest_check(task_id: str) -> bool:
    """
    Returns True if all changed files are in manifest or auto-registered.
    """
    # 1. 获取本任务产生的所有文件变更
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1"],
        capture_output=True, text=True
    )
    changed_files = result.stdout.strip().split("\n")
    changed_files = [f for f in changed_files if f]  # 去空行

    # 2. 额外检查 untracked roundtable 文件
    untracked_roundtables = _find_untracked_roundtables()

    # 3. 合并检查列表
    all_new_files = set(changed_files + untracked_roundtables)

    missing = []
    manifest_path = "config/manifest.yaml"
    with open(manifest_path) as mf:
        manifest_content = mf.read()

    for f in all_new_files:
        if f not in manifest_content:
            missing.append(f)

    if missing:
        # 自动注册
        with open(manifest_path, "a") as mf:
            for f in missing:
                mf.write(f"  - {f}\n")
        return True  # 自动注册成功

    return True

def _find_untracked_roundtables() -> list:
    """D-018: 找 docs/roundtables/ 下未被 git track 的文件"""
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "docs/roundtables/"],
        capture_output=True, text=True
    )
    return result.stdout.strip().split("\n")
```

---

## 8. 组件总览（R5 更新板）

| 组件 | 文件 | 职责 | R5 新增 |
|------|------|------|---------|
| **state.py** | `pipeline/state.py` | 合约校验 + 分支判定 + rollback + gate_roundtable 分发 | roundtable 类型分发 (§2) + close 子步骤执行 (§3) |
| **checkpoint.py** | `pipeline/checkpoint.py` | pipeline_state.db 读写 + schema migration | project_config 表 v2→v3 (§6) |
| **config.py** | `pipeline/config.py` | project_config 读取 + 备份策略查询 | D-012 新增文件 (~30 行) |
| **init_project.py** | `pipeline/init_project.py` | 项目初始化：建库 + 写 project_config | D-012 新增文件 (~15 行) |
| **constants.py** | `pipeline/constants.py` | ProjectType 枚举 + roundtable type/assignees 映射 | D-012/D-016 新增文件 (~20 行) |
| **autopilot.sh** | `scripts/autopilot.sh` | cron 2min 轮询，推进步骤，调用备份脚本 + close 流程 | merge 备份调用 (§4) + close 7 步执行 (§3) |
| **contracts.jsonl** | `config/contracts.jsonl` | 7 步合约定义 | gate_roundtable (§2) + merge branches (§4) + close branches (§3) |
| **close.sh** | （已有，不改） | 事后闭环验证（保留，用作 final verification） | 0 行改动 |
| **dashboard.py** | `pipeline/dashboard.py` | 读 pipeline_state.db v3 → 红绿灯面板 | 解析 verdict_detail JSON → close 子步骤展示 |

---

## 9. 增量工作量估算

| 文件 | 类型 | 行数 | 说明 |
|------|------|:----:|------|
| `pipeline/constants.py` | 新增 | ~20 | ProjectType enum + ROUNDTABLE_ASSIGNEES/WORKFLOWS |
| `pipeline/config.py` | 新增 | ~30 | get_project_config() + get_backup_strategy() |
| `pipeline/init_project.py` | 新增 | ~15 | 初始化 pipeline_state.db + project_config |
| `pipeline/state.py` | 修改 | +35 | gate_roundtable 分发 + close 子步骤 + merge backup_step |
| `pipeline/checkpoint.py` | 修改 | +10 | v2→v3 migration: project_config 表 |
| `scripts/autopilot.sh` | 修改 | +30 | close 7 步流程 + backup 命令调用 |
| `config/contracts.jsonl` | 修改 | ~5 | gate_D_roundtable → gate_roundtable + merge/close 分支 |
| **总计** | | **~145 行** | Product 预估 65 行偏少；实际含 shell + Python + JSONL ~145 行 |

Product 预估 65 行仅覆盖了 Python 部分。加上 shell（autopilot.sh）和 JSONL 合约更新，实际增量 ~145 行。对 Engineer 的 11h 预估增加约 **2h**（新增 shell 逻辑 + 集成测试）。

---

## 10. 架构修正汇总

| # | Product 原意 | 架构修正 | 理由 |
|---|-------------|---------|------|
| 1 | autopilot 调用 close.sh 执行 close-1~5 | autopilot 直接执行 close 子步骤，close.sh 仅做最终验证 | close.sh 是验证脚本不是执行脚本（§3.2） |
| 2 | — | 新增 `pipeline/config.py`（project_config 只读接口） | autopilot.sh 的 shell 层和 state.py 都需要读 project_type |
| 3 | — | 新增 `pipeline/constants.py`（枚举 + 映射表） | ProjectType/ROUNDTABLE_ASSIGNEES 避免硬编码散落各处 |
| 4 | — | `gate_roundtable` 在 JSONL 中新增 `roundtable_type` 字段 | 区分 A/B/C/D 四种类型的分发（§2.2） |
| 5 | — | merge JSONL 新增 `backup_step` 字段 | 区分 pre/post 备份失败的不同重试逻辑（§4.4） |
| 6 | — | close 子步骤状态用 verdict_detail JSON 存储 | 不在主表为每个子步骤建行，保持 7 行/任务的简洁性（§6.3） |

---

## 11. 不做的事（架构边界）

- **不修改 close.sh**：104 行已验证的验证脚本，保持不动。autopilot 在 close-6 之后调用它做最终验证，但不依赖它做执行。
- **不在 pipeline_steps 表中建 close 子步骤行**：增加表复杂度但无查询收益，verdict_detail JSON 足够。
- **不让 autopilot 自动检测项目类型**：混合类的判定需要 Frank 语义，OC 一次性手动写入更可靠。
- **备份点不合并**：三个备份点捕获三种不同逻辑状态，合并会失去细粒度回滚能力。

---

> Product 补全了四个缺失维度的路标，我铺了石板：project_config 表的写入流程、gate_roundtable 的分发逻辑、close 子步骤的 autopilot 直接执行、三重备份的失败策略。close.sh 的定位修正（验证而非执行）是整个设计中最关键的架构决策——它避免了 Product 假设与现有代码实现之间的碰撞。
>
> Engineer 拿到这份设计后可以直接按 §9 的文件清单 + §5/§6 的 schema 写代码。每个函数的输入输出和失败处理都明确了。不需要猜任何接口。

---

> 架构师发言完毕。下一站：engineer（寇豆码）。
