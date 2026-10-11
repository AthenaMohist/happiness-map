# Roundtable R3 独立卷 — Architect: Hermes 记忆中间层宏观规划

> 发言人：高见远（架构师） | 日期：2026-08-10 | 版本：v1.0
> 类型：B 类头脑风暴 — R3 独立卷，不传递，不参考 Engineer/Product 的卷
> 议题：用新技术完整开发一个记忆中间层（memory middleware），弥补现有 Hermes 记忆的不足

---

## 0. 立场声明（Frank 裁决后的架构重定位）

接受 Frank 三点指示，并首先修正我自己的 R1 框架——这是本次发言最重要的自我纠正：

**R1 我把中间层窄化成了「L3 决策档案层」（GAI 详情页）。Frank 裁决后我重读调研资料，这个框架错了：决策档案只是 wiki-llm 的一个应用，不是中间层本身。** 真实目标是完整的记忆中间层——一个把 Hermes 所有记忆原材料编译成互链知识的系统。GAI 待办追溯、跨会话恢复、项目共享文件，都是这个系统建好之后自然长出来的果实。

**核心隐喻（架构的第一性原理）**：Karpathy 的原话——"The LLM Wiki is a compiler for knowledge, not a search engine."
- 传统 RAG = 每次查询重新检索原始 chunk → 无积累、无交叉引用、无复利
- LLM-Wiki = 把源材料编译成互链 markdown → 知识只编译一次，持续保鲜，矛盾显式标记

所以记忆中间层本质是一个**编译器（compile pipeline），不是检索系统（retrieval system）**。检索只是编译质量的副产品。这个定位决定了一切后续设计：正确性度量是"编译质量"（互链完整、矛盾标记、updated 时间戳），不是"检索准确率"。

三条架构铁律（写进 SCHEMA，违反即 lint 失败）：
1. **单一写入者**：所有写入走编译入口（memctl CLI），禁止多路 ad-hoc 写。这是 GAI 双份拷贝分叉 33 天的教训，也是 OBS-01（LLM 忘记手动步骤）的教训。
2. **状态不回写环**：kanban.db / pipeline_state.db / GAI 表是 L0 真源，中间层只读不写。wiki 不产生状态。
3. **机械层零 LLM**：index 维护、双链校验、原子写、git 提交全部脚本化确定性完成；LLM 只做 blast radius 识别与页面语义编译。

---

## 1. 整体架构：分层设计与数据流（问题 1）

### 1.1 五层全景（叠加 + 渐进吸收，不推翻重建）

| 层 | 载体 | 写者 | 读时 | 本质 | 处置 |
|----|------|------|------|------|------|
| L0 确定性状态 | kanban.db / pipeline_state.db / GAI 表 | 机器脚本 | 每轮注入 | 事实真源，零 LLM | **不动**（基础设施） |
| L1 情节检索 | session_search / state.db 转录 | 会话自动 | 按需 | 原始历史，FTS5 | **不动**（基础设施） |
| L2 语义记忆 | memory 工具 / mem0 | agent 策展 | 每轮注入 | 蒸馏事实与偏好 | **保留为 fast-path，长期被 L3 吸收** |
| **L3 编译知识（新增·核心）** | **wiki-llm 互链 markdown** | **编译管线（单一写者）** | 会话启动 + 定向 | 编译后的持久记忆：实体/概念/决策/模式 | 中间层主体 |
| **L4 检索导航（新增）** | **SQLite FTS5 trigram + 空间标签 + 会话恢复协议** | 脚本 | 按需/启动 | 确定性检索、导航、跨会话恢复 | 中间层读路径 |

**叠加还是重构？——叠加 + 渐进吸收，明确否决推倒重建。**

- L0/L1 是机器写的基础设施，10 个 profile、全部依赖 kanban.db/state.db 的脚本都建立在它们上面。破坏性重构 = 一次性瘫痪全系统，收益为零。中间层的价值主张是"补不足"，不是"换地基"。
- L2（mem0/内存 memory）短期叠加保留（每轮注入的 fast-path 仍有价值），长期吸收：wiki concepts 页保存完整上下文与互链（fidelity over compression），mem0 的"压缩成事实摘要"丢 why 的问题被结构性解决后，云依赖逐步退役。
- 关键：**不引入第三个漂移面**。wiki 是编译产物（唯一真源是其自身 + L0），不是 GAI 的复制品。

### 1.2 数据流

**写入路径（事件驱动，单向）**：
```
事件源（kanban 生命周期 / 会话摘要 / 纠正 / 决策 / GAI 更新）
  → ① 增量检测：识别受影响页面清单（LLM，只列不动手）→ blast radius 裁定
  → ② 语义编译：更新 raw/entities/concepts 页（LLM，幂等，bump updated）
  → ③ 机械维护：index.md / log.md / 双链校验（脚本，零 LLM）
  → ④ 原子提交 git + 备份 manifest
```

**检索路径（两级：确定性优先，语义兜底）**：
```
agent 会话启动 → 读 SCHEMA.md + index.md + log.md(最近30条) → 定向读相关页 → 注入上下文
按需查询 → SQLite FTS5 trigram 本地检索（零 LLM，零 API）→ 命中页面 → 读页合成
```

**更新路径（增量，禁止全量重写）**：
```
新信息 → 矛盾检测 prompt → 标记 contested / 双版本并存 → 只更新受影响页 → bump updated → log
```

**反向不成立**：wiki 不产生状态、不回写 kanban、不替代 session_search 的全文检索。状态流单向：L0 → 编译 → wiki → 读取。

---

## 2. wiki-llm 作为核心：三层结构如何承载 Hermes 记忆（问题 2）

### 2.1 映射

```
/workspace/devPPL-wiki/
├── SCHEMA.md          # 域规则：分层/双链解析/frontmatter/不变量/空间标签 taxonomy
├── index.md           # 目录（按类型 + 按空间双视角，脚本维护）
├── log.md             # append-only 操作日志
├── raw/               # L1 不可变源材料（编译输入）
│   ├── sessions/      # 会话编译输入（摘要、决策、纠正）
│   ├── events/        # kanban/GAI 事件快照
│   └── research/      # 调研材料（memory-middleware-research.md 等）
├── entities/          # L2 稳定实体：devPPL, cron, watchdog, kanban, close.sh, mem0…
├── concepts/          # L2 概念/主题/模式：事件驱动, fail-open, 单一写者, 双链约定…
│   ├── decisions/     # ★ 决策档案（GAI 页，[[ID]] 双链）——只是一个应用
│   └── patterns/      # 架构模式页
├── comparisons/       # L2 对比分析（可选）
└── queries/           # 值得保留的查询结果（可选）
```

- **raw/ = 记忆的原材料**：会话转录摘要、kanban 事件、调研资料。不可变，git 版本化，与 L1 的关系是"精炼索引"而非复制（避免双份漂移）。
- **entities/ = 记忆中的稳定事物**：机制、项目、角色、工具。随时间累积事实（"watchdog v5 于 2026-07-23 上线"）。
- **concepts/ = 记忆中的 why**：架构决策、模式、教训。这是"决策可追溯"的真正载体——比 R1 的"四段详情页"更广，GAI 决策页只是 decisions/ 子目录。

### 2.2 决策档案只是其中一个应用

Frank 指示 2 说得对：中间层搭好，GAI 待办追溯自然产生。架构上：
- GAI 表是 L0（orchestrator 路径唯一真源，已由 R1 定案），wiki/actions/ 每 ID 一页是它的决策档案——**一个应用**。
- 中间层的其它应用：跨会话恢复（L4 协议）、项目共享文件（raw/ + entities/）、模式沉淀（concepts/patterns）、对比分析（comparisons/）。
- 因此 memctl CLI 不是"gai.py 改名"，而是**泛化的编译入口**：GAI 是第一个接入的源，后面接会话、接 kanban 事件。

### 2.3 为什么不是"扩展 mem0 / 建向量库 / 扩容 memory 工具"

| 方案 | 否决理由 |
|------|---------|
| 扩展 mem0 | cloud API 依赖、压缩丢上下文（fidelity 反模式）、无互链、无 git 版本、无本地确定性 |
| 只建 ChromaDB 向量库 | 向量索引没有编译 = RAG 无复利；仍丢交叉引用与矛盾标记；MEM-005 实锤 bge-small-en 中文噪声 |
| 扩容 Hermes memory 工具 | 2200 字符/每轮注入，是 fast-path 缓存不是知识库；装不下决策、页面、互链 |

---

## 3. 记忆宫殿增强：哪些引入、怎么协同（问题 3）

引入矩阵——**不是照搬 MemPalace，而是提取其"本地确定性 + 空间导航"两个思想，融入 wiki-llm**：

| 机制 | 决策 | 解决什么问题 | 与 wiki-llm 协同方式 |
|------|------|-------------|---------------------|
| **Wing/Room/Shelf 空间层次** | ✅ **引入（作为标签/索引维度，不是目录）** | MEM-002 空间导航；跨会话"按房间找记忆" | frontmatter `palace: wing/room/shelf` + index.md 空间分区；与 Karpathy 的"按类型分目录"正交（文件类型轴 × 空间轴，双视角索引） |
| **SQLite FTS5 trigram 分词** | ✅ **引入（核心检索）** | **修正 MEM-006**：FTS5 默认 unicode61 分词器不识别 CJK，但 SQLite 3.34+ 内置 trigram tokenizer，按 3 字符切分，天然支持中文，零依赖零成本 | 作为 wiki 页面的本地全文索引；检索路径第一级（确定性、免费、离线），不依赖 embedding |
| **ChromaDB 向量检索** | ⏳ **Phase 4 可选** | 语义相似召回（"我记得有个模式跟 XX 类似"） | 若 FTS5+关键词评分不够再评估；引入时必须换 bge-m3 级中文模型，**不沿用 bge-small-en**（MEM-005 教训） |
| **MCP 集成** | ⏳ **Phase 4 可选** | 外部 agent（Claude Code/OpenCode/Codex）查询 wiki | wiki 作为 MCP server 暴露读接口；Hermes 内部 agent 直接用文件工具即可，MCP 是生态接入不是核心 |

**为什么空间层次是标签不是目录**：MemPalace 用真实目录层级（Palace→Wings→Halls→Rooms→Closets→Drawers），但 wiki 的文件布局由 Karpathy 类型结构决定（raw/entities/concepts 是"按知识类型"轴）。再加一层目录 = 两套文件系统打架。用 frontmatter 标签 + index 分区，一个文件同时属于"实体页"和"devPPL-管线-事件驱动"房间，两个视图都在 index.md 里——零文件移动，纯机械维护。

**协同总结**：wiki-llm 提供编译知识（互链、保真、复利）；记忆宫殿提供导航隐喻（空间标签）+ 本地确定性检索（FTS5 trigram）；两者的共同点是 local-first、零 API 依赖、脚本可维护。

---

## 4. 已知墙与对策（问题 4）

### 4.1 200 文件墙

社区实测：wiki 太大 agent 无法在 context 中持有全图。四层对策（按优先级）：

1. **目录级索引（首要）**：index.md + 每个子目录（entities/concepts/decisions）独立索引；agent 编译时只读 SCHEMA + index + 受影响页，**永不加载全 wiki**。llm-wiki skill 已内置规则（分区超 50 条目拆子区、总索引超 200 建 topic-map）——直接继承。
2. **分区**：按 Wing（顶层域）分目录边界；devPPL 与未来 InfoManager 等域物理隔离（各自独立 wiki repo），天然分墙。
3. **页面瘦身**：每页 ≤200 行（llm-wiki 规则），超限拆子页 + 交叉链。
4. **定期归档**：done 决策、superseded 概念 → `_archive/`，移出活跃索引。GAI 已归档区就是这个机制的雏形。

**关键认识**：200 墙的本质是**编译期**问题（更新时要全局去重），不是检索期问题。检索期 agent 只读少量页面。所以解药集中在编译流程：blast radius + 目录级索引 + 归档，三者缺一不可。

### 4.2 增量更新流程内置

- 编译入口（memctl）内置 Karpathy killer feature：**新源 → 先列受影响页面清单（不动手）→ blast radius 裁定 → 只更新受影响页**。
- 幂等：同一事件重复触发 → 同一结果（骨架页已存在则更新不重建，杜绝重复页）。
- 触发：事件驱动主路径（kanban 生命周期 close.sh S3 接线，R1 已定案）+ 周 cron 兜底（漂移对账）。
- 防漂移：memctl lint 四不变式（断链 / 孤儿页 / status 镜像 GAI / index 与文件列表一致）。

### 4.3 跨会话接入（agent 如何从 wiki 恢复上下文）

**会话启动协议（替代 DPL-011 铁律 6 的搜索式恢复，升级为索引式确定性恢复）**：

```
新会话前 3 轮内：
1. 读 SCHEMA.md（域规则，一次）
2. 读 index.md（目录，一次）
3. 读 log.md 最近 20-30 条（最近活动）
4. 若当前有活跃 kanban task → 定向读相关 entities/concepts/decisions 页
5. 注入上下文摘要："上次做到 X，决策 Y 已定，当前任务 Z 进行中"
```

成本：约 10-20 个文件读取，全确定性路径，零 LLM 检索调用。比 DPL-011 的 session_search 更强：**按名字/索引导航，不依赖 FTS5 CJK 分词**，恰好绕开 MEM-006 的坑。

**boot_context 集成点**：boot_context.py 已读 kanban.db + pipeline_state.db + sessions.db + memory（实测，R1 已核），加一个 `_wiki_digest()` 函数（读 index.md + log.md 尾部，纯机械零 LLM）拼进输出——每个 OC 会话自动看到"记忆最近变更"，无需任何行为约定。这是工程师 R1 说"boot_context 不读 GAI"的正确回应：我们不把 GAI 塞进 boot_context，而是注入 wiki 摘要（更细的编译产物视角）。

---

## 5. 项目共享文件存储：架构上怎么支持（问题 5）

这是中间层的**自然产物**，架构支持点：

1. **wiki repo 本身就是共享存储**：`/workspace/devPPL-wiki` 独立 git repo（R1 已定），所有 profile 可读、编译管线单一写者、接入 manifest.yaml 备份链路（R1 已定 BKP-003 模式）。
2. **raw/ 放不可变共享材料**：研究资料、会议记录、转录摘要——git 版本化，多 agent 共享。
3. **entities/concepts 放项目认知**：机制页（cron/watchdog/kanban 怎么工作）、概念页（架构决策、模式）——这就是"项目共享文件"的知识形态，比散落 docs/ 的文档可检索、可追溯。
4. **与 devPPL repo 的边界**：devPPL 仓库管代码/脚本/标准；wiki 仓库管记忆/决策/认知。提交节奏不同（代码按 slice、记忆按事件），物理隔离让 git log 可分辨（R1 已定，保持）。
5. **多 profile 读写协议**：读者无限制（任何 profile 文件工具可读）；写者唯一（memctl）。InfoManager vault 不复用（R1 已定：数据域不同、写者冲突、repo 边界）。

---

## 6. GAI mem 条目统一评估（Frank 指示 3）

把 GAI 里所有 mem 相关条目捞出，按中间层视角统一重评级——**多数条目不是独立任务，而是中间层的零件**：

| ID | 原评级 | 中间层视角评估 | 新处置 |
|----|--------|---------------|--------|
| MEM-001 /learn + /journey | P1, 1d | 中间层的用户接口：/learn = 编译写入命令，/journey = 空间浏览命令 | **吸收**为 L4 功能，工时并入中间层（Phase 3） |
| MEM-002 Session 层次标签 Wing/Room/Shelf | P2, 1h | 记忆宫殿空间层次 → frontmatter 标签 + index 分区 | **吸收**为 L4 核心（Phase 3），工时不单列 |
| MEM-003 完整 LLM pipeline 未测试 | P3 | 编译管线本身是 LLM pipeline，必须有 pytest 覆盖 | **吸收**为编译管线测试要求（Phase 1 起） |
| MEM-004 LLM-Wiki [[wikilinks]] | P3, 2h | 中间层地基（R1 已拆 004a/004b） | **升级为核心**：Phase 1（本周 11.5h，R1 已定案） |
| MEM-005 bge-small-en 中文噪声 | P5 | 结论维持：不引入 embedding 作为主检索；若 Phase 4 引入必须换模型 | **维持 P5** |
| MEM-006 FTS5 无 CJK 分词器 | P5 | **修正：SQLite FTS5 trigram tokenizer（3.34+）原生支持 CJK，零依赖**——"成本远超收益"的结论过时了 | **升 P2**：Phase 2 实现（第一步验证 sqlite 版本 ≥ 3.34） |
| DPL-011 跨会话记忆 | ✅ 已归档 | 被会话启动协议正式吸收（索引式恢复 > 搜索式恢复） | **归档保持，实现升级** |

**统一评估结论**：7 项里 5 项被中间层吸收（MEM-001/002/003/004/006），1 项维持 P5（MEM-005），1 项升级实现（DPL-011）。中间层不是"做一个小功能"——它就是这 7 项的母体。

---

## 7. 宏观架构图 + 分阶段演进路线（问题 6）

### 7.1 宏观架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        记忆中间层 Memory Middleware (L3 + L4)                 │
│                                                                             │
│  ┌─────────────────── 编译管线 Compile Pipeline（写入·单一入口）────────────┐  │
│  │ 事件源: kanban 生命周期 / 会话摘要 / 纠正 / 决策 / GAI 更新                │  │
│  │    │ ① blast radius 识别（LLM，只列不动手）                                │  │
│  │    ▼                                                                     │  │
│  │ ② 语义编译: 更新 raw/entities/concepts 页（LLM，幂等，bump updated）       │  │
│  │    ▼                                                                     │  │
│  │ ③ 机械维护: index.md / log.md / 双链校验（脚本，零 LLM）                   │  │
│  │    ▼                                                                     │  │
│  │ ④ 原子提交 git + 备份 manifest（BKP-003 链路）                            │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────── 存储层 Wiki Store（L3·核心）────────────────────────┐  │
│  │ SCHEMA.md │ index.md（类型×空间双视角）│ log.md（append-only）           │  │
│  │ raw/（不可变源）│ entities/（稳定实体）│ concepts/（概念·决策·模式）       │  │
│  │ comparisons/ │ queries/ │ _archive/（归档）                              │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────── 检索/导航层 Read Path（L4）─────────────────────────┐  │
│  │ 空间导航: Wing/Room/Shelf 标签 + index 分区（MEM-002 → palace 标签）      │  │
│  │ 本地检索: SQLite FTS5 trigram（CJK 原生）+ 关键词评分（零 LLM·零 API）     │  │
│  │ 会话恢复: SCHEMA→index→log→定向读页→上下文注入（跨会话协议）               │  │
│  │ 用户接口: /learn（编译写入）· /journey（空间浏览）· memctl CLI             │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
          │ 读（机械注入/定向）                        │ 写（事件驱动，唯一入口）
          ▼                                           ▲
┌──────────────────────────── 现有记忆体系（不动）───────────────────────────────┐
│ L0 确定性状态: kanban.db / pipeline_state.db / GAI 表（机器写，真源）            │
│ L1 情节检索: session_search / state.db（FTS5 原始历史）                         │
│ L2 语义记忆: memory 工具 / mem0（每轮注入 fast-path，逐步被 L3 吸收）            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 分阶段演进路线

| 阶段 | 内容 | 工时 | 验收 |
|------|------|------|------|
| **P1 本周** | GAI 决策档案 MVP（R1 已定案：git rm 双份拷贝 + wiki 初始化 + memctl 最小集 + close.sh S3 接线 + P1 七行回填） | ~11.5h | 30s 追溯 / 1h 同步 / 周漂移空（R1 验收标准） |
| **P2 下周** | 中间层核心：编译管线泛化（会话摘要/kanban 事件 → 页）、**FTS5 trigram 检索索引（先验 sqlite 版本）**、增量更新 + 矛盾检测、index 自动维护、boot_context wiki digest | ~2.5 人天 | FTS5 CJK 检索命中；boot_context 出 digest；增量更新不动手先行 |
| **P3** | 记忆宫殿增强：Wing/Room/Shelf 标签 + index 空间分区、/learn /journey 接通、会话启动协议全量、项目共享文件正式启用 | ~1.5 人天 | 新会话 10-20 文件读取恢复上下文；/learn 写入即入 wiki |
| **P4 可选** | 规模化：分区索引/归档策略落地、ChromaDB 评估（换模型）、MCP server（Claude Code 接入） | ~2 人天 | 200+ 文件编译不退化；外部 agent 可查 wiki |

**依赖关系**：P1 是编译管线的第一次实战，P2 建立在 P1 的 memctl 骨架之上（不重写，泛化）；P3 依赖 P2 的索引；P4 全部可选，不进主线。P1-P3 总量约 11.5h + 4 人天。

---

## 8. 风险与取舍汇总

- **取舍：标签 vs 目录的空间层次**——选标签。两套目录 = 双倍维护，frontmatter + index 分区零移动成本。
- **取舍：FTS5 trigram 为主检索 vs ChromaDB 语义检索**——选前者。零依赖、CJK 原生、确定性可测；向量检索 Phase 4 按需评估，且必须换中文模型。
- **风险：编译管线 LLM 质量参差**——缓解：机械层全脚本化（index/校验/提交），LLM 只做 blast radius + 页面语义；lint 四不变式 + 周漂移兜底。
- **风险：worker 忘触发编译**——缓解：close.sh S3 接线（强制路径，R1 已定）+ boot_context digest（被动可见）+ 周 cron 对账。三层保险，不靠约定。
- **风险：P2 泛化时把 memctl 写死成 gai.py**——缓解：接口抽象（source adapter 模式），GAI 只是第一个 source，严禁在 CLI 里硬编码表名。
- **风险：sqlite 版本 < 3.34 无 trigram**——缓解：P2 第一步验证；若真无，退路是关键词评分 + LIKE 前缀，不阻塞整体。

---

## 9. 一句话结论

记忆中间层 = **编译器，不是搜索引擎**：L3 wiki-llm 互链知识（编译产物）+ L4 空间导航与确定性检索（读路径），叠加在 L0/L1/L2 之上渐进吸收，事件驱动单一写者、状态不回写、机械层零 LLM——GAI 追溯、跨会话恢复、项目共享文件都是它长出来的果实，MEM-006 用 trigram 顺手修正，MEM-005 继续搁置。P1（11.5h）验证管线，P2-P3（4 人天）成中间层。
