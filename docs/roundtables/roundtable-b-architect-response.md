# Roundtable B: 跨会话记忆 — 架构师发言

> 发言人: 高见远（架构师） | 日期: 2026-07-24 | 版本: v1.0
> 关联: Product 发言 (t_e78de385), DREAM-003 Mem0 标签系统 (t_6f316778)

---

## 0. 现状盘点

在回答四个问题之前，先盘点当前系统已有的跨会话能力：

| 机制 | 位置 | 覆盖场景 | 可靠性 |
|------|------|---------|--------|
| `memory` 工具自动注入 | 每轮系统提示 | 已保存的持久化事实 | **100%**（确定性注入） |
| `session_search` | OC 手动调用 | 历史对话全文检索 | 取决于 LLM 是否调用 |
| 跨会话续接规则 | `task-handoff` skill §跨会话续接 | kanban 任务断点恢复 | 中等（在 skill 里，不在 SOUL.md） |
| DREAM-003 状态标签 | `mem0_tagged.py` 薄封装层 | 记忆质量过滤（verified/outdated） | 100%（脚本层，零 LLM） |
| .oc_relay.json | PIPELINE.md | kanban relay 续接 | 高（cron 驱动的 polling） |

**关键发现**：OC 已经有「跨会话先 session_search」的规则（2026-07-13 Frank 纠正后写入 task-handoff skill），但它不在 SOUL.md 的 铁律 节中。它存在于一个 skill 的子节里——OC 可能在新会话热启动时没有加载该 skill。

Product 的 P0 方案本质上是要把这条已有规则 **抬高到铁律级别**。方向正确，但执行层面有架构细节需要补充。

---

## 1. Q1: P0 方案技术可行性

> SOUL.md 加铁律 6「新会话前三轮必须 session_search + mem0_search」

### 结论：可行，但可靠性封顶在 ~70-80%

**数据流**：

```
新会话启动
  │
  ├─ [确定性] memory 工具自动注入已保存事实 ← 已有，零 LLM
  │
  └─ [概率性] OC 读取 SOUL.md → 铁律 6 触发
       │
       ├─ Round 1-3: session_search(query=话题关键词)
       ├─ Round 1-3: memory 工具查看最近记忆
       │
       └─ 期望输出: "Frank，我查了一下，上次我们..."
```

**可行部分**：
- `session_search` 和 `memory` 工具已存在，签名稳定
- OC 的 SOUL.md 已有 5 条铁律的注入先例，加第 6 条无架构障碍
- 已有 task-handoff skill 的跨会话续接规则可复用为铁律措辞

**不可靠部分（架构风险）**：
1. **"前三轮" 的判定依赖 LLM 计数**：LLM 需要自己数消息轮次。没有系统层的 `round_number` 变量。可能在长上下文滚动窗口里数错
2. **LLM 有 15-25% 概率跳过 prompt 规则**：尤其是在任务紧迫时（"Frank 很急，直接执行"），铁律可能被 trade-off
3. **搜索质量不可控**：`session_search(query=...)` 的 query 由 LLM 现场构造。如果 OC 判断 "看不出有什么前情"，可能构造弱 query → 空结果 → 误判为无前情

**建议优化**：
- 铁律措辞不要用 "前三轮"，改用 **"在新会话首次回复 Frank 之前"**——一次性动作，不需要轮次计数
- 铁律应该定义 **失败模式**：搜索无结果时 → 告知 Frank "我查了历史，没找到相关话题"（显式确认，而非沉默跳过）

**工期影响**：零代码，纯 SOUL.md 修改（~10 行）。实施成本 0.1h。

---

## 2. Q2: 跨会话"记忆一致性"的深层架构问题

### 结论：有两个真问题，Product 已经触及但未结构化

**问题 2.1：LLM 文本 ≠ 结构化状态**

`session_search` 返回的是 **对话文本片段**，不含结构化状态摘要。例如：

```
OC: "healthchecks.io 已在 crontab 配置，每 5 分钟 ping"
```

这条信息跨会话后，新 OC 通过 session_search 找到这段话，但它需要：
- 判断这段对话是"已完成的结论"还是"讨论中的建议"
- 知道 crontab 是否仍然有效（可能被后续会话改了）
- 找到对应的 crontab 行来交叉验证

**当前无任何结构化层**——全部依赖 LLM 阅读文本并推理。

DREAM-003 的 `verified`/`outdated` 标签部分解决了这个问题，但仅覆盖 `memory` 路径，不覆盖 `session_search` 路径。

**问题 2.2：两个检索通道无统一 ranking**

```
通道 A: memory 工具（持久化事实，DREAM-003 过滤）
通道 B: session_search（对话全文，FTS5 关键词）
```

两条通道各自独立。没有统一的 "bring me up to speed" 入口。OC 需要：
1. 先调 memory 获取持久化事实
2. 再调 session_search 获取对话上下文
3. 自己合并两个结果，解决潜在冲突

这在架构上叫 **联邦检索的排序问题**（federated search ranking）——两个检索源没有统一的 relevance score。

**问题 2.3（产品已暗示但未命名）：上下文窗口预算**

session_search 返回大段对话文本。即使 OC 找到了相关会话，整个对话可能有 200+ 轮，塞不进上下文窗口。当前没有自动摘要压缩——产品 P2 正是针对这个问题。

---

## 3. Q3: 更优技术路径

### 推荐：三层架构（确定层 + 铁律层 + 摘要层）

```
                    ┌─────────────────────────────────┐
                    │   新会话启动                      │
                    └──────────────┬──────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
┌───────────────┐     ┌───────────────────┐     ┌──────────────────┐
│ Layer 1: 确定  │     │ Layer 2: 铁律      │     │ Layer 3: 摘要     │
│ 自动上下文注入  │     │ SOUL.md 铁律 6     │     │ P2: 会话结束摘要   │
│ (系统层,零LLM) │     │ (prompt,概率)      │     │ (结构化,可注入)   │
├───────────────┤     ├───────────────────┤     ├──────────────────┤
│ ✅ memory 工具  │     │ OC 首轮必须:        │     │ 会话结束 →        │
│   已保存事实    │     │ 1. session_search  │     │ 自动生成:         │
│               │     │ 2. memory 查看      │     │ - 本次做了什么    │
│ ✅ 最近3次会话  │     │ 3. 显式告知Frank    │     │ - 未完成的事项     │
│   标题+摘要    │     │    查了还是没查      │     │ - 下次需要的上下文  │
│               │     │                    │     │                  │
│ 覆盖: 100%    │     │ 覆盖: ~70-80%      │     │ → 作为下次        │
│ 成本: 0 token │     │ 成本: 搜索开销      │     │ Layer 1 的输入    │
│ (LLM 推理)     │     │                    │     │                  │
└───────────────┘     └───────────────────┘     └──────────────────┘
```

### Layer 1 实现细节（推荐的增强项）

**现状**：`memory` 工具已自动注入所有已保存事实到每轮系统提示。

**增强**：新增一个轻量级脚本（~30 行 Python），在新会话启动时运行：

```python
# boot_context.py — 新会话引导上下文
# 1. 查询最近 3 次会话的标题 + 最后一条 user message
sessions = session_search(limit=3, sort='newest')
# 2. 查询所有 verified 且未过期的 memory
memories = search_tagged(state='verified', exclude_expired=True)
# 3. 格式化为 "最近上下文" 块
# 4. 注入到系统提示的最前面（在 SOUL.md 之前）
```

输出格式：
```
[最近上下文 — 自动注入]
最近 3 次对话:
  1. (7/24) "Roundtable B: 跨会话记忆 — product 发言" → 未完成，等待 architect/QA 发言
  2. (7/23) "DREAM-003: Mem0 标签系统架构设计" → 已完成，产出架构文档
  3. (7/21) "不做梦报告投递纠错" → 已完成（纠错 3 次，最终确认投递成功）

关键记忆 (7 条 verified):
  - 跨会话续接: 换 session 先查前情
  - watchdog 汇报范围: 仅 OC 当前项目
  - 路径禁令: 强制绝对路径 /root/...
```

**优势**：
- 100% 覆盖——不依赖 LLM 是否记得调用工具
- 零 LLM token 烧在检索决策上
- 格式紧凑（~300 tokens），不占上下文窗口
- 如果相关，OC 自然会深入搜索；如果不相关，快速 skip

**实施成本**：~30 行 Python + 一个 Hermes 系统层 hook（约 0.3h 调研 + 0.2h 实现）

### Layer 2: P0 铁律 6（Product 方案）

在 Layer 1 的确定性覆盖之上，铁律 6 作为 **深度搜索的触发器**：
- Layer 1 给的是摘要——告诉 OC "最近做了什么"
- 铁律 6 要求 OC 在需要细节时主动 `session_search` 深入

**建议铁律 6 措辞**：

```markdown
### 铁律 6：新会话必须先回查上下文再回复

在新会话中，首次回复 Frank 之前，必须完成：
1. 查看 memory（通过 memory 工具）——了解已保存的事实和偏好
2. 如话题涉及过往工作 → session_search 查相关对话
3. 在回复中**显式告知** Frank 查到了什么（或确认未找到相关记录）

禁止行为：不查前情就直接从零提议、假定"不知道就等于没做过"。
违反后果：同铁律 5（三犯升级）
```

### Layer 3: P2 摘要（Product 方案）

作为 Layer 1 的 **数据源**。会话结束时 OC 生成结构化摘要，下次启动时 Layer 1 的脚本读取。

**工期总估算**：
| 层 | 实施 | 工期 |
|----|------|------|
| Layer 1 (boot context) | 新脚本 + 系统 hook | 0.5h |
| Layer 2 (铁律 6) | SOUL.md 修改 | 0.1h |
| Layer 3 (P2 摘要) | SOUL.md 规则 + OC prompt | 0.2h |
| P1 (纠错自动写 memory) | SOUL.md 规则 | 0.1h |
| **合计** | | **0.9h** |

---

## 4. Q4: 与 DREAM-003 联动

### 关系图谱

```
DREAM-003 (mem0_tagged.py)
  │
  ├── add_tagged(memory, state='unverified', ttl_days=7)
  │     ▲
  │     │  P1 调用: Frank 纠错 → OC 写入 memory
  │     │  使用 DREAM-003 的 add_tagged() 而非原始 mem0.add()
  │     │  确保新记忆带 TTL + verified 状态
  │
  ├── search_tagged(state='verified', exclude_expired=True)
  │     ▲
  │     │  铁律 6 调用: OC 查询 memory 时
  │     │  使用 search_tagged() 而非原始 mem0.search()
  │     │  自动过滤 outdated/过期记忆
  │
  └── verify(memory_id) / mark_outdated(memory_id)
        ▲
        │  Layer 1 boot context 脚本 或 OC 确认后调用
        │  确保已确认的事实保持 verified 状态
```

### 具体集成点

1. **铁律 6 的 memory 查询**：应该用 DREAM-003 的 `search_tagged(state='verified')` 而非原始 `memory` 工具。但目前 `memory` 是 Hermes 内置工具——OC 不能绕过它直接调 mem0。短期方案：铁律 6 中注明 "优先看 verified 记忆，忽略 outdated"。长期方案：等 DREAM-003 实现完整后，让 `memory` 工具内部集成标签过滤。

2. **P1 纠错写入**：Frank 纠错 → OC 调用 `memory(action='add', ...)` → 默认进入 DREAM-003 的 `unverified` 状态 → 需要后续确认流程升级为 `verified`。建议 SOUL.md 规则中注明写入时的 target 和 category：
   ```
   纠错内容 → memory(action='add', content="Frank 纠正: ...",
                      category='user_correction', ttl_days=30)
   ```

3. **Layer 1 boot context**：脚本调用 `search_tagged(state='verified')` 时，`mem0_tagged.py` 自动执行 TTL 过期检查（过期→mark outdated→过滤），确保注入到新会话的 context 不包含过期事实。

4. **不重复造轮子**：DREAM-003 的三态模型（unverified/verified/outdated）已经定义了记忆质量。铁律 6 和 P1 不需要重新定义——直接引用 DREAM-003 的状态语义即可。

---

## 5. 总体评价

### 同意 Product 的核心判断

> "核心问题是调用习惯而非搜索能力"

**完全同意。** 当前系统已具备 cross-session 检索的所有基础设施：`session_search`（FTS5 全文检索）、`memory`（持久化注入）、DREAM-003（质量过滤）。缺失的是一层 **系统级的、确定性的** 上下文注入，以及把已有的分散规则提升为 SOUL.md 铁律。

### 补充：架构上的"最后一公里"

Product 方案解决了"OC 会不会搜"的问题（prompt 层），但未解决"搜到的东西能不能用"的问题（内容质量层）。DREAM-003 补上了记忆质量，而 Layer 1 boot context 补上了覆盖率——三者协同形成完整闭环。

### 建议推进顺序

| 优先级 | 事项 | 理由 |
|--------|------|------|
| **P0** | Layer 2: SOUL.md 铁律 6 | 零代码，立即生效，覆盖 70% 场景 |
| **P0** | Layer 1: boot context 脚本 | 确定性 100% 覆盖，堵上剩余 30% |
| **P1** | P1: 纠错自动写 memory | 丰富 memory 库，提高 boot context 质量 |
| **P2** | Layer 3: 会话结束摘要 | 作为 boot context 的数据源优化 |

### 不做的事（确认）

- ❌ 不升级 Mem0 语义搜索（当前 FTS5 + DREAM-003 标签已足够）
- ❌ 不全量会话回放（token 成本爆炸）
- ❌ 不修改 Hermes 引擎层（boot context 在工具层实现，不侵入核心）
- ❌ 不向量化所有决策（过度设计，当前痛点不需要）

---

> 我是地基。今天把这 0.9h 的设计做扎实，明天 Frank 就不用第 4 次纠正同一个梦报告了。
