# Roundtable B: 跨会话记忆 — 工程师发言

> 发言人: 寇豆码（工程师） | 日期: 2026-07-24 | 版本: v1.0
> 关联: Product 发言 (t_e78de385), Architect 发言 (t_eb378392), DREAM-003 (t_6f316778)

---

## 0. 实施前盘点

在写代码之前，先确认我们手里有什么：

| 组件 | 路径 | 行数 | 关键 API | 现状 |
|------|------|:---:|------|------|
| `mem0_tagged.py` | `/root/.hermes/profiles/orchestrator/scripts/` | 624 | `add_tagged()`, `search_tagged(state='verified')`, `mark_outdated()`, `expire_check()` | ✅ 55 测试全通，可 import 直接用 |
| `session_search` 工具 | Hermes 内置 | — | FTS5 全文检索，支持 `limit`, `sort` | ✅ 可用，但返回对话文本无结构 |
| `memory` 工具 | Hermes 内置 | — | 持久化事实，自动注入每轮系统提示 | ✅ 100% 确定性覆盖 |
| `build_context_files_prompt()` | Hermes `agent/prompt_builder.py` | — | 扫描 `.hermes.md` / `AGENTS.md` / `CLAUDE.md` 注入 system prompt | ✅ 静态文件扫描，**无动态脚本 hook** |
| OC SOUL.md | `~/.hermes/profiles/orchestrator/SOUL.md` | 96 | 5 条铁律 + 身份契约 + 任务地图 | ✅ 已有铁律注入先例 |

**关键发现**：Architect 的 L1 设计隐含了一个 Hermes 当前不具备的能力——「session 启动时自动运行脚本并将其输出注入 system prompt」。`build_context_files_prompt()` 只扫描静态文件，不执行脚本。这是 L1 实现的核心工程挑战。

---

## 1. Q1: L1「boot context 自动注入」技术上怎么实现？

Architect 提议的 `boot_context.py`（~30 行 Python）逻辑清晰，但「怎么注入到 system prompt 且在 SOUL.md 之前」需要解决。

### 1.1 问题拆解

Hermes session 启动时的 system prompt 注入顺序（实际观测）：
```
[1] Hermes 核心指令（KANBAN_GUIDANCE 等）
[2] SOUL.md 身份契约          ← profile 级，静态
[3] Project Context (.hermes.md)  ← 项目级，静态文件扫描
[4] Memory 自动注入            ← 持久化事实，动态但来自工具层
[5] 工具描述
```

Architect 要求在 [1] 和 [2] 之间注入 boot context。当前注入点：
- SOUL.md → 静态文件，profile 级
- `.hermes.md` → 静态文件，项目级，`build_context_files_prompt()` 扫描
- Memory → 动态，由 `memory` 工具自动注入，但位置在 [4]

**没有任何机制支持「session 启动时运行 Python 脚本并用其输出注入 system prompt」**。

### 1.2 三个实现路径

#### 路径 A：Cron 预生成 + 文件注入（推荐，0 引擎改动）

```
┌─────────────────────┐
│ Cron: boot_context  │  每 2-5 min 运行
│ (no_agent=True)     │
│                     │
│ 1. session_search(   │
│    limit=3,          │
│    sort='newest')    │
│ 2. mem0_tagged.      │
│    search_tagged(    │
│    state='verified') │
│ 3. 格式化为 markdown  │
│ 4. 写入文件          │
└──────────┬──────────┘
           │ 写入
           ▼
/root/.hermes/profiles/orchestrator/.boot_context.md
           │
           │ OC 启动时
           ▼
┌─────────────────────────────┐
│ 铁律 6 触发:                │
│ "首次回复前读取 boot_context│
│  文件以获取最近上下文"       │
└─────────────────────────────┘
```

**优点**：
- 零 Hermes 引擎改动
- `boot_context.py` 纯 Python，`mem0_tagged.py` 已可 import
- 铁律 6 同时覆盖「读 boot context 文件」和「session_search 深入」

**缺点**：
- 注入时机是 OC「读取文件」而非系统自动注入 → 依赖铁律 6 触发（可靠性 ~70-80%）
- boot context 可能滞后 2-5 分钟（cron 间隔）
- OC 读文件需要 `read_file` 工具调用，消耗 1 轮对话

**代码量**：`boot_context.py` ~60 行 + 1 个 cron job 创建命令。不是 30 行——需要处理 `session_search` 无结果、`mem0_tagged` 连接失败、文件写入原子性等边界情况。

#### 路径 B：修改 `build_context_files_prompt()`（需引擎改动，Architect 已否决）

在 Hermes 的 context file 扫描列表中新增 `.boot_context.md`，让 cron 写入的这个文件自动被 `build_context_files_prompt()` 发现并注入。

- 改动量：`prompt_builder.py` 加 ~5 行（新增文件名到扫描列表）
- 可靠性：100%（确定性注入）
- ⚠️ Architect 明确说「不修改 Hermes 引擎层」

**判断**：尊重 Architect 决策。如果铁律 6 效果不如预期（OC 频繁跳过），这是 fallback 方案。

#### 路径 C：Memory 写入替代文件注入

Cron 脚本调用 `mem0_tagged.add_tagged(content=boot_context, category='session_summary', source='auto')` 将 boot context 写为 memory 条目。

- **已被 Architect 否决**：memory 注入位置在 SOUL.md 之后，不是「之前」
- 且 `source='auto'` → `state='unverified'` → 默认被 `search_tagged(state='verified')` 过滤掉
- 需要额外的 verify 步骤，增加复杂度

### 1.3 结论：选路径 A

| 维度 | 路径 A (cron + 文件) | 路径 B (改引擎) | 路径 C (memory 写入) |
|------|:---:|:---:|:---:|
| 引擎改动 | 0 | ~5 行 | 0 |
| 注入可靠性 | ~70-80%（依赖铁律 6）| 100% | 100%（但注入位置错误）|
| 代码量 | ~60 行 Python + 1 cron | ~5 行 Python | ~30 行 Python |
| 实现工期 | 0.8-1.2h | 0.3h（如允许）| 0.5h |

**最终推荐路径 A**。如果铁律 6 的 L2 效果验证达标（OC 确实读了文件），路径 A 就够了。如果不达标，再考虑路径 B 作为兜底。

---

## 2. Q2: 三层架构的推进顺序和具体实施步骤？

### 2.1 同意 Architect 的推进顺序，但调整工期

| 优先级 | 事项 | Architect 工期 | Engineer 评估 | 理由 |
|:---:|------|:---:|:---:|------|
| **P0** | Layer 2: SOUL.md 铁律 6 | 0.1h | **0.1h** ✅ | 纯文本修改，零代码，同意 |
| **P0** | Layer 1: boot context 脚本 | 0.5h | **0.8-1.0h** ⚠️ | 需调研 cron + session_search 集成、边界处理、测试 |
| **P1** | 纠错自动写 memory | 0.1h | **0.15h** ✅ | SOUL.md 规则 + 引用 DREAM-003 API |
| **P2** | Layer 3: 会话结束摘要 | 0.2h | **0.3h** ⚠️ | Prompt engineering 需要迭代验证 |
| **合计** | | 0.9h | **1.35-1.55h** | |

### 2.2 具体实施步骤（按依赖关系排序）

```
Step 1: P0 铁律 6 — 零依赖，最先上线
  ├── 修改 /root/.hermes/profiles/orchestrator/SOUL.md
  │   └── 新增「铁律 6：新会话必须先回查上下文再回复」
  ├── 措辞采纳 Architect 建议：「首次回复 Frank 之前」而非「前三轮」
  └── 验证：人工在飞书开新会话，观察 OC 是否调 session_search + memory

Step 2: P0 boot context 脚本 — 依赖 mem0_tagged.py (已有)
  ├── 2a. 写 boot_context.py (~60 行)
  │   ├── import mem0_tagged, session_search
  │   ├── 查询最近 3 次会话标题 + 最后一条 user message
  │   ├── 查询 search_tagged(state='verified', exclude_expired=True)
  │   ├── 格式化为紧凑 markdown (~300 tokens)
  │   └── 写入 /root/.hermes/profiles/orchestrator/.boot_context.md
  ├── 2b. 创建 cron job (schedule='every 2m', no_agent=True, script='boot_context.py')
  └── 2c. 更新铁律 6：增加「读取 .boot_context.md」步骤

Step 3: P1 纠错自动写 memory — 依赖铁律 6 和 DREAM-003
  ├── SOUL.md 加规则：Frank 纠正 → OC 必须调 memory(action='add')
  └── 写入时引用 DREAM-003 的 category 语义

Step 4: P2 会话结束摘要 — 依赖 boot context
  ├── SOUL.md 加规则：会话接近结束 → 生成结构化摘要
  └── 摘要格式对齐 DREAM-003（可作为下次 boot context 的数据源）
```

### 2.3 Step 2 的关键实现细节

`boot_context.py` 伪代码（实际需要 ~60 行处理边界）：

```python
#!/usr/bin/env python3
"""boot_context.py — Generate recent context for new Hermes sessions.
Cron: every 2 min, no_agent=True.
Output: /root/.hermes/profiles/orchestrator/.boot_context.md
"""
import sys, os, time, json
from pathlib import Path

# ── Add scripts dir to path ──
SCRIPTS = Path("/root/.hermes/profiles/orchestrator/scripts")
sys.path.insert(0, str(SCRIPTS))

from mem0_tagged import Mem0Tagged, DEFAULT_DB as STATES_DB

OUTPUT = Path("/root/.hermes/profiles/orchestrator/.boot_context.md")
MAX_TOKENS = 400  # budget cap for the context block

def get_recent_sessions(limit=3):
    """Call session_search via Hermes session DB."""
    # session_search is a Hermes tool, not importable.
    # In cron: use sqlite3 directly on ~/.hermes/sessions.db
    # or call hermes CLI: hermes session list --json
    pass

def get_verified_memories():
    """Query DREAM-003 for verified, non-expired memories."""
    # mem0_tagged needs a mem0 client handle → from cron env
    pass

def format_context(sessions, memories) -> str:
    """Format as compact markdown, capped at MAX_TOKENS."""
    pass

def main():
    sessions = get_recent_sessions(3)
    memories = get_verified_memories()
    context = format_context(sessions, memories)
    OUTPUT.write_text(context)  # atomic — no partial reads

if __name__ == "__main__":
    main()
```

**实际代码量 breakdown**：
- 核心逻辑：~30 行
- 错误处理（DB 连接失败、mem0 不可用、session DB 为空）：~20 行
- 格式化 + token 预算控制：~10 行
- **合计 ~60 行**

---

## 3. Q3: 每层的实际代码改动量？

### Layer 2: 铁律 6（SOUL.md 修改）

```
改 1 个文件: /root/.hermes/profiles/orchestrator/SOUL.md
  + ~15 行（铁律 6 正文 + 失败模式定义）
  + ~2 行（铁律列表索引更新：5 条 → 6 条）

总计: ~17 行，0 新文件
```

### Layer 1: boot context 脚本

```
新 1 个文件: /root/.hermes/profiles/orchestrator/scripts/boot_context.py
  ~60 行 Python

新 1 个 cron job: hermes --profile orchestrator cronjob create
  1 条命令

改 1 个文件: SOUL.md（铁律 6 追加步骤）
  ~3 行

总计: ~63 行代码 + 1 条 cron 命令，2 个新/改文件
```

### P1: 纠错自动写 memory

```
改 1 个文件: SOUL.md
  + ~8 行（纠错记录规则）
  + ~2 行（DREAM-003 API 引用）

总计: ~10 行，0 新文件
```

### Layer 3: 会话结束摘要

```
改 1 个文件: SOUL.md
  + ~15 行（摘要生成规则 + 输出模板）

总计: ~15 行，0 新文件
```

### 汇总

| 层 | 新文件 | 改文件 | 代码行 | Cron |
|----|:---:|:---:|:---:|:---:|
| L2 铁律 6 | 0 | 1 (SOUL.md) | ~17 | 0 |
| L1 boot context | 1 (boot_context.py) | 1 (SOUL.md) | ~63 | 1 |
| P1 纠错 | 0 | 1 (SOUL.md) | ~10 | 0 |
| L3 摘要 | 0 | 1 (SOUL.md) | ~15 | 0 |
| **合计** | **1** | **1 (多次)** | **~105** | **1** |

---

## 4. Q4: 有哪些坑？

### 坑 1：L1 注入机制不存在（BLOCKER 级别）

**问题**：Hermes 没有「session 启动时自动运行脚本并注入输出到 system prompt」的能力。Architect 说「不修改引擎层」，但 L1 的核心就是引擎层功能。

**缓释**：用路径 A（cron 预生成 + 铁律 6 触发 OC 读取）绕过去。但这意味着 L1 的 100% 覆盖承诺打了折扣——实际注入可靠性回到 70-80%（铁律 6 的可靠性上限）。

**建议**：接受这个折中。如果铁律 6 验证效果不好（OC 频繁跳过），再考虑路径 B 引擎改动。不要一开始就改引擎。

### 坑 2：上下文窗口预算（MINOR 级别，但累积后变 MAJOR）

**当前 OC system prompt 占用估算**：
```
Hermes 核心指令     ~1500 tokens
SOUL.md           ~1200 tokens
Project Context   ~500 tokens
Memory 自动注入    ~200-3000 tokens（取决于历史记忆量）
工具描述           ~2000 tokens
─────────────────────────────────
合计（不含对话）    ~5200-8200 tokens
```

加 boot context（~300 tokens）后，system prompt 膨胀到 ~8500 tokens。100M token 预算下看起来不重要，但 memory 自动注入会随时间增长（现有 ~50 条 memory，每条 ~50 tokens = ~2500 tokens），boot context 又在 memory 之外新增内容。

**缓释**：boot context 严格控制在 300-400 tokens。用字符数硬限制，超了就截断。

### 坑 3：注入内容去重（MAJOR 级别）

**场景**：boot context 输出「关键记忆: 跨会话续接: 换 session 先查前情」，但 memory 工具已经自动注入了同一条 memory。OC 看到重复信息 → 混淆或浪费 token。

**当前无去重机制**。Architect 提到了「联邦检索的排序问题」，但没有提到去重。

**缓释**：boot context 输出中不列具体 memory 文本，只列「最近 3 次会话标题 + 关键记忆数量统计」（如「关键记忆: 7 条 verified」）。具体 memory 由 memory 工具自动注入。这样 boot context 是「导航」而非「数据」，天然不重复。

### 坑 4：session_search 在脚本中的 query 构造

**问题**：`session_search` 是 LLM 工具，不是 Python 函数。`boot_context.py` 在 cron 中运行时没有 LLM 可用（`no_agent=True`）。无法调用 `session_search(query=...)`。

**实际可行方案**：直接读 Hermes session DB（`~/.hermes/sessions/` 或 SQLite），用 SQL 查询最近的 session 元数据（标题、时间、最后一条消息）。这比 `session_search` 轻量得多，且完全确定性。

```sql
SELECT session_id, title, preview, updated_at
FROM sessions
ORDER BY updated_at DESC
LIMIT 3;
```

**风险**：Hermes session DB schema 不是公开 API，可能随版本变化。需要在 `boot_context.py` 中加 schema 版本检查和 fallback。

### 坑 5：铁律 6 的 LLM 跳过风险

**问题**：OC 在任务紧迫时（「Frank 很急」）可能跳过铁律 6。Architect 估计 15-25% 跳过率——我同意。

**缓释**：
- 铁律措辞用「**禁止跳过**」、「**首次回复前必须**」等强制性语言
- 失败模式显式定义：「如果搜索无结果，告知 Frank '我查了历史，未找到相关记录'」
- 配合 L1 boot context 文件：即使 OC 跳过了 session_search，至少还有 boot context 文件可读（虽然也可能跳过...）

**不可完全消除**：LLM 的概率特性决定了这条铁律永远是 ~70-85% 可靠，不是 100%。只要 Frank 接受这个上限，就可以上线。

### 坑 6：mem0_tagged 客户端在 cron 环境中的初始化

**问题**：`mem0_tagged.Mem0Tagged` 需要 `client` 参数（mem0 Memory 实例）。在 cron 的 `no_agent=True` 模式下，cron 没有 LLM agent 上下文，mem0 客户端可能未初始化。

**缓释**：`boot_context.py` 可以直接读 `mem0_states.db`（DREAM-003 的 SQLite DB）而不通过 mem0 语义搜索。`mem0_tagged.py` 的 `_get_conn()` 和 `_get_state()` 方法本身就支持直接 SQL 查询。或者在 `boot_context.py` 中构造一个最小 mem0 客户端。

**验证**：`DEFAULT_DB = Path("/root/.hermes/profiles/orchestrator/mem0_states.db")` — 这个路径在 cron 环境下应该可访问。

---

## 5. 总体评价

### 同意 Product + Architect 的核心判断

> 「核心问题是调用习惯而非搜索能力」— Product
> 「三层架构：确定层 + 铁律层 + 摘要层」— Architect

**完全同意。** L2 铁律 6 是最高 ROI 的改动——1 个文件，17 行，0.1h，立即覆盖 70% 场景。应该最先上线。

### L1 的工期修正

Architect 的 L1 估算 0.5h **过于乐观**。实际需要：

| 子任务 | 估时 |
|------|:---:|
| `boot_context.py` 编写（60 行，含边界处理） | 0.3h |
| 调研 Hermes session DB schema + 直接 SQL 查询 | 0.2h |
| cron job 创建 + 测试（验证文件生成、刷新间隔） | 0.2h |
| SOUL.md 铁律 6 追加 boot context 读取步骤 | 0.05h |
| 端到端验证（新会话 → boot context 文件 → OC 读取） | 0.15h |
| **合计** | **~0.9h** |

不是 0.5h，是 0.9h——和整个项目的 Architect 估算相同，但仅 L1 一项。

如果接受「L1 先做简化版」（boot_context.py 只查 session DB 不查 mem0_tagged，~30 行），可以压到 0.4-0.5h。

### 建议的施工顺序（修正版）

```
Day 1 (今天)
  1. [0.1h] P0 铁律 6 → 到 SOUL.md 里落地
  2. [0.9h] P0 boot context 脚本 → cron + .boot_context.md

Day 2
  3. [0.15h] P1 纠错写 memory → SOUL.md 规则
  4. [0.3h] P2 会话摘要 → SOUL.md 规则

合计: 1.45h
```

### 不做的事（确认）

- ❌ 不修改 `prompt_builder.py`（尊重 Architect 的引擎层不侵入原则）
- ❌ 不把 boot context 写成 memory 条目（注入顺序错误 + 状态管理复杂度）
- ❌ 不引入新的依赖包（只用 Python stdlib + 已有的 `mem0_tagged` + sqlite3）

---

> 改 SOUL.md 是零代码的活，我 0.1h 就能把铁律 6 落地。但 L1 boot context 不是 0.5h——要写脚本、配 cron、处理 session DB 的查询、验证端到端。实际是 0.9h。建议先上线铁律 6 看效果，如果 OC 真的读了文件，boot context 就是锦上添花；如果不读，那就该考虑改引擎了。
