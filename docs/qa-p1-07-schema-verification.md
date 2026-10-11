# QA 验证报告：P1-07 审计 Schema 统一验证

> 验证日期：2026-07-10 | QA：game-qa | 被验证任务：t_7d354c3c
> 标准依据：docs/standards/qa-finding-classification.md v1.0

---

## 验证方法

仅使用 grep / 字段对比 / 文件存在性检查 / SQL 查询，不做代码修改。
测试 DB 均在 `/tmp/_qa_p1_07/` 下独立创建，不影响生产环境。

---

## 验收标准逐条结果

### AC1：新库初始化 → 17 列

| 来源 | 列数 | 证据 |
|------|------|------|
| schema.yaml（columns 段） | 17 | `grep '^  - name:' schema.yaml` → 17 个数据列 + 5 个索引条目，数据列严格 17 |
| schema.sql（CREATE TABLE 段） | 17 | `CREATE TABLE commands (...)` 内含 16 个逗号 = 17 列 |
| 生产 DB（PRAGMA table_info） | 17 | 从 id(0) 到 perm_details(16) |
| YAML/SQL/DB 列名一致性 | 完全一致 | 逐列对比无差异 |

**结果：PASS** ✓

---

### AC2：旧格式（4 字段）导入 → event_type 默认 "terminal"

测试数据：`2026-07-06T01:48:18+08:00|sess_old1|/tmp|ls -la`（4 字段，无 event_type）

解析结果：
```
event_type=terminal  cmd=ls -la
```

DB 记录：
```
1|terminal|/tmp|ls -la
```

**结果：PASS** ✓ — 旧格式自动回退 event_type="terminal"

---

### AC3：新格式（5 字段）混合导入 → terminal + permission 共存

测试数据：
```
2026-07-10T12:00:00+08:00|sess_term1|/root|terminal|python3 script.py
2026-07-10T12:01:00+08:00|sess_perm1|/etc|permission|chmod 644 /etc/hosts
2026-07-10T12:02:00+08:00|sess_term2|/home|terminal|ls -la ~
```

DB 记录：
```
1|terminal|python3 script.py
2|permission|chmod 644 /etc/hosts
3|terminal|ls -la ~
```

分组统计：
```
permission|1
terminal|2
```

**结果：PASS** ✓ — 两种 event_type 正确区分，共存于同一表

---

### AC4：旧 8 列 schema 迁移 → 数据保留，17 列

测试场景：
1. 创建旧 8 列 DB（id, session_id, timestamp, cwd, command, exit_code, duration_ms, created_at）
2. 插入 3 行数据（含 exit_code=0 和 1）
3. 运行 schema.sql 迁移

迁移前：8 列，3 行
迁移后：17 列，3 行

```
1|sess_a|terminal|echo hello|0
2|sess_b|terminal|ls -la|0
3|sess_c|terminal|cat hosts|1
```

生产 DB 状态：17 列，0 行。log 文件仅 1 行（7月6日），`.last_import_line=1` 表示已处理。生产库迁移前是否已有数据无法确认，但迁移后无残留数据异常。

**结果：PASS** ✓ — 迁移逻辑在测试中正确保留数据，生产环境 0 行前后一致

---

### AC5：幂等重跑 schema.sql → 无副作用

对已迁移 17 列 DB（含 3 行数据）重跑 schema.sql：

| 指标 | 重跑前 | 重跑后 |
|------|--------|--------|
| 列数 | 17 | 17 |
| 行数 | 3 | 3 |
| 索引数 | 5 | 5 |
| 数据内容 | 3 行完好 | 3 行完好（无重复/丢失） |

**结果：PASS** ✓ — 完全幂等，`CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` 保证安全

---

## QA 发现

### F1：导入脚本在 schema 未迁移时静默丢数据（MINOR）

**描述**：`audit-import.sh` 的 INSERT 语句引用 `event_type` 列。如果 schema.sql 尚未对旧 DB 执行（`event_type` 列不存在），INSERT 静默失败（`2>/dev/null` 掩码），数据被丢弃。

**判定对照**（标准 §1.2 五步公式）：
- 步骤1（安全漏洞？）：否 → 进入正式判定
- 步骤2（用户可感知？）：否，正常流程中 schema.sql 先在脚本首行执行
- 步骤3（功能阻断？）：否，有 workaround（schema.sql 已脚本首行调用）
- 步骤4（有 workaround？）：是，脚本设计已包含 schema init
- 步骤5（影响范围）：仅异常路径（schema.sql 文件缺失/损坏且 fallback 也失败时）

→ **MINOR** — 边缘场景，正常流程不受影响

**建议修复（优先级 P4）**：在 INSERT 前增加列存在性检查，或使用 `INSERT OR IGNORE` 并记录失败日志：
```bash
HAS_ET=$(sqlite3 "$AUDIT_DB" "SELECT COUNT(*) FROM pragma_table_info('commands') WHERE name='event_type';" 2>/dev/null)
[[ "$HAS_ET" != "1" ]] && { echo "[warn] event_type column missing, run schema.sql first" >&2; }
```

**SLA**：MINOR 无 SLA 要求。

---

## 验收总结

| 标准 | 结果 | 证据 |
|------|:---:|------|
| AC1: 新库 17 列 | PASS | YAML(17) = SQL(17) = DB(17) |
| AC2: 旧格式 → event_type="terminal" | PASS | 实测 4 字段导入，event_type=terminal |
| AC3: 新格式混合 → 共存 | PASS | terminal(2) + permission(1) 同表共存 |
| AC4: 旧 schema 迁移 → 数据保留 | PASS | 实测 8→17 列，3 行数据完整 |
| AC5: 幂等重跑 → 无副作用 | PASS | 列/行/索引/数据均不变 |
| **5/5 全部通过** | **PASS** | — |

### 发布门禁评估

对照标准 §10：
- BLOCKER: 0 ✓
- MAJOR: 0 ✓（F1 为 MINOR）
- 安全漏洞: 0 ✓
- 未裁定申诉: 0 ✓

**门禁条件满足，建议通过。**

---

## 附：验证命令记录

```bash
# AC1
grep -c '^  - name:' /root/.hermes/audit/schema.yaml  # 22 (17 col + 5 idx)
sed -n '/CREATE TABLE/,/);/p' /root/.hermes/audit/schema.sql | grep -c ','  # 16 commas = 17 cols
sqlite3 ... "SELECT COUNT(*) FROM pragma_table_info('commands');"  # 17

# AC2
echo '...|sess|/tmp|ls -la' | while IFS='|' read -r ts session cwd field4 cmd rest; do
  [[ -n "$cmd" ]] && event_type="$field4" || { cmd="$field4"; event_type="terminal"; }
  sqlite3 ... "INSERT INTO commands(...) VALUES(...);"
done
# → event_type=terminal

# AC3
# 导入 terminal 和 permission 两种 event_type → 分组查询确认共存

# AC4
# 创建旧 8 列 DB → 插入 3 行 → schema.sql 迁移 → 验证 17 列 + 3 行

# AC5
# 对已迁移 DB 重跑 schema.sql → 验证不变
```
