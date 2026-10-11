# RT-B R3: 工程师发言 — AUD-010 审计数据格式

> 角色：寇豆码（Game Engine Programmer）
> 日期：2026-07-11
> 类型：Brainstorming — 聚焦实现难度、具体代码改动量、工单落地路径

---

## 议题：产品/架构方案的可实现性评估

产品方案（R1）：维持 SQLite，加 3 列 + FTS5。架构裁定（R2）：方向正确，附技术条件 + 发现 1 个 MAJOR Bug。

我的发言聚焦 5 个问题：字段实现难度、Bug 根因与修复、历史回填策略、实施顺序、替代方案评估。

---

## 1. 每个字段的实现难度与工时

### 1.1 duration_ms — 低成本，但依赖 tool_call_id 已填充

**实现路径**：修改 `audit_transcribe.py`。当前代码已经同时查询了 assistant message 和 tool response（JOIN on `t.id = a.id + 1`），两个 timestamp 都在手边：

```python
# 当前已有（第53-63行）：
# a.timestamp  ← assistant message 的发送时刻
# t.content    ← tool response，隐式包含接收时刻（但未显式取 t.timestamp）

# 需要改动：显式 SELECT t.timestamp，计算差值
duration_ms = int((t.timestamp - a.timestamp) * 1000)
```

**复杂度**：在 audit_transcribe.py 加 2 行代码。`audit-cron.sh` 不参与（它只看 assistant message，没有 tool response 时间戳）。

**工时**：0.03d（1 行 SQL 改动 + 1 行计算 + 验证）

**历史回填难度**：中等。当前 4,388 条记录中 `tool_call_id` 全为 NULL（实测确认）。必须先回填 tool_call_id，才能计算 duration_ms。见 §3。

### 1.2 task_id — 实现简单，回填需跨库 JOIN

**实现路径**：在 `audit_transcribe.py` 的 INSERT 语句中加一个 LEFT JOIN：

```python
# 在 INSERT 前，跨库查询映射
task_row = kanban.execute(
    "SELECT id FROM tasks WHERE session_id=? LIMIT 1", (session_id,)
).fetchone()
task_id = task_row[0] if task_row else None
```

**风险点**：kanban.db 可能不在预期路径。建议用环境变量 `$HERMES_KANBAN_DB` 定位，fallback 到 `/root/.hermes/kanban.db`。

**复杂度**：低。一个跨库 ATTACH + 一个 LEFT JOIN，或 Python 层做一次查询。

**工时**：0.04d

**历史回填难度**：简单。跑一次性的 UPDATE 即可：
```sql
ATTACH '/root/.hermes/kanban.db' AS kanban;
UPDATE commands SET task_id = (
    SELECT kanban.tasks.id FROM kanban.tasks
    WHERE kanban.tasks.session_id = commands.session_id
);
```
问题：只有 29/302 个 session 有映射（9.6%），其余保持 NULL。这是预期行为。

### 1.3 agent_profile — 零成本

**实现路径**：DEFAULT 'orchestrator'，INSERT 时不需要改任何代码。多 profile 支持时，cron 脚本加 `--profile orchestrator` 参数即可。

```sql
ALTER TABLE commands ADD COLUMN agent_profile TEXT DEFAULT 'orchestrator';
```

**复杂度**：零（对单 profile 场景）。schema 加一列 + 默认值。

**工时**：0.01d（纯 DDL）

**历史回填难度**：零。DEFAULT 值自动覆盖所有旧行（SQLite 的 ADD COLUMN DEFAULT 语义）。无需任何 UPDATE。

### 1.4 cwd — schema.sql 遗漏 + 采集改动

**当前状态**：schema.yaml 有定义，schema.sql 的 CREATE TABLE 有定义，但迁移块（ALTER TABLE）**缺失此列**，导致实际 DB 中不存在 cwd 列（实测：`PRAGMA table_info` 无 cwd）。

**实现路径**：
1. schema.sql 迁移块补 `ALTER TABLE ADD COLUMN cwd TEXT`
2. `audit_transcribe.py` 中从 tool_calls JSON 提取 `workdir` 参数，写入 cwd

**复杂度**：中等。需要解析 tool_calls 的 arguments.home 或 arguments.workdir（取决于 Hermes 版本）。

**工时**：0.06d

**历史回填难度**：不可回填。历史数据中没有 workdir 信息。cwd 只能从此刻开始采集。

### 1.5 FTS5 全文索引 — 无风险，标准操作

**实现路径**：架构师的触发器方案完全正确。

```sql
CREATE VIRTUAL TABLE commands_fts USING fts5(
    command, output_preview,
    content=commands, content_rowid=id
);
-- + 3 个触发器（INSERT/UPDATE/DELETE）
```

**复杂度**：低。4 条 DDL 语句。

**工时**：0.04d（含初始重建）

**历史回填难度**：零。创建 FTS 虚拟表后，执行一次 `INSERT INTO commands_fts(commands_fts) VALUES('rebuild')` 即可全量索引。4,388 条数据耗时 < 1 秒。

### 1.6 汇总

| 字段 | 实现难度 | 回填难度 | 工时 | 依赖 |
|------|:---:|:---:|------|------|
| `agent_profile` | 零 | 零 | 0.01d | 无 |
| `duration_ms` | 低 | 中 | 0.03d | tool_call_id 先回填 |
| `task_id` | 低 | 低 | 0.04d | kanban.db 路径 |
| `cwd` | 中 | 不可能 | 0.06d | tool_calls JSON 中有 workdir |
| FTS5 索引 | 低 | 零 | 0.04d | 无 |
| schema.sql 修复 | 低 | — | 0.03d | 无 |

**总计**：约 0.21d（架构师估的 0.35d 偏保守，实际可更紧）。

---

## 2. schema.sql 迁移 Bug — 根因分析与修复

### 2.1 根因（与架构师的发现略有不同）

架构师诊断为「sqlite3 批处理在 message_id ALTER TABLE 失败后停止」。实测证据不完全支持这个结论：

- 当前 DB 中 event_type、truncated、tool_call_id、以及全部 5 个 permission 列**都存在**
- 这意味着 sqlite3 批处理**没有因 message_id 的 duplicate column 错误而中止**（sqlite3 默认不 bail on error）

**真正的根因**：schema.sql 的迁移块（ALTER TABLE 部分）是**不完整的**。以下 3 个在 CREATE TABLE 中定义但**没有对应 ALTER TABLE** 的列：

| 列 | CREATE TABLE 中有？ | ALTER TABLE 迁移有？ | 实际 DB 中有？ |
|---|:---:|:---:|:---:|
| `cwd` | ✅ 第 13 行 | ❌ | ❌ |
| `duration_ms` | ✅ 第 16 行 | ❌ | ❌ |
| `created_at` | ✅ 第 27 行 | ❌ | ❌ |
| `event_type` | ✅ 第 10 行 | ✅ 第 36 行 | ✅ |
| `tool_call_id` | ✅ 第 19 行 | ✅ 第 43 行 | ✅（但值全 NULL） |

**结论**：这不是「批处理中止」Bug，而是「迁移覆盖不完整」Bug。修复很简单——在迁移块补 3 条 ALTER TABLE。

### 2.2 推荐修复方案

与架构师的「每个 ALTER TABLE 独立执行」方案不同，我推荐**直接在 schema.sql 的迁移块中补上缺失的 ALTER TABLE**，保持管道批处理方式不变（因为 sqlite3 默认不 bail，管道方式已经够用）：

```sql
-- 在迁移块末尾追加：
ALTER TABLE commands ADD COLUMN cwd TEXT;
ALTER TABLE commands ADD COLUMN duration_ms INTEGER;
ALTER TABLE commands ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP;
```

然后新增（本次任务需要）：
```sql
ALTER TABLE commands ADD COLUMN agent_profile TEXT DEFAULT 'orchestrator';
ALTER TABLE commands ADD COLUMN task_id TEXT;
```

**反方论证（架构师方案）**：独立执行每个 ALTER TABLE 虽然更健壮（单条失败不影响后续），但引入了 shell 循环，且每条 ALTER TABLE 单独打开/关闭数据库连接。在当前规模下（10 条 ALTER TABLE 级别），管道批处理足够。

**我的立场**：两者都可以。但不建议为此引入额外的 shell 复杂度和重复连接开销。

---

## 3. 增量列的历史数据回填策略

### 3.1 可以回填的

| 列 | 回填方法 | 耗时 |
|---|---------|------|
| `agent_profile` | 不需要。DEFAULT 'orchestrator' 自动覆盖所有旧行。 | 0 |
| `task_id` | 一次性 UPDATE FROM kanban.db（跨库 JOIN）。4,388 行，绝大部分保持 NULL。 | < 1 秒 |
| FTS5 索引 | `INSERT INTO commands_fts(commands_fts) VALUES('rebuild')` | < 1 秒 |
| `duration_ms` | 需先回填 `tool_call_id`，再通过 state.db 计算时间差。4,388 行一次性 UPDATE。 | ~2 秒 |

### 3.2 duration_ms 回填的关键难点：tool_call_id 当前全 NULL

实测：`SELECT COUNT(*) FROM commands WHERE tool_call_id IS NOT NULL` → **0**。

这意味着必须**先回填 tool_call_id，才能计算 duration_ms**。

tool_call_id 的回填方法：
```sql
-- audit_transcribe.py 已有 JOIN messages a + t ON t.id = a.id + 1
-- 但从未写入 tool_call_id。需要一次性回填：
ATTACH '/root/.hermes/profiles/orchestrator/state.db' AS state;
UPDATE commands SET tool_call_id = (
    SELECT json_extract(state.messages.tool_calls, '$[0].id')
    FROM state.messages
    JOIN state.messages t ON t.id = state.messages.id + 1 AND t.role = 'tool'
    WHERE state.messages.id = commands.message_id - 1
) WHERE tool_call_id IS NULL;
```

⚠️ 注意：commands 表中存的是 tool message 的 id（`ROW["t_id"]`），而 tool_call_id 在 assistant message 的 tool_calls JSON 中。回填时需要 `message_id - 1` 来定位 assistant message。

复杂度上升一级。建议在 `audit_transcribe.py --full` 重跑时自然填充（因为 transcribe 已经拿到了两边的数据），而不是单独写回填 SQL。

### 3.3 不能回填的

| 列 | 原因 |
|---|------|
| `cwd` | 历史 tool_calls 中 workdir 信息不可追溯（旧版 Hermes 不记录 workdir）。 |

---

## 4. 实施顺序建议（与架构师对齐，微调优先级）

```
Phase 0（阻塞修复，~0.03d）
  ├─ schema.sql 补 cwd, duration_ms, created_at 的 ALTER TABLE
  ├─ schema.sql 补 agent_profile, task_id 的 ALTER TABLE
  └─ 验证：sqlite3 < schema.sql 在现有 DB 上无错误执行

Phase 1（核心列 + FTS，~0.08d）
  ├─ agent_profile（ALTER TABLE + DEFAULT，零采集改动）
  ├─ FTS5 虚拟表 + 3 个触发器 + rebuild
  └─ cwd（ALTER TABLE + audit_transcribe.py 采集 workdir）

Phase 2（关联列，~0.07d）
  ├─ task_id（ALTER TABLE + audit_transcribe.py 跨库查询 + 历史回填 UPDATE）
  └─ duration_ms（ALTER TABLE + audit_transcribe.py 计算 + 先回填 tool_call_id）

Phase 3（验证，~0.03d）
  └─ 场景覆盖率回归（目标 12/14）
```

**顺序理由**：
- Phase 0 先修 Bug，否则 Phase 1/2 的列加不上
- Phase 1 放 agent_profile + FTS + cwd：不改采集逻辑的最先做，改采集逻辑的紧随
- Phase 2 放 task_id + duration_ms：都依赖采集脚本改动，且 duration_ms 依赖 tool_call_id 先解决

---

## 5. 替代方案评估

架构师在 R2 已否定了物化视图（数据量 < 10 万不值得），我补充评估一个更"简单"的替代方案：

### 替代方案：不修改 DB，在查询时动态计算

```
不改 schema，不改采集脚本。agent 查询时做个 wrapper：
- duration_ms：JOIN state.db ON tool_call_id，查询时计算
- task_id：JOIN kanban.db ON session_id，查询时计算
- 全文搜索：用 LIKE '%pattern%' 代替 FTS5
```

**优势**：
- 零 schema 变动
- 零采集脚本改动
- 零迁移风险

**劣势（致命）**：
1. Agent 每次查询需要 3 路 JOIN 跨 3 个数据库（audit + state + kanban），查询复杂度暴涨
2. LIKE 全表扫描在 4,388 条时 OK，但日增 200-500 条，半年后就慢了
3. tool_call_id → duration_ms 需要回溯到 state.db，但 state.db 的 messages 表是否完整保留不确定（可能被清理）
4. 产品 S11（合规追溯）需要 task_id 快速过滤，跨库 JOIN 每次写 3 行 SQL 而非 1 行
5. **与产品的"agent 友好"目标背道而驰**——agent 要的是简单查询，不是多库 JOIN

**工程师立场：不接受此替代方案。** 增量列方案的总工时 ~0.21d，省这点时间不值得牺牲 agent 查询体验。

---

## 6. 架构师发现的额外风险：audit-cron.sh 和 audit_transcribe.py 是两套独立系统

这是一个架构层面的问题，虽然不在本次任务范围内，但需要标记：

- `audit-cron.sh`：纯 bash，只插入 command，**不填** exit_code/output_preview
- `audit_transcribe.py`：Python，做 JOIN 后填 exit_code/output_preview，且使用 `INSERT OR IGNORE` 来跳过已有行

两者跑的同一张表，但字段集合不同。如果 audit-cron.sh 先跑（插入 command 行），audit_transcribe.py 后跑（INSERT OR IGNORE 跳过），那么**由 audit-cron.sh 插入的行永远得不到 exit_code 和 output_preview**。

当前 `audit_transcribe.py` 用的是 `INSERT OR IGNORE`（第 117 行），不是 UPSERT。这意味着 cron.sh 先入的行就成了"裸行"（只有 command，没有 exit_code）。

**建议**：要么统一到一套 pipeline，要么 audit_transcribe.py 改用 UPSERT（`INSERT ... ON CONFLICT(message_id) DO UPDATE SET ...`）来补填缺失字段。这是架构层面的决策，不在本次窗口讨论。

---

## 7. 总结

| 决策 | 工程师裁定 |
|------|-----------|
| 产品/架构方向 | ✅ 完全同意。增量列方案是最小可行路径 |
| schema.sql Bug | 根因是「迁移覆盖不完整」（缺 cwd/duration_ms/created_at 的 ALTER TABLE），非批处理中止 |
| 修复方式 | 补 3 条 ALTER TABLE，保持管道批处理不变 |
| 替代方案 | ❌ 驳回（跨库 JOIN 查询方案破坏 agent 友好性） |
| 工时估算 | 0.21d（比架构师的 0.35d 更紧，因 agent_profile 零成本拉低了均值） |
| 实施顺序 | Phase 0（修 Bug）→ Phase 1（不依赖采集的列）→ Phase 2（依赖采集的列）→ Phase 3（验证） |
| 额外发现 | audit-cron.sh 与 audit_transcribe.py 两套系统有数据竞争，需架构层面决策 |

---

> **工程师发言完毕。移交产品（许清楚）和架构师（高见远）做最终确认，QA（罗严谨）开始写回归测试用例。**
