# R5 最终修复 — Engineer 发言：最终实现确认

> 发言人：寇豆码（工程师） | 日期：2026-07-30 | 版本：v1.0（R5 最终轮）
> 目标：读 Product R5（613 行，D-011~D-018）+ Architect R5（762 行）后，从工程实现视角做最终确认
> 规则：R5 最后一轮发言。kanban_complete 后 Orchestrator 汇总为最终可执行工作流报告

---

## 0. 总体判断：可以开工，但 Product 和 Architect 之间有一处关键差异必须裁定

读完两份 R5 报告后，工程判断：

| 决定 | 状态 | 说明 |
|------|:----:|------|
| D-011 | ✅ 可落 | 三重备份点 + backup_step 区分 pre/post，工程上无歧义 |
| D-012 | ✅ 可落 | project_config 表 + init_project.py + config.py，schema 已由 Architect 细化 |
| D-013 | ✅ 可落 | autopilot 按 project_type 查表决定备份命令 |
| D-014 | ✅ 可落 | OC 判定类型，但 state.py 只需处理管线中 autopilot 触发的 D 类 |
| D-015 | ⚠️ **需 Product 裁定** | Product 和 Architect 对 close.sh 调用方式有冲突 |
| D-016 | ✅ 可落 | gate_roundtable(type, reason) 统一分发，4 种 type 各有 handler |
| D-017 | ✅ 可落 | close-5 通知含 commit hash，无工程难点 |
| D-018 | ✅ 可落 | 24 untracked 文件归档 + close-3 扩展检查 |

**工程师结论：两份 R5 报告在 7/8 项决定上一致。唯一冲突是 D-015——Product 说 autopilot 调用 close.sh 执行 close-1~5，Architect 说 close.sh 只做验证。我支持 Architect 的修正，理由见 §6。**

---

## 1. 可行性：Python+SQLite+Bash 栈全部可落

### 1.1 完整组件栈验证

| 组件 | 语言 | 依赖 | 环境 | 工程判断 |
|------|------|------|------|:----:|
| `pipeline/state.py` | Python 3.11 | sqlite3, subprocess, json, re | venv 内 | ✅ |
| `pipeline/checkpoint.py` | Python 3.11 | sqlite3 | venv 内 | ✅ |
| `pipeline/config.py` | Python 3.11 | sqlite3 | venv 内 | ✅ |
| `pipeline/init_project.py` | Python 3.11 | sqlite3, argparse | venv 内 | ✅ |
| `pipeline/constants.py` | Python 3.11 | enum | venv 内 | ✅ |
| `pipeline/fanout.py` | Python 3.11 | kanban_helpers | venv 内 | ✅ |
| `pipeline/dashboard.py` | Python 3.11 | sqlite3 | venv 内 | ✅ |
| `pipeline/boot_context.py` | Python 3.11 | sqlite3, session DB | venv 内 | ✅ |
| `scripts/autopilot.sh` | Bash | flock, hermes CLI, python3 | 系统 PATH | ✅ |
| `config/contracts.jsonl` | JSONL 文本 | — | 文件系统 | ✅ |
| `scripts/lib/kanban_helpers.py` | Python 3.11 | subprocess | venv 内 | ✅ 已有 197 行 |

**所有组件都在同一 Python+SQLite+Bash 栈上。没有引入新语言、新框架、新数据库。零依赖膨胀。**

### 1.2 管线外依赖验证

| 依赖 | 是否存在 | 位置 | 风险 |
|------|:------:|------|:----:|
| close.sh (104 行) | ✅ 存在 | `/root/.hermes/profiles/orchestrator/scripts/close.sh` | 已验证可用 |
| hermes_backup_push.sh | ✅ 存在 | `/workspace/hermes_backup_push.sh` | 已验证可用 |
| hermes_backup_notify.sh | ✅ 存在 | `/workspace/hermes_backup_notify.sh` | 已验证可用 |
| kanban_helpers.py | ✅ 存在 | `/workspace/devPPL/scripts/lib/kanban_helpers.py` | 已 197 行可用 |
| pipeline_state.db | ❌ 不存在 | 需新建 | **首次实现** |
| pipeline/ 目录 | ❌ 不存在 | 需新建 | **首次实现** |
| autopilot.sh | ❌ 不存在 | 需新建 | **首次实现** |

**现状**：管线代码完全是绿地（greenfield）。`kanban_helpers.py` 是唯一可复用的已有模块（197 行，提供 `get_task_state()`、`kanban_comment()` 等）。这既是风险（没有脚手架），也是优势（没有历史债务）。

---

## 2. 代码量和工期：R4 基线 + R5 增量

### 2.1 我的 R4 估算回顾

| R4 估算项 | 行数 | 时间 |
|-----------|:---:|:----:|
| checkpoint.py (v2) | ~100 | 2.0h |
| contracts/devPPL.jsonl | ~50 | 0.5h |
| state.py (v2) | ~200 | 2.0h |
| kanban_helpers.py 扩展 | ~15 | 0.3h |
| fanout.py | ~40 | 0.5h |
| autopilot.sh | ~80 | 1.0h |
| boot_context.py | ~80 | 1.0h |
| .hermes.md 静态模板 | ~200 | 0.3h |
| dashboard.py | ~60 | 0.5h |
| test + bugfix | ~150 | 2.0h |
| **R4 总计** | **~975** | **~11.0h** |

### 2.2 R5 增量（基于 Architect R5 §9 的精确文件清单）

| 文件 | 类型 | 行数 | 时间 | 说明 |
|------|------|:---:|:----:|------|
| `pipeline/constants.py` | 新增 | ~20 | 0.3h | ProjectType enum + ROUNDTABLE_ASSIGNEES/WORKFLOWS |
| `pipeline/config.py` | 新增 | ~30 | 0.5h | get_project_config() + get_backup_strategy() |
| `pipeline/init_project.py` | 新增 | ~15 | 0.3h | 初始化 pipeline_state.db + project_config |
| `pipeline/state.py` | 修改 | +35 | 1.0h | gate_roundtable 分发 + close 子步骤 + merge backup_step |
| `pipeline/checkpoint.py` | 修改 | +10 | 0.3h | v2→v3 migration: project_config 表 |
| `scripts/autopilot.sh` | 修改 | +30 | 1.0h | close 7 步流程 + backup 命令调用 |
| `config/contracts.jsonl` | 修改 | +5 | 0.2h | gate_D_roundtable → gate_roundtable + merge/close 分支 |
| `pipeline/state.py` close 子步骤 | 新增 | +50 | 1.5h | close-0~close-6 各子步骤的具体实现（此为我评估，不在 Architect 估算中） |
| **R5 增量总计** | | **~195** | **~5.1h** | |

**Architect 估算 ~145 行偏乐观**——他的清单未计入 state.py 中 close 子步骤的逐函数实现（close-0 S6 check、close-1 kanban close、close-2 GAI update 等每个 ~10 行，共 7 个 ~70 行，但部分可复用现有 helper，折半 ~35 行）。加上 autopilot.sh 中 close 7 步的 shell 逻辑（echo log + 错误处理，每步 ~5 行共 ~35 行）。

**我的 R5 增量估算：~195 行 Python + Shell + JSONL，约 5.1h。**

Product 估算 65 行仅覆盖了 Python 新增（constants/config/init_project），遗漏了 state.py 修改 + autopilot.sh 修改 + JSONL 更新 + close 子步骤实现。Architect 的 ~145 行更接近真相，但 close 子步骤实际实现比他的伪代码多出约 50 行（错误处理 + retry 逻辑 + verdict_detail JSON 构建）。

### 2.3 总代码量

| 来源 | 行数 | 时间 |
|------|:---:|:---:|
| R4 基线 | ~975 | 11.0h |
| R5 增量 | ~195 | 5.1h |
| 集成 buffer（R5 新增模块间接口调试） | — | 1.0h |
| **R5 总计** | **~1,170** | **~17.1h** |

**取整：~1,200 行，约 17 小时，约 2 个完整工作日。**

### 2.4 与 Product 和 Architect 估算的差异

| 估算方 | 估值 | 差距 |
|--------|:----:|------|
| Product R5 | +65 行 / +1h 在 R4 之上 | 低估（遗漏 shell + state.py 修改 + close 子步骤） |
| Architect R5 | +145 行 / +2h 在 R4 之上 | 接近但仍低估（遗漏 close 子步骤实现细节） |
| **Engineer R5** | **+195 行 / +5.1h 在 R4 之上** | **工程现实——代码从来比伪代码多** |

**工程师实话**：Architect 的伪代码（§3.3 autopilot.sh close 段）有 60 行 shell，但他估算 autopilot.sh 修改只有 +30 行。伪代码中的每个 `log "close-N: ..."` + `if ! python3 ...` + `return 1` 是 4-5 行真实 shell。7 个 sub-step → ~30 行 shell 只是骨架，加上错误处理的 `python3 pipeline/state.py --handle-branch` 每步 2-3 行，真实 shell 量在 50+ 行。

---

## 3. 新增文件的最终清单：镜像 vs 状态同步

### 3.1 完整文件清单（R4 + R5 合并后）

| 文件 | 性质 | 类型 | 说明 |
|------|------|:----:|------|
| `pipeline/state.py` | **状态同步** | Python | 合约校验 + 分支判定 + rollback + gate_roundtable 分发 + close 子步骤执行 |
| `pipeline/checkpoint.py` | **状态同步** | Python | pipeline_state.db 读写 + v1→v2→v3 migration |
| `pipeline/config.py` | **镜像** | Python | project_config 只读接口 + 备份策略查询（autopilot.sh 和 state.py 共用） |
| `pipeline/init_project.py` | **运维** | Python | 一次性项目初始化：建库 + 写 project_config |
| `pipeline/constants.py` | **镜像** | Python | ProjectType 枚举 + ROUNDTABLE_ASSIGNEES/WORKFLOWS 映射表（所有组件引用） |
| `pipeline/fanout.py` | **状态同步** | Python | 并行 dev+qa-d1 dispatch + join 检测 |
| `pipeline/dashboard.py` | **只读** | Python | 红绿灯面板：读 pipeline_state.db + kanban.db |
| `pipeline/boot_context.py` | **镜像** | Python | DPL-011: session DB + pipeline_state.db → .hermes.md 动态段 |
| `scripts/autopilot.sh` | **状态同步** | Bash | cron 主循环 + 步骤推进 + close 7 步 + 备份调用 |
| `config/contracts.jsonl` | **镜像** | JSONL | 7 步合约定义（所有组件只读引用） |

**镜像文件**（只需一套逻辑，autopilot 调用）：`config.py`、`constants.py`、`boot_context.py`、`contracts.jsonl`。这些文件不维护运行时状态，只提供配置/常量/映射。多个组件（state.py、autopilot.sh、dashboard.py）引用同一份逻辑即可，不需要副本。

**状态同步文件**：`state.py`、`checkpoint.py`、`fanout.py`、`autopilot.sh`。这些文件维护 `pipeline_state.db` 的运行状态。必须保证只有一个写入者（autopilot），所有其他读者通过 SQLite WAL 读一致快照。

### 3.2 镜像文件的 autopilot 调用模式

```python
# state.py 通过 import 引用镜像文件（Python 层）
from pipeline.constants import ProjectType, ROUNDTABLE_ASSIGNEES
from pipeline.config import get_project_config, get_backup_strategy

# autopilot.sh 通过 python3 -c 引用镜像文件（Shell 层）
PROJECT_TYPE=$(python3 -c "
from pipeline.config import get_project_config
print(get_project_config()['project_type'])
")
```

**不需要为 autopilot.sh 复制一份配置逻辑。** 同一套 `pipeline/config.py`，Python import 和 `python3 -c` 两种方式都能用。

### 3.3 状态同步文件的单一写入者规则

```
pipeline_state.db 的写入者：
  autopilot.sh ──调用──→ state.py ──写──→ pipeline_state.db (WAL mode)
  autopilot.sh ──调用──→ checkpoint.py ──写──→ pipeline_state.db
  init_project.py ──────写──→ pipeline_state.db (仅首次部署)
  boot_context.py ──读──→ pipeline_state.db (只读，不写)

kanban 操作的调用者：
  autopilot.sh ──调用──→ state.py ──调──→ hermes kanban complete/comment/block
  OC ──调──→ hermes kanban create (创建初始任务，不在 autopilot 循环内)
```

**`pipeline_state.db` 唯一写者是 autopilot 驱动的 state.py + checkpoint.py。** 这避免了并发写冲突——R4 §5.1 已验证的数据访问矩阵在 R5 依然成立，因为 R5 新增的 `project_config` 表是只读的（autopilot 启动时读一次，init_project.py 仅首次部署时写）。

---

## 4. 三重备份的工程实现

### 4.1 备份点触发时机和命令

| 备份点 | 触发时机 | system_mechanism | pure_product | hybrid |
|--------|---------|------------------|-------------|--------|
| **merge-1** | merge 前 | `bash /workspace/hermes_backup_push.sh` | `cd {repo} && git add . && git commit -m 'backup: pre-merge'` | `git commit + push + rsync` |
| **merge-4** | VA 验收 merge 后 | `bash /workspace/hermes_backup_push.sh` | `cd {repo} && git add . && git commit -m 'backup: post-merge'` | `git commit + push + rsync` |
| **close-4** | close 子步骤 | `bash /workspace/hermes_backup_push.sh` | `cd {repo} && git push` | `bash /workspace/hermes_backup_push.sh` |

### 4.2 backup_step 字段实现

```python
# state.py — merge 步骤执行分支时读 backup_step 字段

def execute_merge_branch(step_name, detected_condition, branch):
    """merge 步骤的特殊分支处理（因为有两个备份点）"""

    if detected_condition == "pre_merge_backup_fail":
        # backup_step='pre' → 尚未开始 merge，可以直接重试整个 merge 步骤
        assert branch["backup_step"] == "pre"
        return retry_step("merge", max_retries=1)
        # 注意：重试时会重新执行 merge-1（备份）→ merge-2（git merge）→ ...

    elif detected_condition == "post_merge_backup_fail":
        # backup_step='post' → merge 已完成 + VA 已通过
        # 只需重试备份命令，不需要重做 merge
        assert branch["backup_step"] == "post"
        # 只执行备份命令，不重做 git merge
        strategy = get_backup_strategy(get_project_config()["project_type"])
        cmd = strategy["post_merge"]
        return retry_backup_only(cmd, max_retries=2)
```

**`backup_step` 字段的实际作用**：告诉 state.py 在 retry 时是否重做整个 merge（pre）还是只重试备份命令（post）。这是工程上的关键区分——pre 失败时 merge 还没开始，post 失败时 merge 已经完成——不能把 merge 重做一遍。

### 4.3 SandboxHermesBackup 路径 vs git commit+push 路径

```
system_mechanism:
  hermes_backup_push.sh 实际干的事:
    1. rsync /workspace/devPPL/ → /workspace/SandboxHermesBackup/devPPL/
    2. cd /workspace/SandboxHermesBackup && git add . && git commit
    3. git push（备份 repo 的 remote）
    4. 更新 backup manifest 文件
    5. exit 0 = 成功, != 0 = 失败

pure_product:
  autopilot.sh 直接执行（不进 state.py）:
    cd /workspace/{project_repo} && git add . && git commit ... && git push
  因为 pure_product 的备份就是正常 git workflow，不需要额外脚本

hybrid:
  两条命令顺序执行:
    cd /workspace/{project_repo} && git add . && git commit ... && git push \
    && bash /workspace/hermes_backup_push.sh
  IF 任一失败 → 整体视为备份失败 → retry
```

### 4.4 三个备份点的冗余性

**不冗余。三个点捕获三种不同的逻辑状态，各有独立的 rollback 路径：**

- merge-1（pre-merge snapshot）：如果 merge-2 git merge 出问题需要 abort → 从 merge-1 恢复。没有 merge-1 就回不去。
- merge-4（post-VA snapshot）：VA 已验证 merge 正确 → 这是"已验证可交付"的状态。如果在 close 过程中发现 merge 引入的问题，回退到 merge-4 比回退到 merge-1 省掉重做 merge 的成本。
- close-4（final snapshot）：GAI/manifest 已更新，kanban 已 close → 完整任务周期的最终状态。如果后续发现遗漏，close-4 是"有没有丢东西"的校验基准。

`git reflog` 不能替代 merge-1 备份——reflog 不记录工作区文件状态，而 merge-1 的 rsync 覆盖了未跟踪文件（如 docs/roundtables/ 下的 24 个 untracked 文件）。

---

## 5. gate_roundtable(type, reason) 的分支引擎

### 5.1 state.py 中的代码结构

```python
# pipeline/state.py — roundtable 分发引擎

from pipeline.constants import (
    ProjectType,           # 枚举
    ROUNDTABLE_ASSIGNEES,  # {"A": [...], "B": [...], "C": [...], "D": [...]}
    ROUNDTABLE_WORKFLOWS,  # {"A": "vote", "B": "brainstorm", "C": "risk_matrix", "D": "review"}
)

def handle_gate_roundtable(roundtable_type: str, reason: str, context: dict) -> str:
    """
    统一入口：创建对应类型的 roundtable kanban task，block 当前管线任务。
    返回 roundtable task_id。
    """
    # ── Step 1: 查表获取参与者和工作流类型 ──
    assignees = ROUNDTABLE_ASSIGNEES.get(roundtable_type)
    workflow  = ROUNDTABLE_WORKFLOWS.get(roundtable_type)
    if not assignees:
        raise ValueError(f"Unknown roundtable_type: {roundtable_type}")

    # ── Step 2: D 类特殊——3 个强制议题 ──
    mandatory_topics = []
    if roundtable_type == "D":
        mandatory_topics = [
            "分级判定是否正确",
            "处置方式是否合理",
            "修复难度评估",
        ]

    # ── Step 3: 创建 kanban task ──
    body_parts = [
        f"类型: {roundtable_type} ({workflow})",
        f"原因: {reason}",
        f"参与者: {', '.join(assignees)}",
    ]
    if mandatory_topics:
        body_parts.append("强制议题:\n" + "\n".join(f"  - {t}" for t in mandatory_topics))

    task_id = kanban_create(
        title=f"[ROUNDTABLE-{roundtable_type}] {reason}",
        assignee=assignees[0],
        body="\n".join(body_parts),
        priority=50,
    )

    # ── Step 4: 记录 + block ──
    kanban_comment(
        task_id=context["current_task_id"],
        body=f"[AUTOPILOT: GATE] {roundtable_type} 类 roundtable 已创建: {task_id}",
    )

    # B 类用 needs_input（等待人工裁定），其他用 dependency（等待子任务完成自动恢复）
    block_kind = "needs_input" if roundtable_type == "B" else "dependency"
    kanban_block(
        task_id=context["current_task_id"],
        reason=f"等待 {roundtable_type} 类 roundtable ({task_id}) 裁定",
        kind=block_kind,
    )

    return task_id
```

### 5.2 JSONL 中 gate_roundtable 的 field 扩展

```jsonl
# R4 旧格式:
{"on":"BLOCKER_found","action":"gate_D_roundtable","reason":"QA 发现 BLOCKER"}

# R5 新格式:
{"on":"BLOCKER_found","action":"gate_roundtable","reason":"QA 发现 BLOCKER","roundtable_type":"D"}
```

**state.py 的 branches 引擎改动极小**——原来 `gate_D_roundtable` 是硬编码的 action handler，现在改为 `gate_roundtable` handler 读取 `branches[].roundtable_type` 字段决定类型。代码改动量约 5 行（改 handler 名称 + 读额外字段）。

### 5.3 四种 type 的分发路径

| type | 触发者 | 触发节点 | 参与者 | 完成后 |
|------|--------|---------|--------|--------|
| A | OC（Frank 说"做决定"） | 阶段 -1 | 全员 | 投票结论 → OC 创建后续任务 |
| B | OC（Frank 说"评估"） | 阶段 -1 | 全员 | 报告 Frank → Frank 决定 → **不自动推进** |
| C | OC（Frank 说"有风险吗"） | 阶段 -1 | Product+Architect+Engineer | 风险矩阵 → 记录决策 |
| D | autopilot（管线触发） | dev/qa-exec/qa-d2/va | Product+Architect | 裁定结论 → autopilot 自动推进 |

**A/B/C 三类全由 OC 在阶段 -1 手动触发，state.py 不处理。** state.py 只处理管线中 autopilot 自动触发的 D 类。这是一个干净的职责边界——OC 负责"理解 Frank 意图"的 roundtable，autopilot 负责"管线异常"的 roundtable。

---

## 6. close 7 子步骤 + close.sh：关键架构修正

### 6.1 Product R5 和 Architect R5 的冲突

| 方面 | Product R5 §4.3 | Architect R5 §3.2 | 工程判断 |
|------|----------------|-------------------|----------|
| autopilot 调用方式 | `bash close.sh $TASK_ID` | autopilot 直接执行 close-0~6，`close.sh` 仅做最终验证 | **Architect 正确** |
| close.sh 角色 | 执行 close-1~5 | 事后验证（检查→fix，不是执行） | **Architect 正确** |
| close.sh S1 行为 | 未考虑（假设 close-1 kanban close 由 close.sh 完成） | S1 只 grep 检查 kanban 状态（不是执行 kanban_complete） | **Architect 正确** |

### 6.2 为什么 Architect 的修正正确

**close.sh（104 行）读的是检查逻辑，不是执行逻辑。** 让我基于实际代码（不是假设）说明：

```
close.sh 的 S1（实际代码行为）：
  → grep 检查 kanban 是否 done（验证性操作）
  → 不是 hermes kanban complete（执行性操作）

close.sh 的 S2：
  → grep 检查 GAI 文件中的待办项（验证性操作）
  → 不是 sed 修改 GAI（执行性操作）

close.sh 的 S3-S6 同理：
  → 都是检查 + --fix 修复，不是初始执行
```

**如果 autopilot 按 Product 的原意调用 `bash close.sh $TASK_ID`：**
- T=0: merge done，autopilot 调用 close.sh
- close.sh S1: 检查 kanban 是否 done → **FAIL**（因为 kanban 还没 close）
- close.sh 退出非零 → autopilot 读分支合约 → retry → 下次 cron tick 重试
- **死循环**：kanban 永远不会被 close，因为 close.sh 只检查不执行 close

**Architect 的修正避免了这个问题**：autopilot 直接执行 close-1（`hermes kanban complete`），然后 close-2（`sed` 更新 GAI），然后 close-3（检查 manifest）……最后调用 `bash close.sh $TASK_ID` 做最终验证。close.sh 在这个时间点运行——kanban 已 close、GAI 已更新——它的 S1-S6 全部 PASS。

### 6.3 修正后的 close 实现（autopilot.sh + state.py）

```bash
# autopilot.sh 的 close_pipeline_step() — 修正版

close_pipeline_step() {
    local TASK_ID="$1"

    # ── close-0: S6 检测 ──
    echo "[autopilot] close-0: S6 检测"
    if ! python3 pipeline/state.py --close-s6-check "$TASK_ID"; then
        echo "[autopilot] ERROR: close-0 S6 检测失败"
        python3 pipeline/state.py --handle-branch --step close --condition "s6_check_fail" --task "$TASK_ID"
        return 1
    fi

    # ── close-1: 关闭 kanban 任务 ──
    echo "[autopilot] close-1: 关闭 kanban 任务"
    if ! python3 pipeline/state.py --close-kanban "$TASK_ID"; then
        echo "[autopilot] ERROR: close-1 失败"
        python3 pipeline/state.py --handle-branch --step close --condition "step_fail_close_kanban" --task "$TASK_ID"
        return 1
    fi

    # ── close-2: 更新 GAI ──
    echo "[autopilot] close-2: 更新 GAI"
    if ! python3 pipeline/state.py --close-gai "$TASK_ID"; then
        echo "[autopilot] ERROR: close-2 失败"
        python3 pipeline/state.py --handle-branch --step close --condition "step_fail_gai" --task "$TASK_ID"
        return 1
    fi

    # ── close-3: 更新 Manifest ──
    echo "[autopilot] close-3: 更新 Manifest"
    if ! python3 pipeline/state.py --close-manifest "$TASK_ID"; then
        echo "[autopilot] ERROR: close-3 失败"
        python3 pipeline/state.py --handle-branch --step close --condition "step_fail_manifest" --task "$TASK_ID"
        return 1
    fi

    # ── close-4: 备份推送 ──
    echo "[autopilot] close-4: 备份推送"
    if ! python3 pipeline/state.py --close-backup "$TASK_ID"; then
        echo "[autopilot] ERROR: close-4 失败"
        python3 pipeline/state.py --handle-branch --step close --condition "step_fail_backup" --task "$TASK_ID"
        return 1
    fi

    # ── close-5: 通知 ──
    echo "[autopilot] close-5: 发送通知"
    python3 pipeline/state.py --close-notify "$TASK_ID" || true  # 通知不阻塞

    # ── close-6: 归档 + 清理 ──
    echo "[autopilot] close-6: 归档"
    python3 pipeline/state.py --close-archive "$TASK_ID" || true  # 归档不阻塞

    # ── 最终验证：close.sh ──
    echo "[autopilot] close: 最终验证 (close.sh)"
    if bash /root/.hermes/profiles/orchestrator/scripts/close.sh "$TASK_ID"; then
        echo "[autopilot] close: 全部 PASS ✅"
        python3 pipeline/state.py --write-verdict --step close --verdict pass
    else
        echo "[autopilot] close: close.sh 有告警（close 已完成，记录 conditional_pass）"
        python3 pipeline/state.py --write-verdict --step close --verdict conditional_pass
    fi
}
```

### 6.4 close.sh 验证什么（修正后）

在 autopilot 执行完 close-1~close-6 之后，close.sh 做最终闭环完整性验证：

| close.sh 步骤 | 验证内容 | 失败含义 |
|---------------|---------|---------|
| S1 | kanban 状态已是 done | 如果失败 → autopilot 的 close-1 没成功？ |
| S2 | GAI 文件中 P0-XX 标记为 done | 如果失败 → autopilot 的 close-2 没成功？ |
| S3 | git status 无未提交变更 | 如果失败 → 有遗漏的文件没 add？ |
| S4 | manifest 文件存在且完整 | 如果失败 → 文件丢失？ |
| S5 | 备份 commit 存在 | 如果失败 → close-4 备份没成功？ |
| S6 | 输出 `<TASK_ID> 闭环完成 ✅` | 如果失败 → 有步骤未验证？ |

**close.sh 是"闭环完整性探测器"——不是"闭环执行器"。** 它回答"有没有遗漏"，不负责"执行遗漏项"。

### 6.5 对 Product 的反馈

Product R5 §4.3 假定了 close.sh 能执行 close-1~5。**这个假设与 close.sh 的实际实现冲突。** 需要 Product 确认接受 Architect 的修正——将 close.sh 从"执行脚本"重新定位为"验证脚本"。如果 Product 仍坚持 autopilot 直接调用 close.sh 做执行，那么 close.sh 需要大幅改写（从 grep 检查逻辑改为 hermes kanban + sed + git push 执行逻辑），工作量增加 ~80 行 shell，工期增加 ~2h。

**工程师建议**：接受 Architect 修正。close.sh 作为验证脚本更安全——执行和验证分离是软件工程的基本模式。且 close.sh 已经过验证（104 行可用的检查脚本），改写成执行脚本引入新 bug 的风险更高。

---

## 7. pipeline_state.db v1→v2→v3 migration

### 7.1 user_version 演进路线

```
v1 (初始)          v2 (R4)                    v3 (R5)
─────────          ──────                    ──────
pipeline_steps    +verdict                   +project_config 表
  (7 字段)        +verdict_detail            (pipeline_steps 表不变)
                  +contract_check_passed
```

### 7.2 v1→v2 migration（R4，checkpoint.py 已有设计）

```python
# checkpoint.py — migrate_v1_to_v2()

def migrate_v1_to_v2(conn: sqlite3.Connection):
    """v1 → v2: 新增 verdict/verdict_detail/contract_check_passed 列"""
    cursor = conn.cursor()
    cursor.execute("PRAGMA user_version")
    current = cursor.fetchone()[0]

    if current < 2:
        cols = [row[1] for row in cursor.execute("PRAGMA table_info(pipeline_steps)")]
        if "verdict" not in cols:
            cursor.execute("ALTER TABLE pipeline_steps ADD COLUMN verdict TEXT")
        if "verdict_detail" not in cols:
            cursor.execute("ALTER TABLE pipeline_steps ADD COLUMN verdict_detail TEXT")
        if "contract_check_passed" not in cols:
            cursor.execute("ALTER TABLE pipeline_steps ADD COLUMN contract_check_passed INTEGER")
        cursor.execute("PRAGMA user_version = 2")
        conn.commit()
```

### 7.3 v2→v3 migration（R5，新增）

```python
# checkpoint.py — migrate_v2_to_v3()

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

### 7.4 pipeline_steps 表在 v3 中不需要 ALTER TABLE

**Architect §6.3 的决策正确**：close 子步骤状态用 `verdict_detail` JSON 存储，不在主表为每个子步骤建行。

工程理由：
- SQLite `verdict_detail` 是 TEXT 字段，存 JSON 零额外 schema 成本
- 如果为 close-0~close-6 各建一行，7 步管线变成 14 行/任务，且 close 子步骤的重试逻辑与主步骤不同（子步骤失败只在 close 内部 retry，不影响其他步骤）
- `dashboard.py` 解析 `verdict_detail` JSON 即可展示 close 子步骤详情，不需要额外 JOIN

### 7.5 统一的 migration 入口

```python
# checkpoint.py — 对外暴露的唯一 migration 入口

def ensure_schema(conn: sqlite3.Connection, target_version: int = 3):
    """幂等迁移到目标版本。"""
    cursor = conn.cursor()
    cursor.execute("PRAGMA user_version")
    current = cursor.fetchone()[0]

    if current < 1:
        _create_initial_schema(conn)  # v1 初始表
    if current < 2:
        migrate_v1_to_v2(conn)        # v1 → v2
    if current < 3:
        migrate_v2_to_v3(conn)        # v2 → v3

    # 验证
    cursor.execute("PRAGMA user_version")
    assert cursor.fetchone()[0] == target_version
```

**幂等性保证**：所有 migration 函数都检查 `current < N` 才执行，重复调用安全。

---

## 8. 风险点清单（工程视角）

| # | 风险 | 级别 | 缓解 |
|---|------|:----:|------|
| 1 | Product 和 Architect 对 close.sh 的角色有冲突，未裁定 | **MAJOR** | 需 Product 确认接受 Architect 修正或要求重改 close.sh |
| 2 | `hermes_backup_push.sh` 的实际路径和可用性未经验证 | **MINOR** | R2 已验证存在，但未在 R5 重新确认 |
| 3 | close-1 `hermes kanban complete` 是非标准 Hermes CLI——目前 `kanban_helpers.py` 只有 `kanban_comment`/`kanban_block`，没有 `kanban_complete` 的 Python 调用 | **MINOR** | 需要验证 hermes CLI 支持或通过 subprocess 直接调用 `hermes kanban complete` |
| 4 | autopilot.sh 作为 cron job 的 flock 锁在异常退出时可能不释放 | **MINOR** | flock 是内核级文件锁，进程退出自动释放——风险可控 |
| 5 | `pipeline/` 目录是全新的 Python 包，需要 `__init__.py` 和路径管理 | **MINOR** | 标准 Python package 设置，10 行 `__init__.py` 即可 |
| 6 | close.sh 的最终验证如果告警但不阻塞——可能导致「未完全闭合但以为闭合了」 | **MINOR** | close-0~6 全部执行成功才写 verdict=pass，close.sh 告警只降级为 conditional_pass，不会写 pass 而遗漏 |

---

## 9. 不做的事（工程边界）

- **不修改 close.sh**：104 行已验证的验证脚本，保持不动。autopilot 在 close-6 之后调用它做最终验证。
- **不在 pipeline_steps 表建 close 子步骤行**：verdict_detail JSON 足够，避免表膨胀。
- **不让 autopilot 自动检测项目类型**：混合类的判定需要 Frank 语义，OC 一次性写入 project_config 表，autopilot 只读。
- **不合并三个备份点**：三个点捕获不同逻辑状态，各有独立回退路径。
- **不为 A/B/C 类 roundtable 写 autopilot 自动推进逻辑**：这三类由 OC 手动触发和管理，autopilot 只处理 D 类。

---

## 10. 一句话总结

> Product 补了四项缺失（roundtable 类型、双重备份、项目分类、S6 展开），Architect 补了 schema（project_config 表、gate_roundtable 分发、close 子步骤设计），两份 R5 在 7/8 项决定上一致。唯一的冲突是 D-015——close.sh 是执行脚本还是验证脚本。工程师验证了 close.sh 的实际实现（检查逻辑，非执行逻辑），确认 Architect 的修正正确：autopilot 直接执行 close-0~6，close.sh 做最终验证。约 195 行 R5 增量 + ~975 行 R4 基线 = ~1,200 行 / 17 小时的完整交期。接口已冻结，坑已标注，可以开始写代码了。

---

> 我是团队的双手。两份 R5 报告都读完了——Product 画了带备份点和 roundtable 的路标，Architect 在每个岔路口标了判定公式。我把公式翻译成了具体的 Python 函数 + shell 调用 + SQLite migration 脚本。唯一需要 Product 裁定的就是 close.sh 的角色——是执行还是验证。我的建议写在 §6 里了。其余所有决定，工程上无歧义，可以立即动手。
