# Roundtable B: 管线工具评估与改进建议 — 工程师发言

> 发言人: 寇豆码（工程师） | 日期: 2026-07-30 | 版本: v1.0
> 关联: Product 发言, Architect 发言 (t_5b17ec48)
> 议题: 节点合约/校验、checkpoint、可视化面板、条件路由、中断接口

---

## 0. 现状盘点——代码库里到底有什么

在评估 Architect 的方案可行性之前，先盘点现实：

```
/workspace/devPPL/
├── scripts/lib/
│   ├── kanban_helpers.py    (197行) — kanban CLI 封装，含 JSONL 日志先例
│   └── config_loader.py     (232行) — YAML config 加载，含 semver 校验
├── config/
│   └── qa-classification.yaml (294行) — YAML 单一事实来源模式，已验证可用
├── GLOBAL_ACTION_ITEMS.md   (197行) — 人工维护的 manifest
├── docs/
│   └── analysis-pipeline-scripting-feasibility.md (217行) — 已有管线脚本化预研
└── (无 pipeline/ 目录、无 pipeline_state.db、无 close.sh)
```

### 关键发现

**发现 0.1：close.sh 不存在**

GLOBAL_ACTION_ITEMS.md 第 104 行标注：
> ✅ P19-01 done（2026-07-21：close.sh 完成——强制闭环 6 步验证脚本）

但 `search_files` 在整个仓库中找不到 `close.sh`。两种可能：
- (a) 在 OC 的 profile home 而非 repo 中（`/root/.hermes/profiles/orchestrator/scripts/close.sh`）
- (b) 从未被提交到 devPPL repo

**影响**：如果 close.sh 确实存在 but 不在 repo 中，P0-2（checkpoint）的复用 `pipeline_state.db` 路径需要重新验证。如果 close.sh 不存在，说明 P0-19 的实际完成状态和 GAI 记录不一致。

**发现 0.2：pipeline_state.db 不存在于 devPPL**

分析文档称 `pipeline_state.db (SQLite)，infomanager 已用`——但该 DB 不在 devPPL 仓库中。InfoManager 是独立 workspace（`/workspace/InfoManager/`）。Architect 说「复用 pipeline_state.db 基础设施」——如果 infra 在另一个 workspace，需要确认 schema 兼容性和共享方式。

**发现 0.3：JSONL 日志已有先例**

`kanban_helpers.py` 第 125-142 行的 `log_action()` 函数已经写 `logs/appeal_audit.jsonl`。这意味着 P0-1 的 JSONL 合约文件不需要从零发明模式——直接复用 `scripts/lib/` 的工具函数 + JSONL 格式约定。

**发现 0.4：YAML 配置模式已验证**

`config/qa-classification.yaml` + `config_loader.py` 是生产级的 YAML 配置加载器，支持 semver、缓存、访问器。P1-1 的条件路由 YAML 配置可以直接套用此模式——config_loader 可以扩展一个 `load_pipeline_config()`。

---

## 1. P0-1 步骤合约引擎：JSONL + state.py

### 1.1 Architect 方案评估

> JSONL 合约文件 + state.py 脚本层确定性校验（非 LLM），校验放在步骤切换入口而非出口

**方向正确。** 但有几个实现层面的关键问题需要澄清。

### 1.2 合约文件格式

Architect 说的「JSONL 合约文件」没有给出格式。我需要确认：

```jsonl
{"step": "dev", "requires": ["prd.md", "architecture.md"], "produces": ["branch", "code_changes"], "timeout_min": 60}
{"step": "qa", "requires": ["branch", "code_changes"], "produces": ["test_plan.md", "test_report.md"], "timeout_min": 45, "gate": "D_roundtable"}
{"step": "verify", "requires": ["test_report.md"], "produces": ["va_results"], "timeout_min": 30}
{"step": "merge", "requires": ["va_results", "test_report.md"], "produces": ["merge_commit"], "gate": "human"}
{"step": "close", "requires": ["merge_commit"], "produces": ["gai_update", "manifest_update"], "timeout_min": 15}
```

**问题**：produces 是一个「文件名」还是「逻辑产物」？如果是文件名（如 `docs/qa-test-report-{P0-id}.md`），需要模板变量替换——这和 Architect 反对的「全节点 schema」之间的界限在哪？需要明确。

### 1.3 state.py 的校验逻辑

「脚本层确定性校验」意味着 state.py 做的是文件存在性、超时、产物清单等检查——不需要 LLM。这可以实现。代码量估计：

```python
# state.py 伪结构（~120 行，不是 80 行）
#
# class PipelineState:
#     - load_contract(jsonl_path)       ~15 lines
#     - validate_entry(step, context)   ~30 lines  ← 核心：检查 requires 是否满足
#     - validate_exit(step, context)    ~20 lines  ← 检查 produces 是否产出
#     - transition(from_step, to_step)  ~15 lines
#     - report()                        ~20 lines
#     - (error handling)                ~20 lines
```

Architect 估 2.0h。实际分解：

| 子任务 | 估时 | 说明 |
|--------|:---:|------|
| 设计 JSONL schema + 写 5-6 步的合约文件 | 0.3h | 需要和 product/architect 对齐 produces/requires 语义 |
| state.py 编写 (~120 行) | 0.5h | 含文件存在性检查、超时校验、产物清单比对 |
| 集成到现有 kanban_helpers.py | 0.2h | 读 kanban 状态 → 触发校验 → 写结果 |
| 单元测试 (5-6 步状态转换) | 0.5h | TDD：先写好期望的合约 violation 输出再写校验逻辑 |
| 集成测试（端到端：模拟一个 dev→qa→verify→merge→close） | 0.5h | 用 dry-run 模式跑完整管线 |
| **合计** | **~2.0h** | ⚠️ 和 Architect 一致——但这是写代码+测试，不含调试 |

**但如果再加 0.5h 的边界 case 时间**（合约文件格式错误、步骤跳过、产物部分缺失、超时但产物已生成等）更诚实的估算是 **2.5h**。

### 1.4 校验放在步骤入口而非出口——同意但有坑

Architect 说校验放在入口（「进入 QA 步骤 → 检查 dev 的 produces」）。逻辑正确——在花钱之前检查存款。

**坑**：入口校验需要知道「上一步产出了什么」。这需要 checkpoint 数据（这正是 P0-2）或者从 kanban 卡片 body 中解析——而后者是不可靠的（NL 自由文本）。

**这意味着 P0-1 和 P0-2 的耦合比我预期的更紧**：state.py 的入口校验实际上依赖 checkpoint 来回答「上一个 step 实际产出了什么文件」。如果 P0-2 延后，state.py 的校验就只能做基本的存在性检查（文件在不在期望路径），做不到「这个文件是上一步刚生成的还是 3 天前的」。

### 1.5 现有集成点

state.py 需要集成的现有组件：

| 集成点 | 现有代码 | 集成方式 |
|--------|---------|---------|
| Kanban 状态读取 | `kanban_helpers.get_task()` | import 直接用，JSON → dict |
| 产物清单跟踪 | `pipeline_state.db` (P0-2) | SQLite 查询 `SELECT file_path FROM artifacts WHERE step=? AND task_id=?` |
| 日志记录 | `kanban_helpers.log_action()` (JSONL) | 复用，追加 `{"action": "validate_entry", "step": "qa", "result": "pass|fail"}` |
| 配置读取 | `config_loader.py` | 新增 `load_pipeline_config()` → 读合约 YAML/JSONL |

---

## 2. P0-2 checkpoint：SQLite WAL

### 2.1 SQLite WAL 方案在 Hermes sandbox 下可行吗？

**短答：可行，但有 `~` 路径的坑。**

Architect 选择了 SQLite WAL 而非纯 JSON，理由是「并发写入冲突」。这个判断正确——多个 cron job（autopilot、watchdog）可能同时想写 checkpoint。

但需要确认的工程事实：

**WAL 模式在单文件 SQLite 下的并发行为**：
- SQLite WAL 允许多个 reader + 一个 writer 并发
- 但 writer 是排他的——两个进程同时写，第二个拿 `SQLITE_BUSY`
- 默认 busy_timeout 是 0（立即返回 BUSY）→ 需要显式设置 `PRAGMA busy_timeout = 5000`
- 在 Hermes sandbox 下（多 cron 进程），这会导致偶尔的 checkpoint 写入失败

**缓释**：state.py 的 SQLite 操作需要加 `sqlite3_busy_timeout(5000)` + 重试逻辑（~5 行 Python）。不建议用 WAL 的 `BEGIN IMMEDIATE` 或锁——在 cron 进程中持锁的风险比偶发 BUSY 更高。

### 2.2 `~` 路径陷阱（pitfall 44 复现）

Agent session 中 `~` 展开到 profile home（如 `/root/.hermes/profiles/game-engine/`），而非 `/root/`。如果 pipeline_state.db 路径写成 `~/pipeline_state.db`，实际会写到 profile home。

**必须在 state.py 中使用绝对路径**：

```python
# ✅ 正确
DB_PATH = Path("/workspace/devPPL/pipeline_state.db")

# ❌ 错误——在不同 profile 的 session 下会展开到不同位置
DB_PATH = Path("~/pipeline_state.db").expanduser()
```

### 2.3 跨 profile/worktree 共享

Architect 说「复用 pipeline_state.db 基础设施」。如果 pipeline_state.db 放在 project workspace（如 `/workspace/devPPL/pipeline_state.db`），所有操作此项目的 agent profile 都可以访问。但如果 InfoManager 的 pipeline_state.db 在 `/workspace/InfoManager/`，devPPL 的 agent 不能跨 workspace 读。

**建议**：每个 project workspace 有自己的 `pipeline_state.db`。不跨 workspace 共享——这和 `--workspace` 参数的隔离设计一致。

### 2.4 schema 设计（非「全节点 schema」——同意 Architect）

SQLite 只存步骤级状态，不存节点内部细节：

```sql
CREATE TABLE IF NOT EXISTS pipeline_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,           -- kanban task id
    step_name TEXT NOT NULL,         -- "dev", "qa", "verify", "merge", "close"
    status TEXT NOT NULL,            -- "pending", "running", "done", "failed", "blocked"
    artifact_paths TEXT,             -- JSON array: ["docs/prd-p0-xx.md", "feat/p0-xx"]
    started_at TEXT,
    finished_at TEXT,
    error_msg TEXT,
    retry_count INTEGER DEFAULT 0,
    UNIQUE(task_id, step_name)
);
```

这和 Architect 说的「~80 行 Python」匹配。实际代码量：SQL schema（~15 行）+ Python wrapper（~65 行） = **~80 行**。同意。

### 2.5 工期修正

Architect 估 0.8h。但含：
- 设计 schema + 处理 path resolution + WAL busy_timeout + 重试逻辑
- 单元测试（并发写入冲突模拟）

实际需要 **~1.0h**。差 0.2h 不大，属于正常估计误差。

---

## 3. P0-3 可视化面板

### 3.1 「依赖 P0-1+P0-2 数据就绪」——同意，但补充细节

Architect 的判断是可视化面板需要等合约引擎和 checkpoint 的数据就绪。从工程师角度完全同意——没有数据源，面板就是白屏。

具体数据依赖链：

```
P0-1 (state.py) ──→ 产生步骤状态变更事件
                          │
                          ▼
P0-2 (pipeline_state.db) ← 写入步骤状态 + 产物清单
                          │
                          ▼
P0-3 (仪表盘) ← 从 pipeline_state.db + kanban 读取
```

### 3.2 数据源

| 数据字段 | 来源 | 是否已有 |
|---------|------|:---:|
| 当前步骤 | `pipeline_state.db.steps` | 需 P0-2 新建 |
| 步骤耗时 | `started_at → finished_at` 差值 | 需 P0-2 新建 |
| 产物清单 | `pipeline_state.db.artifact_paths` | 需 P0-2 新建 |
| 任务列表 | `kanban_helpers.list_tasks()` | ✅ 已有 |
| 步骤阻塞原因 | `pipeline_state.db.error_msg` | 需 P0-2 新建 |
| 历史统计 | `logs/appeal_audit.jsonl` 模式 | ✅ 已有 JSONL 先例 |

### 3.3 实现建议：先 CLI dashboard，后 web

Architect 没说面板形式。从工程角度，最小可行是 30 行 Python 的 CLI 面板（`pipeline/dashboard.py`）：

```python
# 输出格式：
# ┌─ Pipeline: devPPL ──────────────────────────┐
# │ t_abc123: [dev:done → qa:running] 0:45:19    │
# │   artifacts: prd.md ✓, arch.md ✓, branch ✓   │
# │ t_def456: [dev:done → qa:blocked] 2:12:05    │
# │   block: D类 roundtable 待产品裁定            │
# │ t_ghi789: [dev:failed] 0:15:30               │
# │   error: missing prd.md                       │
# └──────────────────────────────────────────────┘
```

这不需要任何 web 框架——Python `print()` + 从 pipeline_state.db 读。0.5h 就能跑。先落地验证数据链路通了，再考虑飞书消息格式或 web 面板。

建议把 Architect 的 2.0h 面板工时分拆为：
- CLI dashboard 原型：0.5h
- 飞书消息格式适配：0.5h
- 完整面板（如果 Frank 确实需要）：1.0h

---

## 4. 工时评估：6.8h 现实吗？

### 4.1 逐项真实性检查

| 任务 | Architect | Engineer 评估 | 差距 | 原因 |
|------|:---:|:---:|:---:|------|
| P0-1 步骤合约引擎 | 2.0h | 2.5h | +0.5h | 含边界 case + JSONL schema 对齐 + 集成到 kanban_helpers |
| P0-2 checkpoint | 0.8h | 1.0h | +0.2h | 含 WAL busy_timeout 处理 + `~` 路径 fix |
| P0-3 可视化面板 | 2.0h | 1.5h | -0.5h | 先 CLI 原型，后飞书适配，不满 2.0h |
| P1-1 条件路由 | 1.0h | 1.2h | +0.2h | YAML 设计 + config_loader 扩展 |
| P1-2 铁律层 | 0.2h | 0.15h | ✅ 同意 |
| P2-1 并行 fan-out | 0.5h | 0.8h | +0.3h | kanban 依赖模型是树非 DAG——fan-out 需要等上游 done 再并行，逻辑比预期复杂 |
| P2-2 中断接口 | 0.3h | 0.4h | +0.1h | block/unblock 需要和 kanban 状态机对齐 |
| **合计** | **6.8h** | **~7.6h** | **+0.8h** | |

### 4.2 但还不含这些...

| 隐性成本 | 估时 | 说明 |
|---------|:---:|------|
| 集成测试（所有 P0 一起跑一遍端到端） | 1.0h | 合约引擎 + checkpoint + 仪表盘联调 |
| 文档更新（PIPELINE.md 或新的 pipeline/README.md） | 0.5h | 6.8h 的工具不写文档 = 3 周后没人记得怎么用 |
| 跨组件联调（state.py → pipeline_state.db → kanban → cron） | 0.5h | 每个集成点都可能有意料之外的阻抗 |
| **隐性合计** | **~2.0h** | |

**真实全栈工期：7.6h + 2.0h = ~9.6h ≈ 2 个工作日。**

### 4.3 诚实结论

Architect 的 6.8h 是「理想情况写代码的时间」。加上集成、调试、文档后，**真实世界需要 ~10h**。这不是说 Architect 低估了——这是正常的「理论→实践」膨胀系数（~1.4x），在软件工程中属于健康范围。

**但有一个风险**：如果 P0-2 的 `pipeline_state.db` 和 InfoManager 的现有 DB schema 不兼容，或者 close.sh 根本不存在导致需要从零写闭环逻辑——工时会再膨胀 1-2h。

---

## 5. 代码改造范围——哪些文件需要动？

### 5.1 新增文件

```
pipeline/
├── contracts/
│   └── devPPL.jsonl          (~15 lines) — 5-step contract definition
├── state.py                  (~120 lines) — 合约校验引擎
├── checkpoint.py             (~80 lines) — SQLite WAL wrapper
├── router.py                 (~80 lines) — 条件路由(YAML→decision)
├── dashboard.py              (~50 lines) — CLI 面板
├── fanout.py                 (~40 lines) — 并行 dispatch
├── interrupt.py              (~30 lines) — block/unblock handler
└── README.md                 (~50 lines) — 使用文档

config/
└── pipeline-routes.yaml      (~30 lines) — P1-1 路由规则

tests/
└── test_pipeline.py          (~200 lines) — P0-1 + P0-2 集成测试
```

**总计：~700 行新代码，9 个新文件。**

### 5.2 修改现有文件

| 文件 | 改动 | 行数 | 风险 |
|------|------|:---:|:---:|
| `scripts/lib/kanban_helpers.py` | 新增 `get_task_state()` / `get_task_artifacts()` | ~15 | 低——纯新增函数，不改现有 API |
| `scripts/lib/config_loader.py` | 新增 `load_pipeline_config()` | ~15 | 低——沿用现有 YAML loading 模式 |
| `GLOBAL_ACTION_ITEMS.md` | P0-19 状态更新 | ~3 | 无 |
| `docs/analysis-pipeline-scripting-feasibility.md` | Phase 1 实施记录 | ~20 | 无 |

**总计：~53 行修改，4 个文件。**

### 5.3 不改的文件（确认 Architect 的判断）

- ❌ **不改 Hermes 引擎层**——pipeline 在脚本层实现，不侵入 `prompt_builder.py` 或 kanban dispatcher
- ❌ **不改 kanban 状态机**——复用现有 `todo→running→done` 流程
- ❌ **不引入新依赖**——Python stdlib + sqlite3 + json + yaml（已安装 PyYAML）
- ❌ **不替代 kanban**——脚本只读写 kanban，不替代 dispatcher

---

## 6. 对 Architect 反模式的评估

### 6.1 同意 3 个反模式

| 反模式 | Architect 判断 | Engineer 确认 | 补充 |
|--------|:---:|:---:|------|
| 全节点 JSON Schema | ❌ 不可行——Agent 输出是 NL | ✅ 同意 | JSON Schema 强制结构化输出在 LLM agent 场景下是过度约束。但 `produces` / `requires` 的产物路径可以用正则/glob 校验——这不需要 schema |
| 钻石拓扑 fan-out→fan-in | ❌ kanban 依赖模型是树非 DAG | ✅ 同意 | fan-out 后 fan-in 需要等所有子任务 done。kanban 的 `parents` 字段原生支持——但只能一次性设置，不支持运行时动态添加。如果 fan-out 后发现新依赖，无法加回 |
| DB 级事务保证步骤原子性 | ❌ 步骤跨 agent 会话，无法长持锁 | ✅ 同意 | SQLite 的单 writer 模式 + cron 多进程 = 不可能长持锁。checkpoint 用「步骤状态 + 产物清单」做 soft 保证，不是 hard 事务 |

### 6.2 新增反模式 4：close.sh 的幽灵依赖

**问题**：如果 close.sh 确实存在于 OC profile home 而不是 devPPL repo，P0-2 checkpoint 依赖的 `pipeline_state.db` 路径可能需要跨 profile 协调。更糟：如果 close.sh 不存在（GAI 和实际不符），P0 管线就缺了闭环的最后一步。

**建议**：P0 执行前先做一次 5 分钟的「管线健康检查」——确认 close.sh 位置、pipeline_state.db 状态（如果存在）、kanban helpers 可用性。

---

## 7. 最小可行版本：只做一件事，做哪个？

### 7.1 矩阵分析

| 候选 | 独立价值 | 依赖 | 风险 | 工作量 |
|------|:---:|------|:---:|:---:|
| P0-1 步骤合约引擎 | 高——Frank 最痛的就是「不敢信任管线」 | P0-2（轻依赖） | 中——校验放入口但无 checkpoint 数据，只能做弱校验 | 2.5h |
| P0-2 checkpoint | 中——解决「出问题不重头来」 | 无 | 低——SQLite WAL 是成熟技术，路径隔离是已知坑 | 1.0h |
| P0-3 可视化面板 | 低——产品说 P0-1 优先于可视化 | P0-1+P0-2（重依赖） | 低——CLI 输出无失败路径 | 1.5h |

### 7.2 推荐：先做 P0-2 checkpoint

**理由**：

1. **零依赖**——checkpoint 可以独立于合约引擎运作。写完就能记录步骤状态。
2. **解除 P0-1 的耦合**——state.py 的入口校验需要知道「上一步产出了什么」→ checkpoint 提供答案
3. **cost of delay**：没有 checkpoint，P0-1 的合约校验只能做「文件存在性」而不能做「产物来源追踪」，弱校验 + 无断点恢复 = 返工风险
4. **工期最短**：1.0h，今天就能交付

### 7.3 执行顺序（修正版）

```
Step 1: P0-2 checkpoint    [1.0h] — 零依赖，今天交付
Step 2: P0-1 步骤合约引擎   [2.5h] — 依赖 checkpoint 数据
Step 3: P0-3 CLI dashboard  [0.5h] — 依赖 P0-1+P0-2 数据就绪
Step 4: P1-1 条件路由       [1.2h] — 独立，可并行
Step 5: P2-1/2 并行+中断    [1.2h] — 低优先级
```

总工期：1.0 + 2.5 + 0.5 + 1.2 + 1.2 = 6.4h「理想代码时间」= **~8.5h 含集成调试**。

---

## 8. 一个架构师没提到的坑

### 8.1 kanban comment 作为状态变更通知 channel 的可靠性

当前的 QA 工作流用 kanban comment 中的 `[REJECTED]` / `[APPEAL]` 等前缀做状态机——这是 `kanban_helpers.py` 验证过的模式。但如果 P0-1 的 state.py 也依赖「读 kanban comment 获取步骤状态」，就会有两个风险：

1. **并发问题**：autopilot cron 和 OC 同时写 comment → 后写的覆盖？还是追加？kanban comment 模型是 append-only，但读状态是「扫到最后一条匹配的」
2. **格式漂移**：如果某个 agent 写了不符合预期的 comment 格式，状态解析会失败

**建议**：state.py 不依赖 kanban comment 做状态判定——只依赖 `pipeline_state.db`。kanban comment 作为人类可读的附注，不是 machine-readable 的状态源。这和 Architect 的「校验放脚本层非 LLM」原则一致。

### 8.2 pipeline_state.db 的 schema migration

当未来需要新增字段（如 `retry_count` → `retry_count + retry_reason`）时，SQLite 的 ALTER TABLE 能力有限。需要在 checkpoint.py 中加入简单的 migration 机制：

```python
# 伪代码——5 行就能实现
PRAGMA user_version;  -- 读当前 schema version
if user_version < 2:
    ALTER TABLE pipeline_steps ADD COLUMN retry_reason TEXT;
    PRAGMA user_version = 2;
```

这个 migration 机制在第一版可以不实现（YAGNI），但如果 pipeline 要长期维护，建议在 schema 中预留 `user_version`。

---

## 9. 总结

### 同意 Product + Architect 的核心判断

> 「Frank 最大痛点是不敢信任管线——正确性依赖 OC 记忆而非架构保证」— Product
> 「JSONL 合约 + state.py 确定性校验 + checkpoint + YAML 路由——不换引擎」— Architect

**完全同意。方向正确，方案务实。**

### 关键修正

| 项目 | Architect | Engineer | 原因 |
|------|:---:|:---:|------|
| 全栈工期 | 6.8h | ~9.6h (含集成) | 加了集成测试、文档、跨组件联调 |
| P0-2 工期 | 0.8h | 1.0h | WAL busy_timeout + `~` 路径 fix |
| P0-3 工期 | 2.0h | 1.5h | CLI 原型先行，不满 2.0h |
| 执行顺序 | 先 P0-1 | **先 P0-2 checkpoint** | checkpoint 是 P0-1 的数据依赖 |
| close.sh | 假设存在 | **需先验证** | GAI 记录和实际文件系统可能不一致 |

### 一句话

> Architect 的 6.8h 方案在方向上完全正确——JSONL 合约 + SQLite checkpoint + YAML 路由，零新依赖，不换引擎。但从代码到交付还有 ~1.4x 的集成膨胀系数，真实全栈 ~10h。建议先做 P0-2 checkpoint（1h，零依赖），再以 checkpoint 为数据基座推进合约引擎。以及我需要在动手前先确认 close.sh 到底在哪——GAI 说 done 但 repo 里没有。

---

> 我是团队的双手。蓝图有了，给我 checkpoint 先。两天后管线就能跑起来。
