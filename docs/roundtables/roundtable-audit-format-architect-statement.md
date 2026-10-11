# RT-B R2: 架构师发言 — AUD-010 审计数据格式

> 角色：高见远（架构师）
> 日期：2026-07-11
> 类型：Brainstorming — 聚焦技术可行性、架构影响、数据管线兼容性

---

## 议题：产品增量方案的技术可行性评估

产品方案：维持 SQLite 扁平表，加 3 列（duration_ms / task_id / agent_profile）+ FTS5 全文索引。

---

## 1. 总体判断：方案可行，但有 3 项技术前提 + 1 个迁移 Bug 需先修

产品方向正确。增量成本低、不动核心数据管线、不影响现有 cron。但三个字段的「数据来源」各有关键技术约束，不能只 ALTER TABLE 了事。

---

## 2. duration_ms — 可获取，但语义是「往返延迟」非「纯 shell 执行时间」

### 2.1 数据来源验证

```
state.db messages 表实测数据流：

message 4 | role=assistant | tool_calls JSON | ts=1782049236.99908
  └─ call_id: "019eea688682..." → terminal("hermes kanban list ...")
message 5 | role=tool       | tool_call_id="019eea688682..." | ts=1782049237.00373
  └─ content: {"output": "...", "exit_code": 0, "error": null}

duration_ms = (1782049237.00373 - 1782049236.99908) × 1000 = 4.65ms
```

### 2.2 精确定位方法

```
方案 A（精确，推荐）：解析 assistant message 的 tool_calls JSON
  → 取出 call_id → JOIN tool result message ON tool_call_id
  → duration_ms = (tool_result.timestamp - assistant.timestamp) × 1000

方案 B（近似，简单）：取 assistant message 的下一条 tool message
  → duration_ms = (message[N+1].timestamp - message[N].timestamp) × 1000
  → 多 tool_call 时误差 = 前序 tool_call 的执行时间累积
```

**架构建议**：方案 A。单条 SQL 可完成（json_each + tool_call_id JOIN），性能在 4000 条规模下无压力。

### 2.3 语义澄清

这不是「shell 命令在 bash 中的实际 wall-clock 时间」，而是「Hermes 发起调用 → 收到结果」的往返延迟。包含：
- Hermes runtime 调度开销（~1-5ms）
- 进程 fork/exec
- 实际命令执行
- 输出捕获和 JSON 序列化

对于审计场景（识别慢命令、性能回归）**已经足够**。精度在毫秒级，能满足 S7 性能回归需求。

---

## 3. task_id — 可获取，但仅 29/302 个 session 有 kanban 关联

### 3.1 数据来源

```
kanban.db 中 tasks 表有 session_id 列（实测存在）：

$ sqlite3 kanban.db "SELECT id, session_id FROM tasks WHERE session_id IS NOT NULL LIMIT 3"
t_d0d6e744|20260708_015244_4e116b
t_6989978c|20260708_015244_4e116b
...

交叉验证通过：
$ ATTACH 'terminal_commands.db' AS audit;
  SELECT audit.commands.session_id, tasks.id
  FROM audit.commands JOIN tasks ON tasks.session_id = audit.commands.session_id
  LIMIT 3;
20260708_020029_b50034|t_bd9243fd   ← 映射成立
```

### 3.2 获取方式

```
Cron 采集脚本不需要改 session 表。直接在 queries 中做跨库 JOIN：

sqlite3 terminal_commands.db "
  ATTACH '/root/.hermes/kanban.db' AS kanban;
  SELECT c.*, kt.id as task_id
  FROM commands c
  LEFT JOIN kanban.tasks kt ON kt.session_id = c.session_id
"
```

### 3.3 覆盖率现实

| 指标 | 数值 |
|------|------|
| 有 kanban 关联的 session | 29 个 |
| 总 session 数 | 302 个 |
| 覆盖率 | 9.6% |

**这是预期行为，不是缺陷**。非 kanban 任务的 session（聊天、手动操作）本就不该有 task_id。S11 合规追溯只对「由 kanban task 触发的 session」有意义，覆盖了目标场景。

### 3.4 架构决策

- `task_id` 列应设为 **NULLABLE**（大部分行为 NULL）
- 采集时不做物化写入（跨库值随时变化），改为**查询时动态 JOIN** 或 cron 定期刷新
- 若未来需要物化：cron enrich 阶段做一次性的 task_id 回填

---

## 4. agent_profile — 当前全量数据源为单 profile，可直接常量赋值

### 4.1 数据来源分析

当前 `terminal_commands.db` 的唯一数据源是：

```
audit-cron.sh → state.db (orchestrator profile)
audit-import.sh → terminal_audit.log (orchestrator profile)
```

所有 4,388 条命令的 agent_profile = `orchestrator`。

### 4.2 当前方案

```
方案（最小可行）：
  ALTER TABLE ADD COLUMN agent_profile TEXT DEFAULT 'orchestrator';
```

### 4.3 多 profile 扩展路径

未来如果其他 profile（game-engine、game-architect 等）的 session 也要纳入审计：

```
方案 1（推荐）：每个 profile 的 audit-cron.sh 传 --profile 参数
  → INSERT 时写入各自的 agent_profile
  → 改动量：cron 脚本加 1 个参数 + SQL 加 1 个值

方案 2：从 session_id 推断（不推荐）
  → session_id 格式无 profile 信息（YYYYMMDD_HHMMSS_hex）
  → 不可靠
```

**架构建议**：当前用 DEFAULT 'orchestrator'，列设为 NOT NULL。多 profile 支持时改为参数化。

---

## 5. FTS5 全文索引 — 无性能风险，但需注意同步机制

### 5.1 性能评估

| 指标 | 评估 |
|------|------|
| SQLite FTS5 已启用 | ✅ `SELECT sqlite_compileoption_used('ENABLE_FTS5')` → 1 |
| 当前数据量 | 4,388 条，日增 200-500 条 |
| FTS INSERT 开销 | ~1-5ms/条（含 tokenizer + 索引写入） |
| FTS 查询开销 | 亚毫秒级（倒排索引） |
| 存储增量 | 约 50-100% 于索引文本（command + output_preview 中位数 100-500 字符） |
| 总存储预估 | 当前 ~2MB → 加 FTS 后 ~3-4MB |

**结论：零性能风险。** SQLite FTS5 就是为这种规模设计的。4K 条数据用不到外部搜索引擎。

### 5.2 推荐 FTS 配置

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS commands_fts USING fts5(
    command,
    output_preview,
    content=commands,
    content_rowid=id
);

-- 触发器保持 FTS 同步
CREATE TRIGGER commands_ai AFTER INSERT ON commands BEGIN
    INSERT INTO commands_fts(rowid, command, output_preview)
    VALUES (new.id, new.command, new.output_preview);
END;

CREATE TRIGGER commands_ad AFTER DELETE ON commands BEGIN
    INSERT INTO commands_fts(commands_fts, rowid, command, output_preview)
    VALUES ('delete', old.id, old.command, old.output_preview);
END;

CREATE TRIGGER commands_au AFTER UPDATE ON commands BEGIN
    INSERT INTO commands_fts(commands_fts, rowid, command, output_preview)
    VALUES ('delete', old.id, old.command, old.output_preview);
    INSERT INTO commands_fts(rowid, command, output_preview)
    VALUES (new.id, new.command, new.output_preview);
END;
```

---

## 6. 额外架构发现与建议

### 6.1 【MAJOR】schema.sql 迁移逻辑存在 Bug——阻塞所有增量列

**实测证据**：

```
$ sqlite3 terminal_commands.db < /root/.hermes/audit/schema.sql
Parse error near line 39: duplicate column name: message_id
```

**根因**：当前 DB 已有 `message_id` 列，schema.sql 的 `ALTER TABLE ADD COLUMN message_id` 失败。sqlite3 批处理在第一处错误就停止，导致后续所有 ALTER TABLE 全部未执行。

**影响**：schema.sql 定义的所有增量列（`event_type`, `truncated`, `tool_call_id`, `cwd`, `duration_ms`, 权限相关列）**实际上全未添加**。

**修复方案**：

```bash
# 将每个 ALTER TABLE 独立执行（而非管道批处理）
for stmt in \
    "ALTER TABLE commands ADD COLUMN event_type TEXT NOT NULL DEFAULT 'terminal'" \
    "ALTER TABLE commands ADD COLUMN truncated INTEGER DEFAULT 0" \
    "ALTER TABLE commands ADD COLUMN tool_call_id TEXT" \
    "ALTER TABLE commands ADD COLUMN cwd TEXT" \
    "ALTER TABLE commands ADD COLUMN duration_ms INTEGER" \
    "ALTER TABLE commands ADD COLUMN agent_profile TEXT DEFAULT 'orchestrator'" \
    "ALTER TABLE commands ADD COLUMN task_id TEXT" \
    ; do
    sqlite3 "$AUDIT_DB" "$stmt" 2>/dev/null
done
```

**优先级**：P0 — 此 Bug 导致所有增量方案无法落地。修复后才能谈加列。

### 6.2 建议：不需要保留 state.db 原始 JSON 副本

state.db 的 messages 表本身就是原始数据源。terminal_commands.db 是其物化子集。不需要额外保留 JSON 副本。

### 6.3 建议：不需要物化视图

4,388 条数据，SQL 查询 + 索引已足够。物化视图在数据量 < 10万 时没有收益。

### 6.4 产品字段名与 task body 的差异

| 产品发言（R1） | task body（本任务） | 建议 |
|---------------|---------------------|------|
| `agent_profile` | `cwd` | 两者都要。cwd 已在 schema.sql 中，agent_profile 需新增 |
| `task_id` | `task_id` | 一致 |
| `duration_ms` | `duration` | 统一用 `duration_ms`（INTEGER，毫秒） |

产品发言最终版确认的是 `agent_profile` 而非 `cwd`，但 task body 单独问了 `cwd`。架构建议：两列都加——`cwd` 来自 sessions 表或 tool_call workdir 参数（已有 schema.sql 支持），`agent_profile` 新增。

---

## 7. 最终架构裁定

### 7.1 同意产品方向，附带技术条件

| 产品决策 | 架构裁定 | 条件 |
|---------|---------|------|
| 维持 SQLite | ✅ 同意 | — |
| 加 `duration_ms` | ✅ 同意 | 用方案 A（tool_call_id 精确匹配），标注语义为「往返延迟」 |
| 加 `task_id` | ✅ 同意 | NULLABLE；查询时跨库 JOIN kanban.db；覆盖率 9.6% 是预期行为 |
| 加 `agent_profile` | ✅ 同意 | DEFAULT 'orchestrator'；多 profile 时参数化 |
| 加 `cwd` | ✅ 建议追加 | schema.sql 已有列定义，补写采集逻辑 |
| 加 FTS5 全文索引 | ✅ 同意 | 用 content-sync 虚拟表 + 触发器同步 |
| 不换图数据库/embedding | ✅ 同意 | 4K 数据量不 justify |

### 7.2 实施路径（建议顺序）

```
Phase 0（阻塞修复）：修 schema.sql 迁移 Bug → 所有增量列落地
Phase 1（P0 列 + FTS）：duration_ms + FTS5 全文索引 + cwd
Phase 2（P1 列 + 采集逻辑）：task_id + agent_profile，改 cron 脚本补字段值
Phase 3（验证）：场景覆盖率回归测试（目标 12/14）
```

### 7.3 改动量估算

| 组件 | 改动 | 工时 |
|------|------|------|
| schema.sql | 修复迁移逻辑 + 加 agent_profile/task_id 列 | 0.05d |
| audit-cron.sh | 加 duration_ms 计算 + agent_profile 常量 + cwd 采集 | 0.1d |
| audit-import.sh | 同步列变化 | 0.05d |
| FTS5 触发器 | 新增 DDL | 0.05d |
| 测试验证 | 场景回归 + 迁移回退测试 | 0.1d |
| **总计** | | **~0.35 人天** |

---

> **架构师发言完毕。移交研发（寇豆码）确认采集脚本具体改动，QA（罗严谨）制定回归用例。**
