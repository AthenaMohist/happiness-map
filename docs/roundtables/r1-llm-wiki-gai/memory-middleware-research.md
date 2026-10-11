# LLM-Wiki + MemPalace 调研资料（2026-08-10 获取）

> 用途：记忆中间层 Roundtable 参考材料。来源为公开网络资料，沙箱 DNS 劫持导致 gist/博客直连受限，以下为 curl 抓取 + 搜索摘要的核心要点。

## 一、Karpathy LLM-Wiki 模式（核心）

### 1. 基本思想
- 传统 RAG：每次查询重新检索原始 chunk → 无积累、无交叉引用、无复利理解
- LLM-Wiki：**agent 把源材料编译成互链的 markdown 文件**，形成持续增长的知识库 → 知识只编译一次，持续保鲜
- **"The LLM Wiki is a compiler for knowledge, not a search engine."**
- 来源：Karpathy gist `442a6bf555914893e9891c11519de94f`（5,000+ stars，2026-04 发布）

### 2. 三层架构
```
wiki/
├── SCHEMA.md           # 约定、结构规则、域配置
├── index.md            # 分区内容目录（一行摘要）
├── log.md              # 时间顺序操作日志（append-only）
├── raw/                # L1 不可变源材料（articles/papers/transcripts/assets）
├── entities/           # L2 实体页（人、组织、产品、模型）
├── concepts/           # L2 概念/主题页
├── comparisons/        # L2 对比分析
└── queries/            # L2 值得保留的查询结果
```

### 3. 增量更新（killer feature）
- 新源材料 → agent 先**识别受影响页面清单**（不动手）→ 人工裁定 blast radius → 只更新受影响页
- 关键 prompt："Read sources/new.pdf. List which existing wiki pages would need updates. Don't make changes yet."
- 避免每次全量重写

### 4. 已知边界（社区实测）
- **~200 文件是墙**：wiki 太大 agent 无法在 context 中持有全图 → 需要目录级索引（directory-level indexes）
- 无官方 v2，社区迭代：矛盾检测 prompt、自动索引生成
- 需要定期维护，不是一次性搭建

### 5. 使用栈
- Obsidian vault（或任何 markdown 编辑器）+ 编码 agent（Claude Code / OpenCode / Codex）+ Karpathy gist prompt
- 兼容 Obsidian：wikilinks 可点击、Graph View 可视化、YAML frontmatter 支持 Dataview

## 二、MemPalace / 记忆宫殿模式（增强机制）

### 1. 核心思想
- 用古希腊"记忆宫殿"（Method of Loci）作为组织隐喻：**空间层次结构**导航记忆
- 与 Mem0（压缩成事实摘要）不同：**存储完整对话原文**，按空间结构组织 + 语义搜索检索
- "fidelity over compression"——保真优先于压缩

### 2. 空间层次
```
记忆宫殿（Palace）
├── Wings（翼）
├── Halls（厅）
├── Rooms（房间）
├── Closets（柜）
└── Drawers（抽屉）
```
- 对应 GAI 中 MEM-002 "Session 层次标签（Wing/Room/Shelf）"——Frank 早已有这个想法

### 3. 技术栈（MemPalace 实现）
- **ChromaDB**：语义搜索，索引/决策零 LLM 干预（regex + 关键词评分，确定性、免费）
- **SQLite**：时间实体关系图，可查询特定时间点
- **Local-First**：100% 本地，无 API key（对比 Zep Graphiti 需要 Neo4j 云）
- **MCP Ready**：agent 可自动搜索、添加、查询知识图谱、写日记
- 启动仅 170 tokens，搜索准确率 96.6%（LongMemEval），完全离线

### 4. 关键取舍
- 存储完整性 vs 压缩成本：MemPalace 存全文（检索时按需取），Mem0 存摘要（prompt 注入）
- 记忆层本身零 LLM 调用（确定性启发式分类/分块/房间检测），LLM 只用于实际对话
- 局限：未在 BEAM（10M tokens 规模）测试，海量记忆下架构存疑

## 三、对本项目的启示（初步）

1. **记忆中间层 = L3 决策档案层**：现有 L0（kanban/GAI 状态，机器写）+ L1（session_search 情节检索）+ L2（mem0 语义记忆）之上，需要**可追溯的决策上下文层**
2. **wiki-llm 是核心存储**：互链 markdown 是记忆的"正文"，GAI/跨会话/项目文件都是它的应用
3. **记忆宫殿可作增强**：空间层次导航（Wing/Room/Shelf）正好对 MEM-002 的设想；本地确定性检索补充 FTS5 无 CJK 分词的短板
4. **已知墙**：200 文件上限 → 需要目录级索引策略；增量更新流程要内置
5. **数据源充足**：kanban.db（tasks/runs/comments/events 完整事件源）、devPPL roundtable 文档、会话历史都是 wiki 的原材料

## 四、参考链接
- Karpathy gist: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- kunalganglani 实测: https://www.kunalganglani.com/blog/llm-wiki-karpathy-local-knowledge-base
- SiliconFlow 教程: https://docs.siliconflow.com/en/usercases/how-to-build-a-personal-wiki-knowledge-base-andrej-karpathys-pattern-with-siliconflow-and-opencode
- MemPalace: https://recca0120.github.io/en/2026/04/08/mempalace-ai-memory-system
- MemPalace 评测: https://vectorize.io/articles/what-is-mempalace
