# R5 最终修复 — Product 发言：完整可执行工作流报告

> 发言人：许清楚（产品负责人） | 日期：2026-07-30 | 版本：v1.0（最终版）
> 目标：基于 OC 自查找出的四项缺失，填入 R1-R4 已达成共识的完整框架，产出最终可执行工作流
> 规则：kanban_complete 后传给 architect

---

## 0. 背景：OC 自查发现的四项缺失

R4 三方报告统一后，OC 进行自检发现四个维度完全缺失于所有 R4 报告中：

| # | 缺失维度 | 来源 | 影响 |
|---|---------|------|------|
| 1 | Roundtable 类型分类（A/B/C/D） | PIPELINE.md 定义但未嵌入任何工作流 | autopilot 不知道当前任务触发哪种 roundtable |
| 2 | 双重备份流程 | PIPELINE.md 铁律 2 S6 闭环 + Frank 补充 | merge/close 步骤没有嵌入备份，数据风险 |
| 3 | 项目分类与备份策略 | Frank 明确的三类项目 | autopilot 不知道走哪种备份方式 |
| 4 | S6 闭环 5→6+1 步骤展开 | 铁律 2 规定 6 步不可裁剪 | close 步骤在 R4 中显示为一个原子操作，无法自动化 |

**Product R5 使命**：将以上四项缺失填入 R1-R4 已达成共识的 7 步管线框架中，产出一份「有人拿到就能按图索骥编码实现」的完整工作流报告。

---

## 1. 缺失 1：Roundtable 类型分类（A/B/C/D）嵌入工作流

### 1.1 类型定义（来源：PIPELINE.md 规范）

| 类型 | 用途 | 关键规则 | 触发场景 |
|------|------|---------|---------|
| **A** | Yes/No 决策 | 投票，approve/reject/conditional | 方案选择、标准制定、优先级裁定 |
| **B** | 头脑风暴 | 不产生行动任务，报告提交 Frank | 工具评估、架构探索、前瞻性分析 |
| **C** | 风险评估 | Trade-off 分析，输出风险矩阵 | 技术选型 risk、架构变更影响面 |
| **D** | 测试评审 | D1（方案评审）+ D2（报告评审），3 个强制议题（分级/处置/修复难度） | BLOCKER 发现、MAJOR>3、铁律例外 |

### 1.2 类型判定节点

**谁判定、在哪个节点判定**：

```
│
├─ 阶段 -1：OC 理解 Frank 指令后
│   │
│   │ IF Frank 说"评估一下" 或 "讨论一下" 或 "头脑风暴"
│   │   → roundtable_type = B
│   │   → OC 创建 B 类 roundtable，不产生 kanban 开发任务
│   │
│   │ IF Frank 说"做个决定" 或 "二选一" 或 "定个标准"
│   │   → roundtable_type = A
│   │   → OC 创建 A 类 roundtable，各角色投票
│   │
│   │ IF Frank 说"有风险吗" 或 "有什么坑"
│   │   → roundtable_type = C
│   │   → OC 创建 C 类 roundtable，输出风险矩阵
│   │
│   │ IF Frank 说"做 X"（明确的开发任务）
│   │   → 走标准开发管线（无 roundtable 阶段）
│   │
│   ▼
│
├─ 管线中（autopilot 触发）：
│   │
│   │ IF spec 与 SOUL.md 铁律冲突
│   │   → roundtable_type = D（铁律例外裁定）
│   │   → autopilot 创建 D 类 roundtable，Product + Architect 裁定
│   │
│   │ IF QA 发现 BLOCKER 或 MAJOR > 3
│   │   → roundtable_type = D
│   │   → autopilot 创建 D 类 roundtable，3 个强制议题
│   │
│   │ IF QA D1 评审 fail（覆盖率 < 100%，2 次重试后）
│   │   → roundtable_type = D（需求理解不清）
│   │
│   │ IF QA D2 评审 fail（分级错误或漏报 BLOCKER）
│   │   → roundtable_type = D
```

### 1.3 autopilot 如何根据类型走不同分支

```python
# state.py 中的 roundtable 分发逻辑（伪代码）
ROUNDTABLE_HANDLERS = {
    "A": create_vote_roundtable,        # 创建 A 类：各角色投票 → approve/reject/conditional
    "B": create_brainstorm_roundtable,  # 创建 B 类：不产生 kanban → 报告提交 Frank
    "C": create_risk_roundtable,        # 创建 C 类：输出风险矩阵 → 记录决策
    "D": create_review_roundtable,      # 创建 D 类：D1/D2 评审 → 3 强制议题
}

def handle_gate(roundtable_type, reason, context):
    handler = ROUNDTABLE_HANDLERS[roundtable_type]
    task = handler(
        reason=reason,
        assignees=get_assignees_for_type(roundtable_type),  # A=全员, B=全员, C=Arch+Prod+Eng, D=Prod+Arch
        mandatory_topics=get_topics_for_type(roundtable_type),
        context=context
    )
    kanban_comment(f"[AUTOPILOT: GATE] {roundtable_type} 类 roundtable 已创建: {task.id}")
    kanban_block(task_id=current_task, reason=f"等待 {roundtable_type} 类 roundtable 裁定")

def get_assignees_for_type(t):
    return {
        "A": ["game-director", "game-architect", "game-engine", "game-qa"],
        "B": ["game-director", "game-architect", "game-engine", "game-qa"],
        "C": ["game-director", "game-architect", "game-engine"],
        "D": ["game-director", "game-architect"],
    }[t]

def get_topics_for_type(t):
    if t == "D":
        return ["分级判定是否正确", "处置方式是否合理", "修复难度评估"]
    return None  # A/B/C 由 OC 根据具体议题设定
```

### 1.4 嵌入到 7 步管线的位置

```
dev → qa-d1 → qa-exec → qa-d2 → va → merge → close
  │                       │      │
  │                       │      └── FALSIFIED → D 类 roundtable
  │                       │
  │                       └── BLOCKER/MAJOR>3 → D 类 roundtable
  │                       └── D2 评审 fail → D 类 roundtable
  │
  └── spec 铁律冲突 → D 类 roundtable（阶段 -1）
  └── Frank 说"评估/讨论" → A/B/C 类 roundtable（阶段 -1）
```

**给 Engineer 的信息**：state.py 的 `gate_D_roundtable` action 需要参数化——接收 `roundtable_type` 和 `reason`。当前 JSONL v2 中 `gate_D_roundtable` 应扩展为 `gate_roundtable(type, reason)`。实现时从 `branches[].action` 改为 `branches[].action + branches[].roundtable_type`。

---

## 2. 缺失 2：双重备份流程嵌入

### 2.1 完整备份序列（来源：铁律 2 S6 闭环 + Frank 补充）

```
合并前备份 → git merge → VA 检查合并+运行 → VA通过后最终备份 → 通知
```

三步备份 = 合并前一次 + VA 通过后一次 + close.sh 闭环中的例行备份。

### 2.2 嵌入到 7 步管线的具体位置

```
merge 步骤展开为 5 个 micro-step：

[merge-1] 合并前备份（首次）
    │ 谁执行: autopilot / OC
    │ 命令: cd /workspace && bash hermes_backup_push.sh
    │ 作用: 在 merge 前保存当前状态快照
    │ IF 失败: → 重试 1 次 → block，通知 OC "合并前备份失败"
    │
    ▼
[merge-2] git merge
    │ 谁执行: OC 或 autopilot（按任务类型决定）
    │ 命令: git merge --no-commit --no-ff feat/{task_id}
    │ IF 冲突: → block，engine 解决冲突 → 重新 merge-1, merge-2
    │
    ▼
[merge-3] VA 检查合并结果 + 运行
    │ 谁执行: verifier agent
    │ 内容: 检查 merge commit 的内容完整性 + 确认合并后代码仍通过 VA 验证
    │ IF VA 不通过: → block → 回退 merge（git merge --abort）→ engine 重新 fix
    │
    ▼
[merge-4] 合并后最终备份（第二次）
    │ 谁执行: autopilot / OC
    │ 命令: cd /workspace && bash hermes_backup_push.sh
    │ 作用: 保存 merge 后的完整状态
    │ IF 失败: → 重试 2 次 → block，通知 OC "合并后备份失败"
    │
    ▼
[merge-5] Frank 闸门确认
    │ 谁执行: OC
    │ 内容: OC 通知 Frank "P0-XX 全部通过，可以 merge"
    │ Frank 回复确认 → 继续推进到 close
    │ Frank 暂缓 → 记录 pending
```

### 2.3 备份脚本链路

```
hermes_backup_push.sh 实际执行:
  1. rsync /workspace/ → /workspace/SandboxHermesBackup/ (增量同步)
  2. 更新 /workspace/SandboxHermesBackup/ 中的 manifest 文件
  3. git add + commit + push (在 backup-repo 中)
  4. 返回 exit code 0=成功, 非0=失败

hermes_backup_notify.sh:
  1. 发送飞书通知 "备份完成: <commit_hash>, <timestamp>"
```

### 2.4 backup 的 JSONL 合约扩展

merge 步骤的合约需要体现两个备份点：

```jsonl
{"step":"merge","requires":["va_report.md","test_report.md"],"produces":["merge_commit","backup_snapshot"],"timeout_min":20,"branches":[
  {"on":"pre_merge_backup_fail","action":"retry","target":"merge","max_retries":1,"backup_step":"pre"},
  {"on":"conflict","action":"block","reason":"merge 冲突，engine 需解决"},
  {"on":"va_merge_check_fail","action":"rollback","target":"dev","reason":"VA 合并验证不通过"},
  {"on":"post_merge_backup_fail","action":"retry","target":"merge","max_retries":2,"backup_step":"post"},
  {"on":"human_gate","action":"await_confirm","reason":"等待 Frank 确认 merge"}
]}
```

**给 Engineer 的信息**：
- merge 步骤的合约从单一 `merge_commit` 扩展为 `merge_commit` + `backup_snapshot`（两次备份都记录到 backup_snapshot artifact）
- state.py 需要新增 `backup_step` 上下文——区分"合并前备份失败"和"合并后备份失败"（重试次数不同）
- autopilot.sh 需要在 merge 的 pre-check 中调用 `hermes_backup_push.sh`

---

## 3. 缺失 3：项目分类与备份策略

### 3.1 三类项目定义（Frank 明确）

| 类型 | 示例 | 代码在哪 | 备份方式 | 判定特征 |
|------|------|---------|---------|---------|
| **系统机制类** | devPPL | `/workspace/devPPL/`（非独立 git repo） | SandboxHermesBackup：复制 → 更新 manifest → 更新 setup → git push | 无独立 git repo，文件在 workspace 下 |
| **纯产品类** | Threes | 独立 git repo | git commit + push | 有独立 git repo，代码在标准项目结构中 |
| **混合类** | InfoManager | 独立 repo + hermes 本体 | 双重备份：commit+push + SandboxHermesBackup | 独立 repo + 依赖 Hermes 本体配置 |

### 3.2 autopilot 如何判定当前项目类型

**方案：autopilot 读项目根目录的 `pipeline_state.db` 中新增的 `project_config` 表**。

```sql
-- pipeline_state.db 新增表（user_version = 2 时创建）
CREATE TABLE IF NOT EXISTS project_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- 初始部署时写入（由 OC 或 boot_context cron 首次运行时写入）
INSERT OR REPLACE INTO project_config VALUES
    ('project_type', 'system_mechanism'),  -- system_mechanism | pure_product | hybrid
    ('backup_method', 'SandboxHermesBackup'),
    ('project_name', 'devPPL');
```

**判定逻辑**（state.py 中）：

```python
def get_project_backup_strategy():
    config = load_project_config("pipeline_state.db")
    project_type = config.get("project_type", "system_mechanism")  # 默认系统机制类

    BACKUP_STRATEGIES = {
        "system_mechanism": {
            "pre_merge": "bash /workspace/hermes_backup_push.sh",
            "post_merge": "bash /workspace/hermes_backup_push.sh",
            "close_backup": "bash /workspace/hermes_backup_push.sh",
            "notify": "bash /workspace/hermes_backup_notify.sh",
        },
        "pure_product": {
            "pre_merge": "cd {repo} && git add . && git commit -m 'backup: pre-merge' && git push",
            "post_merge": "cd {repo} && git add . && git commit -m 'backup: post-merge' && git push",
            "close_backup": "cd {repo} && git push",
            "notify": None,  # 纯产品类不发备份通知
        },
        "hybrid": {
            "pre_merge": [
                "cd {repo} && git add . && git commit -m 'backup: pre-merge' && git push",
                "bash /workspace/hermes_backup_push.sh"
            ],
            "post_merge": [
                "cd {repo} && git add . && git commit -m 'backup: post-merge' && git push",
                "bash /workspace/hermes_backup_push.sh"
            ],
            "close_backup": "bash /workspace/hermes_backup_push.sh",
            "notify": "bash /workspace/hermes_backup_notify.sh",
        },
    }
    return BACKUP_STRATEGIES[project_type]
```

### 3.3 项目类型的初始写入时机

```
首次部署时:
  1. OC 创建项目 workspace → 初始化 pipeline_state.db
  2. OC 根据 Frank 对项目的定义写入 project_type
  3. 三类项目判定依据:
     - 在 /workspace/ 下但不是独立 git repo → system_mechanism
     - 有独立 git repo 且代码完全自包含 → pure_product
     - 有独立 git repo 但依赖 Hermes 本体 → hybrid
```

**给 Engineer 的信息**：
- checkpoint.py 需要新增 `project_config` 表的创建逻辑（user_version=2 migration 中）
- state.py 需要在 autopilot 启动时读取 `project_type` 决定备份命令
- 备份命令的执行在 autopilot.sh 中——不在 state.py 中（state.py 只负责策略判定，autopilot.sh 负责 shell 命令执行）

---

## 4. 缺失 4：S6 闭环展开为 6+1 个 micro-step

### 4.1 铁律 2 原文

> 任务闭环序列（S6 检测 → 关任务 → 更新 GAI → 更新 manifest → 备份推送 → 并发通知）缺一不可。不能跳 GAI 直接备份，不能跳 manifest 直接通知。

### 4.2 展开后的 close 步骤（6+1 个 micro-step）

```
close 步骤展开：
  │
  ├── [close-0] S6 检测（前置校验）
  │    谁执行: autopilot
  │    内容: 检查前 6 步（dev → merge）是否全部 pass
  │    IF 任一步未 pass: → block，不允许进入 close
  │    数据源: pipeline_state.db 中所有 step 的 verdict 字段
  │    校验: SELECT COUNT(*) FROM pipeline_steps WHERE task_id=X
  │          AND status='done' AND verdict IN ('pass','VERIFIED','conditional_pass')
  │          必须 = 6（dev + qa-d1 + qa-exec + qa-d2 + va + merge）
  │
  ├── [close-1] 关闭 Kanban 任务
  │    谁执行: OC / autopilot（按任务类型决定）
  │    内容: hermes kanban complete task_id → status = done
  │    产出: kanban task status = done
  │    IF 失败: → retry 1 次 → block
  │
  ├── [close-2] 更新 GAI（GLOBAL_ACTION_ITEMS.md）
  │    谁执行: OC / autopilot
  │    内容: 将 P0-XX 状态从"待办" → "✅ done"
  │    文件: /workspace/devPPL/GLOBAL_ACTION_ITEMS.md
  │    操作: sed -i 's/P0-XX.*待办/P0-XX ✅ done/' 或等效
  │    IF GAI 文件不存在: → block，通知 OC "GAI 文件丢失"
  │    IF 更新失败: → retry 1 次 → block
  │
  ├── [close-3] 更新 Manifest
  │    谁执行: OC / autopilot
  │    内容: 检查本次改动的新增文件是否已在 config/manifest.yaml 中注册
  │    操作: git diff HEAD~1 --name-only | xargs -I{} grep -q '{}' config/manifest.yaml
  │    IF 有未注册文件: → autopilot 自动注册 或 block 通知 OC 手动注册
  │    IF manifest 更新失败: → retry 1 次 → block
  │
  ├── [close-4] 备份推送（按项目类型走不同策略）
  │    谁执行: autopilot
  │    内容: 根据 §3 的项目类型判定执行对应备份命令
  │    系统机制类: bash /workspace/hermes_backup_push.sh
  │    纯产品类: git push
  │    混合类: 双重备份
  │    IF 失败: → retry 2 次 → block "close-4 备份推送失败"
  │
  ├── [close-5] 并发通知（GAI + 备份结果）
  │    谁执行: autopilot
  │    内容:
  │      a. 飞书通知 Frank "P0-XX 闭环完成"（含 6 步验证结果摘要）
  │      b. 备份通知（如果项目配置了 notify 脚本）
  │    格式: "✅ P0-XX 闭环完成。dev→qa-d1→qa-exec→qa-d2→va→merge 全部 pass。
  │            GAI 已更新，manifest 已更新，备份已推送（commit: abc1234）。
  │            耗时: 2h35m"
  │    IF 通知发送失败: → retry 1 次 → block（不阻塞 close 完成但记录失败）
  │
  └── [close-6] 归档 + 清理
       谁执行: OC / autopilot
       内容:
         a. openspec archive {task_id}
         b. 清理临时 worktree（git worktree remove /tmp/{task_id}）
         c. pipeline_state.db: step=close, verdict='pass', status='done'
       IF 归档失败: → 记录 warning（不阻塞）
```

### 4.3 close.sh 的自动调用

现有 `close.sh`（104 行，位于 `/root/.hermes/profiles/orchestrator/scripts/close.sh`）覆盖了 close-1 到 close-5 的 6 步验证。目前的问题是：**没有任何流程自动调用它**（DPL-010）。

**产品 R5 裁定**：

```
autopilot 在检测到 merge done 后：
  1. 先执行 close-0（S6 检测）
  2. S6 检测通过 → 调用 close.sh {task_id}
  3. close.sh 每步返回 exit code
  4. 任一步 fail → autopilot 按 branches 合约处理（retry → block）
  5. 全部 pass → close-5 通知 Frank "闭环完成"
```

**调用方式**（在 autopilot.sh 中）：

```bash
# autopilot.sh 的 close 段
if python3 pipeline/state.py --step-close-ready "$TASK_ID"; then
    # close-0: S6 检测通过
    if bash /root/.hermes/profiles/orchestrator/scripts/close.sh "$TASK_ID"; then
        # close-1~close-5 全部 pass
        python3 pipeline/state.py --write-verdict --step close --verdict pass
        hermes_backup_notify.sh  # close-5 通知
    else
        # close.sh 某步失败 → 按分支合约处理
        python3 pipeline/state.py --handle-branch --step close --condition "step_fail"
    fi
fi
```

### 4.4 close 步骤的 JSONL 合约更新

```jsonl
{"step":"close","requires":["merge_commit"],"produces":["gai_update","manifest_update","backup_snapshot"],"timeout_min":15,"branches":[
  {"on":"s6_check_fail","action":"block","reason":"S6 检测未通过：存在未完成步骤"},
  {"on":"step_fail","action":"retry","target":"close","max_retries":3,"note":"从失败步开始重试"},
  {"on":"step_fail_close_kanban","action":"retry","target":"close","max_retries":1,"note":"kanban 关闭失败"},
  {"on":"step_fail_gai","action":"retry","target":"close","max_retries":1,"note":"GAI 更新失败"},
  {"on":"step_fail_manifest","action":"retry","target":"close","max_retries":1,"note":"manifest 更新失败"},
  {"on":"step_fail_backup","action":"retry","target":"close","max_retries":2,"note":"备份推送失败"},
  {"on":"retry_exhausted","action":"block","reason":"close.sh 重试耗尽，需手动检查"}
]}
```

---

## 5. 完整可执行工作流（7 步管线 + 4 项缺失填入）

### 5.1 端到端流程：Frank 说"做 X"到飞书通知"闭环完成"

```
  Frank 说 "做 P0-XX: 修复 Y"
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  阶段 -1: OC 理解 + 类型判定                                     │
  │                                                                  │
  │  OC 判断 Frank 意图:                                              │
  │    ├─ "评估/讨论" → 创建 B 类 roundtable（头脑风暴）              │
  │    ├─ "做决定/选方案" → 创建 A 类 roundtable（Yes/No 投票）       │
  │    ├─ "有风险吗" → 创建 C 类 roundtable（风险评估）               │
  │    └─ "做 X"（明确开发任务） → 走标准管线 ↓                      │
  │                                                                  │
  │  OpenSpec propose → validate → 铁律冲突检查                       │
  │    └─ 铁律冲突 → D 类 roundtable                                  │
  │                                                                  │
  │  IF A/B/C 类 roundtable:                                          │
  │    → 各角色发言 → 结论报告 Frank → Frank 决定 → 转开发任务 或 结束 │
  │                                                                  │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼  (如果是明确开发任务)
  ┌──────────────────────────────────────────────────────────────────┐
  │ 管线: 7 步 (dev → qa-d1 → qa-exec → qa-d2 → va → merge → close) │
  │                                                                   │
  │  Step 1: dev (研发实现)                                           │
  │  Step 2: qa-d1 (测试方案 + 评审)          ← 与 dev 并行启动       │
  │  Step 3: qa-exec (测试执行)               ← dev AND qa-d1 done    │
  │  Step 4: qa-d2 (测试报告评审)                                     │
  │  Step 5: va (独立验证)                                            │
  │  Step 6: merge (合并 + 双重备份)           ← 含 merge前备份        │
  │           ├─ merge-1: 合并前备份 (hermes_backup_push.sh)          │
  │           ├─ merge-2: git merge                                   │
  │           ├─ merge-3: VA 合并验证                                  │
  │           ├─ merge-4: 合并后备份 (hermes_backup_push.sh)          │
  │           └─ merge-5: Frank 闸门确认                               │
  │  Step 7: close (闭环)                      ← 6+1 micro-step       │
  │           ├─ close-0: S6 检测 (6步全部 pass?)                     │
  │           ├─ close-1: 关闭 kanban 任务                             │
  │           ├─ close-2: 更新 GAI                                    │
  │           ├─ close-3: 更新 manifest                               │
  │           ├─ close-4: 备份推送 (按项目类型)                        │
  │           ├─ close-5: 飞书通知 "闭环完成"                          │
  │           └─ close-6: openspec archive + worktree 清理              │
  │                                                                   │
  │  备份策略判定 (每个备份点):                                        │
  │    ├─ system_mechanism: SandboxHermesBackup                       │
  │    ├─ pure_product:   git commit + push                           │
  │    └─ hybrid:         双重 (git push + SandboxHermesBackup)        │
  │                                                                   │
  │  分支路由 (每个节点, 共 21 个条件):                                │
  │    ├─ action=retry    → 重试 (最多 N 次)                          │
  │    ├─ action=block    → 停止，通知 OC/Frank                       │
  │    ├─ action=rollback → 回退到目标步骤                             │
  │    ├─ action=continue → 记录 pending → 继续                       │
  │    ├─ action=gate_roundtable(type) → 创建 roundtable (A/B/C/D)     │
  │    └─ action=await_confirm → 等待 Frank 确认                      │
  │                                                                   │
  └──────────────────────────────────────────────────────────────────┘
       │
       ▼
  Frank 收到飞书通知: "✅ P0-XX 闭环完成。7 步全部 pass。备份已推送。"
```

### 5.2 数据流与组件全景（复用 R4 共识 + 新增 4 项）

| 组件 | 职责 | 数据源 | 写什么 | 新增于 R5 |
|------|------|--------|--------|----------|
| **OC** | 理解指令、类型判定、创建 roundtable | Frank 飞书 | kanban task, roundtable task | ✅ 类型判定（§1） |
| **OpenSpec** | 规范生成 + 验证 | Frank 意图 | spec.md | — |
| **autopilot** | cron 2min 轮询，推进步骤，创建 kanban card | kanban.db + pipeline_state.db | pipeline_state.db (step status + verdict) + kanban comment | ✅ 备份执行（§2）、项目类型读取（§3） |
| **state.py** | 合约校验 + 分支判定 + rollback | JSONL contracts + file system | pipeline_state.db (verdict + contract_check_passed) | ✅ roundtable 类型分发（§1）、备份策略判定（§3） |
| **checkpoint.py** | checkpoint 写入 | state.py + autopilot | pipeline_state.db (schema v2) | ✅ project_config 表（§3） |
| **fanout.py** | 并行 dev + qa-d1 dispatch | pipeline_state.db | kanban card | — |
| **close.sh** | 6 步闭环验证 | pipeline_state.db + GAI + manifest + git | exit code 每步 | — |
| **boot_context** | cron 5min，更新 .hermes.md 动态段 | session DB + pipeline_state.db + memory | .hermes.md 动态段 | — |
| **watchdog** | cron 30min，监控 autopilot 心跳 | 心跳文件 + kanban.db | 飞书告警 | — |
| **dashboard.py** | 红绿灯面板 | pipeline_state.db v2 + kanban.db | stdout（CLI 输出） | — |
| **Product**（许清楚） | D1/D2 评审、roundtable 裁定、红线维护 | kanban comment | kanban comment（评审结论） | — |
| **hermes_backup_push.sh** | 备份推送 | /workspace/ | backup-repo git push | ✅ 按项目类型调用（§3） |

### 5.3 所有 R1-R4 共识保留（不遗漏）

| 共识项 | 来源 | 在 R5 中的位置 |
|--------|------|--------------|
| 7 步管线 | R4 Architect D-001 | §5.1 |
| 21 分支条件 | R4 Engineer §3 | §5.1 分支路由 |
| JSONL v2 (branches schema) | R4 Architect §2 | §1.3, §2.4, §4.4 |
| pipeline_state.db v2 (verdict/verdict_detail/contract_check_passed) | R4 Architect §4.2 | §3.2 project_config 表追加 |
| dashboard 红绿灯 | R4 Product §5 | —（Architect §4 已给 schema） |
| DPL-011 (.hermes.md + boot_context) | R4 Product §3.1 | —（Architect/Engineer 已细化） |
| Autopilot/Watchdog 共存 | R4 Product §4 | —（Architect §5 已证明） |
| QA D1/D2 三阶段 | R4 Product §2 | §5.1 |
| 成员 I/O 标准 (output/<role>/<task_id>/) | R4 Architect D-007 | §5.2 |
| close.sh 全绿才发通知 | R4 Product §1.1 | §4.3 |
| OC ≠ Product 角色表 | R4 Product §6 | — |
| Engineer 错误引用约束修正 | R4 Product §7 | — |

---

## 6. Product R5 新增决定清单

以下决定是在 R4 D-001~D-010 基础上的 R5 新增决定：

| # | 决定 | 类型 | 执行方 | 对应缺失 |
|---|------|------|--------|---------|
| **D-011** | autopilot 在 merge 前必须执行 `hermes_backup_push.sh`（合并前备份），merge 完成后、VA 验收后再次执行（合并后备份） | 流程变更 | autopilot + state.py | 缺失 2 |
| **D-012** | pipeline_state.db 新增 `project_config` 表，存储 `project_type`（system_mechanism/pure_product/hybrid）。由 OC 在项目首次部署时写入 | 架构新增 | checkpoint.py | 缺失 3 |
| **D-013** | autopilot 在备份前读取 `project_type` 决定备份命令：system_mechanism → SandboxHermesBackup, pure_product → git push, hybrid → 双重 | 流程标准 | autopilot + state.py | 缺失 3 |
| **D-014** | OC 在理解 Frank 指令后判定 roundtable_type（A/B/C/D），写入 kanban task metadata。管线中由 state.py 根据触发条件创建对应类型 roundtable | 流程标准 | OC + state.py | 缺失 1 |
| **D-015** | close 步骤从 1 个原子操作展开为 7 个 sub-step（close-0 到 close-6），每个 sub-step 对应 close.sh 的一个验证项。autopilot 在 merge done 后自动调用 close.sh | 流程变更 | autopilot + close.sh | 缺失 4 |
| **D-016** | `gate_D_roundtable` action 扩展为 `gate_roundtable(type, reason)`，支持 A/B/C/D 四种类型。state.py 的 branches 引擎需参数化 roundtable_type | schema 变更 | state.py + JSONL contracts | 缺失 1 |
| **D-017** | `hermes_backup_notify.sh` 在 close-5（飞书通知）中随通知一并触发。通知内容包含 7 步验证摘要 + 备份 commit hash | 流程标准 | autopilot | 缺失 2 |
| **D-018** | `/workspace/devPPL/docs/roundtables/` 下 24 个 untracked 文件必须纳入 git（系统缺陷 DPL-012）。close-3（manifest 更新）扩展为检查 untracked roundtable 文件 | 架构修正 | OC + close.sh | 附加背景 |

### 6.1 对已有 JSONL v2 schema 的变更（D-016）

```jsonl
# 变更前（Architect R4）:
{"on":"BLOCKER_found","action":"gate_D_roundtable","reason":"QA 发现 BLOCKER"}

# 变更后（Product R5）:
{"on":"BLOCKER_found","action":"gate_roundtable","reason":"QA 发现 BLOCKER","roundtable_type":"D"}

# 新增:
{"on":"spec_violates_ironlaw","action":"gate_roundtable","reason":"spec 违反铁律","roundtable_type":"D"}
{"on":"requirement_unclear","action":"gate_roundtable","reason":"需求理解不清","roundtable_type":"D"}
```

### 6.2 pipeline_state.db schema 追加（D-012）

```sql
-- 在 user_version=2 的 migration 中追加
CREATE TABLE IF NOT EXISTS project_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- 初始部署时写入
INSERT OR REPLACE INTO project_config VALUES ('project_type', 'system_mechanism');
INSERT OR REPLACE INTO project_config VALUES ('project_name', 'devPPL');
INSERT OR REPLACE INTO project_config VALUES ('backup_script', '/workspace/hermes_backup_push.sh');
INSERT OR REPLACE INTO project_config VALUES ('notify_script', '/workspace/hermes_backup_notify.sh');
```

---

## 7. 可执行性验证

### 7.1 如果有人拿到这份报告，能否编码实现？

| 检查项 | 状态 | 依据 |
|--------|:----:|------|
| 每一步谁做 | ✅ 明确 | OC / autopilot / state.py / engine / QA / VA / Product |
| 每步的触发条件 | ✅ 21 个分支，每个有 `on` 条件 + 检测方式 |
| 每步的失败去向 | ✅ 6 种 action: retry/block/rollback/continue/gate_roundtable/await_confirm |
| 数据从哪读 | ✅ kanban.db / pipeline_state.db / file system / kanban comment |
| 数据写到哪 | ✅ pipeline_state.db (v2 schema) / kanban comment / .hermes.md |
| 异常重试次数 | ✅ 每步不同 (openapi 3次, dev 1次, qa-d1 2次, close 3次, backup pre 1次/post 2次) |
| Roundtable 何时触发 | ✅ 4 种触发场景 (§1.2) + 每种类型分配哪些人 (§1.3) |
| 备份何时执行 | ✅ 3 个备份点: merge前、merge后VA通过、close-4 |
| 备份用什么命令 | ✅ 按 project_type 查表 (§3.2) |
| close 怎么展开 | ✅ 7 个 sub-step + close.sh 调用方式 (§4.2-4.3) |
| 谁监控 autopilot | ✅ watchdog（已有） |

### 7.2 与已有实现的兼容性

| 组件 | 是否需要改动 | 改动量 |
|------|:----------:|:------:|
| close.sh (104 行) | ❌ 不需要改 | 0 |
| state.py (待实现) | ✅ 需新增 roundtable 类型分发 + 备份策略读取 | +30 行 |
| autopilot.sh (待实现) | ✅ 需新增备份命令调用 + close.sh 调用 | +25 行 |
| checkpoint.py (待实现) | ✅ 需新增 project_config 表 | +10 行 |
| contracts JSONL | ✅ 需扩展 roundtable_type 参数 | 改 3 行 |
| pipeline_state.db schema | ✅ 需新增 project_config 表 | +1 CREATE TABLE |
| hermes_backup_push.sh (已有) | ❌ 不需要改 | 0 |
| hermes_backup_notify.sh (已有) | ❌ 不需要改 | 0 |

**总增量**：约 65 行代码 + 1 张新表 + 3-5 行 JSONL 修改。在 Engineer 的 11h 预估之上增加约 1h 工作量。

---

## 8. 总结

R4 统一工作流中三方在 8 项核心决策上达成共识——7 步管线、JSONL v2、pipeline_state.db v2、dashboard、DPL-011、Autopilot/Watchdog 共存。OC 自检发现四个维度完全缺失：

1. **Roundtable 类型** — 现在在阶段 -1（OC 判定）和管线闸门点（autopilot 触发）两处嵌入，state.py 支持 gate_roundtable(type) 分发
2. **双重备份** — merge 前一次、VA 通过后一次、close 中一次，三个备份点明确标注，按项目类型走不同命令
3. **项目分类** — autopilot 从 pipeline_state.db 的 project_config 表读取 project_type，决定备份策略
4. **S6 闭环** — close 从 1 个原子操作展开为 7 个 sub-step（close-0 到 close-6），autopilot 在 merge done 后自动调用 close.sh

**全部四项缺失已填入 R1-R4 达成共识的 7 步管线框架中。** 所有 R4 已有的共识项（21 分支条件、JSONL v2、schema v2、dashboard、DPL-011）全部保留，无删减。

**下一步**：传 architect（高见远），更新 JSONL 合约和 pipeline_state.db schema 以体现 R5 新增的 D-011~D-018 决定。然后传 engineer（寇豆码）实现。

---

> 产品发言完毕。OC 的四项自检发现不是批评——是系统在自我纠错。我们把"忘记的类型""忘记的备份""忘记的分类""忘记的展开"全部填回了各自应该在的位置。不是重写，是补全。现在这条路，从 Frank 开口到飞书闭环，每个岔路都有路标，每个备份点都有命令，每种项目都知道自己该怎么走。交给架构和研发，按图索骥就行了。
