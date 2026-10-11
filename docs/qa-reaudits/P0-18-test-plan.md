# P0-18 测试方案：Watchdog 看板监控 — 三态状态机 / 信号协议 / 8 场景边缘

> 版本：v1.0 | 状态：Draft
> 编制日期：2026-07-09
> 编制人：game-qa（QA）
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0
> 架构依据：`tasks_watchdog/docs/architecture.md` v2.0（高见远）
> PRD 依据：`docs/prd-p0-18-watchdog.md` v1.0（许清楚）
> 被测对象：`kanban_watchdog.py`（v3→v2.0） + Cron Job + 事件钩子 skill

---

## 目录

1. [背景与范围](#1-背景与范围)
2. [被测对象概览](#2-被测对象概览)
3. [测试矩阵总览](#3-测试矩阵总览)
4. [L1: 脚本导入与路径绑定](#4-l1-脚本导入与路径绑定)
5. [L2: 三态状态机正确性](#5-l2-三态状态机正确性)
6. [L3: 信号协议验证](#6-l3-信号协议验证)
7. [L4: 8 场景边缘 Case](#7-l4-8-场景边缘-case)
8. [L5: 集成回归测试](#8-l5-集成回归测试)
9. [L6: PRD 合规验证](#9-l6-prd-合规验证)
10. [Findings 分级](#10-findings-分级)
11. [发布门禁评估](#11-发布门禁评估)

---

## 1. 背景与范围

### 1.1 原始任务

| 字段 | 值 |
|------|-----|
| P0 编号 | P0-18 |
| 标题 | watchdog 实现：orchestrator cron + 事件钩子 |
| 架构裁定 | Profile 对等（orchestrator → Feishu）、事件优先轮询兜底、no_agent 确定性脚本 |
| 版本起点 | v3 脚本（`kanban_watchdog.py`，120 行）→ v2.0（arch v2.0 规约） |
| 产出 | 改造后 watchdog 脚本 + cron job（2min）+ 事件钩子 skill + 本测试方案 |

### 1.2 测试目标

P0-18 将架构 v2.0 方案落地为可运行的监控系统。测试需验证：

| 层级 | 目标 | 覆盖内容 |
|------|------|---------|
| **L1: 脚本导入与路径绑定** | 脚本结构完整性，路径常量与 arch §C 一致 | import、PATH 常量、文件存在性、JSON 序列化 |
| **L2: 三态状态机** | ACTIVE↔QUIET↔SILENT 四种转换路径全部正确 | 状态扫描、silent_ticks 累加/重置、announced_done 标记 |
| **L3: 信号协议** | `.kanban_resume` 创建/检测/删除生命周期完整 | orchestrator touch → watchdog 检测→删除→复位 |
| **L4: 8 场景边缘** | arch §4 边缘矩阵全覆盖 | 轮询盲区、空 board、DB 损坏、并发、Frank 手动 |
| **L5: 集成回归** | script + cron + hermes send 端到端 | cron 创建、hermes send 调用、Feishu 投递 |
| **L6: PRD 合规** | BLOCKER 堆积告警、SLA 超时、静默策略 | 4 条告警条件全部验证 |

### 1.3 测试范围说明

- **覆盖**：watchdog 脚本逻辑（状态机/信号/输出格式）、cron job 配置正确性、事件钩子 skill 结构、PRD 告警条件
- **不覆盖**：`hermes send` 内部实现（hermes 项目）、Feishu API 可用性（外部依赖）、gateway 进程管理（hermes 项目）、kanban.db schema（P0-02 已覆盖）
- **单元测试**：纯 Python 逻辑测试（状态机/元数据读写/信号文件）应在 < 2s 内完成
- **集成测试**：涉及真实 kanban.db 和 hermes send 的测试需要 orchestrator profile 环境

---

## 2. 被测对象概览

### 2.1 文件清单

| 文件 | 行数 | 性质 | 变更类型 |
|------|:---:|------|:---:|
| `scripts/kanban_watchdog.py` | ~140（目标） | 主脚本（v3→v2.0 改造） | 修改 |
| `scripts/.kanban_state.json` | 运行时 | 任务状态快照 | 运行时生成 |
| `scripts/.kanban_watchdog_meta.json` | 运行时 | 静默/元数据 | 运行时生成 |
| `scripts/.kanban_resume` | 0B | 信号文件 | orchestrator 创建 |
| `skills/kanban-event-hooks/SKILL.md` | ~50（目标） | 事件钩子 skill | 新建 |

> 注：以上路径均相对于 `/root/.hermes/profiles/orchestrator/`。

### 2.2 三态状态机（被测核心）

```
                    ┌─────────────────────────────────┐
                    │                                 │
                    ▼                                 │
              ┌─────────┐                             │
     ────────▶│ ACTIVE  │◀────────────────────        │
              │ (正常)   │                        │   │
              └────┬────┘                         │   │
                   │                              │   │
                   │ 无活跃任务 × 1 tick           │   │
                   ▼                              │   │
              ┌─────────┐                         │   │
              │ QUIET   │──── 无活跃任务 × 2 tick ─┼───┘
              │ (过渡)   │    (仍保留 ACTIVE)       │
              └────┬────┘
                   │
                   │ 连续 3 ticks 无活跃任务
                   │ (发出 "即将静默" 通知)
                   ▼
              ┌─────────┐
              │ SILENT  │──── .kanban_resume 出现 ────▶ ACTIVE
              │ (静默)   │
              └─────────┘
                   │
                   │ stdout = ""
                   │ → cron 不投递 → 零消息
                   ▼
                 (零消息)

转换规则：
  ACTIVE → QUIET:   当前 tick 无 running/blocked 任务，且 silent_ticks=0→1
  QUIET  → ACTIVE:  当前 tick 出现 running/blocked 任务（不发 "即将静默"）
  QUIET  → SILENT:  silent_ticks 累计 ≥ 3（第 1 tick 发 "⚪ 即将静默"）
  SILENT → ACTIVE:  检测到 .kanban_resume → 删除文件 → silent_ticks=0
  SILENT → SILENT:  stdout=""，不输出任何内容
```

### 2.3 信号协议

```
信号文件：.kanban_resume
  创建者：orchestrator（事件钩子，kanban_create 成功后 touch）
  消费者：kanban_watchdog.py（每 tick 检测，存在则删除 + 复位）
  语义：touch → 通知 watchdog 有新任务，应立即恢复播报
  协议：单向、幂等、不依赖文件内容
```

### 2.4 架构 v2.0 相对 v3 脚本的 5 项修改（arch §2.5）

| # | 修改 | 优先级 | 测试覆盖 |
|---|------|:---:|:---:|
| M1 | 增加 `.kanban_resume` 信号检测 | 🔴 | L3 |
| M2 | 实现真静默（SILENT 状态无 stdout） | 🔴 | L2/L4 |
| M3 | 修正完成通知时机（仅 ACTIVE→SILENT 边界一次） | 🟡 | L2 |
| M4 | 增加 QUIET→ACTIVE 恢复路径 | 🟡 | L2 |
| M5 | DB 异常日志写 stderr | 🟢 | L4 |

---

## 3. 测试矩阵总览

| 层级 | 名称 | 用例数 | 优先级 | 预计耗时 | 类型 |
|:---:|------|:---:|:---:|:---:|:---:|
| L1 | 脚本导入与路径绑定 | 8 | P1 | < 0.5s | 单元 |
| L2 | 三态状态机正确性 | 14 | P0 | < 0.5s | 单元 |
| L3 | 信号协议验证 | 11 | P0 | < 0.5s | 单元 |
| L4 | 8 场景边缘 Case | 12 | P0 | < 1s | 单元+集成 |
| L5 | 集成回归测试 | 9 | P1 | — | 集成/手动 |
| L6 | PRD 合规验证 | 8 | P0 | — | 审查 |
| **合计** | | **62** | | | |

---

## 4. L1: 脚本导入与路径绑定

验证脚本结构完整、路径常量与 arch §C 一致。

| ID | 测试用例 | 验证方法 | 预期结果 | 优先级 |
|----|---------|---------|---------|:---:|
| TC-L1-01 | 脚本文件存在且可解析 | `python3 -c "import ast; ast.parse(open('kanban_watchdog.py').read())"` | 无 SyntaxError | P0 |
| TC-L1-02 | 顶层常量 STATE_FILE 路径正确 | `STATE_FILE.endswith('.kanban_state.json')` | 指向 orchestrator scripts 目录 | P0 |
| TC-L1-03 | 顶层常量 META_FILE 路径正确 | `META_FILE.endswith('.kanban_watchdog_meta.json')` | 指向 orchestrator scripts 目录 | P0 |
| TC-L1-04 | KANBAN_ROOT 路径正确 | `KANBAN_ROOT.endswith('kanban/boards')` | 指向 `/root/.hermes/kanban/boards` | P0 |
| TC-L1-05 | RESUME_FILE 常量存在（v2.0 新增） | `os.path.join(os.path.dirname(__file__), '.kanban_resume')` 或等价 | 路径常量已定义 | P0 |
| TC-L1-06 | load_json() 容错：文件不存在 | 调用 `load_json('/nonexistent')` | 返回 `{}`（不抛异常） | P1 |
| TC-L1-07 | save_json() 创建目录 | 写入临时目录下的新文件 | 自动 mkdir，写入成功 | P1 |
| TC-L1-08 | get_all_boards() 空目录 | 模拟 KANBAN_ROOT 为空 | 返回 `[]`（不抛异常） | P1 |

---

## 5. L2: 三态状态机正确性

验证状态机 4 条转换路径 + silent_ticks 计数 + announced_done 标记。

### 5.1 ACTIVE ↔ QUIET 转换

| ID | 测试用例 | 前置条件 | 触发动作 | 预期结果 | 优先级 |
|----|---------|---------|---------|---------|:---:|
| TC-L2-01 | ACTIVE→QUIET：首次无任务 | silent_ticks=0, has_active=True→False | 1 tick 无 running/blocked | silent_ticks=1, 发送 "即将静默" | P0 |
| TC-L2-02 | QUIET→ACTIVE：新任务出现 | silent_ticks=1, 本 tick has_active=True | 出现 running 任务 | silent_ticks=0, 不发 "即将静默" | P0 |
| TC-L2-03 | QUIET 中间态：第二个无任务 tick | silent_ticks=1→2 | 连续无任务 | silent_ticks=2, output=""（不输出） | P0 |
| TC-L2-04 | QUIET→ACTIVE：blocked 任务恢复 | silent_ticks=2, 本 tick has blocked | blocked 任务出现 | silent_ticks=0, 正常播报 | P1 |

### 5.2 QUIET → SILENT 转换

| ID | 测试用例 | 前置条件 | 触发动作 | 预期结果 | 优先级 |
|----|---------|---------|---------|---------|:---:|
| TC-L2-05 | SILENT 进入：silent_ticks ≥ 3 | silent_ticks=2→3，无任务 | 第 3 个无任务 tick | output=""（真静默），announced_done=False | P0 |
| TC-L2-06 | SILENT 保持：第 4 个无任务 tick | silent_ticks=3→4，无任务 | 第 4 个无任务 tick | output=""，silent_ticks 继续累加 | P0 |
| TC-L2-07 | "即将静默"只在第 1 tick 发送 | silent_ticks=0→1（带 announced_done=False） | 第一个无任务 tick | 输出 "⚪ 即将静默"，announced_done=True | P0 |
| TC-L2-08 | QUIET tick 2/3 不输出 | silent_ticks=1→2 和 2→3 | 过渡期 tick | output=""（不输出任何内容） | P0 |

### 5.3 SILENT → ACTIVE 恢复

| ID | 测试用例 | 前置条件 | 触发动作 | 预期结果 | 优先级 |
|----|---------|---------|---------|---------|:---:|
| TC-L2-09 | SILENT→ACTIVE：resume 信号触发 | silent_ticks=5, .kanban_resume 存在 | tick 检测到信号文件 | 删除 .kanban_resume, silent_ticks=0, 正常播报 | P0 |
| TC-L2-10 | 无 resume 信号时 SILENT 保持 | silent_ticks=5, 无 .kanban_resume | tick 执行 | output=""，silent_ticks=6 | P0 |

### 5.4 状态元数据完整性

| ID | 测试用例 | 验证方法 | 预期结果 | 优先级 |
|----|---------|---------|---------|:---:|
| TC-L2-11 | announced_done 仅重置于 has_active=True | has_active=True 时 | announced_done=False | P1 |
| TC-L2-12 | total_ticks 单调递增 | 连续 3 tick | total_ticks 每次 +1，从不回退 | P1 |
| TC-L2-13 | silent_ticks 边界：不会溢出到恢复后 | has_active=True 后 | silent_ticks 立即归零 | P1 |
| TC-L2-14 | 元数据 JSON 合法 | `python3 -m json.tool <.kanban_watchdog_meta.json>` | JSON 解析成功 | P0 |

---

## 6. L3: 信号协议验证

验证 `.kanban_resume` 文件的创建/检测/删除全生命周期。

| ID | 测试用例 | 前置条件 | 触发动作 | 预期结果 | 优先级 |
|----|---------|---------|---------|---------|:---:|
| TC-L3-01 | 检测到 .kanban_resume → 删除 | 文件存在，silent_ticks=5 | watchdog tick | 文件被删除，silent_ticks=0 | P0 |
| TC-L3-02 | 检测到 .kanban_resume → 状态复位 | 文件存在 | 删除后立即扫描任务 | announced_done=False, 正常播报 | P0 |
| TC-L3-03 | .kanban_resume 不存在 → 无操作 | 文件不存在，silent_ticks=5 | watchdog tick | silent_ticks 继续累加（不抛异常） | P0 |
| TC-L3-04 | orchestrator touch（创建信号） | SILENT 状态，orchestrator kanban_create | `touch .kanban_resume` | 空文件创建成功 | P0 |
| TC-L3-05 | 幂等性：连续 touch 多次 | 文件已存在 | 再次 touch | 不报错（touch 是幂等操作） | P1 |
| TC-L3-06 | 并发：touch 和 rm 竞态 | 文件存在，同时有删除和创建 | 无崩溃 | 最终状态一致（文件不存在 = watchdog 赢了，或文件存在 = 下次 tick 处理） | P1 |
| TC-L3-07 | 信号文件内容无关 | 非空文件（有内容） | watchdog 检测到 | 仍然删除（检查存在性，不读内容） | P0 |
| TC-L3-08 | 恢复后立即输出心跳 | 从 SILENT 恢复，has_active=True | 同一 tick 内 | 有 stdout 输出（含 running/blocked 列表） | P0 |
| TC-L3-09 | 恢复后不重复发"即将静默" | 从 SILENT → ACTIVE，再次进入 QUIET | 任务再次完成 | 正常进入静默流程（announced_done 已重置） | P1 |
| TC-L3-10 | orchestrator 事件钩子存在 .kanban_resume touch 指令 | 检查事件钩子 skill | SKILL.md 包含 `touch .kanban_resume` | 指令存在且路径正确 | P1 |
| TC-L3-11 | 多个 orchestrator 子任务并发 touch | 同一 tick 内多次 kanban_create | 多次 touch | 无竞态崩溃（touch 幂等） | P1 |

---

## 7. L4: 8 场景边缘 Case

覆盖 architecture.md §4 的 8 个边缘场景 + 额外发现。

### 7.1 Arch §4 场景矩阵

| ID | Arch # | 场景 | 预期行为 | 验证方法 | 优先级 |
|----|:---:|------|---------|---------|:---:|
| TC-L4-01 | 1 | 任务在两次轮询间完成 | 轮询捕获不到 running 状态 → 不报 bug，但可能漏通知 | 模拟：tick N 无任务，tick N+1 出现→完成→tick N+2 无任务 | 事件钩子应在 created/done 时推送 | P0 |
| TC-L4-02 | 2 | 无 board 存在 | `get_all_boards()` 返回空 → 算无任务 → 静默 | 清空 KANBAN_ROOT → 运行 | output=""（算无任务），不崩溃 | P0 |
| TC-L4-03 | 3 | board 存在但 kanban.db 损坏 | 跳过该 board（try/except） | 替换为无效 SQLite 文件 → 运行 | 不崩溃，其他 board 正常扫描 | P0 |
| TC-L4-04 | 4 | 同一 tick 内既有新任务又有已完成 | diff 覆盖新增+删除 | 模拟：prev 有 A/B，current 有 B/C | 输出 A→done 和 新增 C | P0 |
| TC-L4-05 | 5 | orchestrator 连续创建 3 个任务 | 每次 kanban_create 都 touch resume | 连续 3 次 touch → watchdog tick | 不报错，恢复后正常播报 | P1 |
| TC-L4-06 | 6 | SILENT 状态删除所有任务（无新任务创建） | 保持 SILENT | 所有任务 done/archived，无 .kanban_resume | output=""，静默保持 | P0 |
| TC-L4-07 | 7 | Frank 手动创建任务（非 orchestrator） | 轮询检测到 → 播报 | 直接往 kanban.db 插入 running 任务 | 2min 内 tick 检测到，播报（无事件钩子） | P1 |
| TC-L4-08 | 8 | 并发：事件钩子 + 轮询同时发送 | 可能重复消息（可接受） | 模拟同时 hermes send | 两条消息都送达（Frank 收到两份，不要紧） | P1 |

### 7.2 额外边缘 Case

| ID | 场景 | 预期行为 | 优先级 |
|----|------|---------|:---:|
| TC-L4-09 | .kanban_state.json 损坏（非 JSON） | `load_json()` 捕获 JSONDecodeError → 返回 {} | P1 |
| TC-L4-10 | .kanban_watchdog_meta.json 损坏 | 同上，返回 default=全零 dict | P1 |
| TC-L4-11 | Kanban DB locked (SQLITE_BUSY) | `get_board_tasks()` excepted → 返回空列表，不崩溃 | P0 |
| TC-L4-12 | 1000+ 任务规模性能 | 模拟大量任务 → tick 执行时间 < 500ms | P1 |

---

## 8. L5: 集成回归测试

验证 script + cron + hermes send 端到端流程。

| ID | 测试用例 | 验证点 | 类型 | 优先级 |
|----|---------|--------|:---:|:---:|
| TC-L5-01 | 手动运行脚本（无 cron） | `python3 kanban_watchdog.py` → 输出格式正确，进程退出码 0 | 手动 | P0 |
| TC-L5-02 | Cron job 创建命令正确 | `hermes cronjob create --schedule "every 2m" --script "kanban_watchdog.py" --no_agent --deliver ...` | 审查 | P1 |
| TC-L5-03 | Cron job 在 orchestrator profile 下 | `hermes --profile orchestrator cronjob list` 可见 watchdog job | 手动 | P1 |
| TC-L5-04 | hermes send 投递格式 | Feishu 消息包含 emoji（📋🔄🚫⚪✅）+ 时间戳 + 任务摘要 | 手动 | P0 |
| TC-L5-05 | 事件钩子：kanban_create → touch + send | orchestrator 执行 `kanban_create` 后调用 `touch .kanban_resume` + `hermes send` | 集成 | P0 |
| TC-L5-06 | 事件钩子：kanban_block → send | orchestrator 执行 `kanban_block` 后调用 `hermes send` | 集成 | P1 |
| TC-L5-07 | 事件钩子：kanban_complete → 归零检测 | 当前 board 无剩余 running/blocked → 可选推送 | 集成 | P1 |
| TC-L5-08 | 端到端：创建→心跳→完成→静默→恢复 | 完整生命周期：创建任务 → 2min 心跳 → done → 6min 静默 → 新任务 touch resume → 恢复 | 手动 | P0 |
| TC-L5-09 | 多 board 扫描正确性 | 至少 2 个 board 各有任务 → 同时播报 | 手动 | P1 |

---

## 9. L6: PRD 合规验证

对照 `docs/prd-p0-18-watchdog.md` v1.0 逐条验证。

| ID | PRD 条款 | 验证点 | 合规状态 | 优先级 |
|----|---------|--------|:---:|:---:|
| TC-L6-01 | §1 监控范围：全域所有 kanban board | `get_all_boards()` 遍历所有 board | 待测 | P0 |
| TC-L6-02 | §1 事件：kanban_create → 即时推送 | 事件钩子 skill 含 kanban_create 后 hermes send | 待测 | P0 |
| TC-L6-03 | §1 事件：kanban_block → 阻塞通知 | 事件钩子 skill 含 kanban_block 后 hermes send "🚫" | 待测 | P1 |
| TC-L6-04 | §1 事件：kanban_complete → 归零检测 | 事件钩子 skill 含 kanban_complete 后检查剩余活跃任务 | 待测 | P1 |
| TC-L6-05 | §2 BLOCKER 堆积告警：连续 2 tick 存在未解决 BLOCKER | 脚本需输出 BLOCKER 计数，或独立告警逻辑 | 待测 | P0 |
| TC-L6-06 | §2 无活跃任务：3 tick 后 "⚪ 全部完成" → 静默 | silent_ticks ≥ 3 触发静默 | 待测 | P0 |
| TC-L6-07 | §2 恢复：新任务 touch 信号文件 → 即时唤醒 | .kanban_resume 检测机制 | 待测 | P0 |
| TC-L6-08 | §3 投递渠道：VA Bot DM 统一通知 | hermes send target 为飞书 open_id | 待测 | P0 |

---

## 10. Findings 分级

### 10.1 分级标准（采用 P0-14 §1.2 判定公式）

对本方案发现的 bug，按以下标准定级：

| 级别 | 判定条件（watchdog 语境） |
|------|----------------------|
| **BLOCKER** | 静默状态下仍持续输出（违反 "真静默" 合约）→ Frank 被消息轰炸 |
| | .kanban_resume 信号未被检测 → 永远无法从静默恢复 |
| | 脚本崩溃导致 cron 永久不输出（stdout="" → Frank 以为一切静默） |
| **MAJOR** | 单次 tick 漏报（但下次恢复） |
| | 状态文件损坏后恢复到错误状态（可手动修复） |
| | 事件钩子未触发（但轮询 2min 内覆盖） |
| **MINOR** | 输出格式轻微偏差（emoji 错误、标题截断） |
| | DB 异常未被日志记录（但有容错） |
| **SUGGESTION** | 代码风格/重构建议 |
| | 性能优化（当前 tick < 100ms，无需优化） |

### 10.2 已知风险（预分级）

| # | 风险描述 | 预分级 | 缓解 |
|---|---------|:---:|------|
| R1 | Cron scheduler 跳过 tick → 最长 4min 盲区 | MAJOR | 事件钩子 0s 延迟覆盖 |
| R2 | .kanban_resume 信号丢失（orchestrator 未 touch） | MINOR | 轮询 2min 内自动发现新任务 |
| R3 | 并发 touch + rm 竞态 | MINOR | touch 幂等，下次 tick 处理 |
| R4 | Gateway 进程挂掉 → cron + 事件钩子同时失效 | MAJOR | 需外部监控（arch §6 Plan B） |

---

## 11. 发布门禁评估

### 11.1 门禁条件

依据 `qa-finding-classification.md` §10：

```
BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定的申诉
```

### 11.2 P0-18 发布前 Checklist

| # | 检查项 | 通过条件 |
|---|--------|---------|
| 1 | 所有 L2 状态机测试 PASS（14/14) | BLOCKER=0 |
| 2 | 所有 L3 信号协议测试 PASS（11/11） | BLOCKER=0 |
| 3 | L4 8 场景边缘测试 PASS（8/8） | MAJOR≤3 |
| 4 | 端到端集成测试通过（TC-L5-08） | 手动确认 |
| 5 | Cron job 运行满 6 个周期无异常 | 心跳持续输出 |
| 6 | 真静默验证：SILENT 状态 5 分钟无消息 | Frank 确认未收到消息 |
| 7 | PRD §2 全部 4 条告警条件覆盖 | L6 全部 PASS |
| 8 | 事件钩子 skill 文件存在且语法正确 | L3 TC-L3-10 PASS |

---

## 附录 A：测试执行环境要求

| 环境变量/配置 | 值/说明 |
|-------------|------|
| Profile | orchestrator（`.hermes/profiles/orchestrator/`） |
| Feishu | `platforms.feishu.enabled: true` |
| KANBAN_ROOT | `/root/.hermes/kanban/boards/` |
| Python | ≥ 3.8（标准库：json, os, sqlite3, datetime） |

## 附录 B：Mock 测试策略

由于 watchdog 脚本依赖真实 kanban.db 和 hermes CLI，单元测试采用 mock 策略：

- **可 mock 的**：`get_all_boards()` 返回列表、`get_board_tasks()` 返回任务列表、`load_json()`/`save_json()` 文件 I/O
- **不可 mock（集成验证）**：hermes send 投递、cron scheduler 调度、真实 Feishu 消息
- **测试方式**：提取 `main()` 的核心逻辑为可注入依赖的函数，或使用 `unittest.mock.patch` 替换 I/O

## 附录 C：与 P0-14/P0-15 的交叉依赖

| 依赖 | 说明 |
|------|------|
| P0-14 §8 SLA | P0-18 PRD 中的 SLA 超时告警依赖 P0-14 的 SLA 定义（BLOCKER 4h / MAJOR 24h） |
| P0-14 §10 发布门禁 | P0-18 自身的发布门禁使用同一套标准 |
| P0-15 申诉机制 | watchdog 检测到 blocked 任务后，通过事件钩子推送 → 不涉及申诉流程 |

---

*本文档由 game-qa 基于 architecture.md v2.0 和 prd-p0-18-watchdog.md v1.0 编制，用于 P0-18 D1 测试方案交付。*
