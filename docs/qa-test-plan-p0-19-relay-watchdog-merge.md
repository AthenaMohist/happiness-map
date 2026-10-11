# QA Test Plan: P0-19 接力 cron 合并到 Watchdog v3.0

> QA: game-qa | 日期: 2026-07-10 | 版本: v1.0
> 对应实现: P0-19 方案C — 接力状态透传 + watchdog 统一播报
> 改动范围: .oc_relay.json / relay_update.py / kanban_collector.py / SOUL.md
> 依据标准: docs/standards/qa-finding-classification.md (v1.0)
> 架构基线: docs/arch-p0-18b-watchdog-v3.md (v1.2)
> 产品裁定: docs/roundtables/roundtable-b-cron-watchdog-merge-product-ruling.md

---

## 目录

1. [测试策略概要](#1-测试策略概要)
2. [改动点分析与覆盖映射](#2-改动点分析与覆盖映射)
3. [TS-R1: relay_update.py 单元测试](#3-ts-r1-relay_updatepy-单元测试)
4. [TS-R2: .oc_relay.json 文件协议测试](#4-ts-r2-oc_relayjson-文件协议测试)
5. [TS-R3: kanban_collector.py Relay 集成测试](#5-ts-r3-kanban_collectorpy-relay-集成测试)
6. [TS-R4: SOUL.md Prompt 合规性测试](#6-ts-r4-soulmd-prompt-合规性测试)
7. [TS-R5: 端到端集成测试](#7-ts-r5-端到端集成测试)
8. [TS-R6: 边缘场景与异常测试](#8-ts-r6-边缘场景与异常测试)
9. [风险与定级清单](#9-风险与定级清单)
10. [发布门禁检查表](#10-发布门禁检查表)
11. [附录: 测试脚本](#11-附录-测试脚本)

---

## 1. 测试策略概要

### 1.1 测试范围与边界

```
P0-19 仅新增 relay 状态透传链路，不改动 watchdog 核心逻辑：

  relay_update.py ──写──→ .oc_relay.json ──读──→ kanban_collector.py
       ↑                                              │
       │                                              ▼
  game-engine SOUL.md §6                      build_output() 追加
  (接力 cron prompt)                          🔄 接力: <phase> <detail>
                                                   │
                                                   ▼
                                            Reporter → Feishu

测试边界：
  ✅ relay_update.py 自身逻辑（phase 校验、detail 截断、原子写）
  ✅ .oc_relay.json 协议正确性（字段、格式、与 .oc_session.json 不冲突）
  ✅ collector 读取 relay 状态（读/不读/损坏/空文件 → 不崩溃）
  ✅ build_output() 输出格式（relay 行追加位置、格式、无 relay 时不出现）
  ✅ SOUL.md prompt 合规（7 阶段模板、relay_update.py 调用、[SILENT] 输出）
  ❌ 不测试: watchdog core 逻辑（四维统计、session TTL、reporter 自删）→ 已在 v3.0 方案覆盖
  ❌ 不测试: cron 运行时行为（调度精度、跨 profile 隔离）→ 属 cron 基础设施
  ❌ 不测试: Feishu 投递正确性 → 属 gateway 层
```

### 1.2 测试金字塔

```
         ╱    TS-R5 端到端     ╲       relay → collector → output 全链路
        ╱──────────────────────╲
       ╱    TS-R6 边缘场景       ╲      损坏文件/并发写/多 phase 切换
      ╱──────────────────────────╲
     ╱     TS-R4 SOUL.md 合规      ╲      prompt 静态检查 + 格式验证
    ╱────────────────────────────────╲
   ╱   TS-R2 .oc_relay.json    TS-R3  ╲  协议正确性   collector 集成
  ╱──────────────────────────────────────╲
 ╱          TS-R1 relay_update.py 单元     ╲ 逐函数: validate/truncate/atomic_write
╱────────────────────────────────────────────╲
```

### 1.3 测试层次汇总

| 层次 | 名称 | 用例数 | 执行方式 | 环境 |
|------|------|:---:|---------|------|
| TS-R1 | relay_update.py 单元 | 12 | pytest / subprocess | 隔离 (临时目录) |
| TS-R2 | .oc_relay.json 协议 | 5 | 文件断言 | 隔离 |
| TS-R3 | Collector Relay 集成 | 8 | subprocess + env var override | 隔离 (mock DB) |
| TS-R4 | SOUL.md 合规 | 7 | grep / 静态分析 | 文件系统 |
| TS-R5 | 端到端集成 | 5 | 全链路 subprocess | 隔离 |
| TS-R6 | 边缘场景 | 7 | 边界条件注入 | 隔离 + 文件 |
| **合计** | | **44** | | |

### 1.4 通过标准

| 级别 | 门禁 |
|------|------|
| BLOCKER | **0** |
| MAJOR | ≤ 3 |
| 安全漏洞 | **0** |
| 未裁定申诉 | **0** |

---

## 2. 改动点分析与覆盖映射

### 2.1 四改动点 → 测试套件映射

| # | 改动点 | 文件 | 关键函数/结构 | 对应测试 |
|---|--------|------|-------------|---------|
| **CP1** | relay_update.py (119行) | orchestrator/scripts/ | `validate_phase`, `truncate_detail`, `atomic_write`, `main` | TS-R1 |
| **CP2** | .oc_relay.json 协议 | orchestrator/scripts/ | `{"phase": "x", "detail": "x", "updated_at": N}` | TS-R2 |
| **CP3** | kanban_collector.py (+42行) | orchestrator/scripts/ | `read_relay_state()`, `build_output(relay_phase, relay_detail)`, `main()` relay 分支 | TS-R3 |
| **CP4** | SOUL.md §6 (orchestrator + game-engine) | 两个 profiles | relay 生命周期规则、7 阶段模板 prompt、[SILENT] 协议 | TS-R4 |

### 2.2 架构设计决策 → 测试检查点

| 设计决策（来自父任务 metadata） | 测试检查点 |
|--------------------------------|-----------|
| relay_update.py uses atomic write | TS-R1-07: .tmp 不存在, .oc_relay.json 完整 |
| collector reads relay best-effort | TS-R3-04/05/06: 文件不存在/损坏/空 → 不崩溃 |
| relay cron outputs [SILENT] | TS-R4-04/05: prompt 不含 send_message, 含 [SILENT] |
| .oc_relay.json cleaned up on OC end | TS-R2-05: SOUL.md 含清理规则 |
| relay state for current OC session only | TS-R5-04: 新会话 relay 不继承旧状态 |

---

## 3. TS-R1: relay_update.py 单元测试

### 3.1 测试范围

对 `relay_update.py` 逐函数测试，覆盖正常路径 + 边界 + 错误路径。

### 3.2 测试用例

#### 3.2.1 validate_phase() — phase 校验

| ID | 测试 | 输入 | 预期输出 | 成功标准 |
|----|------|------|---------|---------|
| **TC-R1-01** | 有效 phase: polling | `polling` | exit=0, stdout 含 `"phase": "polling"` | PASS |
| **TC-R1-02** | 有效 phase: dispatching | `dispatching` | exit=0, stdout 含 `"phase": "dispatching"` | PASS |
| **TC-R1-03** | 有效 phase: waiting | `waiting` | exit=0 | PASS |
| **TC-R1-04** | 有效 phase: completed | `completed` | exit=0 | PASS |
| **TC-R1-05** | 有效 phase: error | `error` | exit=0 | PASS |
| **TC-R1-06** | 无效 phase | `unknown` | exit=1, stderr 含 "invalid phase" + 列出 5 个有效值 | PASS |
| **TC-R1-07** | 无参数 | (no args) | exit=1, stderr 含 "Usage:" + 5 个 phase | PASS |
| **TC-R1-08** | phase 大小写规范化 | `Polling`, `COMPLETED` | exit=0, phase 归一化为小写 | PASS |

#### 3.2.2 truncate_detail() — detail 截断

| ID | 测试 | 输入 | 预期输出 | 成功标准 |
|----|------|------|---------|---------|
| **TC-R1-09** | detail ≤ 60 字符 | `"short message"` | detail 原样保留 | PASS |
| **TC-R1-10** | detail > 60 字符 | `"a" * 80` | detail 截断为 60 字符 + "..." | PASS: len(detail) = 60, 末 3 字符 = "..." |
| **TC-R1-11** | detail 为空字符串 | `""` | detail = "" | PASS |

#### 3.2.3 atomic_write() — 原子写

| ID | 测试 | 输入 | 预期输出 | 成功标准 |
|----|------|------|---------|---------|
| **TC-R1-12** | 原子写完整性 | 正常写入 | .oc_relay.json 存在且 JSON 合法，无 .tmp 残留 | PASS: .tmp 不存在, .oc_relay.json 可 parse |

### 3.3 运行方式

```bash
# 所有测试在临时目录中运行，通过 env var 覆盖 RELAY_FILE
WATCHDOG_RELAY_FILE=/tmp/test_relay.json python3 relay_update.py polling "test"
```

---

## 4. TS-R2: .oc_relay.json 文件协议测试

### 4.1 协议定义

```json
{
  "phase": "polling|dispatching|waiting|completed|error",
  "detail": "human-readable description (max 60 chars)",
  "updated_at": 1750600200.0
}
```

### 4.2 测试用例

| ID | 测试 | 操作 | 预期结果 | 成功标准 |
|----|------|------|---------|---------|
| **TC-R2-01** | 基本写入 | `relay_update.py polling "checking"` | 文件存在，JSON 含 phase/detail/updated_at 三字段 | PASS |
| **TC-R2-02** | updated_at 是浮点数时间戳 | 写入后检查 | `updated_at` 类型为 number，值接近 `time.time()` (±2s) | PASS |
| **TC-R2-03** | 文件不存在时 collector 不死 | `rm .oc_relay.json` → collector | collector exit=0, 无 relay 行 | PASS |
| **TC-R2-04** | 文件路径与 .oc_session.json 不冲突 | 两个文件分别写入 | 两者互不影响，各自独立存在 | PASS |
| **TC-R2-05** | OC 结束时清理规则 | grep SOUL.md | orchestrator SOUL.md 含 "删除 .oc_relay.json" | PASS |

### 4.3 成功标准

- 5/5 PASS = 套件通过
- 协议格式与 `relay_update.py` 输出一致
- 与 `.oc_session.json` 不产生文件冲突

---

## 5. TS-R3: kanban_collector.py Relay 集成测试

### 5.1 变更点回顾

collector 新增了 3 处 relay 相关代码：
1. `read_relay_state()` (L216-236): 读取 .oc_relay.json，best-effort
2. `build_output()` (L239-279): 接受 `relay_phase`/`relay_detail` 参数，追加 `🔄 接力:` 行
3. `main()` (L283-308): 调用 `read_relay_state()` → 传入 `build_output()`

### 5.2 测试用例

#### 5.2.1 read_relay_state() — 读取 relay 状态

| ID | 测试 | 前置条件 | 预期结果 | 成功标准 |
|----|------|---------|---------|---------|
| **TC-R3-01** | relay 文件存在且有效 | .oc_relay.json 含 `{"phase":"dispatching","detail":"QA task t_abc"}` | 返回 `("dispatching", "QA task t_abc")` | PASS |
| **TC-R3-02** | relay 文件不存在 | 无 .oc_relay.json | 返回 `(None, None)`，不抛异常 | PASS |
| **TC-R3-03** | relay 文件为空 | .oc_relay.json = "" | 返回 `(None, None)` | PASS |
| **TC-R3-04** | relay 文件 JSON 损坏 | .oc_relay.json = `{broken` | 返回 `(None, None)`，不抛异常 | PASS |
| **TC-R3-05** | relay phase 为未知值 | .oc_relay.json `{"phase":"unknown_val","detail":"x"}` | 返回 `("unknown_val", "x")` — 透传，不崩溃 | PASS |

#### 5.2.2 build_output() — relay 行追加

| ID | 测试 | 前置条件 | 预期 relay 行 | 成功标准 |
|----|------|---------|-------------|---------|
| **TC-R3-06** | relay_phase 有值 + detail 有值 | phase="dispatching", detail="QA task" | `🔄 接力: dispatching QA task` | PASS |
| **TC-R3-07** | relay_phase 有值 + detail 为空 | phase="polling", detail="" | `🔄 接力: polling` (无多余空格) | PASS |
| **TC-R3-08** | relay_phase 为 None | phase=None | 输出中**不包含** `🔄 接力:` 行 | PASS |

### 5.3 运行方式

```bash
# 使用 env var override 隔离测试
WATCHDOG_SESSION_FILE=/tmp/test_session.json \
WATCHDOG_RELAY_FILE=/tmp/test_relay.json \
WATCHDOG_KANBAN_DIR=/tmp/test_boards \
  python3 kanban_collector.py
```

### 5.4 成功标准

- 8/8 PASS = 套件通过
- collector 在任何 relay 文件状态下不崩溃 (exit=0)
- relay 行格式匹配产品裁定 §3.2: `🔄 接力: <phase> <detail>`

---

## 6. TS-R4: SOUL.md Prompt 合规性测试

### 6.1 测试范围

验证两个 SOUL.md 中的 relay 相关规则是否符合方案 C 设计：

**orchestrator SOUL.md** (L304-310):
- relay 状态文件由接力 cron 通过 `relay_update.py` 写入
- `kanban_collector.py` 读取并追加 `🔄 接力:` 行
- 接力 cron 输出 [SILENT]
- OC 结束时清理 `.oc_relay.json`

**game-engine SOUL.md** (§6, L50-156):
- 6.1 relay_update.py 状态更新规则
- 6.2 去重规则
- 6.3 自停 + 1 tick 缓冲
- 6.4 LOOP_LIMIT=5 轮次上限
- 6.5 QA 验收标准（静态检查）
- 6.6 [SILENT] 输出协议
- 6.7 7 阶段模板 prompt

### 6.2 测试用例

#### 6.2.1 orchestrator SOUL.md 合规

| ID | 测试 | 检查方法 | 预期结果 | 成功标准 |
|----|------|---------|---------|---------|
| **TC-R4-01** | relay 文件路径声明 | grep `.oc_relay.json` orchestrator/SOUL.md | 至少 1 处引用（含路径） | PASS |
| **TC-R4-02** | relay_update.py 路径声明 | grep `relay_update.py` orchestrator/SOUL.md | 至少 1 处引用（含路径） | PASS |
| **TC-R4-03** | OC 结束时清理 relay 文件 | grep "删除 .oc_relay.json" orchestrator/SOUL.md | 至少 1 处（L302） | PASS |

#### 6.2.2 game-engine SOUL.md 合规

| ID | 测试 | 检查方法 | 预期结果 | 成功标准 |
|----|------|---------|---------|---------|
| **TC-R4-04** | relay_update.py 调用指令 | grep `relay_update.py` game-engine/SOUL.md | §6.1 含完整用法 (路径 + 5 个 phase + 参数说明) | PASS |
| **TC-R4-05** | 7 阶段模板含 relay_update.py | grep -A2 "阶段 0" game-engine/SOUL.md | 阶段 0 调用 relay_update.py polling | PASS |
| **TC-R4-06** | [SILENT] 协议声明 | grep "SILENT" game-engine/SOUL.md | §6.6 含 [SILENT] 输出协议 + "播报交给 watchdog" | PASS |
| **TC-R4-07** | LOOP_LIMIT=5 声明 | grep "5 轮" game-engine/SOUL.md | §6.4 明确声明最多 5 轮 + 超限后 relay error + 自删 | PASS |

### 6.3 成功标准

- 7/7 PASS = 套件通过
- 静态 grep 检查，不执行 cron

---

## 7. TS-R5: 端到端集成测试

### 7.1 测试目标

验证完整链路：`relay_update.py → .oc_relay.json → kanban_collector.py → build_output()` 在隔离环境中端到端正确。

### 7.2 测试场景

| ID | 场景 | 步骤 | 预期输出 | 成功标准 |
|----|------|------|---------|---------|
| **TC-R5-01** | 完整接力生命周期 | 依次写入 5 个 phase → collector 读取 | 每次 collector 输出含对应 `🔄 接力:` 行 | 5/5 phase 均有对应输出 |
| **TC-R5-02** | relay + watchdog 四维同显 | 写 relay=dispatching + 建完整 session + kanban | 消息含四维行 + relay 行 + session 行，relay 在 session 之前 | PASS |
| **TC-R5-03** | phase 从 dispatching→waiting→completed 切换 | relay_update 3 次 → collector runs | 每次输出 relay 行反映最新 phase | PASS |
| **TC-R5-04** | 新会话 relay 不继承旧状态 | session 1 写 relay → 删 session → 新 session 2 → collector | session 2 collector 输出无 relay（除非新 relay 写入）| PASS |
| **TC-R5-05** | stale session + relay 同时显示 | stale session + relay 文件 → collector | 输出含 stale 警告 + relay 行 | PASS |

### 7.3 运行方式

```bash
# 隔离环境：临时目录含 mock kanban.db + session file + relay file
# 脚本: tests/scripts/setup_relay_e2e.sh
```

### 7.4 成功标准

- 5/5 PASS = 套件通过
- relay 行始终在 session 行之前（符合产品裁定 §4.2 三行制顺序）

---

## 8. TS-R6: 边缘场景与异常测试

### 8.1 边缘场景矩阵

| ID | 场景 | 操作 | 预期行为 | 成功标准 |
|----|------|------|---------|---------|
| **TC-R6-01** | relay 文件 concurrent read/write | 进程 A 写 .oc_relay.json, 进程 B collector 读 | collector 不崩溃，读到完整 JSON 或旧版本 | PASS |
| **TC-R6-02** | relay_update.py 输出 stdout 验证 | `python3 relay_update.py polling "test"` | stdout 为合法 JSON: `{"phase":"polling","detail":"test","updated_at": <float>}` | PASS |
| **TC-R6-03** | detail 恰好 60 字符 | detail = "x"*60 | 不截断（无 "..." 后缀） | PASS: len(detail)=60 |
| **TC-R6-04** | detail 61 字符 | detail = "x"*61 | 截断为 60 字符 + "..." | PASS: len(detail)=60, 末 3 字符 = "..." |
| **TC-R6-05** | 两个 collector tick 之间 relay 未更新 | relay 不变 → collector tick 2 次 | 两次输出 relay 行内容一致 | PASS |
| **TC-R6-06** | relay 文件为只读目录名冲突 | RELAY_FILE path 是目录而非文件 | collector 不崩溃 | PASS |
| **TC-R6-07** | max_detail_len boundary: 0 chars | detail = "" | relay 行格式: `🔄 接力: polling` (无多余空格) | PASS |

### 8.2 并发场景说明

`relay_update.py` 使用原子写（write .tmp → fsync → rename），collector 使用普通 `open().read()` — POSIX 保证 rename 是原子的，reader 要么读到旧文件，要么读到新文件，不会读到半写文件。

---

## 9. 风险与定级清单

按 `docs/standards/qa-finding-classification.md` §1.2 五步判定公式逐条分析。

### 9.1 风险清单

| ID | 风险 | 公式判定 | 级别 | 缓解 | 状态 |
|----|------|---------|:---:|------|:---:|
| **R-R1** | relay_update.py 与 .oc_session.json 并发写冲突 | 用户可感知=是(relay行消失/错乱); 功能阻断=否(collector 本应 best-effort); workaround=是(删除旧文件重跑) | **MINOR** | 两个文件独立，无共享锁；relay 原子写保证不产生半写文件 | 已缓解 |
| **R-R2** | collector 读取 relay 时文件正在被 rename | 用户可感知=可能(瞬态读不到); 功能阻断=否(下个tick读到); workaround=是(30s自动恢复) | **MINOR** | 原子 rename + collector best-effort = 无崩溃，最多漏 1 tick | 已缓解 |
| **R-R3** | game-engine LLM agent 忘记调用 relay_update.py | 用户可感知=是(Frank看不到接力进度); 功能阻断=否(watchdog仍正常播报); workaround=是(manual trigger) | **MAJOR** | SOUL.md prompt 铁律: "每个状态变更必须先调 relay_update.py" + 阶段0强制调用 | 已缓解 |
| **R-R4** | relay 文件残留在 OC 结束后 | 用户可感知=是(Frank看到过期relay状态); 功能阻断=否(新session会覆盖); workaround=是(等待新session启动) | **MINOR** | OC SOUL.md 含清理规则 (L302)，随 .oc_session.json 一起删除 | 已缓解 |
| **R-R5** | relay_update.py 不在 cron 环境 PATH 中 | 用户可感知=是(relay cron 报错); 功能阻断=否(通过绝对路径调用); workaround=是(改 path) | **MAJOR** | game-engine SOUL.md 使用绝对路径 `/root/.hermes/profiles/orchestrator/scripts/relay_update.py` | 已缓解 |
| **R-R6** | relay phase 枚举值与 collector 输出不匹配 (新增 phase) | 用户可感知=可能(Frank看到未知phase名); 功能阻断=否(透传); workaround=是(collector透传不崩溃) | **MINOR** | collector `read_relay_state()` 透传任意 phase 值，不校验 | 已缓解 |
| **R-R7** | SOUL.md 规则与实际 LLM 行为不一致 | 用户可感知=是(Frank看不到接力状态); 功能阻断=否(watchdog仍播报); workaround=否(LLM不可控) | **MAJOR** | 7阶段模板 prompt 结构化指令 + 铁律规则。需验收期观察 | 需观察 |

### 9.2 分级汇总

| 级别 | 数量 | 项目 |
|:---:|:---:|------|
| BLOCKER | **0** | — |
| MAJOR | 3 | R-R3 (LLM 忘记 relay), R-R5 (relay PATH), R-R7 (SOUL.md 行为一致) |
| MINOR | 4 | R-R1, R-R2, R-R4, R-R6 |
| SUGGESTION | **0** | — |

### 9.3 MAJOR 项详细判定

**R-R3 — LLM 忘记 relay_update.py**  
`用户可感知=是 AND (功能阻断=否 BUT 体验严重退化) → MAJOR`  
Frank 看不到接力过程 = 方案 C 的核心价值（消除黑盒）未达成。风险在 LLM 不可控性，但 SOUL.md 7 阶段模板 + 铁律规则 + 阶段 0 强制调用已作为缓解。建议验收期观察至少 3 个完整接力周期。

**R-R5 — relay_update.py PATH**  
`用户可感知=是 AND 功能阻断=否(有 workaround: 改绝对路径) → MAJOR`  
如果调用失败，接力 cron 报错但不会死。game-engine SOUL.md 已使用绝对路径确保可靠性。

**R-R7 — SOUL.md 行为一致性**  
`用户可感知=是 AND 功能阻断=否 BUT 体验严重退化 → MAJOR`  
SOUL.md 规则不等于 LLM 运行时行为。结构化的 7 阶段模板是缓解，但 LLM 可能跳过阶段。建议在验收期建立 relay 状态监控：如果连续 3 tick 无 relay 更新 → 告警。

---

## 10. 发布门禁检查表

对照 `docs/standards/qa-finding-classification.md` §10:

```
门禁条件: BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定申诉

当前评估: ✅ 可发布
  BLOCKER:    0 ✅
  MAJOR:      3 ✅ (≤3, 边界)
  安全漏洞:    0 ✅
  未裁定申诉:  0 ✅
```

### 10.1 条件性通过说明

MAJOR=3 处于门禁边界（≤3），建议验收期采取以下措施：

1. **R-R3/R-R7 观察期**：发布后监控前 3 个 OC 接力周期，确认：
   - 每个 tick 有 relay 更新（phase 变化）
   - Frank 看到完整接力过程（polling→dispatching→waiting→completed）
   - 无连续 >2 tick 的 relay 状态冻结

2. **R-R5 一票确认**：发布前执行一次 `python3 /root/.hermes/profiles/orchestrator/scripts/relay_update.py polling "smoke"` 确认 PATH 可达。

3. **如果验收期 R-R3 或 R-R7 升级为 BLOCKER**（连续 >3 个 OC 接力周期无 relay 更新），触发 MAJOR→BLOCKER 升级流程。

---

## 11. 附录: 测试脚本

### A. relay_update.py 单元测试脚本

```bash
#!/bin/bash
# tests/scripts/test_relay_update.sh
# 运行方式: bash tests/scripts/test_relay_update.sh

RELAY_SCRIPT="/root/.hermes/profiles/orchestrator/scripts/relay_update.py"
TMPDIR=$(mktemp -d)
export WATCHDOG_RELAY_FILE="$TMPDIR/.oc_relay.json"
PASS=0; FAIL=0

assert_exit() {  # $1=test_name $2=expected_exit $3...=args
    if python3 "$RELAY_SCRIPT" "${@:3}" >/dev/null 2>&1; then actual=0; else actual=$?; fi
    if [ "$actual" = "$2" ]; then echo "  PASS: $1"; ((PASS++)); else echo "  FAIL: $1 (expected exit $2, got $actual)"; ((FAIL++)); fi
}

echo "=== relay_update.py Unit Tests ==="

# Phase validation
assert_exit "valid polling"    0 "polling"
assert_exit "valid dispatching" 0 "dispatching"
assert_exit "valid waiting"     0 "waiting"
assert_exit "valid completed"   0 "completed"
assert_exit "valid error"       0 "error"
assert_exit "invalid phase"     1 "unknown"
assert_exit "no args"           1

# Detail truncation
python3 "$RELAY_SCRIPT" polling "test detail" > /dev/null && echo "  PASS: detail short" && ((PASS++)) || { echo "  FAIL: detail short"; ((FAIL++)); }
LONG=$(python3 -c "print('x'*80)")
python3 "$RELAY_SCRIPT" polling "$LONG" > /dev/null && echo "  PASS: detail long" && ((PASS++)) || { echo "  FAIL: detail long"; ((FAIL++)); }

# Atomic write: no .tmp residue
python3 "$RELAY_SCRIPT" polling "atomic test" > /dev/null
[ ! -f "$TMPDIR/.oc_relay.json.tmp" ] && echo "  PASS: no .tmp residue" && ((PASS++)) || { echo "  FAIL: .tmp residue"; ((FAIL++)); }
[ -f "$TMPDIR/.oc_relay.json" ] && echo "  PASS: .oc_relay.json exists" && ((PASS++)) || { echo "  FAIL: .oc_relay.json missing"; ((FAIL++)); }

# JSON validity
python3 -c "import json; json.load(open('$TMPDIR/.oc_relay.json'))" && echo "  PASS: JSON valid" && ((PASS++)) || { echo "  FAIL: JSON invalid"; ((FAIL++)); }

rm -rf "$TMPDIR"
echo "=== Results: $PASS PASS, $FAIL FAIL ==="
```

### B. collector relay 集成测试脚本

```bash
#!/bin/bash
# tests/scripts/test_collector_relay.sh
# 需要预先准备 mock kanban.db 和 session file

COLLECTOR="/root/.hermes/profiles/orchestrator/scripts/kanban_collector.py"
RELAY="/root/.hermes/profiles/orchestrator/scripts/relay_update.py"
TMPDIR=$(mktemp -d)

export WATCHDOG_SESSION_FILE="$TMPDIR/.oc_session.json"
export WATCHDOG_RELAY_FILE="$TMPDIR/.oc_relay.json"
export WATCHDOG_KANBAN_DIR="$TMPDIR/boards"

# 创建 mock kanban board
mkdir -p "$TMPDIR/boards/testboard"
python3 -c "
import sqlite3
db = sqlite3.connect('$TMPDIR/boards/testboard/kanban.db')
db.execute('CREATE TABLE tasks (id TEXT, status TEXT, archived INTEGER DEFAULT 0, completed_at REAL)')
db.execute(\"INSERT INTO tasks VALUES ('t1', 'ready', 0, NULL)\")
db.execute(\"INSERT INTO tasks VALUES ('t2', 'running', 0, NULL)\")
db.execute(\"INSERT INTO tasks VALUES ('t3', 'done', 0, 1750600200.0)\")
db.commit()
"

# 创建 session file
python3 -c "
import json, time
json.dump({
    'session_id': 'test_session', 'started_at': time.time(),
    'updated_at': time.time(), 'status': 'active',
    'max_age_seconds': 600, 'project_boards': ['testboard']
}, open('$TMPDIR/.oc_session.json', 'w'))
"

echo "=== Collector Relay Integration Tests ==="

# TC-R3-01: relay exists
python3 "$RELAY" dispatching "QA task t_abc" > /dev/null
OUT=$(python3 "$COLLECTOR" 2>/dev/null)
echo "$OUT" | grep -q "🔄 接力: dispatching" && echo "  PASS: relay in output" || echo "  FAIL: relay in output"

# TC-R3-02: no relay file
rm -f "$TMPDIR/.oc_relay.json"
OUT=$(python3 "$COLLECTOR" 2>/dev/null)
echo "$OUT" | grep -qv "🔄 接力:" && echo "  PASS: no relay line" || echo "  FAIL: no relay line"

# TC-R3-03: empty relay file
echo "" > "$TMPDIR/.oc_relay.json"
OUT=$(python3 "$COLLECTOR" 2>/dev/null)
echo "$OUT" | grep -qv "🔄 接力:" && echo "  PASS: empty relay no crash" || echo "  FAIL: empty relay no crash"

# TC-R3-04: corrupt relay file
echo "{broken" > "$TMPDIR/.oc_relay.json"
python3 "$COLLECTOR" > /dev/null 2>&1 && echo "  PASS: corrupt relay no crash" || echo "  FAIL: corrupt relay crash"

rm -rf "$TMPDIR"
echo "=== Done ==="
```

---

> **QA 签署**: game-qa | 2026-07-10 | 测试方案 v1.0
> 
> **判定依据**: 所有风险定级按 `docs/standards/qa-finding-classification.md` §1.2 五步判定公式执行，逐条对照。
> **发布建议**: 条件性通过 — MAJOR=3 边界，需验收期观察 R-R3/R-R7。
