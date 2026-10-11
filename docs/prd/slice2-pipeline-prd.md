# Slice 2 PRD — 完整 7 步管线：分支 + 回退 + gate_roundtable

> 作者：许清楚（产品负责人） | 日期：2026-07-30 | 版本：v1.0
> 来源：DPL-012 R5 最终统一工作流 → Slice 2（3.5h）
> 前提：Slice 1 已交付：5 步线性管线（dev→qa-exec→va→merge→close）+ checkpoint + 简化 autopilot

---

## 0. Slice 2 在整体架构中的定位

DPL-012 最终按三 Slice 分批交付：

```
Slice 1 (3.5h): checkpoint + 5 步合约 + 简化 autopilot    ← ✅ 已交付
Slice 2 (3.5h): 完整 7 步 + 21 分支 + 回退 + gate_roundtable  ← 本 PRD
Slice 3 (~10h):  DPL-011 + dashboard + watchdog + ABCD 类型 + 备份 + S6 闭环
```

**Slice 2 的产品目标**：在 Slice 1 的线性管线基础上，补回 qa-d1 和 qa-d2 两个评审步骤，引入 21 个分支条件使管线不再是 happy-path-only，加入 rollback 机制处理 VA FALSIFIED 等需回退的场景，扩展 gate_roundtable(type, reason) 支持 A/B/C/D 四种类型的 roundtable 分发。同时扩展 autopilot 以支持 fan-out（dev 和 qa-d1 并行启动后 join）。

**与 Slice 1 的关系**：Slice 2 是 Slice 1 的**扩展**，不是重写。Slice 1 的 checkpoint.py、state.py、autopilot.sh、contracts.jsonl 全部保留，Slice 2 在此基础上添加分支引擎、fan-out 调度、rollback 链路。已有代码的接口保持兼容——新字段追加，不删除已有字段。

---

## 1. 7 步管线：从 5 步到 7 步

### 1.1 步骤变更对照

```
Slice 1（5 步）:          dev → qa-exec → va → merge → close
Slice 2（7 步）:          dev → qa-d1 → qa-exec → qa-d2 → va → merge → close
                              ↑ 新增        ↑ 新增
                            fan-out       rollback 源点
```

| 步骤 | 变更类型 | 说明 |
|------|:--------:|------|
| dev | 保持 | Slice 1 逻辑不变，新增与 qa-d1 的 fan-out join |
| **qa-d1** | **新增** | 测试方案生成 + D1 评审（覆盖率检查） |
| qa-exec | 保持 | 测试执行，新增 BLOCKER/MAJOR/安全漏洞判定 |
| **qa-d2** | **新增** | 测试报告评审（分级判定复核），可触发 rollback |
| va | 扩展 | 新增 FALSIFIED → rollback(dev) |
| merge | 扩展 | 新增分支处理（冲突、备份失败、Frank 闸门） |
| close | 扩展 | 新增 S6 检测 + close.sh 调用 + 子步骤重试 |

### 1.2 新增步骤详解

#### qa-d1：测试方案生成 + D1 评审

| 属性 | 值 |
|------|-----|
| 执行者 | game-qa |
| 前置条件 | spec.md 就绪（由 OC 产出） |
| 触发方式 | fan-out：与 dev 并行启动 |
| 产出 | `docs/qa/test-plan-{id}.md` |
| 评审方 | Product（许清楚） + Architect（高见远） |
| 评审标准 | test_plan.md 覆盖 spec.md 所有 requires → 覆盖率 100% = pass |
| 重试次数 | 最多 2 次补充 |

**流程**：

```
spec.md 就绪
    │
    ├──→ [dev] 研发写代码              ← 并行（fan-out）
    │
    └──→ [qa-d1] QA 生成测试方案        ← 并行（fan-out）
              │
              ▼
         test_plan.md
              │
              ▼
         D1 评审（Product + Architect）
              │
              ├── 覆盖率 = 100% → PASS → 等待 dev done（join）
              │
              ├── 覆盖率 < 100% → QA 补充 → 重新 D1（最多 2 次）
              │
              └── 2 次仍不通过 → block → gate_roundtable(D)
```

#### qa-d2：测试报告评审

| 属性 | 值 |
|------|-----|
| 执行者 | Product + Architect（评审） |
| 前置条件 | qa-exec done（test_report.md 产出） |
| 评审内容 | 分级判定是否正确、MAJOR 是否合理、是否漏报 BLOCKER |
| 产出 | D2 评审结论（pass / conditional_pass / fail） |
| 失败去向 | rollback(dev) 或 rollback(qa-exec)（根据失败原因） |

**三级结论**：

| 结论 | 行为 | 示例 |
|------|------|------|
| **pass** | 推进到 va | 分级判定无错误，无漏报 |
| **conditional_pass** | 继续推进 + 记录 pending items | 分级判定总体正确，但有一条边界 case 存疑 |
| **fail** | rollback | 分级错误（MAJOR 误判为 MINOR）或漏报 BLOCKER |

### 1.3 fan-out：dev 与 qa-d1 并行启动

```
spec.md 就绪
    │
    ├── kanban card: dev（assignee=game-engine）
    │
    └── kanban card: qa-d1（assignee=game-qa）
              │
              ▼
         两者并行执行
              │
              ▼
    join 点：qa-exec 的前置条件 = dev done AND qa-d1 done
    ALL done → 推进到 qa-exec
    任一未 done → 等待
```

**实现方式（fanout.py）**：
- autopilot 检测到 spec.md 就绪 → 创建 dev 和 qa-d1 两张 kanban card
- pipeline_state.db 中两条记录：dev（status=pending）+ qa-d1（status=pending）
- state.py 的 `determine_next_action` 在 qa-exec 前检查：dev.status=done AND qa-d1.status=done → 才能推进

**为什么 qa-d1 不与 qa-d2 一起 fan-out**：qa-d2 依赖 qa-exec 的产出（test_report.md），是串行依赖，不是并行候选。

---

## 2. 21 分支条件：每步的 if 🔴 判定逻辑

以下是完整的 21 个分支条件表。每个条件包含：触发条件、自动判定方式、失败去向（action）。

### 2.1 dev 步骤（3 条分支）

| # | 条件 | 判定方式 | action | target | max_retries |
|---|------|---------|--------|--------|:----------:|
| B-01 | dev 超时（> 60min 未产出） | state.py：started_at + timeout_min vs now | retry | dev | 1 |
| B-02 | dev 自测失败 | kanban task failed | retry | dev | 3 |
| B-03 | dev 忘 commit（produces 缺失） | state.py 合约校验：branch 不存在或 diff 为空 | wait → block | — | — |

**B-03 详细**：autopilot 检测到 produces 缺失 → 写 kanban comment `[CONTRACT_VIOLATION: dev produces 缺失]` → 等待 30min → 若仍缺失 → block，通知 OC。

### 2.2 qa-d1 步骤（2 条分支）

| # | 条件 | 判定方式 | action | target | max_retries |
|---|------|---------|--------|--------|:----------:|
| B-04 | qa-d1 无法生成测试方案（需求不清） | kanban task failed + error_msg 包含"需求" | gate_roundtable | D | — |
| B-05 | qa-d1 覆盖率 < 100%（2 次补充后） | D1 评审：test_plan.md 覆盖的 requires 集合 ≠ spec.md requires 集合 | block | — | 2 |

**B-05 详细**：D1 评审由 Product + Architect 联合评审。第 1/2 次 retry 是 QA 补充方案后重新 D1。第 3 次（2 次 retry 后）直接 block。

### 2.3 qa-exec 步骤（4 条分支）

| # | 条件 | 判定方式 | action | target | max_retries |
|---|------|---------|--------|--------|:----------:|
| B-06 | QA 发现 BLOCKER | 读 test_report.md 的分级字段（BLOCKER count > 0） | gate_roundtable | D | — |
| B-07 | QA 发现 MAJOR > 3 | 读 test_report.md：MAJOR 计数 > 3 | gate_roundtable | D | — |
| B-08 | QA 发现安全漏洞 | 读 test_report.md：security 字段 | gate_roundtable | D | — |
| B-09 | qa-exec 超时（> 45min） | state.py：started_at + timeout_min vs now | retry | qa-exec | 1 |

**B-06/B-07/B-08 的 gate_roundtable 行为**：
- autopilot 创建 D 类 roundtable → kanban_block 当前管线任务
- roundtable 3 个强制议题：(1) 分级判定是否正确 (2) 处置方式是否合理 (3) 修复难度评估
- Frank 裁定后：(a) BLOCKER 转 MAJOR → 继续 / (b) 确认 BLOCKER → rollback(dev)
- 安全漏洞（B-08）：不经过"用户可见"过滤，独立判定，最低 MAJOR → 直接 D 类 roundtable

### 2.4 qa-d2 步骤（3 条分支）

| # | 条件 | 判定方式 | action | target | max_retries |
|---|------|---------|--------|--------|:----------:|
| B-10 | D2 评审：分级错误或漏报 BLOCKER | D2 评审结论 = fail | gate_roundtable | D | — |
| B-11 | D2 评审：fail（非分级错误，测试质量问题） | D2 评审结论 = fail（原因 ≠ 分级错误） | rollback | dev 或 qa-exec | — |
| B-12 | D2 评审：conditional_pass | D2 评审结论 = conditional_pass | continue | — | — |

**B-12 详细**：conditional_pass → 记录 pending items → 不阻塞管线 → pending items 加入 kanban follow-up task。

### 2.5 va 步骤（2 条分支）

| # | 条件 | 判定方式 | action | target | max_retries |
|---|------|---------|--------|--------|:----------:|
| B-13 | VA FALSIFIED | 读 va_report.md conclusion = FALSIFIED | rollback | dev | — |
| B-14 | VA 无法判定（信息不足） | va report error / conclusion = INCONCLUSIVE | block | — | — |

**B-13 rollback 全链**（详见 §3）：
1. pipeline_state.db：dev 状态置为 restart（相当于再次 pending）+ qa-d1/qa-exec/qa-d2/va 状态置为 pending（清除中间状态）
2. checkpoint 记录 rollback 原因 + 链路（rollback_from=va, rollback_to=dev, reason=FALSIFIED）
3. 重新走 dev → qa-d1 → qa-exec → qa-d2 → va

### 2.6 merge 步骤（5 条分支）

| # | 条件 | 判定方式 | action | target | max_retries |
|---|------|---------|--------|--------|:----------:|
| B-15 | merge-1 合并前备份失败 | backup script exit ≠ 0 | retry | merge | 1 |
| B-16 | merge-2 git merge 冲突 | git merge 非 0 退出 | block | — | — |
| B-17 | merge-3 VA 合并验证不通过 | va merge check fail | rollback | dev | — |
| B-18 | merge-4 合并后备份失败 | backup script exit ≠ 0 | retry | merge | 2 |
| B-19 | merge-5 Frank 闸门 | 等待人工确认 | await_confirm | — | — |

**merge 展开为 5 个 micro-step**（R5 D-011）：

```
[merge-1] 合并前备份（hermes_backup_push.sh）
[merge-2] git merge --no-commit --no-ff feat/{task_id}
[merge-3] VA 检查合并结果 + 运行
[merge-4] 合并后最终备份（hermes_backup_push.sh）
[merge-5] Frank 闸门确认 → 推进到 close
```

**备份脚本根据 project_type 选择命令**（R5 D-013）：
- system_mechanism → `bash /workspace/hermes_backup_push.sh`
- pure_product → `git add . && git commit -m 'backup' && git push`
- hybrid → 双重（git push + hermes_backup_push.sh）

### 2.7 close 步骤（2 条分支）

| # | 条件 | 判定方式 | action | target | max_retries |
|---|------|---------|--------|--------|:----------:|
| B-20 | close-0 S6 检测未通过 | 前 6 步任一 verdict ≠ pass/VERIFIED/conditional_pass | block | — | — |
| B-21 | close.sh 子步骤失败（close-1~close-4） | close.sh 内部每步 exit ≠ 0 | retry | close | 3 |

**close 展开为 7 个 micro-step**（R5 D-015）：

```
[close-0] S6 检测：前 6 步全部 pass？
[close-1] 关闭 kanban 任务
[close-2] 更新 GAI（GLOBAL_ACTION_ITEMS.md）
[close-3] 更新 manifest
[close-4] 备份推送（按项目类型）
[close-5] 飞书通知 "闭环完成"
[close-6] 归档 + 清理（openspec archive + worktree remove）
```

### 2.8 分支汇总

```
21 个分支条件，6 种 action 动作：

  action=retry          → 重试（最多 N 次），耗尽 → block        （9 条）
  action=block          → 停止，通知 OC/Frank                      （3 条）
  action=rollback       → 回退到目标步骤                            （3 条）
  action=continue       → 记录 pending → 继续                      （1 条）
  action=gate_roundtable → 创建 roundtable（A/B/C/D 类）           （4 条）
  action=await_confirm  → 等待 Frank 确认                          （1 条）
```

---

## 3. Rollback 机制

### 3.1 触发场景

| 场景 | 触发条件 | 回退起点 | 回退终点 |
|------|---------|---------|---------|
| VA FALSIFIED | va_report.md conclusion = FALSIFIED | va | dev |
| qa-d2 fail（质量问题） | D2 评审结论 = fail（原因 ≠ 分级错误） | qa-d2 | dev 或 qa-exec |
| QA BLOCKER（Frank 裁定后） | D 类 roundtable 裁定 = 确认 BLOCKER | qa-exec | dev |
| merge-3 VA 验证不通过 | VA merge check fail | merge | dev |

### 3.2 Rollback 执行流程

```
触发 rollback(dev)
    │
    ▼
┌──────────────────────────────────────────────────────┐
│ state.py handle_rollback(task_id, target='dev')      │
│                                                      │
│ 1. 读 pipeline_state.db：当前 task_id 的所有步骤      │
│ 2. 回退区间：[target='dev', ...当前失败的步骤]         │
│    对于回退区间内的每一步：                            │
│      - 若 step = target（dev）：                      │
│          status → 'pending', verdict → NULL            │
│          retry_count → retry_count + 1                │
│          rollback_reason → 'VA FALSIFIED'             │
│      - 若 step ∈ (target, current]:                   │
│          status → 'pending', verdict → NULL            │
│          （清除中间状态，等待重新走管线）               │
│                                                      │
│ 3. 写 kanban comment:                                │
│    [ROLLBACK] va→dev: VA FALSIFIED — 回退原因: ...    │
│                                                      │
│ 4. 下次 cron tick：autopilot 检测到 dev status=pending│
│    → 重新创建 dev kanban card + qa-d1（fan-out）       │
└──────────────────────────────────────────────────────┘
```

### 3.3 pipeline_state.db 字段扩展

为支持 rollback，pipeline_steps 表新增字段（在 user_version=2 的 migration 中追加）：

```sql
ALTER TABLE pipeline_steps ADD COLUMN verdict TEXT;
-- 取值: pass | fail | FALSIFIED | VERIFIED | conditional_pass | NA

ALTER TABLE pipeline_steps ADD COLUMN verdict_detail TEXT;
-- JSON: {"claims": [...], "sub_verdicts": {...}}，记录判定详情

ALTER TABLE pipeline_steps ADD COLUMN rollback_from TEXT;
-- 回退来源步骤名，如 'va'；NULL 表示非回退记录

ALTER TABLE pipeline_steps ADD COLUMN rollback_reason TEXT;
-- 回退原因，如 'VA FALSIFIED: claim #3 证伪'
```

### 3.4 Rollback 与 fan-out 的配合

rollback(dev) 后，autopilot 重新走 dev → qa-d1（fan-out）→ ...。关键是：
- rollback 后 dev step 的 retry_count 递增，防止无限 rollback 循环
- 如果 dev retry_count > 3 → block（需要人工介入）

---

## 4. gate_roundtable(type, reason)

### 4.1 四种类型

| 类型 | 用途 | 触发场景 | 参与方 |
|------|------|---------|--------|
| **A** | Yes/No 投票决策 | 方案选择、标准制定、优先级裁定 | 全员（Product + Architect + Engineer + QA） |
| **B** | 头脑风暴 | 工具评估、架构探索、前瞻性分析 | 全员（不产生开发任务） |
| **C** | 风险评估 | 技术选型 risk、架构变更影响面 | Product + Architect + Engineer |
| **D** | 测试评审 | D1/D2 评审、BLOCKER 发现、铁律例外 | Product + Architect |

### 4.2 类型判定来源

```
roundtable 来源有两种：

1. 阶段 -1（OC 判定）：
   Frank 说 "评估一下" / "讨论一下"   → B 类
   Frank 说 "做个决定" / "二选一"     → A 类
   Frank 说 "有风险吗"                → C 类
   Frank 说 "做 X"（明确开发任务）     → 不走 roundtable，走标准管线

2. 管线中（autopilot 判定）：
   spec 铁律冲突                      → D 类
   QA BLOCKER / MAJOR>3 / 安全漏洞    → D 类
   qa-d1 需求不清（2次重试后）         → D 类
   qa-d2 分级错误或漏报 BLOCKER       → D 类
   VA FALSIFIED 有争议               → D 类（可选）
```

### 4.3 D 类 roundtable 的 3 个强制议题

每个 D 类 roundtable 必须覆盖：

1. **分级判定是否正确**：BLOCKER/MAJOR 的判定是否符合 `.hermes.md` §1.2 标准
2. **处置方式是否合理**：回退 dev / 降级继续 / 暂缓 —— 推荐方案 + 理由
3. **修复难度评估**：预估工时、影响范围、是否有 workaround

### 4.4 state.py 中的分发逻辑

```python
# state.py 新增 roundtable 引擎（R5 D-016）
def handle_gate_roundtable(roundtable_type: str, reason: str, task_id: str) -> dict:
    """创建对应类型的 roundtable 并 block 当前任务。"""
    # 1. 创建 roundtable kanban task
    assignees = {
        "A": ["game-director", "game-architect", "game-engine", "game-qa"],
        "B": ["game-director", "game-architect", "game-engine", "game-qa"],
        "C": ["game-director", "game-architect", "game-engine"],
        "D": ["game-director", "game-architect"],
    }[roundtable_type]

    mandatory_topics = (
        ["分级判定是否正确", "处置方式是否合理", "修复难度评估"]
        if roundtable_type == "D" else None
    )

    # 2. 创建 roundtable kanban card
    rt_task = kanban_create(
        title=f"Roundtable ({roundtable_type}): {reason}",
        assignee=assignees[0],  # 第一个作为主 assignee
        body=f"原任务: {task_id}\n类型: {roundtable_type}\n原因: {reason}\n"
             + (f"强制议题: {mandatory_topics}" if mandatory_topics else ""),
    )

    # 3. block 当前管线任务，等待 roundtable 裁定
    kanban_block(task_id=task_id,
                 reason=f"等待 {roundtable_type} 类 roundtable 裁定: {reason}")

    return {"action": "gate_roundtable", "roundtable_type": roundtable_type,
            "roundtable_task": rt_task["task_id"], "reason": reason}
```

### 4.5 从 gate_D_roundtable 到 gate_roundtable 的变更

```
JSONL v1（Architect R4）:
  {"on":"BLOCKER_found","action":"gate_D_roundtable","reason":"QA 发现 BLOCKER"}

JSONL v2（Product R5）:
  {"on":"BLOCKER_found","action":"gate_roundtable","roundtable_type":"D","reason":"QA 发现 BLOCKER"}

新增:
  {"on":"spec_violates_ironlaw","action":"gate_roundtable","roundtable_type":"D","reason":"spec 违反铁律"}
  {"on":"requirement_unclear","action":"gate_roundtable","roundtable_type":"D","reason":"需求理解不清"}
```

---

## 5. Contracts JSONL v2：branches 字段扩展

### 5.1 branches 字段 schema

在 Slice 1 合约基础上追加 `branches` 字段（数组，可空）：

```jsonl
{
  "step": "va",
  "requires": ["test_report.md"],
  "produces": ["va_report.md"],
  "timeout_min": 20,
  "pass_condition": "va_report.md validates all claims",
  "branches": [
    {
      "on": "FALSIFIED",
      "action": "rollback",
      "target": "dev",
      "reason": "VA 证伪：至少一条 claim 被证伪"
    },
    {
      "on": "INCONCLUSIVE",
      "action": "block",
      "reason": "VA 无法判定：信息不足"
    }
  ]
}
```

**branches 条目字段定义**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `on` | string | ✅ | 触发条件标识符（如 `FALSIFIED`, `timeout`, `BLOCKER_found`） |
| `action` | string | ✅ | retry / block / rollback / continue / gate_roundtable / await_confirm |
| `target` | string | 条件 | rollback 和 retry 时的目标步骤；其他 action 为 null |
| `max_retries` | int | 条件 | retry 时的最大重试次数 |
| `reason` | string | ✅ | 人类可读的原因说明 |
| `roundtable_type` | string | 条件 | action=gate_roundtable 时指定 A/B/C/D |
| `backup_step` | string | 条件 | merge 的备份分支用，区分 pre/post |

### 5.2 完整 7 步合约 JSONL（v2）

```jsonl
{"step":"dev","requires":[],"produces":["branch","code_changes"],"timeout_min":60,"pass_condition":"code changes committed to branch","branches":[{"on":"timeout","action":"retry","target":"dev","max_retries":1,"reason":"dev 超时（>60min）"},{"on":"self_test_fail","action":"retry","target":"dev","max_retries":3,"reason":"engine 自测失败"},{"on":"produces_missing","action":"block","reason":"dev 产物缺失：忘 commit 或 diff 为空"}]}
{"step":"qa-d1","requires":["spec.md"],"produces":["test_plan.md"],"timeout_min":30,"pass_condition":"test_plan.md 覆盖 spec.md 所有 requires","branches":[{"on":"requirement_unclear","action":"gate_roundtable","roundtable_type":"D","reason":"需求理解不清，无法生成测试方案"},{"on":"coverage_insufficient","action":"retry","target":"qa-d1","max_retries":2,"reason":"覆盖率 < 100%，QA 补充测试方案"}]}
{"step":"qa-exec","requires":["branch","code_changes","test_plan.md"],"produces":["test_report.md"],"timeout_min":45,"pass_condition":"test_report.md 无 BLOCKER 且 MAJOR≤3 且无安全漏洞","branches":[{"on":"BLOCKER_found","action":"gate_roundtable","roundtable_type":"D","reason":"QA 发现 BLOCKER"},{"on":"MAJOR_gt_3","action":"gate_roundtable","roundtable_type":"D","reason":"MAJOR > 3"},{"on":"security_vuln","action":"gate_roundtable","roundtable_type":"D","reason":"发现安全漏洞"},{"on":"timeout","action":"retry","target":"qa-exec","max_retries":1,"reason":"qa-exec 超时（>45min）"}]}
{"step":"qa-d2","requires":["test_report.md"],"produces":["d2_review_conclusion.md"],"timeout_min":25,"pass_condition":"D2 评审结论 = pass 或 conditional_pass","branches":[{"on":"grading_error","action":"gate_roundtable","roundtable_type":"D","reason":"D2 评审：分级错误或漏报 BLOCKER"},{"on":"quality_fail","action":"rollback","target":"dev","reason":"D2 评审 fail：测试质量问题"},{"on":"conditional_pass","action":"continue","reason":"conditional pass：记录 pending items → 继续推进"}]}
{"step":"va","requires":["test_report.md"],"produces":["va_report.md"],"timeout_min":20,"pass_condition":"va_report.md validates all claims","branches":[{"on":"FALSIFIED","action":"rollback","target":"dev","reason":"VA 证伪：至少一条 claim 被证伪"},{"on":"INCONCLUSIVE","action":"block","reason":"VA 无法判定：信息不足"}]}
{"step":"merge","requires":["va_report.md","test_report.md"],"produces":["merge_commit","backup_snapshot"],"timeout_min":20,"pass_condition":"git merge 成功 + 备份完成 + Frank 确认","branches":[{"on":"pre_merge_backup_fail","action":"retry","target":"merge","max_retries":1,"backup_step":"pre","reason":"合并前备份失败"},{"on":"conflict","action":"block","reason":"merge 冲突：engine 需要解决冲突"},{"on":"va_merge_check_fail","action":"rollback","target":"dev","reason":"merge-3 VA 合并验证不通过"},{"on":"post_merge_backup_fail","action":"retry","target":"merge","max_retries":2,"backup_step":"post","reason":"合并后备份失败"},{"on":"human_gate","action":"await_confirm","reason":"等待 Frank 确认 merge"}]}
{"step":"close","requires":["merge_commit"],"produces":["gai_update","manifest_update","backup_snapshot"],"timeout_min":15,"pass_condition":"close.sh 6 步全部 pass","branches":[{"on":"s6_check_fail","action":"block","reason":"S6 检测未通过：存在未完成步骤"},{"on":"step_fail","action":"retry","target":"close","max_retries":3,"reason":"close.sh 子步骤失败"}]}
```

### 5.3 JSONL 文件位置与读取

- **位置**：`config/contracts.jsonl`（保留同一文件路径，直接扩展内容）
- **兼容性**：Slice 1 的 5 步合约被 7 步合约替换。不再兼容 Slice 1——Slice 2 部署时需更新 JSONL 文件。state.py 的 `load_contracts` 无需改动（按行读取 JSON 对象）。
- **branches 为空数组**：表示该步骤无条件分支（如可能的纯通过步骤）。

---

## 6. Autopilot 扩展

### 6.1 state.py：新增 branches 引擎

在 Slice 1 的 `determine_next_action` 基础上，新增分支条件判定逻辑：

```python
# state.py 新增函数

def evaluate_branches(step_name: str, condition: str,
                      contracts: list[dict], db: CheckpointDB) -> dict:
    """根据合约中的 branches 字段判定分支动作。

    Returns:
        {'action': 'retry'|'block'|'rollback'|'continue'|'gate_roundtable'|'await_confirm',
         'detail': str, 'branch': dict}
    """
    contract = _contract_by_step(contracts).get(step_name, {})
    branches = contract.get("branches", [])
    for branch in branches:
        if branch["on"] == condition:
            return {"action": branch["action"], "detail": branch.get("reason", ""),
                    "branch": branch}
    # 无匹配分支 → 默认 block
    return {"action": "block", "detail": f"未匹配到分支条件: {condition}",
            "branch": {"on": condition, "action": "block"}}


def handle_rollback(task_id: str, target_step: str, reason: str, db: CheckpointDB):
    """执行 rollback：将 [target_step ... 当前步骤] 的所有步骤重置为 pending。

    当前步骤（触发 rollback 的那步）设置为 failed + verdict=FALSIFIED（如果是 VA）。
    target_step 设置为 pending（等待重新执行）。
    target 和当前步骤之间的所有步骤清除。
    """
    all_steps = db.get_all_steps(task_id)
    step_names = [s["step_name"] for s in all_steps]
    current_step = all_steps[-1]["step_name"]

    # 找到 target 和 current 之间的所有步骤
    target_idx = step_names.index(target_step) if target_step in step_names else 0
    current_idx = step_names.index(current_step)

    for s in all_steps[target_idx:current_idx + 1]:
        if s["step_name"] == target_step:
            # 目标步骤：重置为 pending，递增 retry_count
            db.upsert_step(task_id, s["step_name"], "pending",
                           rollback_from=current_step,
                           rollback_reason=reason)
            db.increment_retry(task_id, s["step_name"])
        elif s["step_name"] == current_step:
            # 当前步骤：标记 failed + 记录 verdict
            db.upsert_step(task_id, s["step_name"], "failed",
                           verdict="FALSIFIED" if current_step == "va" else "fail",
                           rollback_from=current_step,
                           rollback_reason=reason)
        else:
            # 中间步骤：清除
            db.upsert_step(task_id, s["step_name"], "pending",
                           rollback_from=current_step,
                           rollback_reason=reason)


def check_join_condition(task_id: str, join_steps: list[str], db: CheckpointDB) -> bool:
    """检查 fan-out join 条件：join_steps 中所有步骤是否都 done。

    用于 qa-exec 的前置条件检查：
    check_join_condition(task_id, ["dev", "qa-d1"], db) → True/False
    """
    for step_name in join_steps:
        step = db.get_step(task_id, step_name)
        if step is None or step["status"] != "done":
            return False
    return True
```

### 6.2 fanout.py：并行分发

新增 `pipeline/fanout.py`，负责 fan-out 场景的 kanban card 创建：

```python
"""pipeline/fanout.py — 并行步骤分发

用法：
    python3 pipeline/fanout.py --task t_xxx --steps dev,qa-d1
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Steps that can run in parallel with their assignees
FANOUT_CONFIG = {
    "dev": {"assignee": "game-engine", "title_prefix": "dev"},
    "qa-d1": {"assignee": "game-qa", "title_prefix": "qa-d1"},
}


def create_task(step_name: str, task_id: str) -> bool:
    """创建单个 kanban card"""
    config = FANOUT_CONFIG[step_name]
    title = f"{config['title_prefix']}: {task_id}"
    try:
        subprocess.run(
            ["hermes", "kanban", "create",
             "--title", title,
             "--assignee", config["assignee"],
             "--body", f"task_id={task_id}"],
            capture_output=True, text=True, timeout=15,
        )
        return True
    except Exception:
        return False


def fanout_steps(task_id: str, steps: list[str]) -> dict:
    """并行创建多个步骤的 kanban card"""
    results = {}
    for step in steps:
        ok = create_task(step, task_id)
        results[step] = "created" if ok else "failed"
    return results
```

### 6.3 autopilot.sh：新增分支处理

在 Slice 1 的 autopilot.sh 基础上，新增 `retry`/`rollback`/`gate_roundtable`/`await_confirm` 四种 action 的 shell 处理：

```
autopilot.sh 新增 case 分支：

retry)
    # 检查 retry_count 是否超过 max_retries
    # 未超 → increment_retry + 重新创建 kanban card
    # 已超 → block

rollback)
    # 调用 state.py handle_rollback(task_id, target, reason)
    # 下次 cron tick 会检测到 dev status=pending → 重新 fan-out

gate_roundtable)
    # 调用 state.py handle_gate_roundtable(type, reason)
    # → 创建 roundtable kanban card + kanban_block 当前任务

await_confirm)
    # kanban_comment "等待 Frank 确认 merge"
    # kanban_block 当前任务
```

### 6.4 心跳文件

autopilot.sh 每个 cron tick 写心跳文件 `/.pipeline/heartbeat`：

```bash
# 在 autopilot.sh 主循环结束时
date -u '+%Y-%m-%dT%H:%M:%SZ' > /.pipeline/heartbeat
```

watchdog 通过检查该文件的 mtime 来判断 autopilot 是否存活。

---

## 7. pipeline_state.db v2 Schema

### 7.1 新增字段（pipeline_steps 表）

在 Slice 1 的 v1 schema 基础上，通过 user_version=2 的 migration 追加：

```sql
-- user_version=2 migration
ALTER TABLE pipeline_steps ADD COLUMN verdict TEXT;
-- 取值: 'pass' | 'fail' | 'FALSIFIED' | 'VERIFIED' | 'conditional_pass'

ALTER TABLE pipeline_steps ADD COLUMN verdict_detail TEXT;
-- JSON: {"claims": [{"id":1,"result":"pass"},...], "sub_verdicts": {...}}

ALTER TABLE pipeline_steps ADD COLUMN contract_check_passed INTEGER DEFAULT 0;
-- 合约校验是否通过: 0=未检, 1=通过, -1=失败

ALTER TABLE pipeline_steps ADD COLUMN rollback_from TEXT;
-- 回退来源步骤名（如 'va'）

ALTER TABLE pipeline_steps ADD COLUMN rollback_reason TEXT;
-- 回退原因
```

### 7.2 project_config 表（已实现于 Slice 1）

Slice 1 的 D1 裁定后已加入 `project_config` 表（key-value 结构）。Slice 2 继续使用，不需新增。

---

## 8. 验收标准

### 8.1 功能验收

| # | 验收项 | 验证方式 | 通过标准 |
|---|--------|---------|---------|
| AC-1 | **7 步管线完整流转** | 创建 kanban task → 观察 autopilot 日志 | dev→qa-d1→qa-exec→qa-d2→va→merge→close 全部完成，pipeline_state.db 中 7 行记录 |
| AC-2 | **fan-out 并行** | spec.md 就绪 → 检查 autopilot 创建的 kanban card | dev 和 qa-d1 两张 kanban card 同时创建 |
| AC-3 | **join 条件** | dev done 但 qa-d1 未 done | qa-exec 不推进，等待 qa-d1 完成 |
| AC-4 | **分支 retry** | 模拟 dev 超时 | autopilot 检测 → retry 1 次 → 创建 dev kanban card |
| AC-5 | **分支 retry 耗尽** | 模拟 qa-d1 3 次 retry | 第 4 次 → block，kanban_comment 告警 |
| AC-6 | **gate_roundtable(D)** | 模拟 QA 发现 BLOCKER | autopilot 创建 D 类 roundtable + kanban_block 当前任务 |
| AC-7 | **gate_roundtable(A/B/C/D)** | 检查 roundtable_type 参数化 | 四种类型对应不同的 assignee 集合和强制议题 |
| AC-8 | **rollback VA FALSIFIED** | 模拟 VA report conclusion=FALSIFIED | pipeline_state.db dev=重启, qa/va=清除 → 下轮 cron 重新 fan-out |
| AC-9 | **rollback retry 上限** | 连续 3 次 rollback 到 dev | 第 4 次 → block |
| AC-10 | **branches JSONL 解析** | state.py 加载 branches 字段 | 每条合约的 branches 数组正确解析，包含 on/action/target/max_retries |
| AC-11 | **S6 检测** | 前 6 步中有 1 步未 done | close-0 检测失败 → block |
| AC-12 | **close.sh 调用** | merge done 后 autopilot 调用 close.sh | close.sh 执行 + 返回 exit code |

### 8.2 非功能验收

| # | 验收项 | 标准 |
|---|--------|------|
| AC-13 | **向后兼容** | Slice 1 的 checkpoint.py 接口不变，新增字段不影响已有读写 |
| AC-14 | **幂等 rollback** | 同一 task 的重复 rollback 不产生重复记录 |
| AC-15 | **日志可追溯** | 每个分支判定、rollback、gate_roundtable 都在 autopilot 日志中记录 |

### 8.3 测试场景

| 场景 | 操作 | 预期结果 |
|------|------|---------|
| 正常 7 步流转 | 创建 kanban task → 各 agent 依次完成 | 7 步全部 done，close.sh 闭环完成 |
| fan-out + join | dev 先完成，qa-d1 后完成 | qa-exec 在 qa-d1 done 后才推进 |
| dev 超时 → retry | 设置 timeout_min=1 → dev 超时 | retry 1 次 → 重新创建 dev kanban |
| QA BLOCKER → roundtable | QA report 标记 BLOCKER | autopilot 创建 D 类 roundtable + block |
| VA FALSIFIED → rollback | VA report conclusion=FALSIFIED | rollback → dev 重启 → 重新走完整管线 |
| rollback 上限 | 连续 rollback 3 次 | 第 4 次 block |
| merge 冲突 | git merge 产生冲突 | block → engine 解决 → 继续 |
| close.sh 失败 | close.sh 某步出口非 0 | retry 3 次 → block |
| contract branches 不匹配 | 条件触发但 branches 无匹配 | 默认 action=block |
| 心跳文件 | autopilot cron tick 完成 | `/.pipeline/heartbeat` mtime 更新 |

---

## 9. 不做的事（Slice 3 才做）

| 项目 | 为什么不在 Slice 2 做 | 影响 |
|------|----------------------|------|
| **dashboard.py 红绿灯面板** | 依赖 verdict 字段（Slice 2 引入） + 多维度展示——展示层独立于分支引擎 | Slice 2 通过 SQLite CLI 或日志查看状态 |
| **DPL-011 boot_context** | session DB 查询 + .hermes.md 动态段写入是独立子系统 | 不影响管线核心流转 |
| **ABCD 类型完整的 roundtable 自动化** | A/B/C 三类 roundtable 的创建、投票、风险矩阵输出需要 OC 深度参与 | Slice 2 仅支持 gate_roundtable 的 D 类分发；A/B/C 类由 OC 在阶段 -1 手动判定 |
| **close.sh 7 个 micro-step 完整展开** | close-5（飞书通知）和 close-6（归档清理）涉及外部系统和 OpenSpec CLI | Slice 2 的 close 调用 close.sh 但不细化为 7 个 sub-step 的状态追踪 |
| **备份按项目类型分类** | project_config 表已建，但 system_mechanism/pure_product/hybrid 的备份命令执行在 Slice 3 | Slice 2 中 merge 的备份使用硬编码的 `hermes_backup_push.sh` |
| **watchdog 监控 autopilot 心跳** | watchdog 已有，但 Slice 2 只需确保 autopilot 写心跳文件 | Slice 3 中 watchdog cron 检查心跳并告警 |

---

## 10. 总结

Slice 2 在 Slice 1 的线性骨架上加了三个维度：

1. **横向扩展**：5 步 → 7 步（qa-d1 + qa-d2），fan-out 让 dev 和 qa-d1 并行
2. **纵向扩展**：每步从 happy-path-only 变为 21 条分支条件——超时、失败、BLOCKER、FALSIFIED、冲突、备份失败——每条有明确的判定方式和去向
3. **非线性扩展**：rollback 让管线不再"失败即死亡"——VA FALSIFIED 可以回退到 dev 重新来过，而非需要人工重建整条链路

gate_roundtable(type, reason) 是分歧的官方出口：管线的自动化推进遇到无法自主判定的分歧（铁律冲突、BLOCKER、分级争议）时，不是硬 block 然后等死，而是创建指定类型的 roundtable，把裁定权交给正确的角色集合。

**与 Slice 1 的增量**：
- `config/contracts.jsonl`：5 行 → 7 行，每行追加 branches 字段
- `pipeline/state.py`：~377 行 → ~500 行（+ branches 引擎 + rollback + gate_roundtable）
- `pipeline/fanout.py`：0 → ~70 行（新文件）
- `pipeline/checkpoint.py`：v1 → v2 migration（新增 5 列）
- `scripts/autopilot.sh`：174 行 → ~250 行（+ retry/rollback/gate_roundtable/await_confirm 处理）
- `pipeline/constants.py`：STEP_NAMES 从 5 → 7

---

> 产品发言完毕。Slice 1 证明管线能走路——5 步从 dev 走到 close。Slice 2 让它成为一个真正能在岔路口判断方向、摔倒了能爬起来的系统。21 个分支不是复杂度，是安全感——每个可能的失败都有了预设的应对。交给架构和研发，按图索骥即可。
