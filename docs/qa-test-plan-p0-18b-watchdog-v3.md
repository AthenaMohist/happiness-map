# QA Test Plan: Watchdog v3.0

> QA: Frank 团队游戏QA | 日期: 2026-07-10 | 版本: v1.0
> 对应架构: docs/arch-p0-18b-watchdog-v3.md (v1.1)
> 对应PRD: docs/prd-p0-18b-watchdog-v3.md (v3.0)
> 依据标准: docs/standards/qa-finding-classification.md (v1.0)

---

## 目录

1. [测试策略概要](#1-测试策略概要)
2. [文档审查发现](#2-文档审查发现)
3. [TS1: kanban_collector.py 单元测试](#3-ts1-kanban_collectorpy-单元测试)
4. [TS2: OC Session State File 生命周期测试](#4-ts2-oc-session-state-file-生命周期测试)
5. [TS3: 旧文件清理验证](#5-ts3-旧文件清理验证)
6. [TS4: Layer1+Layer2 集成测试](#6-ts4-layer1layer2-集成测试)
7. [TS5: 异常与边缘场景测试](#7-ts5-异常与边缘场景测试)
8. [风险与定级清单](#8-风险与定级清单)
9. [发布门禁检查表](#9-发布门禁检查表)
10. [附录: 测试数据准备脚本](#10-附录-测试数据准备脚本)

---

## 1. 测试策略概要

### 1.1 测试金字塔

```
         ╱  TS4 集成 ╲           Layer1 + Layer2 + Feishu 端到端
        ╱──────────────╲
       ╱   TS3 清理     ╲         旧文件确认 → 无回归
      ╱──────────────────╲
     ╱    TS2 Session      ╲       .oc_session.json 生命周期
    ╱────────────────────────╲
   ╱     TS1 Collector 单元    ╲     kanban_collector.py 逐函数
  ╱──────────────────────────────╲
```

### 1.2 测试层次

| 层次 | 名称 | 用例数 | 执行方式 | 环境 |
|------|------|:---:|---------|------|
| TS1 | Collector 单元测试 | 15 | pytest / subprocess | 隔离 (mock DB + session file) |
| TS2 | Session File 生命周期 | 8 | subprocess + 文件断言 | orchestrator scripts 目录 |
| TS3 | 旧文件清理验证 | 5 | 文件存在性 + 代码审查 | 文件系统 |
| TS4 | Layer1+Layer2 集成 | 5 | cron job 创建 + stdout 验证 | orchestrator profile |
| TS5 | 异常与边缘场景 | 12 | 边界条件注入 | 隔离 + 活系统 |
| **合计** | | **45** | | |

### 1.3 通过标准

| 级别 | 门禁 |
|------|------|
| BLOCKER | **0** |
| MAJOR | ≤ 3 |
| 安全漏洞 | **0** |
| 未裁定申诉 | **0** |

---

## 2. 文档审查发现

### 2.1 PRD vs 架构文档冲突 (发现于文档审查)

| # | 冲突点 | PRD (§2) | 架构设计 (§3.3) | 影响 |
|---|--------|----------|----------------|------|
| **D1** | 「安排」定级 | `running + ready + blocked` | `ready + running`（排除 blocked）| **实现依赖于解决此冲突** |
| **D2** | 「安排」/「跑完」范围 | "OC 创建的任务" | 全局任务（通过 session started_at 过滤"跑完"）| collector 无需区分创建者 |
| **D3** |「在跑」/「未跑」范围 | "全局看板" | 全局看板（一致 ✓）| 无冲突 |

> **D1 风险等级**: BLOCKER — 产品和架构未对齐，collector 无法实现。需要 Frank 或产品裁定。
> **按 §1.2 判定**: 用户可感知 = 是 (Frank 看到的数字); 功能阻断 = 是 (定义不一致 → collector 输出错误); workaround = 无 (只能等裁定)。

### 2.2 基础设施风险

| # | 发现 | 证据 | 风险 |
|---|------|------|------|
| **I1** | cron.db 为空 (0 bytes) | `ls -la /root/.hermes/profiles/orchestrator/cron.db` → 0 bytes | 「下一轮启动时间」功能无数据源 |
| **I2** | .oc_session.json 不存在 | 文件系统扫描 | collector 当前永远返回空输出 (正常——等待 OC 实现) |
| **I3** | v2 旧文件残留 | `.kanban_resume`, `.kanban_watchdog_meta.json`, `.kanban_state.json` 均存在 | 需在 Phase 4 清理 |
| **I4** | boards 目录仅 1 个 board | `/root/.hermes/kanban/boards/` 仅 `infomanager` | 多 board 过滤逻辑需额外测试数据 |

---

## 3. TS1: kanban_collector.py 单元测试

### 3.1 测试范围

测试 `kanban_collector.py` 中的每个函数：

- `read_session_state()` — session file 读取 + TTL 检测
- `scan_all_boards(session)` — kanban.db 扫描 + 四维统计
- `read_next_cron()` — cron.db 读取
- `build_output(stats, session, next_cron)` — 输出格式化
- `main()` — 集成流程

### 3.2 测试用例

#### 3.2.1 read_session_state()

| ID | 用例 | 输入 | 预期输出 | 级别 |
|----|------|------|---------|:---:|
| TS1-01 | 文件不存在 | SESSION_FILE 不存在 | 返回 None | BLOCKER |
| TS1-02 | 有效 session file | 有效 JSON, updated_at = now | 返回完整 dict | BLOCKER |
| TS1-03 | JSON 损坏 | 无效 JSON 内容 | 返回 None | MAJOR |
| TS1-04 | TTL 过期 | updated_at 超过 600s | 返回 None (stale) | BLOCKER |
| TS1-05 | TTL 边界 — 刚好 600s | updated_at = now - 600 | 返回 None (time.time() - updated_at > ttl) | MAJOR |
| TS1-06 | TTL 边界 — 599s | updated_at = now - 599 | 返回完整 dict | MAJOR |
| TS1-07 | 缺少 max_age_seconds 字段 | JSON 无 max_age_seconds | 使用默认 600 | MINOR |
| TS1-08 | 空 session file | 文件存在但为空 (0 bytes) | 返回 None (JSON decode error) | MAJOR |

#### 3.2.2 scan_all_boards()

| ID | 用例 | 输入 | 预期输出 | 级别 |
|----|------|------|---------|:---:|
| TS1-09 | 四维统计准确性 | 已知任务：2 running, 3 ready, 1 blocked, 5 done | stats = {ready:3, running:2, blocked:1, done:5} | BLOCKER |
| TS1-10 | 空 board | 无任务 | 全部 count = 0 | MAJOR |
| TS1-11 | board 目录为空 | KANBAN_DIR 无任何子目录 | 全部 count = 0，不崩溃 | MAJOR |
| TS1-12 | kanban.db 损坏 | 文件存在但非 SQLite 格式 | 跳过该 board，继续扫描其他 | MAJOR |
| TS1-13 | 「安排」= ready+running（排除 blocked） | 3 ready + 2 running + 1 blocked | scheduled = 5 (不是 6) | BLOCKER |
| TS1-14 | 「跑完」= 会话期间完成 | session_started_at = T, 2 done (completed_at >= T), 1 done (completed_at < T) | _done_in_session = 2 | BLOCKER |
| TS1-15 | project_boards 过滤 | session 含 project_boards=["devPPL"]，仅 infomanager board 存在 | 若 project_boards 不匹配 → 全 0 | MAJOR |
| TS1-16 | project_boards=None 回退 | session 无 project_boards 字段 | 扫描所有 board | MAJOR |
| TS1-17 | project_boards 跨 board 汇总 | session 含 project_boards=["devPPL","infomanager"]，两 board 各有任务 | 汇总两个 board 的任务计数 | BLOCKER |
| TS1-18 | archived 任务不计数 | archived=1 的任务 | 不在任何统计中 | MAJOR |

#### 3.2.3 read_next_cron()

| ID | 用例 | 输入 | 预期输出 | 级别 |
|----|------|------|---------|:---:|
| TS1-19 | cron.db 存在且有 one-shot job | 1 个 active one-shot job | 返回 next_run_at | MAJOR |
| TS1-20 | cron.db 不存在 | CRON_DB 路径不存在 | 返回 None | MINOR |
| TS1-21 | cron.db 为空 (0 bytes) | 当前实际状态 | 返回 None (sqlite3 异常捕获) | MAJOR |

#### 3.2.4 build_output()

| ID | 用例 | 输入 | 预期输出 | 级别 |
|----|------|------|---------|:---:|
| TS1-21 | 正常四维格式 | scheduled=5, done=2, running=2, pending=3 | `📋 安排5个 \| ✅ 跑完2个 \| 🔄 在跑2个 \| ⏳ 未跑3个` | BLOCKER |
| TS1-22 | 有 session 信息 | session + next_cron | 输出包含 🕐 OC 会话行 + 下一轮时间 | MAJOR |
| TS1-23 | 无 session 信息 | session=None | 仅输出四维统计（无 🕐 行） | MAJOR |
| TS1-24 | 无 next_cron | next_cron=None | 🕐 行不显示 "下一轮" | MINOR |

#### 3.2.5 main()

| ID | 用例 | 输入 | 预期输出 | 级别 |
|----|------|------|---------|:---:|
| TS1-25 | 完整流程 — 有 session | 有效 session + kanban 有任务 | stdout 包含四维统计 + OC 信息 | BLOCKER |
| TS1-26 | 无 session — 空输出 | SESSION_FILE 不存在 | stdout 为空，exit code 0 | BLOCKER |
| TS1-27 | 有 session 但无任务 | 有效 session + 空 kanban | stdout 包含 `📋 安排0个...` | MAJOR |

### 3.3 成功标准

- TS1-01 到 TS1-27 全部 PASS
- 0 个 BLOCKER
- 伪代码不等同于实现——测试基于最终 .py 文件

---

## 4. TS2: OC Session State File 生命周期测试

### 4.1 测试范围

验证 `.oc_session.json` 的完整生命周期：创建 → active → draining → 删除。

### 4.2 测试用例

| ID | 用例 | 操作 | 预期结果 | 级别 |
|----|------|------|---------|:---:|
| TS2-01 | 原子写 (tmp→mv) | 写 .tmp → os.rename() → 最终路径 | 最终路径存在，.tmp 不存在；文件内容完整 | BLOCKER |
| TS2-02 | active → collector 读到 | 写 status=active 的 session file | collector 返回非空输出 | BLOCKER |
| TS2-03 | updated_at 心跳更新 | 多次 touch (间隔 < TTL) | collector 持续返回非空 | MAJOR |
| TS2-04 | status=draining → OC 等 60s → 删文件 | OC 写 draining，sleep 60s，删文件 | collector: draining 期间仍有输出 → 删除后空输出 | BLOCKER |
| TS2-05 | 崩溃恢复 — 残留 active (TTL 未过期) | 残留 active session，updated_at < 600s 内 | OC 重启后续用 → collector 正常播报 | MAJOR |
| TS2-06 | 崩溃恢复 — 残留 active (TTL 过期) | 残留 active session，updated_at > 600s | collector 返回空输出 → reporter 告别 → OC 重启时清理 | BLOCKER |
| TS2-07 | 崩溃恢复 — 残留 draining | 残留 status=draining 的 session | OC 重启时直接清理 (不续用) | MAJOR |
| TS2-08 | 并发安全 — 读写不交叉 | collector 读取同时 OC 写入 | collector 不读到半写文件 (原子 rename 保证) | MAJOR |

### 4.3 成功标准

- 所有 TS2 用例 PASS
- 崩溃恢复不产生僵尸 session file
- collector 在 session file 删除后 2 个 tick 内切换为静默

---

## 5. TS3: 旧文件清理验证

### 5.1 测试范围

确认 v2.0 遗留文件不再被使用，且清理脚本正确执行。

### 5.2 变更清单 (架构 §8.4)

| 文件 | 动作 | 验证方法 |
|------|------|---------|
| `.kanban_resume` | 删除 | 文件不存在于 orchestrator scripts 目录 |
| `.kanban_watchdog_meta.json` | 删除 | 文件不存在 |
| `.kanban_state.json` | 删除 | 文件不存在 |
| `kanban_watchdog.py` | 废弃 (保留备查) | 不被任何 cron job 引用 |

### 5.3 测试用例

| ID | 用例 | 检查内容 | 预期结果 | 级别 |
|----|------|---------|---------|:---:|
| TS3-01 | .kanban_resume 已删除 | 文件存在性 | 不存在 | MAJOR |
| TS3-02 | .kanban_watchdog_meta.json 已删除 | 文件存在性 | 不存在 | MAJOR |
| TS3-03 | .kanban_state.json 已删除 | 文件存在性 | 不存在 | MAJOR |
| TS3-04 | v2 cron job 已清理 | cronjob list 或检查 cron.db | 无引用 kanban_watchdog.py 的 cron | MAJOR |
| TS3-05 | kanban_collector.py 不引用 v2 路径 | grep 旧文件名 | 无匹配 | BLOCKER |

### 5.4 当前状态 (基线快照)

```
/root/.hermes/.kanban_resume                            ← 存在 (根目录, 非 scripts)
/root/.hermes/profiles/orchestrator/scripts/.kanban_resume ← 需确认
/root/.hermes/profiles/orchestrator/scripts/.kanban_watchdog_meta.json  ← 存在
/root/.hermes/profiles/orchestrator/scripts/.kanban_state.json           ← 存在
/root/.hermes/profiles/orchestrator/scripts/kanban_watchdog.py           ← 存在
/root/.hermes/scripts/kanban_watchdog.py                                ← 存在 (旧位置)
```

> **注意**: `/root/.hermes/.kanban_resume` 是一个特殊残留——架构文档说路径应在 `scripts/` 下，但实际存在于根目录。需确认是两个位置都清理还是仅清理 scripts 版本。

---

## 6. TS4: Layer1+Layer2 集成测试

### 6.1 测试范围

端到端验证：collector cron → reporter cron → Feishu 投递。

### 6.2 测试用例

| ID | 用例 | 步骤 | 预期结果 | 级别 |
|----|------|------|---------|:---:|
| TS4-01 | 正常心跳链路 | 1. 创建 test session file 2. 等待 collector tick (30s) 3. 等待 reporter tick (1min) | reporter 输出四维统计到聊天 | BLOCKER |
| TS4-02 | collector 空输出 → reporter 告别 | 1. 删除 session file 2. 等待 collector tick → 空 output 3. 等待 reporter tick | reporter 输出 "👋 无任务在跑，即将静默" | BLOCKER |
| TS4-03 | reporter 自删 | 完成 TS4-02 后 | reporter cron job 被删除 | BLOCKER |
| TS4-04 | collector 继续运行但 reporter 不存在 | reporter 已自删，collector 仍运行 | 无消息投递（正确，reporter 是唯一投递通道） | MAJOR |
| TS4-05 | OC 重启 → reporter 重建 | 1. 模拟 OC 重启 2. 写新 session file 3. 创建新 reporter cron | 心跳恢复正常 | MAJOR |

### 6.3 成功标准

- 3 个完整周期：session 创建 → 心跳 → 静默 → 重启 → 心跳
- 无僵尸 cron 残留
- reporter 不修改 collector 的输出格式 (原文转发)

---

## 7. TS5: 异常与边缘场景测试

### 7.1 测试用例 (对照架构 §10 边缘场景矩阵)

| ID | 场景 (架构编号) | 注入条件 | 预期行为 | 级别 |
|----|---------------|---------|---------|:---:|
| TS5-01 | E1: OC 正常启动有任务 | 标准流程 | 1min 内心跳 | BLOCKER |
| TS5-02 | E2: OC 正常停止 | status=draining → 删 session | 告别消息 → 无后续消息 | BLOCKER |
| TS5-03 | E3: OC 崩溃 | kill OC 进程，残留 session | TTL 过期 → "OC 无响应" 或静默 | BLOCKER |
| TS5-04 | E4: OC 重启 | 清理 → 重写 session → 重建 cron | 无缝恢复，无重复 cron | MAJOR |
| TS5-05 | E5: 任务 30s 内完成 | 快速创建+完成 | collector 可能捕获不到 running | MINOR |
| TS5-06 | E6: kanban.db 锁 | SQLite BUSY | 跳过本次 tick，下次重试 | MAJOR |
| TS5-07 | E7: cron.db 不可读 | 权限 000 或删除 | 不显示"下一轮"，其余正常 | MINOR |
| TS5-08 | E8: .oc_session.json 损坏 | 写半截 JSON | collector 返回 None → 空输出 → 告别 | MAJOR |
| TS5-09 | E9: OC 忘记更新 session | 写 session 后停止心跳 | TTL 过期 → 静默 | MAJOR |
| TS5-10 | E11: Frank 手动创建任务 | 非 OC → kanban_create | 心跳中可见 (全局扫描 ✓) | MAJOR |
| TS5-11 | E12: 无 session 但 kanban 有任务 | 删除 session，看板有活跃任务 | collector 空输出 → 不播报 | MAJOR |
| TS5-12 | R5: SQLite WAL 模式 | 高频读 (30s) + 偶尔写 | 无锁竞争异常 | MINOR |

### 7.2 额外边界测试

| ID | 用例 | 条件 | 预期 | 级别 |
|----|------|------|------|:---:|
| TS5-13 | session file 字段缺失 | 仅有 session_id + started_at，缺少所有可选字段 | collector 不崩溃，合理降级 | MAJOR |
| TS5-14 | 超长 board 名称 | board name = 256 字符 | collector 正常处理 | MINOR |
| TS5-15 | 大量任务 (1000+) | kanban.db 中有 1000+ 非终态任务 | 30s 内完成扫描 (性能检查) | MAJOR |

---

## 8. 风险与定级清单

按 `qa-finding-classification.md` 标准逐条定级。

### 8.1 文档风险 (发布前必须解决)

| ID | 风险 | 判定 | 判定依据 (§1.2) |
|----|------|:---:|----------------|
| R-D1 | 「安排」定级 PRD vs 架构冲突 | **BLOCKER** | 用户可感知(Frank看到) + 功能阻断(定义不一致→错误输出) + 无workaround |
| R-D2 | cron.db 为空 (下一轮功能无数据) | **MAJOR** | 用户可感知 + 功能部分阻断 + 有降级(不显示该行) |

### 8.2 代码风险

| ID | 风险 | 判定 | 缓解 |
|----|------|:---:|------|
| R-C1 | OC LLM agent 行为不可靠 (忘记写 session) | **MAJOR** | TTL 自动过期 + SOUL.md 规则 |
| R-C2 | Stale session file 残留 | **MAJOR** | TTL 600s + collector 检测 |
| R-C3 | 僵尸 cron 残留 | **MAJOR** | 幂等 idempotency_key + OC 启动清理 |
| R-C4 | SQLite 锁竞争 | **MINOR** | try/except + WAL 模式 |

### 8.3 集成风险

| ID | 风险 | 判定 | 缓解 |
|----|------|:---:|------|
| R-I1 | Reporter 转发时修改了 collector 格式 | **MAJOR** | Prompt 明确指令 "原文字符串不要修改格式" |
| R-I2 | Reporter 自删失败 (权限/API 错误) | **MAJOR** | OC 启动时主动清理旧 reporter cron |
| R-I3 | 多 OC 会话并存 | **MINOR** | 预留扩展 (session_id 命名)——当前不处理 |

---

## 9. 发布门禁检查表

对照 `qa-finding-classification.md §10`:

| 条件 | 当前 | 目标 |
|------|:---:|:---:|
| BLOCKER = 0 | ❌ (R-D1 未解决) | 0 |
| MAJOR ≤ 3 | ❌ (R-D2, R-C1, R-C2, R-C3, R-I1, R-I2 均为 MAJOR) | ≤ 3 |
| 安全漏洞 = 0 | ✅ (未发现安全漏洞) | 0 |
| 无未裁定申诉 | ✅ | 0 |

**当前状态**: 🚫 不可发布 — 需要 R-D1 裁定 + MAJOR 数量超出门禁。

---

## 10. 附录: 测试数据准备脚本

### A. 模拟 kanban.db 数据

```python
"""prepare_test_data.py — 创建测试用 kanban.db"""
import sqlite3, os, json, time

def create_test_board(board_name="test_board", tasks=None):
    board_dir = f"/tmp/test_kanban/boards/{board_name}"
    os.makedirs(board_dir, exist_ok=True)
    db_path = f"{board_dir}/kanban.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, title TEXT, status TEXT,
            completed_at INTEGER, archived INTEGER DEFAULT 0
        )
    """)
    if tasks:
        conn.executemany(
            "INSERT OR REPLACE INTO tasks VALUES(?,?,?,?,?)", tasks
        )
    conn.commit()
    conn.close()
    return db_path

# 示例：模拟 8 个任务 (按架构 §3.3 四维分布)
# id, title, status, completed_at, archived
TEST_TASKS = [
    ("t_01", "App bug fix", "ready", None, 0),
    ("t_02", "API refactor", "ready", None, 0),
    ("t_03", "DB migration", "ready", None, 0),
    ("t_04", "Frontend deploy", "running", None, 0),
    ("t_05", "Backend deploy", "running", None, 0),
    ("t_06", "Security audit", "blocked", None, 0),  # 不纳入「安排」
    ("t_07", "Old feature A", "done", int(time.time()) - 3600, 0),  # 会话前完成 → 不计入「跑完」
    ("t_08", "Feature B", "done", int(time.time()) - 100, 0),       # 会话后完成 → 计入「跑完」
]

create_test_board("test_board", TEST_TASKS)
print("Test board created at /tmp/test_kanban/boards/test_board/kanban.db")
```

### B. 模拟 .oc_session.json

```python
"""prepare_session.py — 创建测试用 session file"""
import json, time, os

SESSION = {
    "session_id": "oc_20260710_143000",
    "started_at": int(time.time()) - 1800,  # 30min 前启动
    "updated_at": int(time.time()),
    "status": "active",
    "role": "orchestrating",
    "max_age_seconds": 600,
    "project_boards": ["test_board"]
}

path = "/root/.hermes/profiles/orchestrator/scripts/.oc_session.json"
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as f:
    json.dump(SESSION, f, indent=2)
print(f"Session file written to {path}")
```

### C. 运行 collector 测试

```bash
# 1. 准备测试数据
python3 /workspace/devPPL/scripts/prepare_test_data.py
python3 /workspace/devPPL/scripts/prepare_session.py

# 2. 设置环境变量指向测试数据
export KANBAN_DIR=/tmp/test_kanban/boards
export SESSION_FILE=/root/.hermes/profiles/orchestrator/scripts/.oc_session.json

# 3. 运行 collector
python3 /root/.hermes/profiles/orchestrator/scripts/kanban_collector.py

# 预期输出:
# 📋 安排5个 | ✅ 跑完1个 | 🔄 在跑2个 | ⏳ 未跑3个
# 🕐 OC 会话: oc_20260710_143000 | 已运行 30min
```

---

> **QA 结论**: Watchdog v3.0 架构清晰，两层分离可测性优于 v2.0。主要阻塞项为 R-D1（PRD vs 架构对「安排」的定义冲突）。所有 MAJOR 项均有缓解措施，但需要落实。建议在 R-D1 裁定后立即进入 Phase 1 实现 + TS1 测试。

> **判定依据**: 本文档所有风险定级均按 `docs/standards/qa-finding-classification.md` §1.2 五步判定公式执行。安全漏洞检查通过了 §14 附录B 的 OWASP Top 10 checklist（本项目无网络面 → 注入/XSS/CSRF 等不适用）。
