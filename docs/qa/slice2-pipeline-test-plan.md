# Slice 2 完整 7 步管线 — QA D1 测试方案

> 版本：v1.0 | 日期：2026-07-30 | 作者：game-qa
>
> 被测范围：`pipeline/state.py` + `pipeline/fanout.py` + `pipeline/checkpoint.py` + `pipeline/constants.py` + `scripts/autopilot.sh` + `config/contracts.jsonl`
>
> 输入文档：
> - PRD：`docs/prd/slice2-pipeline-prd.md`（v1.0，731 行）
> - Slice 1 测试方案：`docs/qa/slice1-pipeline-test-plan.md`（v1.0，411 行）
> - 已有代码：`pipeline/` 下 7 个 .py 文件（~1000 行 state.py）+ `scripts/autopilot.sh`（174 行）
>
> 分级依据：`docs/standards/qa-finding-classification.md` v1.0

---

## 0. 测试范围概览

```
被测模块                       PRD AC 覆盖      分支覆盖             新增/扩展
───────────────────────────────────────────────────────────────────────────
pipeline/state.py (1001行)     AC-1~12,14~15    B-01~B-21 (21条)     Slice 2 主战场
pipeline/fanout.py (53行)      AC-2, AC-3       —                    Slice 2 新增
pipeline/checkpoint.py (296行) AC-13, AC-14     —                    v1→v2 migration
pipeline/constants.py (50行)   AC-7             —                    ROUNDTABLE 常量
scripts/autopilot.sh (174行)   AC-4~6,8~9,11~12 所有 action 响应     需扩展
config/contracts.jsonl (7行)   AC-10            B-01~B-21            Slice 1→2 替换
```

### 0.1 Slice 1 回归范围

Slice 1 的以下 TC 需在 Slice 2 环境中重新验证（步骤名已从 5 步变为 7 步，但核心机制保留）：

| Slice 1 TC | 说明 | Slice 2 适配 |
|:---:|------|------|
| TC-01 | checkpoint 初始化 + WAL | 验证 user_version=2，migration 正确执行 |
| TC-02 | 断点续跑 | 适配 7 步步骤名 |
| TC-06 | flock 防重入 | 不变 |
| TC-09 | 幂等建表 | 验证 migration 幂等 |

---

## ⚠️ D1 前置发现：PRD 与实现的关键冲突（4 项）

在编写测试方案前，QA 对比 PRD §2（21 分支）与 `config/contracts.jsonl`（实际合约），以及 `scripts/autopilot.sh`（实际调度器），发现以下关键冲突。

| # | 冲突项 | PRD 规定 | 实际代码/合约 | 影响 | 风险级别 |
|---|--------|---------|-------------|------|:---:|
| **D1-F1** | **VA FALSIFIED 处理** | PRD §2.5 B-13：`action=rollback, target=dev` | contracts.jsonl 第5行：`{"on":"FALSIFIED","action":"gate_roundtable","roundtable_type":"D"}` | FALSIFIED 时是直接回退还是先走 D 类 roundtable？PRD 正文要求回退，但合约先走 roundtable。两者行为完全不同——rollback 直接清除中间状态，gate_roundtable 需等待 Frank 裁定后再回退。 | **BLOCKER** |
| **D1-F2** | **autopilot.sh 未适配 Slice 2** | PRD §6.3 描述 autopilot.sh 新增 retry/rollback/gate_roundtable/await_confirm 四种 action 处理 | 实际 autopilot.sh 仍为 Slice 1 版本：只处理 start_step/wait/complete/error 四种 action，无 retry/rollback/gate_roundtable/await_confirm 分支 | state.py 的 `advance_pipeline()` 返回 retry/rollback/gate_roundtable/await_confirm 时，autopilot.sh 会落入 default `*` case 输出 "未知 action" 日志——**所有分支 action 均无法执行**。 | **BLOCKER** |
| **D1-F3** | **qa-exec 缺少 security_vuln 和 timeout 分支** | PRD §2.3 B-08=安全漏洞→gate_roundtable(D)，B-09=超时→retry | contracts.jsonl 第3行 qa-exec branches 只有 BLOCKER_found/MAJOR_gt_3/MAJOR_le_3 三条，缺少 security_vuln 和 timeout 分支 | 安全漏洞触发时会有 "未匹配到分支条件" 导致的默认 block（幸运的是这符合"不要静默放过"原则），但超时场景没有 retry 机会——直接 block 而非 PRD 规定的重试 1 次。 | **MAJOR** |
| **D1-F4** | **contracts.jsonl dev branches 与 PRD B-01~B-03 不完全对应** | PRD B-02=self_test_fail→retry(3)，B-03=produces_missing→wait→block | contracts.jsonl 第1行 dev branches：timeout→retry(1), timeout_after_retry→block, contract_violation→block, spec_violates_ironlaw→gate_roundtable(D)。B-02 self_test_fail 没有对应分支。B-03 produces_missing 由 contract_violation 覆盖但少了 wait 30min 的中间步骤。 | B-02 缺失意味着 engine 自测失败时不会自动 retry（kanban task failed 直接 block），与 PRD 规定的 3 次重试不一致。 | **MAJOR** |

**裁定要求**：上述 4 项冲突必须由产品（许清楚）+ 架构师（高见远）在 24h 内给出统一口径。D1-F1 和 D1-F2 直接影响 21 条分支中的 9 条分支的可测试性。

---

## 1. 测试环境准备

### 1.1 硬件/OS

| 维度 | 要求 |
|------|------|
| OS | Linux（与生产环境一致，`/workspace/devPPL`） |
| Python | 3.11+（标准库：sqlite3, json, subprocess, pathlib, argparse） |
| Bash | ≥ 4.0（支持 `set -euo pipefail`） |
| SQLite | ≥ 3.35（支持 ALTER TABLE ADD COLUMN） |
| 测试框架 | pytest ≥ 7.0（现有项目已安装） |

### 1.2 测试前清理脚本

```bash
#!/bin/bash
# 每次测试前执行，恢复干净状态
cd /workspace/devPPL

# 1. 删除旧 pipeline_state.db
rm -f pipeline_state.db test_pipeline_state.db

# 2. 确认 contracts.jsonl 存在且 7 行可解析
python3 -c "
import json
with open('config/contracts.jsonl') as f:
    lines = [json.loads(l) for l in f if l.strip()]
assert len(lines) == 7, f'Expected 7 steps, got {len(lines)}'
steps = [l['step'] for l in lines]
assert steps == ['dev','qa-d1','qa-exec','qa-d2','va','merge','close'], f'Steps: {steps}'
print(f'contracts.jsonl OK: {len(lines)} steps')
"

# 3. 确认 pipeline/ 模块可导入
python3 -c "
from pipeline.checkpoint import CheckpointDB
from pipeline.state import advance_pipeline, BranchesEvaluator, execute_rollback
from pipeline.fanout import detect_fanout_opportunity, check_join_point
from pipeline.constants import STEP_NAMES, ROUNDTABLE_ASSIGNEES
print('import OK')
print(f'STEP_NAMES: {STEP_NAMES}')
print(f'STEP_ORDER: {dict(zip(STEP_NAMES, range(7)))}')
"

# 4. 清理残留锁文件
rm -f /tmp/autopilot.lock
```

### 1.3 Mock 策略

与 Slice 1 类似，autopilot 依赖 kanban 系统。Mock 方法：

| 依赖 | Mock 方式 | 影响 TC |
|------|----------|:---:|
| `hermes kanban show --json` | 替换为本地 JSON 响应文件 | 所有需要读 kanban 状态的 TC |
| `hermes kanban create` | `echo "created: t_mock"` + exit 0 | fanout TC |
| `hermes kanban comment` | `echo "commented"` + exit 0 | 错误通知 TC |
| `hermes kanban complete` | `echo "completed"` + exit 0 | close TC |
| `hermes kanban block` | `echo "blocked: t_mock"` + exit 0 | gate_roundtable TC |

**重要变更**：由于 Slice 2 的 state.py 新增了 retry/rollback/gate_roundtable/await_confirm 返回，**测试将直接调用 state.py 的 `advance_pipeline()` 函数**（绕过 autopilot.sh），配合 mock kanban 响应。autopilot.sh 的端到端测试需等 D1-F2 修复后进行。

### 1.4 状态模拟辅助函数

```python
"""测试辅助：pipeline_state.db 状态预设"""
from pipeline.checkpoint import CheckpointDB

def setup_task_with_steps(db, task_id, steps_spec):
    """
    预设 pipeline_state.db 状态。
    steps_spec: [(step_name, status, extra), ...]
    extra: dict with optional error_msg, verdict, retry_count, started_at
    """
    for step_name, status, extra in steps_spec:
        kwargs = {"task_id": task_id, "step_name": step_name, "status": status}
        kwargs.update(extra)
        db.upsert_step(**kwargs)
```

---

## 2. 功能验收测试用例（AC 1-12）

### TC-01：7 步管线完整流转（AC-1）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-01 |
| **对应 AC** | AC-1：7 步管线完整流转 |
| **触发条件** | 新 kanban task → autopilot 依次推进 7 步 |
| **前置步骤** | 清理 pipeline_state.db，contracts.jsonl 就绪 |
| **步骤** | 1. advance_pipeline("t_tc01") → 应返回 action=start_step, step=dev<br>2. 模拟 dev done（upsert_step dev done + mock kanban dev done）→ advance → 应返回 start_step qa-d1<br>3. 模拟 qa-d1 done → advance → 应返回 start_step qa-exec<br>4. 模拟 qa-exec done（无 BLOCKER）→ advance → 应返回 start_step qa-d2<br>5. 模拟 qa-d2 pass → advance → 应返回 start_step va<br>6. 模拟 va VERIFIED → advance → 应返回 start_step merge<br>7. 模拟 merge done → advance → 应返回 start_step close<br>8. 模拟 close done → advance → 应返回 action=complete |
| **预期结果** | 1. pipeline_state.db 含 7 行：全部 status='done'<br>2. 步骤顺序：dev→qa-d1→qa-exec→qa-d2→va→merge→close<br>3. 最终 advance 返回 action=complete<br>4. 每行有 started_at 和 finished_at（非空） |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（7 步管线是最小可行骨架）+ 功能阻断（全流程核心路径）+ 无 workaround。 |
| **环境依赖** | mock kanban（每一步需返回 done 状态） |

### TC-02：fan-out 并行创建（AC-2）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-02 |
| **对应 AC** | AC-2：fan-out 并行——dev 和 qa-d1 同时创建 kanban card |
| **触发条件** | spec.md 就绪 → autopilot 检测到 fanout 机会 |
| **前置步骤** | 1. 清理 pipeline_state.db<br>2. 初始化 dev step status='done'（模拟 spec.md 已产出） |
| **步骤** | 1. 调用 `detect_fanout_opportunity("t_tc02", db)`<br>2. 验证返回值<br>3. 调用 `advance_pipeline("t_tc02")` |
| **预期结果** | 1. `detect_fanout_opportunity` 返回 `('dev', 'qa-d1')`<br>2. advance_pipeline 返回 action=start_step, step=qa-d1<br>3. dev 和 qa-d1 的 kanban card 都应被创建（验证 fanout.py 的 `fanout_steps` 函数） |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（fan-out 失效 = d1 不会开始，管线卡在 dev 完成之后）+ 功能阻断（管线无法前进到 qa-exec）+ 无 workaround。 |
| **环境依赖** | mock kanban create |

### TC-03：join 条件——qa-exec 等待 dev + qa-d1 都 done（AC-3）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-03 |
| **对应 AC** | AC-3：join 条件——dev done 但 qa-d1 未 done → qa-exec 不推进 |
| **触发条件** | dev=done, qa-d1=pending/running |
| **前置步骤** | 1. 预设状态：dev done, qa-d1 running<br>2. `check_join_point("t_tc03", db)` |
| **步骤** | 1. 验证 check_join_point 返回 False<br>2. advance_pipeline — 状态为 qa-d1 running 时应返回 action=wait<br>3. 将 qa-d1 也设为 done<br>4. 再次 check_join_point → 应返回 True（因为 join-step qa-exec 还未创建）<br>5. advance_pipeline — qa-d1 done + dev done → 应返回 action=start_step, step=qa-exec |
| **预期结果** | 1. qa-d1 未 done 时，qa-exec 不推进<br>2. dev + qa-d1 都 done → qa-exec 可推进<br>3. check_join_point 判定逻辑正确 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（join 失效 = qa-exec 可能在 qa-d1 完成前就开始执行）+ 功能阻断（破坏并行逻辑）+ 无 workaround。 |
| **环境依赖** | mock kanban |

### TC-04：分支 retry——dev 超时（AC-4, B-01）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-04 |
| **对应 AC/B** | AC-4 / B-01：dev 超时 → retry 1 次 |
| **触发条件** | dev 步骤运行时间 > timeout_min=60 |
| **前置步骤** | 1. 预设 dev status='running', started_at=<61min ago><br>2. contracts.jsonl dev timeout_min=60 |
| **步骤** | 1. advance_pipeline("t_tc04")<br>2. 检查返回 action<br>3. 检查 dev 的 retry_count |
| **预期结果** | 1. state.py 检测超时 → 标记 failed + 分支引擎返回 action=retry<br>2. dev retry_count = 1（第 1 次重试）<br>3. dev status 重置为 pending |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（超时检测 + 自动重试是管线的核心自动化能力）+ 功能阻断（失效则管线静默卡死）+ 无 workaround。 |
| **环境依赖** | 无需 mock kanban（超时检测发生在 kanban 查询之前） |

### TC-05：分支 retry 耗尽（AC-5）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-05 |
| **对应 AC/B** | AC-5：qa-d1 retry 耗尽 → block |
| **触发条件** | qa-d1 已重试 2 次（retry_count=2），第 3 次触发后超过 max_retries=2 |
| **前置步骤** | 预设 qa-d1 status='failed', retry_count=2, error_msg='不完整' |
| **步骤** | 1. advance_pipeline("t_tc05")<br>2. 检查返回 action |
| **预期结果** | 1. BranchesEvaluator 检测 retry_count(2) >= max_retries(2) → 返回 action=block<br>2. qa-d1 status='blocked'<br>3. 不创建新的 qa-d1 kanban card |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（无限重试循环浪费资源 + 管线无法推进）+ 功能阻断（安全边界）+ 无 workaround。 |
| **环境依赖** | 无 |

### TC-06：gate_roundtable(D) — QA 发现 BLOCKER（AC-6, B-06）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-06 |
| **对应 AC/B** | AC-6 / B-06：qa-exec 完成，test_report.md 标记 BLOCKER → gate_roundtable(D) |
| **触发条件** | qa-exec done + test_report 含 BLOCKER |
| **前置步骤** | 1. 预设 qa-exec status='done', error_msg 或 detail 含 "BLOCKER"（由 _match_condition 匹配）<br>2. contracts.jsonl qa-exec branch BLOCKER_found→gate_roundtable(D) |
| **步骤** | 1. advance_pipeline("t_tc06") → qa-exec done 后分支引擎评估<br>2. 检查返回 action<br>3. 检查 qa-exec 状态 |
| **预期结果** | 1. 返回 action=gate_roundtable, roundtable_type='D'<br>2. qa-exec status='blocked', error_msg 含 '[GATE]'<br>3. roundtable body 含 3 个强制议题：分级判定是否正确 / 处置方式是否合理 / 修复难度评估<br>4. assignees=['game-director', 'game-architect'] |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（BLOCKER 发现后不创建 roundtable = 管线静默绕过安全闸门）+ 功能阻断（安全决策流程缺失）+ 无 workaround。 |
| **环境依赖** | mock kanban create（roundtable kanban task）+ mock kanban block |

### TC-07：gate_roundtable 类型映射（AC-7）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-07 |
| **对应 AC** | AC-7：4 种 roundtable type 的 assignee 和 workflow 映射 |
| **触发条件** | 直接调用 `handle_gate_roundtable(type, reason, context, db)` |
| **前置步骤** | 无 |
| **步骤** | 分别以 A/B/C/D 类型调用 handle_gate_roundtable：<br>1. type='A' → 验证 assignees 含 4 人 + workflow='vote'<br>2. type='B' → 验证 creates_dev_tasks=False<br>3. type='C' → 验证 assignees 不含 game-qa<br>4. type='D' → 验证强制议题出现 |
| **预期结果** | 1. A: assignees=['game-director','game-architect','game-engine','game-qa'], workflow='vote', creates_dev_tasks=True<br>2. B: creates_dev_tasks=False, workflow='brainstorm', block_kind='needs_input'<br>3. C: assignees 只有 3 人（无 game-qa）, workflow='risk_matrix'<br>4. D: mandatory_topics 含 3 项，workflow='review' |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（类型映射错误导致错误的参与人集合）+ 功能部分阻断但有 workaround（手动纠正参与人）。 |
| **环境依赖** | 无 |

### TC-08：rollback VA FALSIFIED（AC-8, B-13）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-08 |
| **对应 AC/B** | AC-8 / B-13（注：如 D1-F1 未裁定，按 PRD 正文的 rollback→dev 路径测试） |
| **触发条件** | va 步骤 conclusion=FALSIFIED |
| **前置步骤** | 1. 预设完整管线：dev done, qa-d1 done, qa-exec done, qa-d2 done, va running<br>2. 触发 va FALSIFIED → rollback(dev) |
| **步骤** | 1. 直接调用 `execute_rollback("t_tc08", "va", "dev", "VA FALSIFIED: claim #3", db)`<br>2. 检查 pipeline_state.db 各步骤状态 |
| **预期结果** | 1. va step: status='failed', verdict='fail'<br>2. dev step: status='pending', retry_count 递增（从 0→1 或恢复为 0）<br>3. qa-d1/qa-exec/qa-d2: status='cancelled', verdict='cancelled_by_rollback'<br>4. merge/close 未创建的步骤不受影响 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（VA 证伪后无法回退 = 管线卡死，需人工重建）+ 功能阻断（回退是 Slice 2 的核心非线性能力）+ 无 workaround。 |
| **环境依赖** | 无 |

### TC-09：rollback retry 上限（AC-9）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-09 |
| **对应 AC** | AC-9：连续 3 次 rollback 到 dev → 第 4 次 block |
| **触发条件** | dev retry_count 已达 3，再次 rollback |
| **前置步骤** | 1. 预设 dev retry_count=3<br>2. 再次触发 rollback(dev) |
| **步骤** | 1. execute_rollback → dev retry_count 不变（因 execute_rollback 设置 retry_count=0）<br>2. **需由 autopilot/state.py 的逻辑检查 retry_count 上限**：在 advance_pipeline 的新任务初始化时检查 dev retry_count |
| **预期结果** | **注：当前 execute_rollback 直接 set retry_count=0，不保留历史 retry_count。此行为与 PRD §3.4「rollback 后 dev step 的 retry_count 递增」不一致。** 如果按 PRD 预期：第 3 次 rollback 后 dev retry_count=3，第 4 次触发时应 block。|
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知的扩展定义——系统健康度（无限 rollback 循环浪费资源）。有 workaround（人工介入 kill 循环），但设计上应自保护。 |
| **环境依赖** | 需确认 PRD §3.4 vs 实际 execute_rollback 行为（retry_count 应递增而非重置为 0） |

### TC-10：branches JSONL 解析（AC-10）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-10 |
| **对应 AC** | AC-10：branches 字段解析 |
| **触发条件** | load_contracts() + 验证每个步骤的 branches |
| **前置步骤** | contracts.jsonl 已部署 |
| **步骤** | 1. `load_contracts('config/contracts.jsonl')` → 验证 7 行<br>2. 每行检查 branches 数组结构<br>3. 验证必填字段 on/action/reason |
| **预期结果** | 1. 7 行全部解析成功<br>2. 每行 branches 有 on/action/reason 字段<br>3. retry action 有 target 和 max_retries<br>4. gate_roundtable action 有 roundtable_type<br>5. rollback action 有 target |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（branches 解析失败 = 所有分支逻辑失效）+ 功能阻断（分支引擎的元数据基础）+ 无 workaround。 |
| **环境依赖** | 无 |

### TC-11：S6 检测——前 6 步未全部 done（AC-11, B-20）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-11 |
| **对应 AC/B** | AC-11 / B-20：close-0 S6 检测失败 → block |
| **触发条件** | merge done 后推进到 close，但前 6 步中有 1 步未 done |
| **前置步骤** | 1. 预设：dev done, qa-d1 done, qa-exec done, qa-d2 pending(未 done), va done, merge done<br>2. 推进到 close → trigger close_s6_check |
| **步骤** | 1. `close_s6_check("t_tc11", db)` → 应返回 False<br>2. close step status='blocked'<br>3. advance_pipeline 处理 close 时返回 action=block（B-20 s6_check_fail） |
| **预期结果** | 1. close_s6_check 返回 False<br>2. error_msg 含 "S6检测失败: 未完成步骤 ['qa-d2']"<br>3. close status='blocked', verdict='blocked' |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（S6 检测跳过 = 不完整的工作被错误关闭）+ 功能阻断（安全边界——管线最后的完整性检查）+ 无 workaround。 |
| **环境依赖** | 无 |

### TC-12：close.sh 调用（AC-12, B-21）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-12 |
| **对应 AC/B** | AC-12 / B-21：merge done → close.sh 执行 → 子步骤失败 retry |
| **触发条件** | close 步骤推进，close.sh 某子步骤失败 |
| **前置步骤** | 1. 预设前 6 步全部 done<br>2. advance_pipeline 推进到 close |
| **步骤** | 1. advance → 应返回 start_step close<br>2. 模拟 close-1 kanban 关闭失败 → 应触发 B-21 step_fail → retry<br>3. 验证 close retry_count 递增<br>4. 模拟 3 次 retry → 应触发 block (retry_exhausted) |
| **预期结果** | 1. close 步骤创建<br>2. 子步骤失败 → retry 不 block 整个管线（B-21）<br>3. 3 次 retry 耗尽 → block（B-21 → retry_exhausted） |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（close 是管线的最终环节）+ 有 workaround（手动执行 close.sh 各步骤）。 |
| **环境依赖** | mock kanban complete/comment |

---

## 3. 非功能验收测试用例（AC 13-15）

### TC-13：向后兼容——Slice 1 接口不变（AC-13）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-13 |
| **对应 AC** | AC-13：CheckpointDB 接口不变，新增字段不影响已有读写 |
| **触发条件** | Slice 1 的 CheckpointDB 调用方式在 Slice 2 环境运行 |
| **前置步骤** | Slice 1 测试再用 Slice 2 的 pipeline/ 模块 |
| **步骤** | 1. upsert_step 不带 Slice 2 新增字段（verdict/verdict_detail/contract_check_passed）→ 不报错<br>2. get_step → 返回的 dict 含 verdict/verdict_detail/contract_check_passed（值为 None）<br>3. get_all_steps → 返回列表含所有步骤<br>4. ensure_schema → 幂等（user_version 从 1 auto-migrate 到 2） |
| **预期结果** | 1. Slice 1 调用方式全部兼容<br>2. 新增字段默认为 None<br>3. v1→v2 migration 自动执行，幂等 |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户不可直接感知但影响数据完整性（B 级数据：内部状态）。有 workaround（手动 migration）。 |
| **环境依赖** | 无 |

### TC-14：幂等 rollback（AC-14）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-14 |
| **对应 AC** | AC-14：重复 rollback 不产生重复记录 |
| **触发条件** | 对同一 task 连续调用两次 execute_rollback |
| **前置步骤** | 预设完整管线 |
| **步骤** | 1. execute_rollback("t_tc14", "va", "dev", "first", db)<br>2. execute_rollback("t_tc14", "va", "dev", "second", db)<br>3. get_all_steps 检查是否有重复记录 |
| **预期结果** | 1. 两次 rollback 后，pipeline_steps 仍只有至多 7 行（UNIQUE 约束起作用）<br>2. 第二次 rollback 后状态与第一次一致（不重复 upsert） |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：数据完整性（B 级数据：内部状态）+ 有 workaround（手动清理重复行）。 |
| **环境依赖** | 无 |

### TC-15：日志可追溯（AC-15）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-15 |
| **对应 AC** | AC-15：分支判定、rollback、gate_roundtable 在 autopilot 日志中记录 |
| **触发条件** | 各分支 action 触发时 |
| **前置步骤** | autopilot.sh 适配 Slice 2 后（D1-F2 修复后） |
| **步骤** | 1. 触发 retry → 验证日志含 "[autopilot] t_xxx: 重试步骤 dev: ..."<br>2. 触发 rollback → 验证日志含 "[ROLLBACK]" 和回退链路<br>3. 触发 gate_roundtable → 验证日志含 roundtable type 和 reason<br>4. 触发 await_confirm → 验证日志含等待确认信息 |
| **预期结果** | 每种 action 在 autopilot 日志中有明确的可追溯记录 |
| **风险等级** | **MINOR** |
| **分级依据** | 按标准 §1.2：用户可感知（OC/Frank 通过日志确认分支决策）+ 不影响核心任务完成 + 有变通方案（直接查 pipeline_state.db）。 |
| **环境依赖** | 需 D1-F2 修复后方可验证 |

---

## 4. 21 分支回归测试用例（B-01 ~ B-21）

以下用例按 PRD §2 顺序排列，每个分支一条 TC。标注了与 contracts.jsonl 的实际对应关系。

### 4.1 dev 步骤分支（B-01 ~ B-03）

#### TC-B01：dev 超时 → retry（B-01）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B01 |
| **对应分支** | B-01（PRD）/ contracts.jsonl: timeout→retry(1) |
| **触发条件** | dev started_at > 60min ago, status='running' |
| **操作** | advance_pipeline → 超时检测 → branch timeout |
| **预期结果** | action=retry, step=dev, retry_count=1, max_retries=1 |
| **风险等级** | BLOCKER（与 TC-04 一致） |

#### TC-B02：dev 自测失败 → retry（B-02）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B02 |
| **对应分支** | B-02（PRD）/ contracts.jsonl: ⚠️ 缺失此分支 |
| **触发条件** | dev kanban task failed |
| **操作** | mock kanban 返回 dev failed |
| **预期结果** | **按 PRD**：action=retry, max_retries=3；**按 contracts.jsonl**：无匹配分支 → 默认 block |
| **风险等级** | **MAJOR**（依赖 D1-F4 裁定结果） |
| **分级依据** | 合约与 PRD 不一致，行为依赖裁定结果。 |

#### TC-B03：dev 产物缺失 → block（B-03）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B03 |
| **对应分支** | B-03（PRD）/ contracts.jsonl: contract_violation→block |
| **触发条件** | dev kanban done 但 produces 检查失败（branch/diff 缺失） |
| **操作** | 1. mock kanban dev=done<br>2. produces 检查：branch 文件不存在 |
| **预期结果** | action=block, step=dev, error_msg 含 "produces 缺失" |
| **风险等级** | **BLOCKER** |
| **分级依据** | produces 验证是合约约束基础，失效则管线形同虚设。合约中有 contract_violation→block（与 B-03 功能一致，但少了 PRD 的 30min wait 中间步骤）。 |

### 4.2 qa-d1 步骤分支（B-04 ~ B-05）

#### TC-B04：qa-d1 需求不清 → gate_roundtable(D)（B-04）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B04 |
| **对应分支** | B-04（PRD）/ contracts.jsonl: ⚠️ qa-d1 branches 无 requirement_unclear 分支 |
| **触发条件** | qa-d1 kanban task failed + error_msg 含 "需求" |
| **操作** | 预设 qa-d1 status='failed', error_msg='需求理解不清' |
| **预期结果** | **按 PRD**：action=gate_roundtable, roundtable_type='D'；**按 contracts.jsonl**：无匹配 → 默认 block |
| **风险等级** | **MAJOR** |
| **分级依据** | contracts.jsonl qa-d1 缺少 requirement_unclear 分支。state.py 的 BranchesEvaluator._match_condition 中有 `requirement_unclear` 匹配逻辑（第332行），但合约中无对应 branch 条目 → 导致默认 block 而非 gate_roundtable。 |

#### TC-B05：qa-d1 覆盖率不足 2 次重试后 → block（B-05）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B05 |
| **对应分支** | B-05（PRD）/ contracts.jsonl: test_plan_incomplete→retry(2), test_plan_incomplete_after_retry→block |
| **触发条件** | qa-d1 retry_count=2 (max_retries=2) |
| **操作** | 预设 qa-d1 status='failed', retry_count=2, error_msg='不完整' |
| **预期结果** | action=block（retry 耗尽 → test_plan_incomplete_after_retry→block） |
| **风险等级** | **BLOCKER**（与 TC-05 一致） |

### 4.3 qa-exec 步骤分支（B-06 ~ B-09）

#### TC-B06：QA 发现 BLOCKER → gate_roundtable(D)（B-06）

同 TC-06。已验证。

#### TC-B07：QA 发现 MAJOR > 3 → gate_roundtable(D)（B-07）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B07 |
| **对应分支** | B-07（PRD）/ contracts.jsonl: MAJOR_gt_3→gate_roundtable(D) |
| **触发条件** | qa-exec done + detail 含 "MAJOR>3" |
| **操作** | advance_pipeline（qa-exec done, detail='MAJOR>3'）→ branch 匹配 MAJOR_gt_3 |
| **预期结果** | action=gate_roundtable, roundtable_type='D' |
| **风险等级** | **BLOCKER** |

#### TC-B08：QA 发现安全漏洞 → gate_roundtable(D)（B-08）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B08 |
| **对应分支** | B-08（PRD）/ contracts.jsonl: ⚠️ qa-exec branches 无 security_vuln 分支 |
| **触发条件** | qa-exec done + test_report.md 安全漏洞字段 |
| **操作** | 预设 qa-exec done, detail 含 security 相关内容 |
| **预期结果** | **按 PRD**：action=gate_roundtable, roundtable_type='D'；**按 contracts.jsonl**：无匹配分支 → 默认 block |
| **风险等级** | **MAJOR**（依赖 D1-F3 裁定） |
| **分级依据** | 安全漏洞遗漏 roundtable → 降低了安全问题的决策优先级。但默认 block（而非静默通过）是 acceptable 的 defense-in-depth 结果。 |

#### TC-B09：qa-exec 超时 → retry（B-09）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B09 |
| **对应分支** | B-09（PRD）/ contracts.jsonl: ⚠️ qa-exec branches 无 timeout 分支 |
| **触发条件** | qa-exec started_at > 45min ago |
| **操作** | advance_pipeline → 超时检测 → 标记 failed, verdict='timeout' → branch 匹配 |
| **预期结果** | **按 PRD**：action=retry(1)；**按 contracts.jsonl**：无匹配 → 默认 block |
| **风险等级** | **MAJOR**（依赖 D1-F3 裁定） |

### 4.4 qa-d2 步骤分支（B-10 ~ B-12）

#### TC-B10：D2 评审：分级错误或漏报 BLOCKER → gate_roundtable(D)（B-10）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B10 |
| **对应分支** | B-10（PRD）/ contracts.jsonl: qa-d2 review_fail→rollback （PRD B-10 + B-11 合并为一条） |
| **触发条件** | qa-d2 done + detail='不通过' （review_fail） |
| **操作** | advance_pipeline → branch 匹配 review_fail → action=rollback, target='dev' |
| **预期结果** | **按 contracts.jsonl**：action=rollback（不分 grading_error vs quality_fail）；**按 PRD**：grading_error→gate_roundtable, quality_fail→rollback |
| **风险等级** | **MAJOR** |
| **分级依据** | 合约将 PRD B-10 和 B-11 合并为一条 rollback。grading_error 本应创建 roundtable 让产品+架构师裁定，直接 rollback 跳过了裁定环节。 |

#### TC-B11：D2 评审 fail → rollback（B-11）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B11 |
| **对应分支** | B-11（PRD）/ contracts.jsonl: review_fail→rollback (与 B-10 共用) |
| **触发条件** | qa-d2 done + detail='不通过' |
| **操作** | 同 TC-B10（合约不区分 grading_error 和 quality_fail） |
| **预期结果** | action=rollback, target='dev' |
| **风险等级** | **BLOCKER**（rollback 链路核心） |

#### TC-B12：D2 评审 conditional_pass → continue（B-12）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B12 |
| **对应分支** | B-12（PRD）/ contracts.jsonl: review_conditional→continue |
| **触发条件** | qa-d2 done + detail='conditional' |
| **操作** | advance_pipeline → branch 匹配 review_conditional → action=continue |
| **预期结果** | action=advance/continue → 推进到 va |
| **风险等级** | **MAJOR** |

### 4.5 va 步骤分支（B-13 ~ B-14）

#### TC-B13：VA FALSIFIED → rollback(dev)（B-13）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B13 |
| **对应分支** | B-13（PRD）/ contracts.jsonl: FALSIFIED→gate_roundtable(D) |
| **触发条件** | va report conclusion=FALSIFIED |
| **操作** | advance_pipeline → branch 匹配 FALSIFIED |
| **预期结果** | **按 contracts.jsonl**：action=gate_roundtable, roundtable_type='D'；**按 PRD**：action=rollback, target='dev' |
| **风险等级** | **BLOCKER**（依赖 D1-F1 裁定） |
| **分级依据** | PRD 要求直接 rollback，合约要求先 roundtable。行为差异显著——其中之一是错的。 |

#### TC-B14：VA INCONCLUSIVE → block（B-14）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B14 |
| **对应分支** | B-14（PRD）/ contracts.jsonl: undetermined→block |
| **触发条件** | va done + detail='undetermined' |
| **操作** | advance_pipeline → branch 匹配 undetermined |
| **预期结果** | action=block |
| **风险等级** | **BLOCKER** |

### 4.6 merge 步骤分支（B-15 ~ B-19）

#### TC-B15：合并前备份失败 → retry（B-15）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B15 |
| **对应分支** | B-15（PRD）/ contracts.jsonl: pre_merge_backup_fail→retry(1) |
| **触发条件** | merge step, backup_step='pre' 失败 |
| **操作** | 预设 merge status='failed', error_msg='备份失败' + backup_step='pre' |
| **预期结果** | action=retry, target='merge', max_retries=1 |
| **风险等级** | **MAJOR** |

#### TC-B16：git merge 冲突 → block（B-16）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B16 |
| **对应分支** | B-16（PRD）/ contracts.jsonl: conflict→block |
| **触发条件** | merge step, git merge conflict |
| **操作** | 预设 merge status='failed', error_msg='冲突' |
| **预期结果** | action=block |
| **风险等级** | **BLOCKER** |
| **分级依据** | merge 冲突不 block = 可能强行合并冲突代码。 |

#### TC-B17：VA 合并验证不通过 → rollback（B-17）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B17 |
| **对应分支** | B-17（PRD）/ contracts.jsonl: va_merge_check_fail→rollback(dev) |
| **触发条件** | merge-3 VA merge check fail |
| **操作** | 预设 merge status='failed', error_msg='合并验证失败' |
| **预期结果** | action=rollback, target='dev' |
| **风险等级** | **BLOCKER** |

#### TC-B18：合并后备份失败 → retry（B-18）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B18 |
| **对应分支** | B-18（PRD）/ contracts.jsonl: post_merge_backup_fail→retry(2) |
| **触发条件** | merge step, backup_step='post' 失败 |
| **操作** | 预设 merge status='failed', error_msg='备份失败' + backup_step='post' |
| **预期结果** | action=retry, max_retries=2 |
| **风险等级** | **MAJOR** |

#### TC-B19：Frank 闸门 → await_confirm（B-19）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B19 |
| **对应分支** | B-19（PRD）/ contracts.jsonl: human_gate→await_confirm |
| **触发条件** | merge done + 需 Frank 确认 |
| **操作** | 预设 merge done + detail='等待确认' |
| **预期结果** | action=await_confirm, detail 含 "等待 Frank 确认" |
| **风险等级** | **MAJOR** |

### 4.7 close 步骤分支（B-20 ~ B-21）

#### TC-B20：S6 检测未通过 → block（B-20）

同 TC-11。已验证。

#### TC-B21：close.sh 子步骤失败 → retry（B-21）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-B21 |
| **对应分支** | B-21（PRD）/ contracts.jsonl: step_fail→retry(3) |
| **触发条件** | close step, close.sh 子步骤失败 |
| **操作** | 预设 close status='failed', error_msg='子步骤失败' |
| **预期结果** | action=retry, target='close', max_retries=3 |
| **风险等级** | **MAJOR** |

---

## 5. 测试场景用例（5 场景）

### TS-01：正常 7 步 Full-Green 流转

| 维度 | 内容 |
|------|------|
| **场景编号** | TS-01 |
| **场景描述** | 从零开始，7 步全部 pass，close 完成 |
| **操作** | 与 TC-01 一致 |
| **预期结果** | 7 步全部 done，close.sh 闭环完成 |

### TS-02：fan-out + dev 先完成 join 等待

| 维度 | 内容 |
|------|------|
| **场景编号** | TS-02 |
| **场景描述** | dev 先 done，qa-d1 仍在 running → qa-exec 等待 |
| **操作** | 1. dev done → advance → qa-d1 start_step（fan-out）<br>2. qa-d1 running（未done）<br>3. advance → action=wait |
| **预期结果** | 管线在 dev done 后不直接跳到 qa-exec，而是等待 qa-d1 |

### TS-03：dev 超时 → retry → 成功

| 维度 | 内容 |
|------|------|
| **场景编号** | TS-03 |
| **场景描述** | dev 超时 1 次 → retry → 第 2 次成功 |
| **操作** | 1. 第 1 次 dev 超时 → retry, retry_count=1<br>2. 第 2 次 dev done → advance |
| **预期结果** | 第 2 次 dev 成功完成，管线正常推进 |

### TS-04：QA BLOCKER → D roundtable → 裁定 BLOCKER → rollback

| 维度 | 内容 |
|------|------|
| **场景编号** | TS-04 |
| **场景描述** | qa-exec 发现 BLOCKER → D roundtable → Frank 确认 BLOCKER → rollback dev |
| **操作** | 1. qa-exec done + BLOCKER → gate_roundtable(D) + block<br>2. Frank 裁定 确认 BLOCKER → 解除 block 并触发 rollback(dev)<br>3. dev 重新执行 |
| **预期结果** | rollback 后 dev status='pending', 中间步骤清除 |
| **注意** | Roundtable → rollback 的自动化链路需要 autopilot 或 OC 手动触发。当前由人驱动。 |

### TS-05：VA FALSIFIED → 回退到 dev → 重新走完整管线

| 维度 | 内容 |
|------|------|
| **场景编号** | TS-05 |
| **场景描述** | 管线走到 va 发现 FALSIFIED → rollback(dev) → 重新 7 步 |
| **操作** | 1. 7 步中前 6 步 done, va FALSIFIED<br>2. execute_rollback(va→dev)<br>3. dev 重新 pending → advance → start_step dev |
| **预期结果** | 回退后 dev 重新执行，自动推进到 qa-exec（fan-out） |
| **风险等级** | **BLOCKER** |

---

## 6. 边界条件 & 异常路径

### BE-01：BranchesEvaluator 无匹配时默认 block

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-01 |
| **触发条件** | 步骤 failed + 条件不在 branches 数组中 |
| **操作** | 1. 设置某步骤 status='failed', error_msg='完全未知的条件'<br>2. 该步骤 branches 为空或无匹配 |
| **预期结果** | _default_advance 被调用（action='advance'） — ⚠️ **这是当前实现的行为！** |
| **风险等级** | **BLOCKER** |
| **分级依据** | 当前 BranchesEvaluator.evaluate() 在 branches 为空或无匹配时调用 `_default_advance(result)` 返回 action='advance'——这意味着一个 failed 的步骤会被**静默推进到下一步**！这与代码第 484 行注释「无匹配分支 → 默认 block」完全相反。见 state.py:203-204（空 branches → `_default_advance`）和 state.py:284-285（遍历完无匹配 → `_default_advance`）。 |
| **详情** | PRD §6.1 evaluate_branches 的注释写 'No match → default block'，但实际实现是推进。这应该是 **advance** loop 中的一个 bug：当 status='failed' 进入 `_apply_branch_action`，如果 branch_action['action']='advance'，`_apply_branch_action` 会调用 `_advance_to_next` 推进到下一步——跳过了 failed 步骤。 |

### BE-02：pipeline_state.db 不存在于 advance_pipeline

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-02 |
| **触发条件** | db_path 指向不存在的文件 |
| **操作** | advance_pipeline("t_new", "/nonexistent/pipeline_state.db") |
| **预期结果** | ensure_schema() 创建新文件 + 返回新任务初始化 (start_step dev) |
| **风险等级** | MINOR |

### BE-03：STEP_ORDER 与 contracts.jsonl 顺序不一致

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-03 |
| **触发条件** | contracts.jsonl 步骤顺序 ≠ STEP_NAMES |
| **操作** | 修改 contracts.jsonl 将第 2 行和第 3 行互换 → 验证 advance_pipeline 行为 |
| **预期结果** | _advance_to_next 按 contracts 中的顺序推进（而非 STEP_ORDER） |
| **风险等级** | MAJOR |
| **分级依据** | 合约是唯一权威源，STEP_ORDER 仅用于 rollback 区间计算。不一致时 rollback 区间可能错误（清除了不该清除的步骤）。 |

### BE-04：空 contracts.jsonl

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-04 |
| **触发条件** | contracts.jsonl 为空文件 |
| **操作** | advance_pipeline("t_tc_be04") |
| **预期结果** | action='error', detail='合约文件为空或无法解析' |
| **风险等级** | MAJOR |

---

## 7. 风险矩阵

| 风险 | 级别 | 可能性 | 影响 | 缓解 |
|------|:---:|:---:|------|------|
| D1-F1 VA FALSIFIED 行为不一致 | **BLOCKER** | 确认存在 | FALSIFIED 后行为不可预测 | D1 审定会当场裁定 |
| D1-F2 autopilot.sh 未适配 Slice 2 | **BLOCKER** | 确认存在 | 所有分支 action 无法执行 | **P0 修复**：autopilot.sh 新增 retry/rollback/gate_roundtable/await_confirm case |
| BE-01 BranchesEvaluator 无匹配时静默推进 | **BLOCKER** | 确认存在 | failed 步骤被跳过，管线错误推进 | 修复 evaluate() 中空 branches 的默认行为为 block |
| D1-F3 qa-exec 缺 security_vuln/timeout | **MAJOR** | 确认存在 | 安全漏洞处理和超时重试不符合 PRD | 补充 contracts.jsonl 分支 |
| D1-F4 dev 缺 self_test_fail 分支 | **MAJOR** | 确认存在 | engine 自测失败不可自动重试 | 补充 contracts.jsonl 分支 |
| B-10/B-11 合并导致 grading_error 跳过 roundtable | **MAJOR** | 确认存在 | 分级错误直接 rollback 绕过裁定 | 拆分 review_fail 为 grading_error(→gate_roundtable) 和 quality_fail(→rollback) |
| TC-09 rollback retry_count 重置而非递增 | **MAJOR** | 确认存在 | 无限 rollback 循环 | execute_rollback 中 dev retry_count 应递增而非重置为 0 |
| kanban mock 不准确导致假阳性 | **MAJOR** | 中 | 分支判定 TC 全部受影响 | mock 脚本 code review |
| autopilot.sh 的 Slice 2 扩展未落地导致集成测试阻塞 | **MAJOR** | 高 | TS-01/02/03/04/05 全链路测试无法执行 | D1-F2 修复为 P0 |

---

## 8. 测试执行顺序与依赖

```
Round 0: 静态检查 + D1 冲突裁定（无需外部依赖）
  ├── TC-10: branches JSONL 解析
  ├── TC-07: gate_roundtable 类型映射
  ├── TC-13: 向后兼容（CheckpointDB）
  ├── TC-14: 幂等 rollback
  ├── D1 审定会：裁定 D1-F1 ~ D1-F4
  └── 根据裁定结果调整 contracts.jsonl + state.py + autopilot.sh

Round 1: 单步分支引擎（无需 mock kanban，直接调用 Python 函数）
  ├── TC-04: 超时 → retry (dev)
  ├── TC-05: retry 耗尽 → block (qa-d1)
  ├── TC-08: rollback (va FALSIFIED)
  ├── TC-09: rollback retry 上限
  └── TC-11: S6 检测

Round 2: 需 mock kanban 的步骤
  ├── TC-B02: dev 自测失败
  ├── TC-B03: dev 产物缺失
  ├── TC-B04: qa-d1 需求不清
  ├── TC-B06~B09: qa-exec 各分支
  ├── TC-B10~B12: qa-d2 各分支
  ├── TC-B14: va INCONCLUSIVE
  └── TC-B15~B21: merge + close 各分支

Round 3: 全链路场景（需 D1-F2 修复 + mock kanban）
  ├── TS-01: 7 步 Full-Green 流转 (TC-01)
  ├── TS-02: fan-out + join
  ├── TS-03: 超时 → retry → 成功
  ├── TS-04: BLOCKER → roundtable → rollback
  ├── TS-05: VA FALSIFIED → rollback → 重新流转
  ├── TC-02: fan-out 并行创建
  └── TC-03: join 条件

Round 4: 边界条件
  ├── BE-01: 无匹配时默认 block（修复后）
  ├── BE-02: DB 不存在
  ├── BE-03: 步骤顺序不一致
  └── BE-04: 空合约

Round 5: Slice 1 回归（Slice 2 环境）
  ├── TC-01(sl1) → checkpoint 初始化 + v2 migration 验证
  ├── TC-06(sl1) → flock 防重入（不变）
  └── TC-09(sl1) → 幂等建表（含 migration 幂等）
```

---

## 9. 测试用例统计

| 分类 | 数量 | BLOCKER | MAJOR | MINOR |
|------|:---:|:---:|:---:|:---:|
| AC 验收用例 (TC-01~12) | 12 | 8 | 4 | 0 |
| 非功能验收 (TC-13~15) | 3 | 0 | 2 | 1 |
| 21 分支回归 (TC-B01~B21) | 21 | 8 | 13 | 0 |
| 场景用例 (TS-01~05) | 5 | 2 | 0 | 0 |
| 边界条件 (BE-01~04) | 4 | 1 | 2 | 1 |
| Slice 1 回归 | 3 | 0 | 2 | 0 |
| **合计** | **48** | **19** | **23** | **2** |

---

## 10. QA 初步判定

| 判定维度 | 结论 |
|---------|------|
| **可测试性** | ⚠️ 部分可测——state.py/fanout.py/checkpoint.py 可直接测试；autopilot.sh 需等 D1-F2 修复后全链路测试 |
| **代码覆盖率目标** | BranchesEvaluator: 100%（26 条条件匹配 + 默认行为 → 需测所有 26 条 match 路径）；execute_rollback: 100%；handle_gate_roundtable: 100%；advance_pipeline: ≥90%（核心推进逻辑 + 所有 action 分支） |
| **阻塞项** | D1-F1 (VA FALSIFIED 行为不一致)、D1-F2 (autopilot.sh 未适配) 必须在 Round 0 裁定和修复 |
| **实现缺陷** | BE-01（BranchesEvaluator 无匹配时静默推进而非 block）——需要在 D1 审查中确认，按产品意图修复 |
| **测试时间估算** | Round 0（静态 + 裁定）：1h；Round 1（单步分支引擎）：2h；Round 2（mock kanban）：3h；Round 3（全链路）：2h（D1-F2 修复后）；Round 4（边界）：1h；Round 5（回归）：1h。总计约 10h |
| **发布门禁建议** | 19 项 BLOCKER 必须全部 PASS。23 项 MAJOR 中 ≤3 项可延后（标注 known issue）。2 项 MINOR 不阻塞。D1-F1/F2/F3/F4 裁定后 BLOCKER 数量可能变化。 |

---

## 11. D1 审定 Checklist

审定会需确认以下问题：

- [ ] **D1-F1 VA FALSIFIED 行为**：PRD 要求 rollback(dev)，contracts.jsonl 要求 gate_roundtable(D)。最终是哪个？
- [ ] **D1-F2 autopilot.sh 适配**：autopilot.sh 是否需要在 D1 阶段完成 Slice 2 扩展？还是 D2 阶段再做？
- [ ] **D1-F3 qa-exec 缺少 security_vuln 和 timeout 分支**：需补充到 contracts.jsonl
- [ ] **D1-F4 dev 缺少 self_test_fail 分支**：需补充到 contracts.jsonl
- [ ] **B-10/B-11 合并**：contracts.jsonl 是否应拆分 review_fail 为 grading_error 和 quality_fail？
- [ ] **BE-01 BranchesEvaluator 默认行为**：无匹配分支时是推进（当前实现）还是 block（PRD 注释）？
- [ ] **TC-09 rollback retry_count**：execute_rollback 中 retry_count 应递增还是重置？
- [ ] **Mock 策略**：全链路场景是否接受 mock kanban？还是要求真实 cron + 真实 kanban？
- [ ] **测试优先级**：如果时间有限，哪些 TC 是 D1 必须通过的（建议：TC-01/04/06/08/10/11 + 全部 BLOCKER 级 B-TC）？

---

> QA 测试方案完毕。下一步：发起 D1 审定（product + architect），裁定 4 项 PRD/合约冲突后进入 Round 0 静态检查。
>
> 分级依据：`docs/standards/qa-finding-classification.md` v1.0
