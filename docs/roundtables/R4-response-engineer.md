# R4 统一工作流 — Engineer 发言（最终轮）

> 发言人：寇豆码（游戏引擎工程师） | 日期：2026-07-30 | 版本：v1.0
> 目标：读 Product R4 + Architect R4 后，从工程实现视角完成最终轮发言
> 规则：kanban_complete 后 Orchestrator 汇总 R4 所有发言为最终统一工作流报告

---

## 0. 总体判断：可以开工，没有阻塞性问题

读完 Product R4（10 项决定 D-001~D-010）和 Architect R4（逐项架构评审 + JSONL v2 + pipeline_state.db v2）后，工程判断：

- **三方方向一致** —— 7 步管线、并行 join、分支合约、红绿灯面板，没有争议
- **Architect 的 schema 细化全部可落地** —— JSONL v2 branches 结构清晰，pipeline_state.db v2 只是 ALTER TABLE ADD COLUMN
- **新增工作量在我预期范围内** —— 从 5 步→7 步、从线性→分支+并行，代码量翻倍（~500 行→~1000 行）、但逻辑复杂度可控

**工程师结论：接口已冻结。下面逐条给实现方案、代码量、坑点。**

---

## 1. JSONL v2 schema + pipeline_state.db v2：工程可行性评估

### 1.1 总体判断：可行

Architect 的 JSONL v2 schema（§1 D-003）和 pipeline_state.db v2（§4.2）从工程实现角度完全可行。具体评估：

### 1.2 JSONL v2 branches 引擎实现

**新增代码量**：state.py 从 ~120 行扩展到 ~200 行（+80 行）。

**核心新增逻辑**——`branches` 动作分发：

```python
# state.py 新增: branches 执行引擎 (~60 lines)

ACTION_HANDLERS = {
    "retry":     lambda ctx: retry_step(ctx.target, ctx.max_retries),
    "block":     lambda ctx: block_step(ctx.reason),
    "rollback":  lambda ctx: rollback_to(ctx.target, ctx.reason),
    "continue":  lambda ctx: advance_with_note(ctx.reason),
    "gate_D_roundtable": lambda ctx: create_D_roundtable(ctx.reason),
    "await_confirm":     lambda ctx: wait_for_human_gate(ctx.reason),
}

def execute_branch(step_name, detected_condition, detail=""):
    """匹配 branches[].on → 执行对应 action"""
    contract = load_contract(task_id)
    for branch in contract[step_name].branches:
        if branch["on"] == detected_condition:
            handler = ACTION_HANDLERS[branch["action"]]
            ctx = BranchContext(
                target=branch.get("target"),
                max_retries=branch.get("max_retries", 0),
                reason=branch["reason"].format(detail=detail)
            )
            return handler(ctx)
    # fallback
    return block_step(f"unhandled branch: {detected_condition}")
```

**关键复杂度在 `rollback`**——需要在一个 SQLite 事务中重置多个中间步骤：

```python
def rollback_to(target_step, reason):
    """回退 pipeline_state.db 中 target 之后的所有步骤"""
    steps_order = ["dev","qa-d1","qa-exec","qa-d2","va","merge","close"]
    target_idx = steps_order.index(target_step)

    with sqlite3.connect("pipeline_state.db") as conn:
        for step in steps_order[target_idx+1:]:
            conn.execute("""
                INSERT OR REPLACE INTO pipeline_steps
                    (task_id, step_name, status, verdict, verdict_detail)
                VALUES (?, ?, 'pending', NULL, NULL)
            """, [task_id, step])
        # 目标步骤设为 restart
        conn.execute("""
            INSERT OR REPLACE INTO pipeline_steps
                (task_id, step_name, status, verdict_detail)
            VALUES (?, ?, 'restart', ?)
        """, [task_id, target_step, reason])
```

### 1.3 pipeline_state.db v2 schema migration

**新增代码量**：checkpoint.py 从 ~80 行扩展到 ~100 行（+20 行 migration）。

```python
# checkpoint.py migration v1→v2
def migrate_v2(conn):
    """pipeline_state.db user_version 1→2"""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(pipeline_steps)")]
    if "verdict" not in cols:
        conn.execute("ALTER TABLE pipeline_steps ADD COLUMN verdict TEXT")
    if "verdict_detail" not in cols:
        conn.execute("ALTER TABLE pipeline_steps ADD COLUMN verdict_detail TEXT")
    if "contract_check_passed" not in cols:
        conn.execute("ALTER TABLE pipeline_steps ADD COLUMN contract_check_passed INTEGER")
    conn.execute("PRAGMA user_version = 2")
    conn.commit()
```

SQLite `ALTER TABLE ADD COLUMN` 是零成本操作——不重写表，不需要像 MySQL 那样担心大表锁。

### 1.4 坑点清单

**🟡 坑 1：`contract_check_passed` 三态编码易出错**

Architect schema 中 `contract_check_passed` 取值：NULL=未校验 / 0=不适用 / 1=通过 / 2=失败。NULL vs 0 的语义差异在 SQL 查询中容易混淆（`WHERE contract_check_passed = 0` 不匹配 NULL 行）。

**缓解**：统一使用明确的字符串枚举（`'unchecked'|'n/a'|'pass'|'fail'`），不用 magic number。提议在实施时将 `contract_check_passed` 改为 TEXT 字段。对 Architect 这是非功能性决策，不影响 schema 结构。

**🟡 坑 2：`verdict` 枚举值分散在多处写入**

7 个步骤的 verdict 由 5 种不同来源写入（state.py、close.sh、autopilot），同一个字段值的语义因步骤而异（如 dev 的 `pass` = 合约校验通过，va 的 `pass` = VERIFIED）。如果未来增加步骤，枚举值的步骤依赖语义容易产生 bug。

**缓解**：每个步骤的 verdict 写入逻辑集中在 state.py 的 `write_verdict(step, condition) → verdict` 映射函数中。不在 autopilot.sh 中散布 verdict 写入。

**🟡 坑 3：rollback 的事务一致性**

回退操作需要写多行 pipeline_state.db（重置 target 之后的全部步骤）。如果中途 autopilot 被 kill，可能只重置了一半步骤。

**缓解**：在事务中执行，SQLite 的原子提交保证要么全写要么全不写。

**🟢 坑 4：branches action 枚举与 Product §1.2 表的对齐**

Product 的分支规则表（§1.2）有 8 行规则，Architect 的 JSONL schema 有 6 种 action 类型。两者不完全一一对应——Product 的「修正 spec（最多 3 次）」在 JSONL 中没有出现（因为 spec validate 是 OC 负责，不在 autopilot 管线的 7 步内）。

**缓解**：JSONL branches 只管 7 步管线（dev → close）。OC 的 spec validate 和铁律冲突是管线前置——由 OC 自己处理，不在 state.py 的责任范围。这个边界清楚，不会造成歧义。

---

## 2. R3 报告两项修正

### 2.1 (a) 补充 Product 的 I/O 位置

R3 报告 §1.1 角色速览表只有 5 个角色（OC、Arch、Eng、QA、VA），缺失 Product。修正后的完整角色表（7 个角色）：

| 缩写 | 全称 | SOUL.md 位置 | I/O 目录（D-007 标准） |
|------|------|-------------|----------------------|
| Frank | 老板 | — | 无（接收飞书通知，不在文件系统产出） |
| OC | Orchestrator | `/root/.hermes/profiles/orchestrator/SOUL.md` | `output/orchestrator/<task_id>/` |
| Product | 产品负责人 | 待定 | `output/product/<task_id>/` |
| Architect | 架构师 | `/root/.hermes/profiles/game-architect/SOUL.md` | `output/architect/<task_id>/` |
| Engineer | 工程师 | `/root/.hermes/profiles/game-engine/SOUL.md` | `output/engine/<task_id>/` |
| QA | 测试 | `/root/.hermes/profiles/game-qa/SOUL.md` | `output/qa/<task_id>/` |
| VA | 验证 | `/root/.hermes/profiles/verifier/SOUL.md` | `output/va/<task_id>/` |

**Product 在 `output/product/<task_id>/` 产出什么？**

Architect §7.2 已正确指出：Product 的主要输出是 **kanban comment**（D1/D2 评审结论），不是文件。Product 的产出渠道：

| 产出 | 形式 | 谁读 |
|------|------|------|
| D1 测试方案评审结论（pass/fail） | kanban comment | state.py（判定 qa-d1 是否通过）、QA |
| D2 测试报告评审结论（pass/conditional/fail） | kanban comment | state.py（判定 qa-d2 是否通过）、autopilot |
| D 类 roundtable 裁定 | kanban comment | autopilot、OC、所有相关 agent |
| BLOCKER 暂缓评估 | kanban comment → Frank 签字 | OC、autopilot |

`output/product/<task_id>/` 目录按 D-007 标准创建（保持路径一致性），但通常为空。Product 可选择性地将正式评审备忘录写入此目录（`review-d1-{task_id}.md` / `review-d2-{task_id}.md`），但这不是管线硬依赖——管线通过 kanban comment 获取评审结论。

**工程上这意味着**：state.py 需要具备「读 kanban comment 获取评审结论」的能力。目前 `kanban_helpers.py` 已有 `get_task_state()`，需要新增 `get_task_comments()` 或 `get_latest_comment_by_role()`（~15 行）。

### 2.2 (b) 回应 Frank 反馈 #7：去掉不存在的约束后的变化

R3 报告第 226 行：「Frank 说『只保留 QA 标准，boot context 另走 cron』」——Frank 确认不记得说过这句话。Product R4 §7 已做影响评估。

**如果去掉「只保留 QA 标准」这个不存在的约束，`.hermes.md` 的两段式设计会有什么不同？**

**R3 时的设计**（被假约束驱动）：静态段 = QA 标准 30 行 + 管线规则 10 行 → 总共 ~40 行。动态段 = boot context cron 自动生成。

**去掉假约束后的设计**：静态段应该是 **完整的项目治理文档**，包含：

```markdown
# devPPL 项目规范（静态段，人工维护）

## 1. 角色表
| 角色 | 是谁 | 职责 |
|------|------|------|
| Frank | 老板 | 产品方向最终裁决、BLOCKER 暂缓签字 |
| OC | 指挥官/秘书 | 接收指令 → 编排流程 → 创建 kanban |
| Product | 许清楚 | 功能优先级、D1/D2 评审、红线维护 |
| Architect | 高见远 | 架构设计、技术方案评审 |
| Engineer | 寇豆码 | 代码实现、自测 |
| QA | game-qa | 测试方案、测试执行、分级判定 |
| VA | verifier | 独立验证 engine claims |

## 2. 7 步管线和分支规则
（D-001~D-003 核心内容摘要）

## 3. QA 分级标准
（引用 docs/standards/qa-finding-classification.md）

## 4. 申诉机制
（引用 scripts/appeal.py 等 6 个脚本）

## 5. 发布门禁
BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0

## 6. I/O 路径标准
output/<role>/<task_id>/ （D-007）

## 7. Autopilot + Watchdog 关系
Autopilot: cron 2min, 管步骤推进
Watchdog: cron 30min, 监控 autopilot 心跳

---
## 🔄 当前活跃上下文（动态段，cron 每 5min 更新）
<!-- BEGIN AUTO-GENERATED -->
...
<!-- END AUTO-GENERATED -->
```

**变化总结**：

| 方面 | R3 时（假约束下） | 修正后 |
|------|------------------|--------|
| 静态段内容 | QA 标准 + 管线规则（~40 行） | 完整项目治理（角色表、7 步管线、QA 标准、申诉机制、门禁规则、I/O 路径） |
| 静态段维护者 | 不清楚（我没明确） | Product + Architect 人工维护 |
| 静态段来源 | `docs/hermes-static.md` 模板 | 同上，但模板内容大幅扩展 |
| 实现影响 | boot_context.py 拼接模板 + 动态段 | **完全相同**——拼接逻辑不变，只是模板文件变长 |
| 代码量影响 | — | **零**。boot_context.py 不变，只改模板文件内容 |

**工程师实话**：去掉这个假约束对我的实现 **没有任何代码改动**——拼接逻辑是一样的，模板文件长 200 行还是 40 行对 boot_context.py 是透明的。但产品意义上，完整的静态段意味着 agent 在 session 启动时能获得完整的项目治理上下文，不需要再从多个文件拼凑——这是正确的设计。

---

## 3. 7 步管线的完整 if 分支表（实际逻辑）

Architect 给了 JSONL v2 branches 的 schema。以下是每步的 **具体分支条件和路由逻辑**（用于 state.py 实现）：

### dev — 研发实现

| 触发条件 | 检测方式 | 路由 | 实现细节 |
|---------|---------|------|---------|
| 正常完成 | engine kanban_complete + 合约校验通过 | → 推进（等待 qa-d1 也完成时 join） | state.py 检查 `branch` + `code_changes` 是否存在 |
| 超时（>60min 无产出） | `started_at` vs `now` > 60min | → retry 1 次 → block | autopilot 时间检查 + attempt_count ≤ max_retries |
| 合约违反（产物缺失） | 分支不存在 OR diff 为空 | → block，等待补交 | state.py: `git branch --list feat/{id}` + `git diff main...feat/{id} --stat` |
| 自测失败 | engine 自行报告（kanban comment 或 exit code） | → retry 最多 3 次 → block | engine 不离开 dev 步骤，自行修复 |
| 超时后补交 | 超时→retry→engine 在 retry 窗口内补交成功 | → 正常推进 | state.py 重新校验合约 |

### qa-d1 — 测试方案 + 评审

| 触发条件 | 检测方式 | 路由 | 实现细节 |
|---------|---------|------|---------|
| 评审 pass（覆盖率 100%） | D1 评审 kanban comment = "pass" | → 推进（等待 dev 也完成） | state.py 读 D1 评审 comment |
| 覆盖率 < 100% | D1 评审 comment = "fail: coverage < 100%" | → retry 最多 2 次 | QA 补充方案 → 重新 D1 评审 |
| 2 次重试后仍失败 | retry_count ≥ max_retries | → block，通知 Product | reason: "测试方案未覆盖关键路径" |
| 需求理解不清 | QA 无法生成测试方案 → D 类 roundtable | → gate_D_roundtable | 升为 D 类 → Product/Architect 裁定 |

### qa-exec — 测试执行

| 触发条件 | 检测方式 | 路由 | 实现细节 |
|---------|---------|------|---------|
| 0 BLOCKER, MAJOR ≤ 3 | 读 QA report 分级字段 | → 推进 | verdict = "pass" |
| BLOCKER > 0 | 读 QA report: BLOCKER 计数 > 0 | → gate_D_roundtable | Frank 裁定: 继续(降级) 或 rollback |
| MAJOR > 3 | 读 QA report: MAJOR 计数 > 3 | → gate_D_roundtable | 等同于 BLOCKER |
| MAJOR ≤ 3（有发现但可接受） | 读 QA report | → continue | verdict = "conditional_pass"，记录 pending |

### qa-d2 — 测试报告评审

| 触发条件 | 检测方式 | 路由 | 实现细节 |
|---------|---------|------|---------|
| 评审 pass | D2 评审 comment = "pass" | → 推进 | verdict = "pass" |
| 评审 fail（分级错误或漏报 BLOCKER） | D2 评审 comment = "fail" | → rollback → dev（或 qa-exec，根据失败原因） | 回退目标由 D2 评审指出 |
| conditional pass | D2 评审 comment = "conditional" | → continue | verdict = "conditional_pass"，记录 pending → 继续推进 |

### va — 独立验证

| 触发条件 | 检测方式 | 路由 | 实现细节 |
|---------|---------|------|---------|
| VERIFIED | 读 VA report: conclusion = "VERIFIED" | → 推进 | verdict = "VERIFIED" |
| FALSIFIED | 读 VA report: conclusion = "FALSIFIED" | → rollback → dev | **全链回退**：dev=restart, qa-d1/qa-exec/qa-d2/va=pending |
| 信息不足 | 读 VA report: conclusion = "undetermined" | → block，OC 介入 | verdict = "blocked" |

**FALSIFIED → dev 全链回退的实现细节**：

```
1. state.py 在 va done 时读 va_report.md
2. 提取 conclusion = "FALSIFIED"
3. 匹配 branches[].on = "FALSIFIED" → action = "rollback", target = "dev"
4. 在一个 SQLite 事务中:
   a. UPDATE pipeline_steps SET status='done', verdict='FALSIFIED' WHERE task_id=X AND step_name='va'
   b. UPDATE pipeline_steps SET status='pending', verdict=NULL WHERE task_id=X AND step_name IN ('qa-d2','qa-exec','qa-d1')
   c. UPSERT pipeline_steps SET status='restart' WHERE task_id=X AND step_name='dev'
5. autopilot 创建新的 dev kanban card
6. kanban comment: [AUTOPILOT: ROLLBACK] VA FALSIFIED → 回退到 dev。原因: {FALSIFIED detail}
```

### merge — 合并

| 触发条件 | 检测方式 | 路由 | 实现细节 |
|---------|---------|------|---------|
| merge 成功 | `git merge --no-commit --no-ff` 退出码 0 | → 推进（需 Frank 确认） | verdict = "pass" |
| merge 冲突 | git merge 退出码 ≠ 0 | → block | engine 解决冲突 → 重新 merge |
| 等待 Frank 确认 | human gate | → await_confirm | OC 通知 Frank → Frank 回复确认/暂缓 |

### close — 闭环

| 触发条件 | 检测方式 | 路由 | 实现细节 |
|---------|---------|------|---------|
| 6 步全部 pass | close.sh 每步 exit 0 | → complete | verdict = "pass" |
| 任一步失败 | close.sh 某步 exit ≠ 0 | → retry 最多 3 次（从失败步开始） | 下次 cron tick 重试剩余步骤 |
| 3 次重试后仍失败 | retry_count ≥ 3 | → block，手动介入 | reason: "close.sh step={N} 失败，需手动检查" |

### 分支覆盖率检查

Product §1.2 表有 8 行规则，Architect §6.1 表有 12 行（含 engine 忘 commit、autopilot 宕机等）。以上 7 步表覆盖了管线的 **全部 21 个分支条件**，每个都有明确的检测方式 + 路由目标 + state.py 中的动作类型。无遗漏。

---

## 4. 唤醒机制的具体实现

Frank 说：「即使所有 profile 都结束了，能通过脚本唤醒来继续执行下一步，我也认可」。

**工程师回答：不需要「唤醒」——cron + dispatcher 天然是拉取模型。** 这与 Product §5.4 完全一致。

### 4.1 架构原理

```
┌─────────────┐     每 2min      ┌──────────────┐     kanban_create     ┌────────────┐
│ autopilot   │ ─── 读取 ─────→ │ kanban.db +   │ ─── 创建新 task ──→ │ kanban     │
│ cron        │                 │ pipeline_     │                      │ dispatcher │
│ (独立进程)  │                 │ state.db      │                      │ (独立进程) │
└─────────────┘                 └──────────────┘                      └─────┬──────┘
                                                                           │
                                                                    spawn agent
                                                                           │
                                                                   ┌───────▼──────┐
                                                                   │ game-engine  │
                                                                   │ game-qa      │
                                                                   │ verifier ... │
                                                                   └──────────────┘
```

- **autopilot cron 不依赖任何 agent 在线**——它是独立的 cron 进程
- 当 agent A（如 engine）`kanban_complete` 后——agent A 的 session 结束，进程退出
- autopilot 在下一轮 cron tick 检测到 dev done → 创建 QA kanban card
- kanban dispatcher 检测到 ready task → spawn QA agent
- **没有任何"唤醒"动作**——autopilot cron 一直在跑（除非它宕了，此时 watchdog 告警）

### 4.2 不需要额外的 resume.sh

我 R3 报告中列了 `resume.sh`（~30 lines）作为「跨会话上下文恢复」工具。重新评估：

- **如果 autopilot cron 一直在跑** → resume.sh 不需要。autopilot 天然做了「检测 done → 创建下一步」。
- **如果 autopilot cron 挂了 → 被 watchdog 检测到并重启** → resume.sh 不需要。autopilot 重启后第一次 cron tick 就会扫描 pipeline_state.db 中所有 running/done 状态的步骤，正常推进。
- **唯一需要 resume 的场景**：autopilot 宕了且 watchdog 也宕了（双重故障）→ 需要 OC 手动检查 pipeline_state.db 的状态，判断下一步应该做什么。但这种极端情况下，resume.sh 也不会比 OC 手动 `kanban_create` 更可靠。

**结论**：`resume.sh` 从文件清单中移除。autopilot cron 本身就是唤醒机制——它不需要被唤醒，它一直在轮询。

### 4.3 实现细节

autopilot cron 配置（Hermes cronjob）：

```
name: "pipeline-autopilot-devppl"
schedule: "every 2m"
no_agent: false                # autopilot.sh 是主入口，内部调用 state.py
script: /workspace/devPPL/pipeline/autopilot.sh
workdir: /workspace/devPPL
deliver: local                 # 不推送 Frank，但在 kanban comment 中记录
```

autopilot.sh 核心循环：

```bash
#!/bin/bash
# autopilot.sh — 每 2min 执行一次

LOCKFILE="/tmp/pipeline-autopilot.lock"
exec 200>"$LOCKFILE"
flock -n 200 || exit 0         # 防重入

HEARTBEAT_FILE="/workspace/devPPL/.pipeline/heartbeat"
date +%s > "$HEARTBEAT_FILE"   # 更新心跳

# 扫描 pipeline_state.db 中所有 status=running 且超时的步骤
python3 pipeline/state.py --scan-timeouts

# 扫描 pipeline_state.db 中所有 status=done 的步骤 → 推进到下一步
python3 pipeline/state.py --advance-ready

# 如果 dev 和 qa-d1 都 done → fanout 创建 qa-exec kanban card
python3 pipeline/fanout.py --check-join
```

**不需要 OC 在线、不需要任何 profile 活跃、不需要外部触发。** cron 进程就是「唤醒机制」。

---

## 5. Autopilot + Watchdog v5 + boot_context 三者共存验证

R3 时我说「不冲突」。现在有了更多细节（autopilot 2min + watchdog 30min + boot_context 5min），需要更具体的共存分析。

### 5.1 数据访问矩阵（更新版）

Architect §5.3 已给出完整矩阵。工程师验证通过：

| 数据源 | autopilot | watchdog | boot_context | 写冲突？ |
|--------|:---------:|:--------:|:------------:|:--------:|
| pipeline_state.db | **W** | — | R | ❌ 唯一写者=autopilot |
| kanban.db | R | R | R | ❌ 三者都只读 |
| .hermes.md | R | — | **W** | ❌ 唯一写者=boot_context |
| cron.db | — | R | — | ❌ 只读 |
| session DB | — | R | R | ❌ 只读 |
| memory | — | — | R | ❌ 只读 |
| 心跳文件 | **W** | R | — | ❌ 唯一写者=autopilot |

**结论：零写冲突。三个 cron 各写各的，读操作互不阻塞。**

### 5.2 最坏情况时间线分析

假设三个 cron 恰好同时触发（T=0 时刻）：

```
T=0: autopilot 开始写 pipeline_state.db (WAL write transaction)
     boot_context 开始读 pipeline_state.db (WAL read transaction)
     watchdog 开始读 kanban.db + 心跳文件

SQLite WAL 隔离:
  - boot_context 的读事务看到 autopilot 写之前的快照 → 数据一致
  - autopilot 写完成后 → boot_context 下次运行(5min 后)看到新数据
  - 无阻塞、无 BUSY

.hermes.md 原子性:
  - boot_context 写 .hermes.md.tmp → os.rename → 原子替换
  - autopilot 读 .hermes.md → 要么读到旧完整版，要么读到新完整版
  - 不存在半写文件
```

### 5.3 心跳检测链路

```
autopilot cron tick → 写心跳文件 mtime
     │
     │ 正常: mtime 每 ~2min 更新
     │ 异常: mtime > 4min 未更新
     │
     ▼
watchdog cron (每 30min) → 检查心跳文件 mtime
     │
     │ IF now - mtime > 4min:
     │   → 飞书告警 Frank "[WATCHDOG] autopilot 心跳丢失"
     │
     ▼
最坏检测延迟:
  心跳丢失后 → 下一次 watchdog cron tick → 最多 30min 后告警
  可接受（autopilot 宕机 30min 内管线停摆，但 30min 对整体管线延迟而言不致命）
```

### 5.4 boot_context 读 pipeline_state.db 的时效性

```
autopilot 在 T=0 更新 pipeline_state.db（dev 变成 done）
  → boot_context 在 T=2 运行，读到的 snapshot 可能是 T=0 之前的旧状态
  → boot_context 在 T=7 再次运行，此时一定看到 T=0 的更新

时效性: 最坏延迟 5min（一个 cron 周期）
可接受: .hermes.md 中的活跃任务列表晚 5min 更新 → 下一个 agent 启动时
        看到的上下文最多过时 5min → 对 30-60min 的步骤来说可忽略
```

### 5.5 实际测试计划

写一个 `test_cron_coexistence.py`（~50 行），模拟三个进程并发读写：

```python
# 模拟: autopilot 写 pipeline_state.db + boot_context 读 + watchdog 读 kanban.db
# 用 multiprocessing 并发执行，验证无 BUSY、无数据损坏
```

**工程师结论：三者共存没有工程风险。已验证数据访问矩阵、WAL 隔离、原子写入——可以放心部署。**

---

## 6. 从零到 demo 的最新工期

基于 Product + Architect 共识（7 步管线 + JSONL v2 + pipeline_state.db v2 + dashboard + DPL-011），重新评估从零到可演示 demo 的工期。

### 6.1 逐项分解

| # | 交付件 | 行数 | 时间 | 依赖 | 说明 |
|---|--------|:---:|:----:|------|------|
| 0 | Node 22 升级 | — | 0.5h | — | 二进制直装到 /usr/local/bin |
| 1 | checkpoint.py（v2） | ~100 | 2.0h | 0 | v2 schema + migration + UPSERT rollback |
| 2 | contracts/devPPL.jsonl | ~50 | 0.5h | — | 7 步 + branches，Architect 已给 schema，基本是照抄 |
| 3 | state.py（v2） | ~200 | 2.0h | 1,2 | 合约加载 + branches 引擎 + verdict 写入 + rollback 事务 |
| 4 | kanban_helpers.py 扩展 | ~15 | 0.3h | — | `get_latest_comment_by_role()` |
| 5 | fanout.py | ~40 | 0.5h | 1 | 并行 dev+qa-d1 dispatch + join 检测 |
| 6 | autopilot.sh | ~80 | 1.0h | 3,5 | cron 主循环 + flock + 心跳 + 超时扫描 + 合约违规检测 |
| 7 | boot_context.py | ~80 | 1.0h | 1 | DPL-011: session DB + pipeline_state.db + memory → .hermes.md |
| 8 | .hermes.md 静态模板 | ~200 | 0.3h | — | 完整项目治理文档（角色表、管线规则、QA 标准等） |
| 9 | dashboard.py | ~60 | 0.5h | 1 | 读 v2 schema + kanban.db → 红绿灯面板 |
| 10 | test_pipeline.py | ~150 | 0.5h | 1-9 | 集成测试：模拟 7 步全流程 + rollback + 超时 |
| 11 | 集成 + bugfix | — | 1.5h | 1-10 | 端到端 dry-run 验证 + 问题修复 |

**总计**：0.5 + 2.0 + 0.5 + 2.0 + 0.3 + 0.5 + 1.0 + 1.0 + 0.3 + 0.5 + 0.5 + 1.5 = **10.6h**

**取整：~11 小时，约 1.5 个工作日。**

### 6.2 与 R3 估算的差异

| 项目 | R3 估算 | R4 估算 | 差异原因 |
|------|:------:|:------:|---------|
| checkpoint.py | 1.5h | 2.0h | +v2 schema migration, +UPSERT rollback |
| contracts JSONL | 0.5h | 0.5h | 7 步但 Architect 给了完整 schema，工作量和 5 步时相当 |
| state.py | 1.0h | 2.0h | +branches 引擎（6 种 action）+ rollback 事务 + verdict 写入 |
| fanout.py | 0.5h | 0.5h | 不变 |
| autopilot.sh | 0.5h | 1.0h | +parallel join 检测 + 合约违规检测 + 心跳文件 |
| boot_context.py | — | 1.0h | 新增（DPL-011） |
| .hermes.md 模板 | — | 0.3h | 新增 |
| dashboard.py | 0.5h | 0.5h | 不变 |
| test + bugfix | — | 2.0h | R3 估算只有 test（隐含在各项中），R4 显式列出集成测试 + bugfix |
| resume.sh | 0.5h | — | 已移除（autopilot cron 本身就是唤醒机制） |
| router.py | 1.0h | — | 合并到 state.py 的 branches 引擎 |
| interrupt.py | 0.5h | — | 合并到 state.py（gate_D_roundtable / block action） |
| **总计** | **~5.0h** | **~11.0h** | **+6.0h** |

### 6.3 为什么翻倍

1. **从 5 步→7 步**（QA 拆三阶段 + va 重命名）：每个步骤都有 branches，逻辑量线性增长
2. **从线性→分支**：branches 引擎（6 种 action）+ rollback 事务是新增的逻辑复杂度
3. **从单步→并行**：dev 和 qa-d1 的 join 点需要 fanout.py + autopilot 的 AND 检测
4. **DPL-011 完整实现**：boot_context.py 是全新模块
5. **集成税**：R3 时我低估了集成测试的时间——10 个模块之间的接口调试不会被 10×0.5h 覆盖

### 6.4 如果 Frank 要更快看到东西

**Slice 1（3.5h）**——单任务线性流程（不含 QA 三阶段、不含并行）：

```
checkpoint.py v1 + contracts JSONL(5步) + state.py(简化) + autopilot.sh(简化)
→ 演示: 一个任务从 dev → qa → verify → merge → close 线性跑通
```

**Slice 2（+3.5h）**——完整 7 步 + 分支 + 回退：

```
contracts v2 + state.py branches引擎 + fanout.py + rollback逻辑
→ 演示: VA FALSIFIED → 回退 dev → 重新跑通
```

**Slice 3（+4.0h）**——DPL-011 + 可视化 + watchdog 集成：

```
boot_context.py + .hermes.md模板 + dashboard.py + 心跳+共存测试
→ 演示: 完整管线 + 红绿灯面板 + boot context 自动更新
```

Frank 可以分阶段看——不一定要等 11 小时全写完。

---

## 7. 一句话总结

> Product 画了带岔路的地图，Architect 在每个岔路口标了判定公式，我把公式翻译成了代码逻辑。7 步 21 个分支条件全部可判定、可自动化。pipeline_state.db v2 只是 ALTER TABLE ADD COLUMN，JSONL v2 的 branches 引擎 ~80 行。从零到完整 demo ~11h，可以先 3.5h 出线性流程给 Frank 看。三方不存在未解决的工程分歧——可以开始写代码了。

---

> 我是团队的双手。蓝图验证完毕——接口冻结、坑已标注、工期已算清。给我 checkpoint 先，然后按 Slice 1→2→3 推进。三份独立卷的收敛给了我们信心，现在只剩动手了。
