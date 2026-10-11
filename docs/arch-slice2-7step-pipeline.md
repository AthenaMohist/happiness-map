# Slice 2 架构设计 — 完整 7 步管线（分支引擎 + rollback + fanout）

> 发言人：高见远（架构师） | 日期：2026-07-30 | 版本：v1.0
> 目标：在 Slice 1 的 5 步线性管线之上，扩展为 7 步完整管线，加入 branches 分支引擎、gate_roundtable 分发、rollback 回退、fanout 并行
> 输入：Slice 1 架构设计 + R5 统一架构 + D1 代码审查发现
> 规则：不重写 Slice 1 代码，只扩展

---

## 0. Slice 2 范围定义

### 0.1 做什么

```
Slice 1: dev → qa-exec → va → merge → close (5 步，线性，失败即停止)
Slice 2: dev → qa-d1 → qa-exec → qa-d2 → va → merge → close (7 步，带分支/回退/并行)
```

### 0.2 新增组件一览

| 组件 | 文件 | 类型 | 核心变更 |
|------|------|:----:|---------|
| `contracts.jsonl` v2 | `config/contracts.jsonl` | 修改 | 5 步 → 7 步，每步加 branches 数组（21 条分支条件） |
| `fanout.py` | `pipeline/fanout.py` | **新增** | dev + qa-d1 并行调度 + join-point 检测 |
| `pipeline/state.py` | `pipeline/state.py` | 扩展 | 分支引擎 + gate_roundtable 分发 + rollback + close 子步骤 |
| `pipeline/checkpoint.py` | `pipeline/checkpoint.py` | 扩展 | user_version=1→2 migration，加 verdict 字段 |
| `pipeline/constants.py` | `pipeline/constants.py` | 扩展 | 7 步 STEP_NAMES + ROUNDTABLE_ASSIGNEES/WORKFLOWS |
| `scripts/autopilot.sh` | `scripts/autopilot.sh` | 扩展 | fanout 调用 + rollback 处理 + qa-d1/qa-d2/va kanban 创建 |
| `pipeline_state.db` schema | `pipeline_state.db` | migration | v1→v2: ALTER ADD verdict 列 |

### 0.3 不改的组件

| 文件 | 理由 |
|------|------|
| `pipeline/config.py` | 只读 project_config，Slice 2 无新增配置项 |
| `pipeline/init_project.py` | 一次性初始化，不受 Slice 2 影响 |
| `pipeline/__init__.py` | 空文件 |
| `close.sh` | 104 行验证脚本，保持不动。autopilot 在 close-6 之后调用它做最终验证 |

### 0.4 Slice 1 → Slice 2 的 API 兼容性

| Slice 1 接口 | Slice 2 是否保持 | 说明 |
|-------------|:----------------:|------|
| `CheckpointDB(db_path)` | ✅ 不变 | 构造签名不变 |
| `CheckpointDB.upsert_step(...)` | ⚠️ 新增参数 | 加 `verdict`, `verdict_detail`, `contract_check_passed` |
| `CheckpointDB.ensure_schema()` | ⚠️ 自动 migration | 首次调用从 v1→v2 |
| `advance_pipeline(task_id, db_path, contract_path)` | ✅ 不变 | 返回 dict 格式不变 |
| `load_contracts(contract_path)` | ✅ 不变 | 额外解析 branches 字段 |
| `get_kanban_task_state(task_id)` | ✅ 不变 | |

---

## 1. 7 步管线：完整步骤链

### 1.1 步骤顺序与依赖

```
Step 1: dev        requires: []                           produces: [branch, code_changes]
Step 2: qa-d1      requires: [spec.md]                    produces: [test_plan.md]
Step 3: qa-exec    requires: [branch, code_changes,         produces: [test_report.md]
                              test_plan.md]
Step 4: qa-d2      requires: [test_report.md]              produces: [review_conclusion]
Step 5: va         requires: [test_report.md]              produces: [va_report.md]
Step 6: merge      requires: [va_report.md, test_report.md] produces: [merge_commit, backup_snapshot]
Step 7: close      requires: [merge_commit]                produces: [gai_update, manifest_update, backup_snapshot]
```

### 1.2 数据流图（含 fanout）

```
                    ┌─────────┐
                    │  START  │
                    └────┬────┘
                         │
                    ┌────▼────┐
                    │   dev   │
                    └────┬────┘
                         │ (produces: branch, code_changes)
                         │
                    ┌────▼──────────────────────────┐
                    │         FANOUT JOIN-POINT      │
                    │                                 │
                    │  ┌──────────┐                  │
                    │  │  qa-d1   │ (并行，无依赖)    │
                    │  │ produces │                  │
                    │  │test_plan │                  │
                    │  └────┬─────┘                  │
                    │       │                        │
                    │       ▼                        │
                    │  ┌──────────┐                  │
                    │  │ qa-exec  │◄── 等待 dev +    │
                    │  │          │    qa-d1 都 done │
                    │  └────┬─────┘                  │
                    │       │                        │
                    └───────┼────────────────────────┘
                            │
                       ┌────▼────┐
                       │  qa-d2  │
                       └────┬────┘
                            │
                       ┌────▼────┐
                       │   va    │
                       └────┬────┘
                            │
                       ┌────▼────┐
                       │  merge  │
                       └────┬────┘
                            │
                       ┌────▼────┐
                       │  close  │
                       └────┬────┘
                            │
                       ┌────▼────┐
                       │  DONE   │
                       └─────────┘
```

### 1.3 为什么 qa-d1 插在 dev 和 qa-exec 之间

qa-d1 的产物是 `test_plan.md`（测试方案）。qa-d1 和 dev **没有互相依赖**：
- dev 只需要 spec → 不需要 test_plan.md
- qa-d1 只需要 spec → 不需要 code_changes

因此 dev 和 qa-d1 **可以并行启动**。fanout.py 负责：
1. 检测 dev done → 立即创建 qa-d1 kanban card
2. 检测 dev done AND qa-d1 done → 推进到 qa-exec（join-point）

这是 Slice 2 唯一的并行点。其他步骤严格顺序执行。

### 1.4 STEP_NAMES 变更

```python
# Slice 1: pipeline/constants.py
STEP_NAMES = ["dev", "qa-exec", "va", "merge", "close"]

# Slice 2: pipeline/constants.py（替换）
STEP_NAMES = ["dev", "qa-d1", "qa-exec", "qa-d2", "va", "merge", "close"]
STEP_ORDER = {name: i for i, name in enumerate(STEP_NAMES)}
```

---

## 2. contracts.jsonl v2：完整 7 步合约 + 21 分支条件

### 2.1 完整 JSONL

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

### 2.2 21 分支条件汇总

| # | 步骤 | on 条件 | action | 触发场景 |
|---|------|---------|--------|---------|
| 1 | dev | `timeout` | retry (1) | dev 步骤超时 |
| 2 | dev | `timeout_after_retry` | block | dev 重试后仍超时 |
| 3 | dev | `contract_violation` | block | dev produces 缺失 |
| 4 | dev | `spec_violates_ironlaw` | gate_roundtable:D | spec 违反 SOUL 铁律 |
| 5 | qa-d1 | `test_plan_incomplete` | retry (2) | 测试方案不完整 |
| 6 | qa-d1 | `test_plan_incomplete_after_retry` | block | 重试后仍不完整 |
| 7 | qa-exec | `BLOCKER_found` | gate_roundtable:D | QA 发现 BLOCKER |
| 8 | qa-exec | `MAJOR_gt_3` | gate_roundtable:D | MAJOR > 3 |
| 9 | qa-exec | `MAJOR_le_3` | continue | MAJOR ≤ 3，可接受 |
| 10 | qa-d2 | `review_fail` | rollback→dev | D2 评审不通过 |
| 11 | qa-d2 | `review_conditional` | continue | 有条件通过 |
| 12 | qa-d2 | `requirement_unclear` | gate_roundtable:D | 需求不清 |
| 13 | va | `FALSIFIED` | gate_roundtable:D | VA 证伪 |
| 14 | va | `undetermined` | block | VA 信息不足 |
| 15 | merge | `pre_merge_backup_fail` | retry (1, pre) | 合并前备份失败 |
| 16 | merge | `conflict` | block | merge 冲突 |
| 17 | merge | `va_merge_check_fail` | rollback→dev | VA 合并验证不通过 |
| 18 | merge | `post_merge_backup_fail` | retry (2, post) | 合并后备份失败 |
| 19 | merge | `human_gate` | await_confirm | 等待 Frank 确认 |
| 20 | close | `s6_check_fail` | block | S6 检测不通过 |
| 21 | close | `step_fail` / `step_fail_*` / `retry_exhausted` | retry/block | close 子步骤失败 |

### 2.3 v1 → v2 字段变更

| 字段 | v1 | v2 |
|------|----|----|
| `pass_condition` | ✅ 字符串（人类可读） | ❌ 移除——被 `branches[].on` 替代 |
| `branches` | ❌ 不存在 | ✅ 每步 2-7 个分支条件 |
| `branches[].on` | — | ✅ 触发条件标识符 |
| `branches[].action` | — | ✅ retry/block/rollback/continue/gate_roundtable/await_confirm |
| `branches[].target` | — | * retry/rollback 时必填 |
| `branches[].max_retries` | — | * retry 时必填 |
| `branches[].reason` | — | ✅ 失败原因模板 |
| `branches[].roundtable_type` | — | * gate_roundtable 时必填 (A/B/C/D) |
| `branches[].backup_step` | — | * merge 备份失败时区分 pre/post |
| `branches[].note` | — | 附注 |

---

## 3. branches 分支引擎：state.py 核心扩展

### 3.1 分支判定器（BranchesEvaluator）

Slab 1 的 `determine_next_action()` 只做二元判断：done → 下一步 / failed → 停止。Slice 2 新增 `BranchesEvaluator` 类，在每步完成后评估 branches 数组。

```python
# pipeline/state.py — 新增类（约 80 行）

class BranchesEvaluator:
    """分支条件判定器。根据步骤结果 + 合约 branches 数组，返回下一步动作。"""

    def evaluate(
        self,
        step_name: str,
        result: dict,          # {'status': 'done'|'failed', 'detail': str, ...}
        branches: list[dict],   # 合约中的 branches 数组
        retry_count: int,       # 当前步的已重试次数
    ) -> dict:
        """
        Returns:
            {'action': 'advance'|'retry'|'block'|'rollback'|'gate_roundtable'|'await_confirm',
             'target': str|None,    # retry/rollback 的目标步骤
             'reason': str,          # 人类可读原因
             'roundtable_type': str|None,  # gate_roundtable 时
             'max_retries': int|None,       # retry 时
             'backup_step': str|None,       # merge backup 时
            }
        """
        ...
```

### 3.2 六种 action 的处理逻辑

| action | state.py 行为 | autopilot.sh 行为 |
|--------|--------------|------------------|
| `advance` | 推进到下一个 step，`upsert_step(status='pending')` | 创建下一步 kanban card |
| `retry` | 检查 `retry_count < max_retries` → `retry_count += 1`，`status='pending'`，继续等 | 重新创建同一步 kanban card |
| `block` | `upsert_step(status='blocked', error_msg=reason)` | `hermes kanban block(task_id, reason=...)` |
| `rollback` | 当前步标记 `failed`，所有中间步标记 `cancelled`，dev 步重置为 `pending` | 创建新 dev kanban card + `hermes kanban comment` 通知 |
| `gate_roundtable` | 创建 roundtable kanban task，当前管线任务 `block` | `hermes kanban create` roundtable card + `hermes kanban block` 原任务 |
| `await_confirm` | 当前步标记 `blocked`，reason 写"等待 Frank 确认" | `hermes kanban block(task_id, kind='needs_input')` |

### 3.3 完整判定流程图

```
step done/failed
       │
       ▼
读合约 branches 数组
       │
       ▼
匹配 on 条件（按顺序，第一个匹配的生效）
       │
       ├── action=retry ──────► retry_count < max_retries?
       │                             ├─ YES → 重新 pending，等待下一轮
       │                             └─ NO  → 匹配 retry_exhausted 分支
       │
       ├── action=block ──────► upsert_step(status='blocked')
       │                        autopilot → kanban block
       │
       ├── action=rollback ───► reset to dev（→ §4）
       │
       ├── action=gate_roundtable ─► create roundtable card（→ §5）
       │                             block current task
       │
       ├── action=await_confirm ──► block current task (kind=needs_input)
       │
       ├── action=continue ───► advance to next step
       │
       └── （无匹配）──────────► advance to next step（默认行为）
```

### 3.4 超时检测集成

Slice 1 的超时检测在 `determine_next_action()` 的 running 分支中。Slice 2 将超时检测独立为函数，供分支引擎调用：

```python
def _check_timeout(started_at: str | None, timeout_min: int) -> bool:
    """返回 True 表示已超时。"""
    if not started_at:
        return False
    try:
        elapsed = (
            datetime.now(timezone.utc) - datetime.fromisoformat(started_at)
        ).total_seconds() / 60
        return elapsed > timeout_min
    except (ValueError, TypeError):
        return False
```

超时后的处理通过 branches 引擎：
1. 匹配 `on: "timeout"` 分支 → retry
2. 如果 retry_count >= max_retries → 匹配 `on: "timeout_after_retry"` 分支 → block

---

## 4. rollback 机制

### 4.1 触发条件

| 步骤 | 条件 | 说明 |
|------|------|------|
| qa-d2 | `review_fail` | D2 评审不通过，代码需返工 |
| merge | `va_merge_check_fail` | VA 发现合并后验证不通过 |

注意：**va 的 FALSIFIED 不会直接触发 rollback**——它走 gate_roundtable(D) 流程，Product + Architect 裁定后才决定是 rollback 还是其他处置。

### 4.2 rollback 执行流程

```
触发 rollback(target='dev')
       │
       ▼
1. 当前步 upsert_step(status='failed', error_msg=reason)
       │
       ▼
2. 遍历当前步与 dev 之间的所有中间步骤：
   - 如果已 done → upsert_step(status='cancelled', verdict='cancelled_by_rollback')
   - 如果 pending → upsert_step(status='cancelled')
       │
       ▼
3. dev 步重置：
   - upsert_step(status='pending', retry_count=0, error_msg=None)
   - （保留 dev 原有的 artifact_paths 作为参考）
       │
       ▼
4. 通知：
   - hermes kanban comment(task_id, "[ROLLBACK] {reason} → 回退到 dev")
   - 如果配置了 notify_script → 发送通知
       │
       ▼
5. 创建新 dev kanban card：
   - hermes kanban create --title "dev [ROLLBACK]: {task_id}" --assignee game-engine
   - body 包含 rollback reason + 原始 spec 引用
```

### 4.3 rollback 的状态写入示例

```python
# pipeline/state.py — rollback 函数

def execute_rollback(
    task_id: str,
    current_step: str,      # 触发 rollback 的步骤（如 'qa-d2'）
    target_step: str,       # 回退目标（始终 'dev'）
    reason: str,
    db: CheckpointDB,
) -> dict:
    """执行 rollback：清空中间步骤，重置 target 步。"""
    current_idx = STEP_ORDER[current_step]
    target_idx = STEP_ORDER[target_step]

    # 1. 标记当前步 failed
    db.upsert_step(
        task_id=task_id, step_name=current_step,
        status='failed', error_msg=f"[ROLLBACK] {reason}"
    )

    # 2. 遍历中间步骤（current_step 和 target_step 之间的所有步）
    for name, idx in STEP_ORDER.items():
        if target_idx < idx < current_idx:
            # 只在步骤已存在时操作
            existing = db.get_step(task_id, name)
            if existing:
                db.upsert_step(
                    task_id=task_id, step_name=name,
                    status='cancelled', verdict='cancelled_by_rollback',
                    error_msg=f"因 {current_step} rollback 而取消"
                )

    # 3. 重置 target 步
    db.upsert_step(
        task_id=task_id, step_name=target_step,
        status='pending', retry_count=0, error_msg=None
    )

    return {
        'action': 'rollback',
        'target': target_step,
        'from_step': current_step,
        'reason': reason,
        'task_id': task_id,
    }
```

### 4.4 对应的文件结构

```
rollback 前 (qa-d2 review_fail):
  dev       done
  qa-d1     done
  qa-exec   done
  qa-d2     running  → 触发 rollback
  va        pending
  merge     pending
  close     pending

rollback 后:
  dev       pending   ← 重置
  qa-d1     cancelled ← 被取消
  qa-exec   cancelled ← 被取消
  qa-d2     failed    ← 失败（触发点）
  va        (如果已存在) cancelled
  merge     (不存在)
  close     (不存在)
```

---

## 5. gate_roundtable 分支引擎

### 5.1 统一分发

gate_roundtable 在 contracts.jsonl v2 中通过 `roundtable_type` 字段区分类型（替代 v1 的 `gate_D_roundtable`）：

```json
{"on":"BLOCKER_found","action":"gate_roundtable","reason":"QA 发现 BLOCKER","roundtable_type":"D"}
```

### 5.2 四类 roundtable

| 类型 | 工作流 | 参与者 | 触发条件 | 是否自动恢复 |
|:----:|--------|--------|---------|:----------:|
| **A** | vote（投票决议） | Director + Architect + Engineer + QA | Frank 说"做决定/选方案" | ❌ |
| **B** | brainstorm（头脑风暴） | 全员 | Frank 说"评估/讨论" | ❌ |
| **C** | risk_matrix（风险评估） | Product + Architect + Engineer | Frank 说"有风险吗" | ❌ |
| **D** | review（评审裁定） | Product + Architect | BLOCKER / MAJOR>3 / FALSIFIED / spec违反铁律 | ❌（裁定后手动恢复） |

### 5.3 常量化映射表

```python
# pipeline/constants.py — Slice 2 新增

ROUNDTABLE_ASSIGNEES = {
    "A": ["game-director", "game-architect", "game-engine", "game-qa"],
    "B": ["game-director", "game-architect", "game-engine", "game-qa"],
    "C": ["game-director", "game-architect", "game-engine"],
    "D": ["game-director", "game-architect"],
}

ROUNDTABLE_WORKFLOWS = {
    "A": "vote",
    "B": "brainstorm",
    "C": "risk_matrix",
    "D": "review",
}

ROUNDTABLE_BLOCK_KIND = {
    "A": "dependency",     # 等 roundtable done → 自动恢复
    "B": "needs_input",    # 等 Frank 指令 → 人工恢复
    "C": "dependency",     # 等 roundtable done → 自动恢复
    "D": "dependency",     # 等 roundtable done → 自动恢复
}
```

### 5.4 gate_roundtable 执行函数

```python
# pipeline/state.py — 新增函数（约 50 行）

def handle_gate_roundtable(
    roundtable_type: str,
    reason: str,
    context: dict,   # {'task_id': str, 'step': str, 'kanban_task_id': str}
    db: CheckpointDB,
) -> dict:
    """
    创建 roundtable kanban task，block 当前管线任务。
    返回 roundtable 的 task_id 和 block 状态。
    """
    from pipeline.constants import ROUNDTABLE_ASSIGNEES, ROUNDTABLE_WORKFLOWS

    if roundtable_type not in ROUNDTABLE_ASSIGNEES:
        raise ValueError(f"Unknown roundtable_type: {roundtable_type}")

    assignees = ROUNDTABLE_ASSIGNEES[roundtable_type]
    workflow  = ROUNDTABLE_WORKFLOWS[roundtable_type]

    # D 类特殊规则：3 个强制议题
    mandatory_topics = ""
    if roundtable_type == "D":
        mandatory_topics = (
            "强制议题:\n"
            "  - 分级判定是否正确\n"
            "  - 处置方式是否合理\n"
            "  - 修复难度评估\n"
        )

    # B 类特殊规则：不产生 kanban 开发任务
    creates_dev_tasks = (roundtable_type != "B")

    # 构造 roundtable body
    body = (
        f"类型: {roundtable_type} ({workflow})\n"
        f"原因: {reason}\n"
        f"管线任务: {context['task_id']}\n"
        f"触发步骤: {context['step']}\n"
        f"参与者: {', '.join(assignees)}\n"
        + (f"产生开发任务: {'是' if creates_dev_tasks else '否（B-brainstorming 特殊规则）'}\n")
        + mandatory_topics
    )

    return {
        'action': 'gate_roundtable',
        'roundtable_type': roundtable_type,
        'workflow': workflow,
        'assignees': assignees,
        'body': body,
        'reason': reason,
        'task_id': context['task_id'],
        'step': context['step'],
        'creates_dev_tasks': creates_dev_tasks,
    }
```

### 5.5 autopilot.sh 中的 gate_roundtable 处理

```bash
# autopilot.sh — gate_roundtable 段（新增）

gate_roundtable)
    RT_TYPE=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('roundtable_type','D'))")
    RT_BODY=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('body',''))")
    RT_ASSIGNEES=$(echo "$RESULT" | python3 -c "import sys,json; print(','.join(json.load(sys.stdin).get('assignees',[])))")

    # 创建 roundtable kanban card
    RT_TASK_ID=$(hermes kanban create \
        --title "[ROUNDTABLE-$RT_TYPE] $TASK_ID: $DETAIL" \
        --assignee "$(echo $RT_ASSIGNEES | cut -d',' -f1)" \
        --body "$RT_BODY" \
        --priority 50 \
        2>/dev/null)

    if [ -n "$RT_TASK_ID" ]; then
        # 在原任务上 comment + block
        hermes kanban comment "$TASK_ID" \
            "[AUTOPILOT: GATE] ${RT_TYPE} 类 roundtable 已创建: $RT_TASK_ID" \
            2>/dev/null || true
        hermes kanban block "$TASK_ID" \
            --reason "等待 ${RT_TYPE} 类 roundtable ($RT_TASK_ID) 裁定" \
            2>/dev/null || true
    fi
    ;;
```

---

## 6. fanout.py：dev + qa-d1 并行调度

### 6.1 为什么需要 fanout

dev 和 qa-d1 **没有相互依赖**：
- dev 需要 spec.md → 不需要 test_plan.md
- qa-d1 需要 spec.md → 不需要 code_changes

现有 state.py 是串行的：每步 done 才推进到下一步。fanout.py 在 dev 启动后立即创建 qa-d1，二者并行执行。

### 6.2 join-point 检测

qa-exec 的 requires 包含 `[branch, code_changes, test_plan.md]`——它同时依赖 dev 和 qa-d1 的产物。join-point 检测在 autopilot 轮询时执行：

```
每轮 cron 轮询时:
  1. state.py advance_pipeline(task_id)
  2. 如果 current_step=qa-exec 且 status=pending:
     a. 检查 dev 是否 done → 否 → wait
     b. 检查 qa-d1 是否 done → 否 → wait
     c. 两者都 done → upsert_step(qa-exec, status='running')
```

### 6.3 fanout.py 接口

```python
# pipeline/fanout.py — 新增文件（约 60 行）

"""pipeline/fanout.py — dev + qa-d1 并行调度器

职责：
  1. detect: 检测 dev 已 done 但 qa-d1 尚未创建 → create qa-d1
  2. join: 检测 dev + qa-d1 都 done → 推进到 qa-exec
"""

from pipeline.checkpoint import CheckpointDB

FANOUT_PAIRS = [
    # (上游步骤, 并行步骤, join 步骤)
    ("dev", "qa-d1", "qa-exec"),
]


def detect_fanout_opportunity(task_id: str, db: CheckpointDB) -> tuple[str, str] | None:
    """
    检测是否有可并行启动的步骤。

    Returns: (upstream_step, parallel_step) | None
    例：dev done 但 qa-d1 未创建 → ('dev', 'qa-d1')
    """
    for upstream, parallel, join_step in FANOUT_PAIRS:
        upstream_step = db.get_step(task_id, upstream)
        if upstream_step and upstream_step["status"] == "done":
            parallel_step = db.get_step(task_id, parallel)
            if parallel_step is None:
                return (upstream, parallel)
    return None


def check_join_point(task_id: str, db: CheckpointDB) -> bool:
    """
    检查 join-point 是否满足：所有前置步骤都 done。

    Returns: True = 可以推进到 join 步骤
    """
    for upstream, parallel, join_step in FANOUT_PAIRS:
        join = db.get_step(task_id, join_step)
        if join is None or join["status"] == "pending":
            upstream_done = db.get_step(task_id, upstream)
            parallel_done = db.get_step(task_id, parallel)
            if (upstream_done and upstream_done["status"] == "done" and
                parallel_done and parallel_done["status"] == "done"):
                return True
    return False
```

### 6.4 autopilot.sh 中的 fanout 集成

```bash
# autopilot.sh — fanout 段（在现有 "对于每个活跃任务推进" 循环内，advance_pipeline 之后）

# 检测 fanout 机会：dev done → 立即启动 qa-d1
FANOUT=$(python3 -c "
import sys, json; sys.path.insert(0, '$REPO_ROOT')
from pipeline.fanout import detect_fanout_opportunity
from pipeline.checkpoint import CheckpointDB
db = CheckpointDB('$REPO_ROOT/pipeline_state.db')
result = detect_fanout_opportunity('$TASK_ID', db)
print(json.dumps({'upstream': result[0], 'parallel': result[1]}) if result else 'null')
" 2>/dev/null)

if [ "$FANOUT" != "null" ] && [ -n "$FANOUT" ]; then
    PARALLEL_STEP=$(echo "$FANOUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['parallel'])")
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') $LOG_TAG $TASK_ID: fanout → 启动并行步骤 $PARALLEL_STEP"

    case "$PARALLEL_STEP" in
        qa-d1)
            hermes kanban create \
                --title "qa-d1: $TASK_ID" \
                --assignee game-qa \
                --body "编写测试方案。task_id=$TASK_ID" \
                2>/dev/null || echo "$LOG_TAG 创建 qa-d1 kanban card 失败"

            python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT')
from pipeline.checkpoint import CheckpointDB
db = CheckpointDB('$REPO_ROOT/pipeline_state.db')
db.upsert_step('$TASK_ID', 'qa-d1', status='pending', assigned_agent='game-qa')
" 2>/dev/null
            ;;
    esac
fi
```

---

## 7. pipeline_state.db v1 → v2 migration

### 7.1 D1-F3 修正回顾

Slice 1 当前 `pipeline/checkpoint.py` 的 SCHEMA_SQL 存在 D1-F3 发现的不一致：
- `PRAGMA user_version = 2` → 应为 1（Product 裁定：v1 不含 verdict 列）
- 含 `verdict`, `verdict_detail`, `contract_check_passed` 三列 → 应删除

Slice 2 在修正 v1 的基础上，通过 migration 添加 verdict 列。

### 7.2 修正后的 v1 schema（checkpoint.py 变更）

```sql
PRAGMA user_version = 1;

CREATE TABLE IF NOT EXISTS pipeline_steps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT NOT NULL,
    step_name       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    artifact_paths  TEXT NOT NULL DEFAULT '[]',
    started_at      TEXT,
    finished_at     TEXT,
    error_msg       TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    assigned_agent  TEXT,
    openspec_ref    TEXT,
    -- Slice 2 新增（通过 migration 添加）:
    -- verdict       TEXT,
    -- verdict_detail TEXT,
    -- contract_check_passed INTEGER,
    UNIQUE(task_id, step_name)
);
```

### 7.3 v1 → v2 migration 逻辑

```python
# pipeline/checkpoint.py — 新增 migration 方法

def migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """v1 → v2: ALTER ADD verdict 三列。"""
    cursor = conn.cursor()
    cursor.execute("PRAGMA user_version")
    current = cursor.fetchone()[0]

    if current < 2:
        # 只添加不存在的列（幂等）
        for col, col_def in [
            ("verdict", "TEXT"),
            ("verdict_detail", "TEXT"),
            ("contract_check_passed", "INTEGER"),
        ]:
            try:
                cursor.execute(
                    f"ALTER TABLE pipeline_steps ADD COLUMN {col} {col_def}"
                )
            except sqlite3.OperationalError:
                pass  # 列已存在，跳过

        cursor.execute("PRAGMA user_version = 2")
        conn.commit()
```

### 7.4 ensure_schema() 变更

```python
def ensure_schema(self) -> None:
    """幂等建表 + 自动 migration。"""
    conn = self._connect()
    try:
        conn.executescript(SCHEMA_SQL)  # v1 schema（已修正，user_version=1）
        conn.commit()
        migrate_v1_to_v2(conn)          # 自动迁移到 v2
    finally:
        conn.close()
```

### 7.5 CheckpointDB.upsert_step() 变更

新增三个可选参数，保持向后兼容：

```python
def upsert_step(
    self,
    task_id: str,
    step_name: str,
    status: str = "pending",
    artifact_paths: Optional[list[str]] = None,
    error_msg: Optional[str] = None,
    assigned_agent: Optional[str] = None,
    openspec_ref: Optional[str] = None,
    retry_count: int = 0,
    # Slice 2 新增:
    verdict: Optional[str] = None,           # pass|fail|conditional_pass|FALSIFIED|VERIFIED|blocked|timeout|cancelled_by_rollback
    verdict_detail: Optional[str] = None,     # JSON string: close 子步骤状态等
    contract_check_passed: Optional[int] = None,  # NULL|0|1|2
) -> None:
    ...
```

### 7.6 verdict 枚举值

| verdict | 含义 | 触发场景 |
|---------|------|---------|
| `pass` | 步骤通过 | 正常完成 |
| `fail` | 步骤失败 | error 条件触发 |
| `conditional_pass` | 有条件通过 | qa-d2 review_conditional / close 最终验证有 warning |
| `FALSIFIED` | VA 证伪 | va step |
| `VERIFIED` | VA 验证通过 | va step |
| `blocked` | 被阻塞 | block action |
| `timeout` | 超时 | timeout 条件 |
| `cancelled_by_rollback` | 因 rollback 取消 | rollback 时的中间步骤 |

---

## 8. 组件间接口契约（Slice 2 更新版）

### 8.1 文件依赖图

```
pipeline/constants.py          ← 零依赖（7 步 STEP_NAMES + ROUNDTABLE 映射）
       │
       ▼
pipeline/checkpoint.py         ← 依赖 sqlite3（v1→v2 migration，verdict 列）
       │
       ├──────────────┐
       ▼              ▼
pipeline/config.py  pipeline/fanout.py    ← 各自依赖 checkpoint.py
       │              │
       ▼              ▼
pipeline/state.py              ← 依赖 constants + config + fanout + checkpoint
       │                           + subprocess（hermes kanban）
       │                           + BranchesEvaluator + gate_roundtable
       │
       ▼
scripts/autopilot.sh           ← 依赖 state.py + fanout.py（python3 -c）
                                    + flock（系统工具）
                                    + gate_roundtable 的 kanban_create/block
```

### 8.2 数据流向（含 Slice 2 新增路径）

```
日常运行:
  cron → autopilot.sh
            │
            ├── 1. advance_pipeline(task_id)  → state.py
            │       ├── 读 contracts.jsonl v2（7 步 + branches）
            │       ├── 读 pipeline_state.db v2（checkpoint + verdict）
            │       ├── 读 kanban.db（via hermes kanban show）
            │       ├── BranchesEvaluator → 判定 action
            │       └── 写 pipeline_state.db (checkpoint + verdict)
            │
            ├── 2. detect_fanout() → fanout.py
            │       └── dev done + qa-d1 未创建 → 创建 qa-d1 kanban card
            │
            ├── 3. 根据 state.py 返回的 action:
            │       ├── start_step → 创建 kanban card（含 qa-d1, va）
            │       ├── gate_roundtable → 创建 roundtable card + block 原任务
            │       ├── rollback → 执行 rollback + 创建新 dev card
            │       ├── wait → 记录日志
            │       ├── complete → 记录完成
            │       └── error → kanban_comment 告警
            │
            └── 4. close 子步骤（autopilot 直接执行）
                    close-0: S6 检查
                    close-1: kanban complete
                    close-2: GAI 更新
                    close-3: manifest 更新
                    close-4: 备份推送
                    close-5: 并发通知
                    close-6: 归档 + close.sh 最终验证
```

### 8.3 state.py 新增的 action 类型

| action | Slice 1 | Slice 2 |
|--------|:------:|:------:|
| `start_step` | ✅ | ✅ |
| `wait` | ✅ | ✅ |
| `complete` | ✅ | ✅ |
| `error` | ✅ | ✅ |
| `retry` | — | ✅ 新增 |
| `block` | — | ✅ 新增 |
| `rollback` | — | ✅ 新增 |
| `gate_roundtable` | — | ✅ 新增 |
| `await_confirm` | — | ✅ 新增 |

---

## 9. autopilot.sh 扩展

### 9.1 新增的 step → kanban card 映射

```bash
# autopilot.sh — 扩展 start_step 段

case "$STEP" in
    dev)
        hermes kanban create --title "dev: $TASK_ID" --assignee game-engine ...
        ;;
    qa-d1)                                     # ← 新增
        hermes kanban create --title "qa-d1: $TASK_ID" --assignee game-qa \
            --body "编写测试方案。task_id=$TASK_ID" ...
        ;;
    qa-exec)
        hermes kanban create --title "qa-exec: $TASK_ID" --assignee game-qa ...
        ;;
    qa-d2)                                     # ← 新增
        hermes kanban create --title "qa-d2: $TASK_ID" --assignee game-qa \
            --body "D2 评审测试报告。task_id=$TASK_ID" ...
        ;;
    va)
        hermes kanban create --title "va: $TASK_ID" --assignee verifier ...
        ;;
    merge)
        # 同 Slice 1
        ;;
    close)
        # 展开为 7 个子步骤
        close_pipeline_step "$TASK_ID"
        ;;
esac
```

### 9.2 close 子步骤函数

```bash
close_pipeline_step() {
    local TASK_ID="$1"

    # close-0: S6 检测
    local S6_OK
    S6_OK=$(python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT')
from pipeline.checkpoint import CheckpointDB
from pipeline.constants import STEP_NAMES
db = CheckpointDB('$REPO_ROOT/pipeline_state.db')
steps = db.get_all_steps('$TASK_ID')
done = [s['step_name'] for s in steps if s['status'] == 'done']
missing = [s for s in STEP_NAMES[:6] if s not in done]  # 前 6 步
print('OK' if not missing else 'FAIL: ' + ','.join(missing))
" 2>/dev/null)

    if [[ "$S6_OK" != OK* ]]; then
        echo "$LOG_TAG $TASK_ID: close-0 S6 检测失败 — $S6_OK"
        python3 -c "from pipeline.checkpoint import CheckpointDB; CheckpointDB('$REPO_ROOT/pipeline_state.db').upsert_step('$TASK_ID','close','blocked',error_msg='S6检测失败',verdict='blocked')"
        return 1
    fi

    # close-1: 关闭 kanban
    hermes kanban complete "$TASK_ID" 2>/dev/null || {
        echo "$LOG_TAG $TASK_ID: close-1 失败"
        return 1
    }

    # close-2: GAI 更新
    python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT')
from pipeline.state import _close_gai_update
_close_gai_update('$TASK_ID')
" 2>/dev/null || {
        echo "$LOG_TAG $TASK_ID: close-2 失败"
        return 1
    }

    # close-3: manifest 更新
    python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT')
from pipeline.state import _close_manifest_update
_close_manifest_update('$TASK_ID')
" 2>/dev/null || {
        echo "$LOG_TAG $TASK_ID: close-3 失败"
        return 1
    }

    # close-4: 备份推送
    python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT')
from pipeline.state import _close_backup
_close_backup('$TASK_ID')
" 2>/dev/null || {
        echo "$LOG_TAG $TASK_ID: close-4 失败"
        return 1
    }

    # close-5: 通知（失败不阻塞）
    python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT')
from pipeline.state import _close_notify
_close_notify('$TASK_ID')
" 2>/dev/null || true

    # close-6: 归档 + close.sh 最终验证
    python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT')
from pipeline.state import _close_archive
_close_archive('$TASK_ID')
" 2>/dev/null || true

    # 最终验证
    if [ -f "/root/.hermes/profiles/orchestrator/scripts/close.sh" ]; then
        bash /root/.hermes/profiles/orchestrator/scripts/close.sh "$TASK_ID" 2>/dev/null || true
    fi

    python3 -c "
from pipeline.checkpoint import CheckpointDB
db = CheckpointDB('$REPO_ROOT/pipeline_state.db')
db.upsert_step('$TASK_ID', 'close', 'done', verdict='pass')
"
}
```

---

## 10. pipeline/ 目录结构（Slice 2 更新版）

```
pipeline/
├── __init__.py           # 空文件（不变）
├── constants.py          # ~45 行（+20）：STEP_NAMES 7 步 + ROUNDTABLE 映射表
├── checkpoint.py         # ~270 行（+25）：v1→v2 migration + verdict 字段支持
├── config.py             # ~40 行（不变）
├── state.py              # ~200 行（+80）：BranchesEvaluator + gate_roundtable + rollback + close 子步骤
├── fanout.py             # ~60 行（新增）：dev + qa-d1 并行调度 + join-point
└── init_project.py       # ~58 行（不变）

config/
└── contracts.jsonl       # v2：7 步 + 21 分支条件

scripts/
├── autopilot.sh          # ~250 行（+80）：fanout + rollback + gate_roundtable + close 子步骤
└── ...
```

---

## 11. 增量工作量估算

| 文件 | 类型 | 行数 | 说明 |
|------|------|:----:|------|
| `pipeline/constants.py` | 修改 | +20 | STEP_NAMES 7 步 + ROUNDTABLE_ASSIGNEES/WORKFLOWS |
| `pipeline/checkpoint.py` | 修改 | +25 | user_version=2→1 修正 + v1→v2 migration + verdict 参数 |
| `pipeline/fanout.py` | **新增** | ~60 | dev+qa-d1 并行 + join-point |
| `pipeline/state.py` | 修改 | +80 | BranchesEvaluator + gate_roundtable + rollback + close 子步骤 |
| `pipeline/config.py` | 不变 | 0 | — |
| `pipeline/init_project.py` | 不变 | 0 | — |
| `scripts/autopilot.sh` | 修改 | +80 | fanout 集成 + rollback 处理 + gate_roundtable + close 子步骤 |
| `config/contracts.jsonl` | 修改 | +2 | 5→7 步 + 21 branches |
| **Slice 2 总计** | | **~267 行** | 含 Python + Shell + JSONL |

---

## 12. 不做的事（架构边界）

| 项目 | 归属 | 理由 |
|------|:----:|------|
| close.sh 修改 | — | 104 行验证脚本保持不动，autopilot 在 close-6 后调用做最终验证 |
| DPL-011 boot_context | Slice 3 | .hermes.md 动态段的生成和注入 |
| dashboard 红绿灯 | Slice 3 | 读 pipeline_state.db 的可视化面板 |
| B-brainstorming 自动恢复 | — | B 类 roundtable 的 block 用 `kind='needs_input'`，永远等待人工 |
| fanout 扩展到其他步骤 | — | 只有 dev + qa-d1 是真正的无依赖并行。其他步骤有严格顺序依赖 |
| pipeline_steps 表建 close 子步骤行 | — | close 子步骤状态写 verdict_detail JSON，不在主表膨胀 |

---

## 13. 技术风险点

| # | 风险 | 级别 | 缓解 |
|---|------|:----:|------|
| 1 | v1→v2 migration 与现有 v2 schema 冲突（D1-F3 未修复） | MAJOR | 先修正 checkpoint.py 回到 v1 基准，再做 v1→v2 |
| 2 | fanout 并行时 cron 两轮之间状态不一致 | MINOR | fanout 在同一轮 cron 中的 advance_pipeline 之后立即检测 + 创建 |
| 3 | rollback 后 dev 步骤的产物路径丢失 | MINOR | rollback 保留 dev 的 artifact_paths，在 body 中引用 |
| 4 | gate_roundtable card 创建失败但 block 已写入 | MINOR | 先创建 card → 获取 task_id → 再 block 原任务 |
| 5 | contracts.jsonl v2 热加载兼容 v1 调用 | — | v2 新增字段不影响 v1 消费（branches 为空 → 走默认 advance 逻辑） |

---

## 14. 一句话总结

> Slice 2 把 Slice 1 的 5 步线性管线扩展为 7 步完整管线，加入 branches 分支引擎（21 条条件 → 6 种 action）、gate_roundtable 统一分发（4 类 roundtable）、rollback 回退（任意 FALSIFIED → 回到 dev）、fanout 并行（dev + qa-d1 同时启动，qa-exec join）。不重写 Slice 1 代码，约 267 行增量（Python + Shell + JSONL）。每个函数的输入输出和分支处理都明确了，Engineer 可以直接按 §8.2 的数据流 + §10 的目录结构 + §2.1 的合约写代码。

---

> 架构师发言完毕。下一站：engineer（寇豆码），请按 Slice 2 Step 2 开始编码实现。
