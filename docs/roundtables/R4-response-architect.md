# R4 统一工作流 — Architect 发言（第二轮）：架构修正 + 细化设计

> 发言人：高见远（架构师） | 日期：2026-07-30 | 版本：v1.0
> 目标：读 Product R4 + 三方 R3 后，从架构视角修正、细化、达成统一
> 规则：kanban_complete 后传给 engineer

---

## 0. 总体判断：方向一致，需修正 3 处、细化 4 处

读完 Product R4（10 项决定 D-001~D-010）和三方 R3 报告后，架构判断：

- **8 项技术完全支持**：D-001, D-002, D-004, D-005, D-006, D-008, D-009, D-010
- **1 项需要架构修正**：D-007（I/O 路径与 Product §3.3 冲突，需统一）
- **1 项需要架构细化**：D-003（合约 JSONL 的分支结构需给出具体 schema）
- **1 项存在架构风险**：D-005（pipeline_state.db 单表不够支撑红绿灯，需新增查询/聚合视图）

---

## 1. Product 10 项决定逐项架构评审

### D-001: QA 拆为三阶段（✅ 完全支持）

**架构判断**：三阶段拆分是正确的。pipeline_state.db 的 `step_name` 枚举需从 5 步扩展为 7 步：

```
原: dev → qa → verify → merge → close
新: dev → qa-d1 → qa-exec → qa-d2 → va → merge → close
```

**schema 影响**：`step_name` 字段目前使用 TEXT 无约束（Engineer §1.4），直接可以存 `qa-d1` / `qa-exec` / `qa-d2`。不需要 migration。

**contracts JSONL 影响**：需要新增 2 行合约定义：
```jsonl
{"step":"qa-d1","requires":["spec.md"],"produces":["test_plan.md"],"timeout_min":30}
{"step":"qa-d2","requires":["test_report.md"],"produces":["review_conclusion"],"timeout_min":20,"gate":"human"}
```

原 `qa` 行改为 `qa-exec`：
```jsonl
{"step":"qa-exec","requires":["branch","code_changes","test_plan.md"],"produces":["test_report.md"],"timeout_min":45,"gate":"D_roundtable"}
```

**并行语义**：Product 设计是 dev 和 qa-d1 并行启动。autopilot 在检测到 spec.md 就绪后需要同时创建 dev 和 qa-d1 两个 kanban card。这需要 fanout.py（Engineer 已预计 ~40 行）。两个 card 都完成（dev done AND qa-d1 done）才能推进到 qa-exec。

### D-002: boot_context 5min / 2000 字符硬限制（✅ 完全支持）

**架构判断**：频率和容量限制合理。

- 5min：agent 派发是间歇性的，5min 覆盖"上一条 task done → 下一条 task 的 agent 启动时已看到最新上下文"。
- 2000 字符（~500 tokens）：作为导航摘要完全够用。Product R4 §3.1 中建议的格式（活跃任务 + 最近决策 + 最近纠正）在此预算内绰绰有余。

**原子写入**：`boot_context.py` 必须使用 `.tmp → os.rename` 模式写 `.hermes.md`。否则 autopilot 或 agent 可能读到半写文件。这个要求应该写入 `.hermes.md` 项目规范。

### D-003: 每个节点显式 if 分支写入合约 JSONL（⚠️ 需要架构细化）

**架构判断**：方向正确，但需要在合约 schema 中定义分支结构。当前 Engineer 的 JSONL 合约只定义了 `requires/produces/timeout`，没有分支逻辑。

**架构设计 — 合约 JSONL 扩展 schema**：

```jsonl
{"step":"dev","requires":[],"produces":["branch","code_changes"],"timeout_min":60,"branches":[
  {"on":"timeout","action":"retry","target":"dev","max_retries":1},
  {"on":"timeout_after_retry","action":"block","reason":"dev 超时，需 OC 介入"},
  {"on":"contract_violation","action":"block","reason":"dev produces 缺失：{detail}"}
]}
{"step":"qa-d1","requires":["spec.md"],"produces":["test_plan.md"],"timeout_min":30,"branches":[
  {"on":"test_plan_incomplete","action":"retry","target":"qa-d1","max_retries":2},
  {"on":"test_plan_incomplete_after_retry","action":"block","reason":"测试方案未覆盖关键路径"}
]}
{"step":"qa-exec","requires":["branch","code_changes","test_plan.md"],"produces":["test_report.md"],"timeout_min":45,"branches":[
  {"on":"BLOCKER_found","action":"gate_D_roundtable","reason":"QA 发现 BLOCKER"},
  {"on":"MAJOR_gt_3","action":"gate_D_roundtable","reason":"MAJOR > 3，等同于 BLOCKER"},
  {"on":"MAJOR_le_3","action":"continue","reason":"记录后继续推进"}
]}
{"step":"qa-d2","requires":["test_report.md"],"produces":["review_conclusion"],"timeout_min":20,"branches":[
  {"on":"review_fail","action":"rollback","target":"dev","reason":"D2 评审不通过：{detail}"},
  {"on":"review_conditional","action":"continue","reason":"记录 pending items → 继续推进"}
]}
{"step":"va","requires":["test_report.md"],"produces":["va_report.md"],"timeout_min":30,"branches":[
  {"on":"FALSIFIED","action":"rollback","target":"dev","reason":"VA 证伪：{detail}"},
  {"on":"undetermined","action":"block","reason":"VA 信息不足，需 OC 介入"}
]}
{"step":"merge","requires":["va_report.md","test_report.md"],"produces":["merge_commit"],"timeout_min":15,"branches":[
  {"on":"conflict","action":"block","reason":"merge 冲突，engine 需解决"},
  {"on":"human_gate","action":"await_confirm","reason":"等待 Frank 确认 merge"}
]}
{"step":"close","requires":["merge_commit"],"produces":["gai_update","manifest_update"],"timeout_min":15,"branches":[
  {"on":"step_fail","action":"retry","target":"close","max_retries":3},
  {"on":"retry_exhausted","action":"block","reason":"close.sh {step} 失败，需手动检查"}
]}
```

**JSONL 字段定义**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `step` | string | 步骤名 |
| `requires` | [string] | 进入此步骤前必须存在的 artifact |
| `produces` | [string] | 此步骤完成后产出的 artifact |
| `timeout_min` | int | 超时阈值（分钟） |
| `branches` | [object] | 分支列表 |
| `branches[].on` | string | 触发条件标识符 |
| `branches[].action` | string | 动作：retry / block / rollback / continue / gate_D_roundtable / await_confirm |
| `branches[].target` | string | 动作目标步骤（retry 和 rollback 时需要） |
| `branches[].max_retries` | int | retry 时的最大重试次数 |
| `branches[].reason` | string | 失败原因模板 |

**autopilot 读取方式**：`state.py` 在合约校验时载入 JSONL → 根据检测到的状态（如 `FALSIFIED`）匹配 `branches[].on` → 执行对应的 `action`。匹配不到任何 branch → fallback 到默认行为（block）。

**红灯时的路由**：Product 的 §1.2 表已经定义了每个节点的"失败去向"。`action: rollback` 对应"回退到 dev"（修改 pipeline_state.db 中 dev=restart, qa-exec/va=pending）。`action: block` 对应"通过 kanban_block 停止，通知 OC/Frank"。

### D-004: Autopilot + Watchdog 并行（✅ 完全支持）

**架构判断**：职责边界清晰，无冲突。

**频率设计**：

| 组件 | 频率 | 理由 |
|------|------|------|
| autopilot cron | 每 2min | 步骤切换延迟上限 2min；对 30-60min 的步骤来说可接受 |
| watchdog cron | 每 30min | 系统级健康检查，不需要分钟级精度 |
| boot_context cron | 每 5min | 上下文刷新，覆盖 agent 派发间隙 |

**互不干扰的架构理由**：

```
数据源分析：
  autopilot:     写 pipeline_state.db + 读 kanban.db
  watchdog:      读 kanban.db + cron.db + session file（只读）
  boot_context:  读 session DB + pipeline_state.db + memory → 写 .hermes.md

  写冲突: 无 —— autopilot 是 pipeline_state.db 唯一写者，boot_context 是 .hermes.md 唯一写者
  读冲突: 无 —— SQLite WAL 支持并发读 + 单写
  kanban.db: 三者都只读 —— 零冲突
```

**唯一交集**：watchdog 监控 `pipeline-autopilot` cron job 的心跳。Engineer §6.1 已正确指出：

```yaml
watchdog:
  cron_jobs_to_monitor:
    - pipeline-autopilot
    - pipeline-boot-context
```

如果 autopilot 心跳 > 2×cron_interval（即 > 4min）未更新 → watchdog 发飞书告警。

### D-005: dashboard 红绿灯（⚠️ 需要架构补充）

**架构判断**：pipeline_state.db 的当前 schema（单表 `pipeline_steps`）不够直接支撑红绿灯展示。需要补充。

**问题分析**：单表 `pipeline_steps` 是 append-only 的步骤记录。要回答"当前这个 task 的每个节点的红绿灯是什么"，需要聚合查询。但以下信息在当前 schema 中不存在：

1. **合约校验结果**（dev 的 produces 是否通过合约校验 → 不在 pipeline_state.db 中，在 autopilot 的运行时判定里）
2. **D1/D2 评审结论**（pass/conditional pass/fail → 在 kanban comment 中，不在 pipeline_state.db 中）
3. **VA FALSIFIED/VERIFIED 结论**（在 VA report 文件中，结构化状态不在 pipeline_state.db 中）

**架构修正**：pipeline_steps 表需要新增字段：

```sql
-- 新增字段（需要 PRAGMA user_version = 2 的 migration）
ALTER TABLE pipeline_steps ADD COLUMN verdict TEXT;
-- verdict 取值: null (pending/running) | 'pass' | 'fail' | 'conditional_pass'
--              | 'FALSIFIED' | 'VERIFIED' | 'blocked' | 'timeout'

ALTER TABLE pipeline_steps ADD COLUMN verdict_detail TEXT;
-- 可选的详细原因（如 "MAJOR=2, 安全漏洞=0" 或 "合约校验: branch 不存在"）

ALTER TABLE pipeline_steps ADD COLUMN contract_check_passed INTEGER;
-- 0/1/NULL：合约校验是否通过（0=未校验, 1=通过, 2=失败）
```

**数据流补充**：

| 节点 | 谁写 verdict | 写入时机 | 判定依据 |
|------|-------------|---------|---------|
| dev | state.py（合约校验后） | dev done 且合约校验完成 | contract_check_passed |
| qa-d1 | state.py（读 kanban comment 中的 D1 评审结论） | D1 评审 pass/fail | kanban comment |
| qa-exec | state.py（读 QA report 分级字段） | QA report 产出 | BLOCKER=0 AND MAJOR≤3 |
| qa-d2 | state.py（读 D2 评审结论） | D2 评审 pass/fail | kanban comment |
| va | state.py（读 VA report） | VA report 产出 | FALSIFIED/VERIFIED |
| merge | state.py（git merge 返回值） | merge 完成 | 退出码 |
| close | close.sh（6 步返回值） | close.sh 完成 | 每步 exit code |

**dashboard.py 数据源**：`pipeline_state.db` + `kanban.db`（读 task 优先级 + assignee）。单一 SQL 查询即可生成 Product §5.2 格式的面板输出。不需要额外 API——两个 SQLite DB 足够。

**新增查询 SQL 原型**：

```sql
-- 获取所有活跃 task 的节点级红绿灯状态
SELECT
    ps.task_id,
    ps.step_name,
    ps.status,
    ps.verdict,
    ps.started_at,
    ps.finished_at,
    t.priority,
    t.assignee
FROM pipeline_steps ps
JOIN kanban_db.tasks t ON ps.task_id = t.id
WHERE t.status != 'done' AND t.status != 'failed'
ORDER BY t.priority DESC, ps.started_at ASC;
```

### D-006: .hermes.md 动态区块 cron 唯一写入（✅ 完全支持，补充互斥锁）

**架构判断**：方向正确。所有 profile 读同一个 `.hermes.md` = Hermes 框架行为（Project Context 自动加载）。boot_context cron 是唯一写入者。

**互斥锁**：boot_context cron 运行期间如果恰好有 agent 在启动，Hermes 会读取 `.hermes.md`。需要原子写入避免读到半截文件：

```python
# boot_context.py 写入逻辑
import os, tempfile

tmp_path = workspace_root + "/.hermes.md.tmp"
target_path = workspace_root + "/.hermes.md"

with open(tmp_path, "w") as f:
    f.write(full_content)
os.rename(tmp_path, target_path)  # POSIX 原子 rename
```

`os.rename` 在 Linux 上是原子的——读进程要么读到旧版本（完整的），要么读到新版本（完整的），不存在中间态。

### D-007: 成员 I/O 标准化路径（⚠️ 需要架构统一）

**架构判断**：Product D-007 的路径 `<workspace>/output/<role>/<task_id>/` 与 Product R4 §3.3 表中的约定 **存在冲突**。

**冲突对照**：

| 角色 | Product §3.3 表 | D-007 标准 | 冲突？ |
|------|----------------|-----------|--------|
| QA | `docs/qa/test-plan-{id}.md` | `output/qa/{task_id}/test_plan.md` | ⚠️ 冲突 |
| VA | `docs/va/va-report-{id}.md` | `output/va/{task_id}/va_report.md` | ⚠️ 冲突 |
| Architect | `docs/arch-{id}.md` | `output/architect/{task_id}/arch.md` | ⚠️ 冲突 |
| Engine | 分支 `feat/{id}`（不在 docs/ 下） | `output/engine/{task_id}/` | — |

**架构建议：统一为 D-007 方案**。理由：

1. **可预测性**：autopilot 和 state.py 不需要记住"QA 的输出在 `docs/qa/` 但 VA 的在 `docs/va/`"——一个规则 `output/<role>/<task_id>/` 覆盖所有。
2. **隔离性**：按 task_id 分目录，P0-21 的 QA 产出不会和 P0-22 的混在一起。
3. **合约校验简化**：state.py 检查 `output/{role}/{task_id}/{artifact}` 是否存在——不需要硬编码每种角色的路径约定。

**实施影响**：
- Product §3.3 表的"路径约定"段落需要修正为：`output/<role>/<task_id>/` 格式
- Engineer 的 contract JSONL 中 `produces` 字段从绝对路径改为相对 artifact 名（`test_plan.md` 而非 `docs/qa/test-plan-{id}.md`）
- state.py 按 `output/<role>/<task_id>/<artifact>` 解析完整路径

### D-008: OpenSpec specs 项目级存储（✅ 完全支持）

**架构判断**：项目级是对的。`openspec/` 绑定 workspace root。

**多项目场景下的隔离**：如果 `/workspace/` 下有 project-a 和 project-b：

```
/workspace/project-a/openspec/changes/{id}/     ← project-a 的 specs
/workspace/project-b/openspec/changes/{id}/     ← project-b 的 specs
```

各自有各自的 `pipeline_state.db` 和 `.hermes.md`。Specs 不会跨项目混淆——OpenSpec CLI 的 propose/apply 天然绑定当前工作目录。

### D-009: pipeline_state.db 项目级存储（✅ 完全支持）

**架构判断**：Product 的理由（隔离性、可移植性、跨项目独立）都是正确的架构理由。

**多项目共用 workspace 的风险**：如果两个 project 共用一个 workspace 目录，各自的 `pipeline_state.db` 和 OpenSpec specs 都在同一根目录下 → 冲突。但这是 workspace 组织层面的问题，不是 pipeline_state.db 的问题。

**boot_context cron 如何知道写哪个项目的 `.hermes.md`**：cron job 配置中指定 `workdir` 参数：

```
cronjob:
  name: "pipeline-boot-context-devppl"
  schedule: "every 5m"
  workdir: /workspace/devPPL
  script: scripts/boot_context.py
```

`boot_context.py` 从当前工作目录推导 project root → 写 `<cwd>/.hermes.md`。不同项目各配一个 cron job，互不干扰。

### D-010: Engineer 角色表修正（✅ 完全支持，无架构影响）

**架构判断**：角色缺失不影响管线技术实现。Engineer 的角色表是文档描述，不是代码。修正后只需在 `pipeline_steps` 的 `assigned_agent` 字段中增加 Product 作为可能的赋值值（用于 D1/D2 评审 kanban card 的 assignee）。

---

## 2. D-003 细化：分支合约 JSONL 完整设计

已在 §1 D-003 中给出完整 schema。补充以下细节：

### 2.1 state.py 如何读取和执行分支

```python
# state.py 合约校验 + 分支判定伪代码

contract = load_contract_jsonl(task_id)
step = get_current_step(task_id)

for branch in contract[step].branches:
    if detect_condition(branch["on"]):   # 检测触发条件
        action = branch["action"]
        if action == "retry":
            if attempt_count <= branch["max_retries"]:
                retry_step(branch["target"])
            else:
                block_step(reason=branch["reason"])
        elif action == "rollback":
            rollback_to(branch["target"])
            write_checkpoint(step="rollback", detail=branch["reason"])
        elif action == "block":
            block_step(reason=branch["reason"])
        elif action == "continue":
            write_checkpoint(verdict="conditional_pass", detail=branch["reason"])
            advance_to_next_step()
        elif action == "gate_D_roundtable":
            create_roundtable_task(type="D", reason=branch["reason"])
            block_step()
        elif action == "await_confirm":
            wait_for_kanban_unblock()
```

### 2.2 红灯路由全链路

以「VA FALSIFIED → 回退 dev」为例：

```
1. VA agent 产出 va_report.md，conclusion = FALSIFIED
2. VA agent 调用 kanban_complete
3. autopilot 检测到 va done
4. state.py 合约校验：
   a. 读 va_report.md → 提取 conclusion = FALSIFIED
   b. 匹配 branches[].on = "FALSIFIED"
   c. 执行 action = "rollback", target = "dev"
5. checkpoint 写入：
   a. pipeline_state.db: step=va, verdict=FALSIFIED, status=done
   b. pipeline_state.db: step=qa-d2, status=pending (重置)
   c. pipeline_state.db: step=qa-exec, status=pending (重置)
   d. pipeline_state.db: step=qa-d1, status=pending (重置)
   e. pipeline_state.db: step=dev, status=restart (回退目标)
6. autopilot 创建新的 dev kanban card（assignee=game-engine）
7. kanban comment: [AUTOPILOT: ROLLBACK] VA FALSIFIED → 回退到 dev
```

**回退时 pipeline_state.db 的写入**：使用 UPSERT（task_id + step_name 是 UNIQUE 约束），覆盖旧状态。保留旧的 attempt 记录在单独的 audit log 中（未来可选）。

---

## 3. D-006 ~ D-009 存储层级全链路校验

### 3.1 多项目场景下的 schema 冲突分析

**场景**：`/workspace/` 下有 `project-a` 和 `project-b`，各有一个 `.hermes.md`。两个项目的 agent 都会被派发到 `/workspace/` 下的不同工作区。

**结论：不冲突**。理由：

| 组件 | 存储路径 | 冲突？ |
|------|---------|--------|
| `.hermes.md` | `<project_root>/.hermes.md` | ❌ Hermes 从 agent 的 workdir 向上遍历到 git root，找到最近的 `.hermes.md`。project-a 和 project-b 的 agent 各读各的 |
| `pipeline_state.db` | `<project_root>/pipeline_state.db` | ❌ 物理分离 |
| `openspec/` | `<project_root>/openspec/` | ❌ 物理分离 |
| `output/` | `<project_root>/output/` | ❌ 按 D-007 标准，物理分离 |

**唯一潜在冲突**：如果 autopilot cron 的 workdir 指向 `/workspace/`（而非具体项目），它不知道该读哪个 `pipeline_state.db`。解决方案：**每个项目一个 autopilot cron**，workdir 精确指向项目根目录。

### 3.2 boot_context cron 如何知道写哪个 `.hermes.md`

```python
# scripts/boot_context.py 关键段

import os

def find_project_root():
    """从 cwd 向上遍历找 .git / .hermes.md / pipeline_state.db"""
    cwd = os.getcwd()  # cron 的 workdir 设置了这个
    while cwd != "/":
        if os.path.exists(os.path.join(cwd, ".hermes.md")):
            return cwd
        if os.path.exists(os.path.join(cwd, ".git")):
            return cwd
        cwd = os.path.dirname(cwd)
    return os.getcwd()  # fallback

project_root = find_project_root()
target = os.path.join(project_root, ".hermes.md")
# ... 拼接 + 原子写入
```

**多项目**：每个项目各配一个 boot_context cron，workdir 不同：

```
cron: pipeline-boot-context-devppl    workdir: /workspace/devPPL
cron: pipeline-boot-context-other     workdir: /workspace/other-project
```

---

## 4. D-005 细化：dashboard 数据源与 pipeline_state.db schema 扩展

已在 §1 D-005 中给出 schema 扩展方案。以下是数据源的完整分析：

### 4.1 数据源清单

| 信息需求 | 当前数据源 | 够不够？ | 需要补充 |
|---------|-----------|---------|---------|
| 步骤进度（running/done） | pipeline_state.db.status | ✅ 够 | — |
| 红绿灯（✅/🔴） | — | ❌ | 新增 verdict 字段 |
| 持续时间 | pipeline_state.db.started_at / finished_at | ✅ 够 | — |
| 阻塞原因 | — | ❌ | 新增 verdict_detail 字段 |
| 合约校验结果 | — | ❌ | 新增 contract_check_passed 字段 |
| autopilot 心跳 | 心跳文件 `/.pipeline/heartbeat` | ✅ 够 | — |
| 全局阻塞计数 | 聚合查询 | ✅ 够（SQL） | — |

### 4.2 pipeline_state.db v2 schema

```sql
PRAGMA user_version = 2;

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
    -- v2 新增字段
    verdict TEXT,                         -- pass|fail|conditional_pass|FALSIFIED|VERIFIED
    verdict_detail TEXT,                  -- 详细原因
    contract_check_passed INTEGER,        -- NULL(未校验)|1(通过)|2(失败)
    UNIQUE(task_id, step_name)
);
```

**migration**：Engineer 已预留 `PRAGMA user_version` 机制（§4 坑 3）。v1→v2 只需 `ALTER TABLE ADD COLUMN`，SQLite 支持。

### 4.3 dashboard.py 查询接口

不需要新增 API。dashboard.py 直接读 pipeline_state.db + kanban.db：

```python
# pipeline/dashboard.py 核心逻辑

def get_pipeline_view():
    """返回 Product §5.2 格式所需的所有数据"""
    conn = sqlite3.connect("pipeline_state.db")
    rows = conn.execute("""
        SELECT task_id, step_name, status, verdict, verdict_detail,
               started_at, finished_at, contract_check_passed
        FROM pipeline_steps
        WHERE status != 'done'
        ORDER BY task_id, step_name
    """).fetchall()

    # 读 kanban.db 获取任务优先级和 assignee
    kanban = sqlite3.connect("/root/.hermes/kanban.db")
    tasks = kanban.execute("""
        SELECT id, title, priority, assignee
        FROM tasks WHERE status NOT IN ('done','failed')
    """).fetchall()

    return assemble_dashboard(rows, tasks)
```

---

## 5. D-004 细化：Autopilot/Watchdog 频率与互不干扰证明

### 5.1 频率设计理由（数值论证）

| 参数 | 值 | 为什么是这个值 |
|------|-----|---------------|
| autopilot cron | 2min | 步骤持续时间 30-60min → 2min 延迟占总时间 3-7%，可接受。低于 1min 对 SQLite WAL 压力增加但无感知收益 |
| watchdog cron | 30min | 系统级监控。autopilot 心跳 2min 级，watchdog 检测"心跳超过 4min 未更新"由 watchdog 自己的轮询+心跳文件 mtime 计算——不依赖 30min 的 cron 频率做及时告警 |
| boot_context cron | 5min | agent 派发间隔 > 5min（一个 step 完成后下一个 agent 被 dispatcher 派发需要数分钟），5min 足够覆盖 |

### 5.2 autopilot 自身防重入

Engineer §6.3 的建议正确——`flock` 文件锁防止 cron tick 重叠：

```bash
#!/bin/bash
# autopilot.sh 开头
LOCKFILE="/tmp/pipeline-autopilot.lock"
exec 200>"$LOCKFILE"
flock -n 200 || exit 0  # 已有实例在跑，静默退出
```

### 5.3 互不干扰完整证明

```
┌────────────────────────────────────────────────────────────┐
│                    数据源访问矩阵                            │
├──────────────────┬──────────┬──────────┬───────────────────┤
│                  │ autopilot│ watchdog │ boot_context      │
├──────────────────┼──────────┼──────────┼───────────────────┤
│ pipeline_state.db│   W      │    —     │   R               │
│ kanban.db        │   R      │    R     │   R               │
│ .hermes.md       │   R      │    —     │   W (原子)        │
│ cron.db          │   —      │    R     │   —               │
│ session DB       │   —      │    R     │   R               │
│ memory           │   —      │    —     │   R               │
│ 心跳文件         │   W      │    R     │   —               │
└──────────────────┴──────────┴──────────┴───────────────────┘

W = 写入, R = 只读, — = 不接触

写冲突矩阵:
  pipeline_state.db: 唯一写者 = autopilot → 零冲突
  .hermes.md:        唯一写者 = boot_context → 零冲突
  心跳文件:          唯一写者 = autopilot → 零冲突

结论: 三者之间不存在任何写-写冲突或写-读冲突。
      SQLite WAL 支持并发读+单写，三者的读操作互不阻塞。
```

---

## 6. Frank 反馈 #1：分支处理 — 每个节点的 if 条件 + 失败路由

Product R4 §1.1 的完整分支流程图已经覆盖了所有节点。从架构角度补充以下实现细节：

### 6.1 节点 → 判定方式 → 失败路由（架构实现映射）

| 节点 | if 条件 | 判定方式 | 实现组件 | 失败路由 |
|------|--------|---------|---------|---------|
| OpenSpec validate | `validate --strict` 非 0 | CLI exit code | OC 调用 | 修正 spec（最多 3 次）→ block |
| 铁律冲突 | spec 违反 SOUL.md | autopilot 交叉检查脚本 | state.py 预检 | D 类 roundtable |
| dev 合约 | produces 缺失 | 文件系统检查 | state.py | 阻塞 → 等待补交 → 超时 block |
| qa-d1 评审 | 覆盖率 < 100% | 读 test_plan.md vs spec.md | state.py 读 review 结论 | QA 补充 → 重新 D1 |
| qa-exec BLOCKER | BLOCKER > 0 | 读 QA report 分级字段 | state.py 解析 report | D 类 roundtable → 回退 dev |
| MAJOR > 3 | MAJOR 计数 > 3 | 读 QA report | state.py | 等同于 BLOCKER |
| qa-d2 评审 fail | 分级错误 / 漏报 | 读 D2 评审结论 | state.py | 回退 dev 或 QA 重测 |
| VA FALSIFIED | conclusion = FALSIFIED | 读 VA report | state.py | 全链回退到 dev |
| VA 无法判定 | 信息不足 | 读 VA report | state.py | block → OC 介入 |
| merge 冲突 | git merge ≠ 0 | git merge 返回值 | autopilot | engine 解决 → 重新 merge |
| close.sh 失败 | 任一步 exit ≠ 0 | close.sh 返回码 | autopilot | 重试 → block → OC 介入 |
| engine 忘 commit | produces 缺失 | 合约校验 | state.py | 阻塞 → 等待补交 → 超时 block |
| autopilot 宕机 | 心跳文件 mtime > 4min | watchdog 检测 | watchdog | 飞书告警 Frank |

### 6.2 「engine 忘 commit」的检测链

这是 Product §1.1 中最具体的架构实现场景：

```
1. engine 标记 kanban_complete → autopilot 检测到 dev done
2. state.py 合约校验：
   a. requires: [] (无前置依赖)
   b. produces: ["branch", "code_changes"]
   c. 检查: git branch --list "feat/{task_id}" → 分支存在?
   d. 检查: git diff main...feat/{task_id} --stat → 有文件改动?
3. 如果分支不存在 或 diff 为空:
   → state.py 返回 CONTRACT_VIOLATION
   → autopilot 写 kanban comment [CONTRACT_VIOLATION: dev produces 缺失 {detail}]
   → 不创建 QA 卡片
   → 30min 超时 → kanban_block(reason="engine 未补交产物")
4. engine 补交代码 → 重新 kanban_complete → autopilot 再次校验 → 通过 → 推进
```

---

## 7. Engineer R3 角色缺失的架构影响

Engineer 的 R3 §1.1 角色速览表只有 5 个角色（OC, Arch, Eng, QA, VA），缺失了 Product 和 VA 的实际更多角色。

### 7.1 直接架构影响

**正影响**（Engineer 的设计结果正确，仅文档描述缺失）：
- 管线脚本（state.py / autopilot.sh / close.sh）不依赖角色表——它们依赖的是 `kanban.assignee` 字段和 `pipeline_steps.assigned_agent` 字段
- D1/D2 评审的 kanban card assignee 可以是 Product（`game-director`）— 只要 kanban task 上有这个 profile，dispatcher 就能派发

**无直接影响**（仅文档层面）：
- `pipeline_steps.assigned_agent` 字段是 TEXT，不校验枚举值——缺失 Product 角色不影响 DB 写入
- I/O 路径按 D-007 标准统一后，`output/product/` 目录会在 Product agent 执行时自动创建（如果 Product 作为 agent 被 dispatcher 派发）

### 7.2 如果 Engineer 的 I/O 目录不包含 Product

如果 Engineer 在实现时按旧角色表（5 角色），可能遗漏 `output/product/` 目录的契约定义。

**架构预防**：contract JSONL 中不按角色名——按 step 名。step = `qa-d1` / `qa-d2` 的评审结论写入 kanban comment（不通过文件系统传数据），所以不需要 `output/product/` 目录来传 artifact。Product 的 D1/D2 评审结论是 kanban comment，被 state.py 通过 kanban API 读取。

修正理解：**Product 的输出是 kanban comment（评审结论），不是文件。**Product §3.3 表需要修正——Product 的输出渠道是 kanban comment，不是 `output/product/{task_id}/`。

---

## 8. 架构修正汇总

以下是我在 R4 中对 Product 决定进行架构修正的汇总，供 Engineer 作为实现输入：

### 8.1 需要修正的决定

| 决定 | 问题 | 架构修正 |
|------|------|---------|
| D-007 | 与 Product §3.3 路径冲突 | 统一为 `output/<role>/<task_id>/`，Product §3.3 表需更新 |
| D-005 | pipeline_state.db schema 不完整 | v2 新增 verdict / verdict_detail / contract_check_passed 字段 |

### 8.2 需要细化的决定

| 决定 | 架构细化 |
|------|---------|
| D-003 | JSONL 合约扩展 `branches` 字段（完整 schema 见 §2） |
| D-004 | 频率论证 + 防重入锁 + 互不干扰证明（见 §5） |
| D-006 | 原子写入（`os.rename`）+ boot_context cron workdir 配置（见 §1 D-006、§3.2） |
| D-008/D-009 | 多项目隔离 + cron 配置模板（见 §3） |

### 8.3 完全支持的 8 项

D-001, D-002, D-004（职责边界）, D-005（视觉方案）, D-006, D-008, D-009, D-010

### 8.4 pipeline_state.db v2 schema（给 Engineer 的实现输入）

```sql
PRAGMA user_version = 2;

CREATE TABLE IF NOT EXISTS pipeline_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    step_name TEXT NOT NULL,              -- dev|qa-d1|qa-exec|qa-d2|va|merge|close
    status TEXT NOT NULL DEFAULT 'pending',  -- pending|running|done|failed|blocked|restart
    artifact_paths TEXT DEFAULT '[]',     -- JSON array of artifact filenames (relative to output/<role>/<task_id>/)
    started_at TEXT,
    finished_at TEXT,
    error_msg TEXT,
    retry_count INTEGER DEFAULT 0,
    assigned_agent TEXT,
    openspec_ref TEXT,
    -- v2 新增 ─────────────────────────────
    verdict TEXT,                         -- pass|fail|conditional_pass|FALSIFIED|VERIFIED|blocked|timeout
    verdict_detail TEXT,
    contract_check_passed INTEGER,        -- NULL(未校验)|0(不适用)|1(通过)|2(失败)
    UNIQUE(task_id, step_name)
);
```

### 8.5 合约 JSONL v2（7 步，含分支）

完整 JSONL 已在 §1 D-003 中给出。总结步骤清单：`dev → qa-d1 → qa-exec → qa-d2 → va → merge → close`（7 步）。

---

## 9. 架构推进顺序建议

基于以上分析，我的推进顺序与 R3 时一致（无需调整）：

```
Phase 0: 前置条件（0.4h）
  └─ Node 升级 → OpenSpec CLI 安装

Phase 1: 数据基座（1.0h）
  └─ P0-3: checkpoint.py（含 v2 schema + migration）

Phase 2: 合约 + 编排（2.5h）
  ├─ P0-1: state.py（含 JSONL v2 解析 + branches 执行引擎）
  └─ P0-2: autopilot.sh（含 cron + flock + 心跳文件）

Phase 3: 上下文（0.7h）
  ├─ DPL-011 Layer 1: boot_context.py（含原子写入 + project_root 检测）
  └─ DPL-011 Layer 2: SOUL.md 铁律 6

Phase 4: 可视化（0.5h）
  └─ P1-2: dashboard.py（读 pipeline_state.db v2 + kanban.db）
```

总计 ~4.6h，与 Engineer 的 5.0h 估算对齐。

---

## 10. 不做的事（架构边界）

- 不引入 webhook 替代 cron polling（Hermes 不支持 kanban 事件）
- 不在 pipeline_state.db 中存全量 audit log（单表足够；audit log 未来可选）
- 不修改 Hermes 引擎源码（管线完全在脚本层实现）
- 不要求所有 agent 修改 SOUL.md（铁律 6 只需添加到 OC/engineer/QA 的 SOUL.md）

---

> 地基已经夯实。Product 画了带岔路的路，我在上面铺了石板——每个岔路口的判定公式、JSONL 的 schema、pipeline_state.db 的字段、autopilot 和 watchdog 怎么并行不打架。Engineer 接着这条路往下铺，不需要猜任何接口。
>
> 这次对齐后，三方不存在未解决的架构分歧。可以交给 Engineer 写代码了。
