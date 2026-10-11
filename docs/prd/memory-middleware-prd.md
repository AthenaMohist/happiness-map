# Memory Middleware PRD — 记忆中间层（wiki-llm 核心）

> 作者：许清楚（产品负责人） | 日期：2026-08-12 | 版本：v1.2
> 来源：R3 圆桌三卷（product / architect / engineer）+ Frank 裁定（2026-08-10）→ 6 步闭环 Step 1 PRD
> 前提：R1/R2 已定案可继承项（GAI 决策档案四段式、memctl CLI、FTS5 trigram、boot_context v2 第五源）；R3 三方全部回归「wiki-llm 为核心」共识
> v1.1 修订（2026-08-10，D1 裁定）：§4 P0-4 命令面与 §10 交接项 2 统一为架构 §4 定稿面（MVP 7 命令 + V2 4 命令 + V3 占位），消除 §4/§10 命令数矛盾（D1-F2）
> v1.2 修订（2026-08-12，Frank 任务页愿景）：新增 §12 任务页愿景细化——补 4 缺口（page_type 枚举 / 建卡→wiki 采集链路 / 执行中更新机制 / bug→经验页关联），§4 增 P1-5，§5 增 §5.5 断言 G1-G4，§10 交接项同步（SCHEMA v1.1 + memctl 命令面扩展）。示范样板：mem-core commit f65b1ac 三页（WIKI-001 任务页 / devppl 项目页 / bug-lesson-template 经验页）
> v1.2 增补（2026-08-12，建卡流程固化）：新增 §12.6 交叉引用建卡铁律 v4（编号强制分配 + 连续步骤卡链，见 docs/prd/refine-card-numbering-chain-prd.md）——本任务（MEM-002）暴露的无编号/无卡链流程缺陷由此规则修复

---

## 0. 本 PRD 在整体规划中的定位

本 PRD 是记忆中间层 6 步闭环（PRD → 架构设计 → dev → QA → VA → merge/close）的 **Step 1**。它把 Frank 裁定与 R3 三卷共识转成一份可执行的需求文档：

```
Step 1  PRD（本文件）        ← 需求定义，Frank 裁定全量覆盖
Step 2  架构设计              ← 同仓/分仓落地细节、SCHEMA 定稿、memctl 接口契约
Step 3  dev（MVP 9.5h）       ← 引擎本体：repo + SCHEMA + 索引 + CLI + pytest
Step 4  QA                    ← golden file 测试体系（吸收 MEM-003）
Step 5  VA（验收）            ← 按 §5 验收标准逐条断言
Step 6  merge/close           ← close.sh S3 接线即中间层第一个强制写入点
```

**一句话定位**：记忆中间层 = Hermes 记忆的「知识编译层」（L3）+「检索导航层」（L4），以 wiki-llm 为核心完整开发，叠加在现有 L0/L1/L2 记忆之上渐进吸收，不推翻重建。**Frank 的厚望：它等价于 state.db，但自带双链和知识结构——每份文档（node）自带 frontmatter 和内容。**

---

## 1. 背景与痛点

### 1.1 五个痛点（按 Frank 可感知程度排序）

| # | 痛点 | 现状证据 | 中间层解法 |
|---|------|---------|-----------|
| P1 | **纠正遗忘**：教过的又忘 | 梦境报告投递被纠正 3 次仍复发（Roundtable-B 量化：Frank 月浪费 7-17h） | 纠正事件自动落 wiki 页，跨会话可检索 → 二次纠正率归零 |
| P2 | **决策不可追溯**：不知道当初为什么这么定 | 32 行 GAI 待办只有标题无背景/验收；kanban 只有状态机，没有"为什么" | 决策页四段式（背景/问题/验收/参考），30s 追溯 |
| P3 | **记忆碎片化**：5 个存储互不相通 | memory / mem0 / session_search / kanban.db / GAI 各自为政，无结构、无互链、无复利 | wiki-llm 编译层：各源知识编译成互链页面，知识只编译一次、持续保鲜 |
| P4 | **会话上下文断点**：换 session 就归零 | 100M token 上限被动切会话，OC 每次"失忆"，Frank 被迫重复解释 | 启动读取协议：新会话自动带出相关 wiki 页 |
| P5 | **待办无细节**（Frank 点名副产品） | GAI 32 行只有一行行动描述，无验收无背景 | 双链：GAI 行 → 详情页（中间层第一个应用，不是目标） |

### 1.2 核心隐喻：编译器，不是搜索引擎

Karpathy 原话——"The LLM Wiki is a compiler for knowledge, not a search engine."

- 传统 RAG = 每次查询重新检索原始 chunk → 无积累、无交叉引用、无复利
- LLM-Wiki = 把源材料编译成互链 markdown → 知识只编译一次，持续保鲜，矛盾显式标记

这个定位决定一切后续设计：**正确性度量是"编译质量"（互链完整、矛盾标记、updated 时间戳），不是"检索准确率"。**

### 1.3 北极星指标

**Frank 重复教的次数是否归零。**

- 辅助指标：决策追溯时长 ≤30s；新会话首轮主动带出正确上下文；同一纠正跨会话复发次数 = 0。
- **反指标（不是成功标准）**：wiki 页数、GAI 同步率、双链覆盖率。页面多是手段，"不重复教"才是目的。所有验收断言都往北极星靠，不往页数靠。

---

## 2. 目标与范围

### 2.1 核心目标

用新技术完整开发一个记忆中间层（memory middleware），wiki-llm 为绝对核心，弥补现有 Hermes 记忆不足。**它等价于 state.db，但自带双链和知识结构；每份文档（node）自带 frontmatter 和内容。**

关键判定（Frank 已裁定）：
1. **引擎本体优先**（F1）：MVP 9.5h = repo + SCHEMA + 索引 + CLI + pytest；GAI 只是 V2 适配器 1.5h，不是本体
2. **GAI 待办是附属品/MVP**：中间层搭成功后，GAI、跨记忆会话、项目共享文件存储自然产生解决办法
3. **LLM-WIKI 只要一个副本**：不要 12 个 profile 副本；通过标签、frontmatter 区分内容来自哪个 profile

### 2.2 覆盖范围：5 类记忆（Frank 原话）

| # | 记忆范围 | 中间层承载 |
|---|---------|-----------|
| 1 | profile 定义、积累的知识 | entities/（每 profile 一个实体页或标签）+ concepts/；frontmatter `profile:` 字段区分来源 |
| 2 | 某领域积累的知识 | 按 Wing（顶层域）分区；frontmatter `domain:` / `palace:` 标签 |
| 3 | 某项目积累的知识和踩过的坑 | 项目级 wiki（WIKI_PATH 按项目）；entities/ 机制页 + concepts/patterns 教训页 + raw/ 项目材料 |
| 4 | 所有会话及会话产生的知识和产物 | raw/sessions/ 摘要 + 会话编译产物（决策页、实体页）；log.md 操作日志 |
| 5 | **天然兼容并最终替代**：soul.md、memory.md、hermes.md（.hermes.md）、所有 skill 的 SKILL.md | 编译产物形态（frontmatter + 内容 + 双链）；**替代必须走红线流程（§7.2）** |

### 2.3 定位：补充层（L3 + L4），叠加渐进吸收

| 层 | 载体 | 写者 | 读时 | 本质 | 处置 |
|----|------|------|------|------|------|
| L0 确定性状态 | kanban.db / pipeline_state.db / GAI 表 | 机器脚本 | 每轮注入 | 事实真源，零 LLM | **不动**（基础设施） |
| L1 情节检索 | session_search / state.db 转录 | 会话自动 | 按需 | 原始历史，FTS5 | **不动**（基础设施） |
| L2 语义记忆 | memory 工具 / mem0 | agent 策展 | 每轮注入 | 蒸馏事实与偏好 | **保留为 fast-path，长期被 L3 吸收** |
| **L3 编译知识（新增·核心）** | **wiki-llm 互链 markdown** | **编译管线（单一写者）** | 会话启动 + 定向 | 编译后的持久记忆 | 中间层主体 |
| **L4 检索导航（新增）** | **SQLite FTS5 trigram + 空间标签 + 会话恢复协议** | 脚本 | 按需/启动 | 确定性检索、导航、跨会话恢复 | 中间层读路径 |

- **叠加 + 渐进吸收，明确否决推倒重建**：L0/L1 是机器写的基础设施，10 个 profile、全部依赖 kanban.db/state.db 的脚本都建立在它们上面；L2 短期保留（每轮注入的 fast-path 仍有价值），长期被 L3 的保真互链页吸收。
- **不是抽象层**：不统一封装 mem0/session_search/memory。三层检索语义不同、消费场景不同，强行抽象 = 让简单问题背上复杂度。中间层只做它们都做不到的事：长期、结构化、可追溯。

---

## 3. 非目标（明确不做）

| # | 不做 | 理由 / 处置 |
|---|------|------------|
| N1 | 不替代注入型记忆（memory/mem0 每轮注入机制） | 注入型解决"当前该记住什么"，检索型解决"为什么/怎么做"，两层分工 |
| N2 | 不做抽象层（统一封装 L0-L2 API） | 三层检索语义不同，强行统一成本远超收益 |
| N3 | 不引入向量检索作主路径（ChromaDB/embedding） | MEM-005 裁定维持不修；若未来上向量必须换 bge-m3 级中文模型，且为 V3 可选 |
| N4 | 不做 MCP server | 本环境集成面是 CLI + skill + boot_context 注入，无 MCP host 需求；预留 `mem mcp-serve` 占位 |
| N5 | 不修 mem0 平台侧债（MEM-003 原卡） | 独立平台侧质量债；中间层自己的测试体系是**新的** golden file 测试义务，不拿原卡掩盖 |
| N6 | 不替代 session_search 全文检索 | wiki 摘要给"现在该知道什么"，session_search 给"过去发生过什么"，两个检索面不合并 |
| N7 | MVP 不全量回填 GAI 32 行 | Frank 裁定：MVP 迁移时选 **5 项最重要待办**即可，不是全量 |
| N8 | 不复制 12 个 profile 副本 | LLM-WIKI 只要一个副本，标签/frontmatter 区分来源 |
| N9 | 不做"记得调用"类行为约定 | OBS-01 已证失败模式；写入必须挂已有强制路径（close.sh S3） |
| N10 | 不把 wiki 塞进每轮注入 | wiki 页太大不能注入；只通过 boot_context 摘要（≤800 字）被动可见 |

---

## 4. 需求清单（按优先级）

> 工时口径采用 Frank 裁定的 Engineer 版本：**MVP 9.5h（引擎本体）→ V2 ~10h（增量更新 + GAI 适配器）**。

### P0 — 引擎本体（MVP，9.5h，本周）

| ID | 需求 | 内容 | 工时 |
|----|------|------|:---:|
| P0-0 | 消灭双份拷贝 | `git rm` workspace GAI 副本（/workspace/devPPL/GLOBAL_ACTION_ITEMS.md，已实测零引用、分叉 33 天）；否则 wiki 就是第三个漂移面 | 0.2h |
| P0-1 | repo 初始化 + SCHEMA.md | mem-core repo 初始化；SCHEMA 定制：frontmatter 字段、wikilink 解析规则、**location 枚举（吸收 MEM-002，Wing/Room/Shelf）**、增量更新约定、单一写入者、三边界（wiki 不存状态/不替代检索/不存事实偏好）、目录级索引策略预留 | 1.5h |
| P0-2 | index/log 骨架 | index.md（类型 × 空间双视角）+ log.md（append-only） | 折叠进 P0-1 |
| P0-3 | memcore 库（确定性引擎） | parse.py（frontmatter + wikilink + 表格容错解析）、indexer.py（mem_meta.db：pages/links/events 三表 + **trigram FTS5 + bigram 回退表**，吸收 MEM-006 翻案）、lint.py（四不变式：断链 / 孤儿页 / status 镜像 / index 与文件一致） | 3h |
| P0-4 | `mem` CLI 骨架 | 单一写入者入口（**MVP 7 命令**）：`add / done / query / lint / index / status / context`；`mem lint` 零问题为一切提交前置；正式名 `memctl`，`mem` 为软链；V2 增 `update/drift/gai-links/demote`，V3 占位 `mcp-serve`——命令全集与退出码见架构 §4（D1-F2 裁定后定稿） | 1h |
| P0-5 | pytest 测试体系 | ~15 pytest（golden file 测试，吸收 MEM-003 为中间层测试义务）：解析器容错、索引幂等重建、lint 四不变式、trigram CJK 检索 | 折叠进 P0-3/P0-4 |
| P0-6 | boot_context v2 第五源 | `mem context --scope project/task` 引擎接入 boot_context.py；try-except 静默降级（mem-core 缺失不阻塞 5min 注入）；wiki 段 ≤800 字、优先级低于活跃任务段 | 1h |
| P0-7 | close.sh S3 替换 | `sed` → `mem done <ID>`（替换已有强制步骤，非新增约定）；任务完成自动写 wiki 页 + 状态镜像 | 0.5h |
| P0-8 | 备份接入 | mem-core repo 接入 manifest.yaml 备份链路（BKP-003 模式） | 0.3h |
| P0-9 | mem-worker skill 骨架 | 策展协议（何时调、怎么策展）；**单副本**，随 repo 走，各 profile 通过 skills 配置指向 repo 路径 | 0.2h |
| P0-10 | 首批真实内容 | R3 三方发言回填 3 页（LLM 策展）——用真实数据验证读/写/检索/漂移全链路 | 1.5h |
| | **小计** | | **9.5h** |

### P1 — 增量更新 + GAI 适配器（V2，~10h，下周）

| ID | 需求 | 内容 | 工时 |
|----|------|------|:---:|
| P1-1 | 增量更新引擎 | blast.py：`mem update <source> --plan`（反向索引查候选页，零 LLM，只列不动手）→ `--apply <pages...>`（LLM 只在候选集内读页改写、bump updated）；幂等：同一事件重复触发同一结果 | 3h |
| P1-2 | GAI 适配器 | `mem gai-links`（待办行补/校验 [[ID]] 命名双链）+ drift 三方对账（kanban vs wiki vs GAI）+ 状态镜像；**不需要 gai.py 表感知解析器**（GAI 降级为应用视图，R1 的 3h 预算整体消失） | 1.5h |
| P1-3 | 5 项最重要待办回填 | Frank 裁定：从 GAI 32 行中选 5 项最重要的待办，LLM 策展回填四段详情页（每页四段非空 + ≥1 参考 + ≥2 出链）；与编码并行 | 3.5h（并行） |
| P1-4 | 矛盾检测 | 同 topic 页冲突识别 + `contradictions:` 标记 + review 队列 | 2h（可与回填并行） |
| P1-5 | **任务页愿景增量（Frank 2026-08-12，4 缺口）** | ① SCHEMA 增 `page_type` 枚举（task/project/experience/conversation）+ `project`/`project_folder`/`task_code` 字段（G1）；② `memctl add task` 骨架采集链：从建卡信息（kanban 卡 body/标题/优先级/assignee/项目）机械采集 frontmatter + 背景节，零 LLM（G2）；③ `memctl note` 执行中更新：追加执行记录/状态变更（active→blocked→done）/bug 记录，机械零 LLM + 可选 LLM 补语义（G3）；④ `memctl experience` 关联：bug+方案 → 自动建/链经验页（page_type=experience），lint 校验关联完整（G4） | 3h |
| | **小计** | | **~13h** |

### P2 — 检索导航与记忆宫殿（L4，优先做机制设计，组件按规模触发）

| ID | 需求 | 内容 | 触发条件 |
|----|------|------|---------|
| P2-1 | 空间层次导航 | Wing/Room/Shelf frontmatter 标签 + index.md 空间分区（非目录，两套目录=双倍维护）；frontmatter 校验入 lint | SCHEMA 已含枚举，M0 折叠 |
| P2-2 | 会话启动协议 | SCHEMA → index → log（最近 20-30 条）→ 定向读相关页 → 注入上下文摘要；约 10-20 文件读取，全确定性路径 | P0 交付后立即启用 |
| P2-3 | /learn + /journey | /learn = 编译写入命令（L2 写入源），/journey = 空间浏览命令；learn 内容必须同时映射 wiki 概念页（防第 6 个孤岛） | P1 稳定后 |
| P2-4 | 项目共享文件正式启用 | raw/ 收不可变源材料 + entities/ 项目实体页 + index 分区；多项目 = 多 WIKI_PATH | P0 交付后 |

### P3 — 规模化与可选智能化（Frank 按优先级切，13h 上限）

| ID | 需求 | 内容 | 触发条件 |
|----|------|------|---------|
| P3-1 | 200 文件墙四层对策 | 目录级索引 > 分区 > 页 ≤200 行 > 归档（done/superseded → `_archive/` 移出活跃索引） | wiki >50 页 |
| P3-2 | embeddings 语义排序 | sqlite-vec + 中文向量（bge-m3-zh） | 语料 >500 页且关键词召回不足 |
| P3-3 | MCP adapter | `mem mcp-serve` 落地 | Hermes 生态出现 MCP 消费方 |
| P3-4 | DPL-013 事件钩子 | 引擎 post-kanban hook，约定层整体退役 | devPPL DPL-013 排期 |
| P3-5 | 每 profile 会话摘要 | `mem context --scope task` 推广到 worker 自动注入 | V2 稳定后 |

---

## 5. 验收标准（可验证断言）

> 每条断言在 VA 阶段可机械验证或可复现验证。**MVP 验收 = §5.1 全绿**；北极星为长期观测。

### 5.1 MVP 验收（P0 交付门禁）

| # | 断言 | 验证方式 |
|---|------|---------|
| A1 | workspace GAI 副本已从 git 删除，`git log` 可追溯删除提交 | `git ls-files | grep GLOBAL_ACTION_ITEMS` 为空 |
| A2 | `mem lint` 输出零问题（四不变式 I1-I4 全过；I5 page_type 校验随 P1-5 落地，MVP 阶段不生效） | 执行 `mem lint`，退出码 0 |
| A3 | `mem query <任意≥3 字中文词>` 命中对应页（trigram）；2 字词通过 bigram 回退表/LIKE 命中 | 对首批 3 页内容执行查询，预期词全命中 |
| A4 | `mem index --rebuild` 幂等：重复构建后 mem_meta.db 与 wiki 文件一致 | `mem lint` 在 rebuild 前后均为 0 问题 |
| A5 | close.sh 关闭任务自动写 wiki 页（`mem done` 生效），页面含结果节 + status=done + updated 时间戳 | 关闭一个测试任务，检查 wiki 页 |
| A6 | boot_context 输出包含 wiki 段（第五源）；mem-core 缺失/失败时 5min 注入不阻塞（静默降级） | 移除 mem-core 路径跑一次 cron，注入照常 |
| A7 | 备份 manifest 包含 mem-core repo | 执行备份，检查 manifest.yaml |
| A8 | 首批 3 页（R3 三方发言编译）四段非空 + ≥1 参考来源 + ≥2 出链 | `mem lint` 断链检查 + 人工抽查 |
| A9 | pytest 套件全绿（≥15 用例，含 golden file 测试） | `pytest` 退出码 0 |

### 5.2 V2 验收（P1 交付门禁）

| # | 断言 | 验证方式 |
|---|------|---------|
| B1 | `mem update <source> --plan` 输出候选页清单（含命中理由 term→pages），且**不读全 wiki** | 观察执行日志：读取文件数 < 20 |
| B2 | `mem gai-links` 对 5 项已回填待办零断链 | 执行 `mem gai-links`，输出为空 |
| B3 | 5 项最重要待办回填完成，每页四段非空 + ≥1 参考 + ≥2 出链 | `mem lint` + 人工抽查 |
| B4 | 矛盾检测：对同 topic 冲突内容打 `contradictions:` 标记并进 review 队列 | 注入两条冲突源，检查标记 |
| B5 | 周 drift 三方对账报告为空（kanban vs wiki vs GAI） | 执行 `mem drift`，输出为空 |

> **v1.2 增补（Frank 2026-08-12 任务页愿景，对应 P1-5 / §12）**：B6-B9 为任务页 4 缺口验收。

| # | 断言 | 验证方式 |
|---|------|---------|
| B6 | SCHEMA 定义 `page_type` 枚举（task/project/experience/conversation）+ `project`/`project_folder`/`task_code` 字段；示范三页（WIKI-001/devppl/bug-lesson-template）page_type 与目录/type 一致，lint 零问题 | 读 SCHEMA §3/§4 + 执行 `mem lint` |
| B7 | 建卡→wiki 采集链：新建待办（kanban 卡）→ 任务页骨架自动生成，frontmatter 含 page_type=task + project 双链 + project_folder + task_code + created/updated + 建卡信息（来源任务/优先级/assignee）；背景节含建卡上下文 | 建一张测试卡 → 检查 wiki 页 frontmatter/背景节 |
| B8 | 执行中更新：`mem note` 追加执行记录（状态/进展/bug），页面 updated 时间戳 bump；状态镜像 active→blocked→done 单向同步（L0→wiki，不回写） | 对测试任务执行 note/状态变更 → 检查执行记录节 + status |
| B9 | bug+方案 → 经验页关联：`mem experience`（或 note --bug）自动建/链经验页（page_type=experience，五段式模板），任务页与经验页双链互指；同类 bug 复用既有经验页不重复建 | 触发一次 bug 记录 → 检查经验页存在 + 双链 + lint 零问题 |

### 5.3 北极星长期观测（每项都有明确观测点）

| # | 断言 | 观测方式 |
|---|------|---------|
| C1 | **Frank 重复教的次数归零**（首观测点：MVP 交付后 1 周） | Frank 主观记录 / OC 会话日志 |
| C2 | 决策追溯时长 ≤30s：Frank 问"X 为什么这么做"→ 30s 内给出四段页 | 计时实测 |
| C3 | 新会话首轮主动带出正确上下文（最近纠正 + 活跃决策 + 当前任务） | 新会话首轮观察 |
| C4 | 同一纠正跨会话复发次数 = 0 | 跟踪已知纠正事件 |

### 5.4 反指标（验收时明确**不看**）

- ❌ wiki 页数增长（手段不是目的）
- ❌ GAI 同步率 100%（状态镜像只是副作用）
- ❌ 双链覆盖率（质量指标已有 lint 兜底，不做数字游戏）

---

## 6. 与现有系统的关系

### 6.1 五层关系总表

```
事件源（kanban 生命周期 / 会话摘要 / 纠正 / 决策 / GAI 更新）
  → ① 增量检测：识别受影响页面清单（LLM，只列不动手）→ blast radius 裁定
  → ② 语义编译：更新 raw/entities/concepts 页（LLM，幂等，bump updated）
  → ③ 机械维护：index.md / log.md / 双链校验（脚本，零 LLM）
  → ④ 原子提交 git + 备份 manifest

读取路径（两级：确定性优先，语义兜底）：
agent 会话启动 → 读 SCHEMA.md + index.md + log.md → 定向读相关页 → 注入上下文
按需查询 → SQLite FTS5 trigram 本地检索（零 LLM，零 API）→ 命中页面 → 读页合成

反向不成立：wiki 不产生状态、不回写 kanban、不替代 session_search 的全文检索。
状态流单向：L0 → 编译 → wiki → 读取。
```

### 6.2 关键集成点

| 集成点 | 现状 | 变更 |
|--------|------|------|
| close.sh S3 | `sed -i 's/待办/✅ done/'`（对新格式已 no-op） | 替换为 `mem done <ID>`（强制写入主路径） |
| boot_context.py | 读 pipeline_state/kanban/sessions/memory 四源 | v2 加第五源 `mem context`（≤800 字，try-except 降级） |
| 备份链路 | BKP-003 LFS 模式 | mem-core repo 接入 manifest.yaml |
| kanban-worker skill | — | 创建任务/新决策时 `mem add`（次路径，行为约定） |
| 周 cron | — | `mem drift` 只读兜底（滞后 ≤1 周可探测） |

### 6.3 repo 边界（与 devPPL 的物理隔离）

- **devPPL repo**：管代码/脚本/标准/PRD；提交按 slice
- **mem-core repo**：管记忆/决策/认知（引擎 + wiki 正文 + skill）；提交按事件
- 物理隔离保持：提交节奏不同（代码按 slice、记忆按事件），混仓毁 git log；单一写入者靠 repo 权限强制

---

## 7. 约束与红线

### 7.1 三条铁律（写进 SCHEMA，违反即 lint 失败）

1. **单一写入者**：所有写入走编译入口（memctl CLI），禁止多路 ad-hoc 写。GAI 双份拷贝分叉 33 天的教训 + OBS-01（LLM 忘记手动步骤）的教训。
2. **状态不回写环**：kanban.db / pipeline_state.db / GAI 表是 L0 真源，中间层只读不写。wiki 不产生状态。
3. **机械层零 LLM**：index 维护、双链校验、原子写、git 提交全部脚本化确定性完成；LLM 只做 blast radius 识别与页面语义编译。

### 7.2 🔴 红线：替代 Hermes 本体文件必须 Frank 确认（硬约束）

**涉及替代 soul.md、memory.md、hermes.md（.hermes.md）、SKILL.md 时，必须提前与 Frank 确认。本 PRD 将此写成硬约束：**

1. 中间层先以编译产物存在（L3），上述 Hermes 本体文件保持现状，**任何一项都不默认被替换**
2. 只有当"注入型需求"被证明可以等价地由 wiki 读取协议满足时，才逐项提出替换提案
3. 每个替换提案必须包含：GAI 决策档案四段式（背景/问题/验收/参考）+ 迁移脚本 + 回退方案
4. 替换提案由 Frank 逐项签字后方可执行；未签字 = 不替换

### 7.3 其他硬约束

| # | 约束 | 说明 |
|---|------|------|
| C1 | LLM-WIKI 只有一个副本 | 不复制 12 profile；frontmatter `profile:` 标签区分来源；mem-worker skill 单副本随 repo 走 |
| C2 | 旧 GAI 副本不用维护 | 引擎开发好后重新创建新的；迁移后把旧的删掉 |
| C3 | wiki 三边界 | 不存状态、不替代检索、不存事实偏好 |
| C4 | 每页 ≤200 行 | 超限拆子页 + 交叉链（llm-wiki 规则继承） |
| C5 | 增量更新禁止全量重写 | 新信息 → 矛盾检测 → 只更新受影响页 → bump updated → log |
| C6 | 主路径不依赖 embedding | MEM-005 裁定维持不修；上向量须换 bge-m3 级中文模型 |
| C7 | mem_meta.db 是派生数据 | 唯一真源是 wiki 文件；db 幂等重建 + lint 校验一致（复用双份拷贝教训） |
| C8 | Frank 只读 | git 写权限仅编译管线（memctl） |
| C9 | boot_context 降级优先 | mem-core 缺失/失败不得阻塞 5min 注入 |

---

## 8. 关键决策：F2 同仓 vs 分仓（产品推荐）

> Frank 裁定 F2 待架构裁决；本 PRD 给出产品侧明确推荐，供 Step 2 架构设计落地。

### 8.1 推荐：同仓（单一 mem-core repo，引擎 + wiki 正文 + skill 一个仓库）

```
/workspace/mem-core/            ← 独立 git repo（与 devPPL/InfoManager 同级）
├── memcore/                    # Python 库（确定性引擎）
│   ├── schema.py               # SCHEMA.md 的机器可读镜像
│   ├── parse.py                # frontmatter + wikilink + 表格解析（容错）
│   ├── indexer.py              # SQLite 图索引 + trigram FTS5 + bigram 回退表
│   ├── blast.py                # 增量更新候选集（反向索引，零 LLM）
│   ├── drift.py                # 漂移检测（时间戳/状态/断链）
│   ├── context.py              # 会话上下文摘要（boot_context v2 引擎）
│   └── lint.py                 # 五不变式校验（I1-I4 MVP + I5 page_type 随 P1-5）
├── bin/mem                     # CLI 入口：add / update / query / lint / drift / context / status
├── wiki/                       # 记忆正文（SCHEMA.md + index.md + log.md + entities/ + concepts/ + raw/ + _archive/）
└── SKILL.md                    # mem-worker skill 正文（策展协议，随 repo 走）
```

### 8.2 推荐理由（结合"方便安装/配置/维护/迁移 + 可能替换 Hermes 本体文件"的目标）

| # | 维度 | 同仓优势 | 分仓代价 |
|---|------|---------|---------|
| 1 | **防漂移（维护）** | SCHEMA 与解析器必须同步提交，lint 才能验证；改 SCHEMA 不提交解析器 = CI 红 | 两仓两套同步，SCHEMA 与解析器天然分家——GAI 双份拷贝分叉 33 天是同一个病 |
| 2 | **测试一致性（质量）** | golden file 测试需要正文样本与解析器同版本；同仓 = 测试夹具随代码走 | 跨仓 fixture 引用脆弱，测试环境难复现 |
| 3 | **备份/迁移单点（运维）** | 一个 repo 接入 BKP-003 链路；迁移 = `git clone` 一个单元 | 两仓两套备份两套 manifest，漏一个就是灾难 |
| 4 | **安装配置（部署）** | `git clone` + `pip install -e` + skills 配置指向 = 一个安装单元；各 profile 零拷贝 | 安装脚本要拼两仓，profile 引用点翻倍 |
| 5 | **替换本体文件（未来）** | 每个替换提案 = 一个 wiki 决策页 + 一个迁移脚本 + 回退方案，全部在 mem-core 内闭环；mem-core 作为**唯一同步/迁移单元** | 提案散落两仓，回退要跨仓协调 |
| 6 | **200 文件墙（规模）** | 分区即分目录，与代码同仓不冲突（wiki/ 子目录内部分区）；页面瘦身/归档规则在 SCHEMA 内统一维护 | 分仓不解决墙的问题，反而多一层跨仓导航 |

### 8.3 边界澄清（同仓 ≠ 塞进 devPPL）

- **同仓** = 引擎 + wiki 正文 + skill 在同一 mem-core repo（Engineer 反共识 3）
- **隔离保持** = mem-core 与 devPPL 物理隔离（Architect："wiki repo 本身就是共享存储"的定位不变）
- 两个裁定不冲突：devPPL 管代码/标准，mem-core 管记忆/认知；提交节奏不同，git log 可分辨

### 8.4 同仓的风险与对策（Step 2 架构设计需落实）

| 风险 | 对策 |
|------|------|
| wiki 正文高频提交污染 git log | 正文由 memctl 原子提交（单一写者）；按事件粒度提交，日志可接受；必要时 wiki/ 子目录独立 commit 约定 |
| 未来确需分仓（如多项目大 wiki） | 引擎保持对 SCHEMA 的 lint 校验；分仓时 CI 联动（引擎 repo 引 wiki 子模块或路径注入），SCHEMA 双版本漂移由 lint 拦截 |
| repo 变大拖慢 clone | 正文是 markdown 文本，量级 <10MB（200 页 × 50KB）；BKP-003 LFS 模式对超大附件按需启用 |

---

## 9. 风险与对策

| # | 风险 | 缓解 |
|---|------|------|
| R1 | 编译管线 LLM 质量参差 | 机械层全脚本化（index/校验/提交），LLM 只做 blast radius + 页面语义；lint 四不变式 + 周漂移兜底 |
| R2 | worker 忘触发编译 | close.sh S3 接线（强制路径）+ boot_context digest（被动可见）+ 周 cron 对账，三层保险，不靠约定 |
| R3 | P1 泛化时把 memctl 写死成 gai.py | 接口抽象（source adapter 模式），GAI 只是第一个 source，严禁 CLI 硬编码表名 |
| R4 | sqlite 版本 < 3.34 无 trigram | M1 第一步验证 sqlite 版本；退路 = 关键词评分 + LIKE 前缀，不阻塞整体 |
| R5 | mem_meta.db 双写漂移 | 唯一真源是 wiki 文件；db 幂等重建 + lint 校验 db/文件一致 |
| R6 | 回填质量参差 | 只求四段非空 + ≥1 参考来源 + ≥2 出链；措辞靠 lint 迭代，不追求一次性完美 |
| R7 | 200 文件墙 | 四层对策（目录级索引 > 分区 > 页≤200 行 > 归档）；关键认识：墙是编译期问题（blast radius 控制更新集），不是检索期问题 |
| R8 | 替代本体文件引发回归 | 红线流程（§7.2）：逐项提案 + 回退方案 + Frank 签字，任何一项未签字 = 不替换 |

---

## 10. 与下一阶段（Step 2 架构设计）的交接

Step 2 架构设计必须落地的关键项：

1. **SCHEMA.md 定稿（v1.1）**：frontmatter 字段全集（含 `profile:` / `palace:` / `location:` 枚举 + **v1.2 新增 `page_type`/`project`/`project_folder`/`task_code`，§12.1**）、wikilink 解析规则、三边界、四不变式定义（+ **v1.2 新增 I5：page_type 校验/映射/经验页入链**）
2. **memctl CLI 接口契约**：以架构 §4 定稿面为准——MVP 7 命令 `add / done / query / lint / index / status / context`，V2 4 命令 `update / drift / gai-links / demote`，V3 占位 `mcp-serve`；退出码 0=成功 / 1=一般错误 / 2=用法错误 / 3=校验失败（D1-F2 裁定，本 PRD §4 P0-4 同改）；**v1.2 扩展：`add task --from-kanban`（G2 机械采集）+ `note`（G3 执行中更新）+ `done --collect-notes`（G3 完成回填）**
3. **F2 落地**：按 §8 推荐同仓，细化 mem-core repo 目录布局与提交约定
4. **mem_meta.db schema**：pages/links/events 三表 + trigram FTS5 + bigram 回退表
5. **golden file 测试夹具**：首批测试用真实正文样本（R3 三页 + **WIKI-001/devppl/bug-lesson-template 示范三页**）
6. **boot_context v2 集成契约**：`mem context` 输出格式 + 字符预算分配
7. **close.sh S3 替换方案**：`mem done <ID>` 的调用点与状态镜像格式（**v1.2：扩展 `--collect-notes` 完成时回填**）
8. **建卡→wiki 采集链接线**（G2，§12.2）：autopilot discover 注册新任务时调 `memctl add task --from-kanban` 的调用点 + fail-open 守卫 + `--from-kanban` 读 kanban.db 的字段映射
9. **执行中更新接线**（G3，§12.3）：autopilot advance start_step 调 `memctl note --status active` 的调用点；worker 协议（mem-worker skill）中 note/bug 的调用约定；drift 对 status 镜像的兜底规则

---

## 11. 一句话结论

以 wiki-llm 为核心完整开发记忆中间层（L3 知识编译 + L4 检索导航），叠加在 L0/L1/L2 之上渐进吸收；**引擎本体 MVP 9.5h 优先**，单一写入者、状态不回写、机械层零 LLM，写入走 close.sh S3 强制路径 + boot_context v2 读取 + FTS5 trigram 零依赖解决 CJK 检索；**北极星是 Frank 重复教的次数归零**；替代 soul/memory/hermes.md/SKILL.md 必须逐项经 Frank 确认（硬红线）；**F2 推荐同仓**——mem-core 单仓让安装/配置/维护/迁移都是单点，未来替换本体文件时是唯一同步单元。**v1.2（Frank 2026-08-12 任务页愿景）**：任务页成为 wiki 的第一公民——page_type 四枚举 + project/project_folder 采集链 + 执行中 note 更新 + bug→经验页关联，详见 §12。

---

## 12. 任务页愿景细化（Frank 2026-08-12，4 缺口方案）

> 来源：Frank 2026-08-12 原话（完整愿景）+ OC 示范三页（mem-core commit f65b1ac）。本节是 v1.1 的增量需求，**不推翻 v1.1 任何定案**，只补 4 缺口。

**Frank 愿景一句话**：GAI 保存待办，OC 据 GAI 推进开发（调 autopilot 执行），每个任务双链进任务详情页；任务页要像 Hermes 记忆一样**自动维护迭代**——新建待办 = 全量采集（frontmatter + 相关对象 + 背景 + 上下文 + 建卡信息），执行中自动更新状态/记录 bug/关键改动点，bug+方案关联经验页，PRD/架构图/测试方案等 md 文档直接存 wiki（其他格式存项目文件夹，开发内容另算），日常对话发现的新技术/趣事也可记入。

### 12.1 G1 — page_type 枚举 + project/project_folder 字段（SCHEMA §3/§4 增量）

**设计原则：page_type 是"页面用途"维度，type 是"存储形态"维度，两者正交，不互相替代。**

| page_type | 用途（Frank 视角） | 对应 type | 目录 | 示范页 |
|-----------|-------------------|-----------|------|--------|
| `task` | 任务详情页（GAI 待办/kanban 卡详情） | `action` | `wiki/actions/` | WIKI-001 |
| `project` | 项目实体页（任务归属 + 项目级知识） | `entity` | `wiki/entities/` | devppl |
| `experience` | 经验/教训页（bug+方案、复盘） | `concept` | `wiki/concepts/patterns/` | bug-lesson-template |
| `conversation` | 对话历史页（日常对话发现、趣事） | `raw` | `wiki/raw/sessions/` | （预留，P2） |

**为什么不替换 type**：type 决定目录布局与解析器行为（机器视角，已有 14 页 + indexer + lint 依赖它）；page_type 决定语义用途（人/LLM 策展视角）。替换 = 破坏性重构；正交双字段 = 向后兼容（老页无 page_type，lint 按 type 推断默认值）。

**新增 frontmatter 字段（SCHEMA §4）**：

```yaml
page_type: task          # 可选（新页必填，老页缺省按 type 推断）。枚举: task|project|experience|conversation
project: "[[entities/devppl.md|devPPL]]"  # 可选。所属项目双链（任务页/经验页建议填）
project_folder: /workspace/devPPL  # 可选。项目文件夹路径（引用项目 frontmatter 的 project_folder）
task_code: DPL-010       # 可选。任务编号（项目内代码，与 GAI ID 对齐）
```

**lint 校验（新增不变式 I5）**：
- page_type 枚举非法 = lint 失败
- page_type↔type 映射不一致（task→action / project→entity / experience→concept / conversation→raw）= lint 失败
- page_type=task 且 project 存在时：project 双链必须指向存在的 entity 页，project_folder 非空
- 老页（无 page_type）不报错：按 type 推断（action→task、entity→project、concept→experience 仅当在 patterns/、raw→conversation）

### 12.2 G2 — 建卡→wiki 采集链（谁在何时写什么，不违反单一写入者）

**Frank 原话**："当我说新建一个待办任务，不光是加一行字上去，而是要把它的所有信息 frontmatter、相关对象、背景、上下文、建卡信息等等全都收集起来保存。"

**采集链设计（两段式：机械骨架 + 语义补全）**：

```
建卡（kanban_create / GAI 新增行）
  → ① 机械骨架（零 LLM，强制路径）：memctl add task <id> --from-kanban <卡ID>
       从 kanban 卡读结构化字段（标题/优先级/assignee/项目/body 摘要）
       → 生成 frontmatter（id/type=action/page_type=task/status=draft/priority/
         source_task/project/project_folder/task_code/created/updated/mechanism=memctl add）
       + 背景节（建卡上下文摘要，来自卡 body）
       + 参考节（相关对象双链占位：项目页/父任务/关联卡）
  → ② 语义补全（LLM，update 通道）：执行中/完成后 memctl update --apply 补四段式
       （背景/要解决的问题/验收标准/参考 + 执行记录），幂等
```

**谁在何时写什么**：

| 角色 | 何时 | 写什么 | 通道 |
|------|------|--------|------|
| autopilot/OC | 建卡瞬间（discover 注册新任务时） | 调 memctl add task 机械骨架（fail-open，mem-core 缺失不阻塞建卡） | memctl add task --from-kanban |
| worker | 领卡后、执行前 | 补全四段式背景/问题/验收（可选，LLM） | memctl update --apply |
| worker/autopilot | 执行中/完成 | 状态镜像 + 执行记录 + bug（§12.3） | memctl note / demote / done |
| memctl（脚本） | 每次写入后 | index/log/双链校验/原子提交（零 LLM） | 机械维护 |

**为什么挂 autopilot 而非 SQLite 触发器**：f56cd1f 的建卡瞬间触发器（est_intercept_after_insert）是 SQL 层，只能建评估卡不能调外部 CLI；采集链需要读 kanban 卡 body 并写 wiki 文件，必须走 memctl CLI。autopilot discover 是现成强制路径（新卡注册 pipeline 时触发），fail-open 保证不阻塞。

**三铁律合规**：
- 单一写入者 ✅：所有 wiki 写都经 memctl CLI；autopilot/worker 只调用 memctl，不直接 touch wiki 文件
- 状态不回写 ✅：采集只**读** kanban 卡字段，绝不写 kanban.db；status=draft 是 wiki 自身状态
- 机械层零 LLM ✅：骨架采集是从 kanban.db 读结构化字段 → 写 frontmatter 的确定性脚本；LLM 只在 update 通道做可选语义补全

### 12.3 G3 — 执行中更新机制（状态镜像 + 执行记录 + bug）

**Frank 原话**："当执行任务的过程中，要能自动更新状态，记录 bug，关键改动点等。"

**机制：memctl note（新增命令，机械零 LLM）+ 状态镜像扩展**：

```bash
memctl note <id> --status <active|blocked|done> [--text "进展/bug/关键改动点"] [--bug "现象" --solution "方案"]
# 动作：追加「执行记录」节条目（ISO 时间戳 + 文本）→ bump updated → 若 --status 则同步 status 镜像 → 维护 + 提交
# 零 LLM：纯确定性脚本（追加文本、时间戳、状态字段、index/log/commit）
```

**接线点（强制路径优先，行为约定兜底）**：

| 事件 | 触发者 | 命令 | 强制程度 |
|------|--------|------|---------|
| 任务开始执行 | autopilot advance start_step | memctl note <id> --status active | 强制（挂 advance） |
| 执行中进展/bug/改动点 | worker | memctl note <id> --text "..." / --bug ... | 协议约定（OBS-01 已证纯约定会忘，故以完成时回填兜底） |
| 任务阻塞 | worker kanban_block 时 | memctl demote <id> --status blocked --reason "..." | 协议约定 + drift 兜底 |
| 任务完成 | close.sh S3（已有） | memctl done <id> --result "..." | 强制（close.sh 已接线） |

**完成时回填兜底（解决 OBS-01 "LLM 忘记手动步骤"）**：close.sh S3 扩展为 `memctl done <id> --collect-notes`——若执行中 worker 漏了 note，完成时从 kanban 卡 comment/claim 提取关键记录一次性回填执行记录节（机械提取，零 LLM）。

**三铁律合规**：
- 单一写入者 ✅：note/demote/done 全部 memctl CLI
- 状态不回写 ✅：status 镜像单向 L0→wiki；note --status 只写 wiki 页 status 字段
- 机械层零 LLM ✅：note/demote/done 都是确定性脚本；LLM 不参与状态机，只在 update 通道补语义

### 12.4 G4 — bug+方案 → 经验页关联

**Frank 原话**："bug 和解决方案可以关联到经验页面。"

**机制：经验页五段式（现象/根因/解决方案/教训/来源任务）+ 自动查重关联**：

```bash
# worker 记录 bug（机械追加执行记录 + 自动查重经验页）
memctl note <task_id> --bug "现象描述" --solution "解决方案"
# memctl 内部（零 LLM 部分）：
#   1. 追加任务页「执行记录」节
#   2. FTS5 查询 concepts/patterns/ 既有经验页（按 bug 关键词查重）
#   3a. 命中同类 → 任务页 links 追加既有经验页双链（不重复建）
#   3b. 未命中 → 建经验页骨架（page_type=experience，五段式模板，status=draft）
# 可选 LLM 补全：memctl update --apply 补根因/教训语义
```

**经验页形态**（示范：concepts/patterns/bug-lesson-template.md）：
- frontmatter：`type: concept` + `page_type: experience` + `tags: [bug, lesson]` + `links`（来源任务双链）
- 正文五段：现象 → 根因 → 解决方案 → 教训 → 来源任务（`[[任务页]]` 双链回任务）

**lint 校验（I5 扩展）**：
- page_type=experience 页必须 ≥1 入链来自 task 页（防孤儿经验页——"来源任务"节双链即满足）
- 经验页与任务页双链互指校验（任务页 links 含经验页 ↔ 经验页来源任务含任务页）

**三铁律合规**：经验页创建/更新全部经 memctl CLI（单一写入者 ✅）；经验页是 wiki 编译产物，不回写任何 L0 状态（✅）；查重（FTS5）与骨架生成是确定性脚本，LLM 仅在 update 通道补根因/教训（机械层零 LLM ✅）。

### 12.5 文档与日常对话落库（Frank 愿景其余部分）

| Frank 要求 | 方案 | 状态 |
|-----------|------|------|
| PRD/架构图/测试方案等 md 文档存 wiki | `raw/` 收不可变源材料（P2-4 已有）；决策/概念页编译形态 | 已有（P2-4） |
| 非 md 格式文件存项目文件夹 | 项目文件夹 = project_folder 指向的目录；wiki 页引用路径 | 已有（project_folder 字段） |
| 开发内容另算 | devPPL repo 管代码；wiki 只存编译知识 | 已有（§6.3 物理隔离） |
| 日常对话发现新技术/趣事记入 | conversation 页（page_type=conversation，raw/sessions/）+ /learn（P2-3 已有） | P1-5 落地后启用 |

### 12.6 建卡编号 / 卡链机制（v1.2 增补，交叉引用建卡铁律 v4）

Frank 2026-08-12 裁定：「以后从 gai 来建任务，必须要有唯一编号」。本任务（MEM-002）暴露的两个流程缺陷（无 MEM-0xx 编号、PRD-REFINE 与架构设计卡 task_links=0）由跨项目流程规则修复：

- **规则文档**：`docs/prd/refine-card-numbering-chain-prd.md`（建卡铁律 v4，2026-08-12）
- **规则 1（编号强制分配）**：任何从 GAI 发起 / 属于某项目的任务，建卡时必须带唯一编号 `[CODE]-NNN`（记忆中间层=MEM-0xx）；编号在 GAI 行 + wiki 页（frontmatter `id`/`task_code`）+ kanban 卡三处一致
- **规则 2（连续步骤卡链）**：同一任务连续步骤（PRD→架构→dev→QA→VA）必须构成 task_links parent→child 链，禁止独立平铺
- **MEM-002 承接**：本任务即编号与卡链机制的「示范样本」——wiki 页 `id: MEM-002` + GAI 行 `[[MEM-002]]` + 补链 t_b476baba→t_b353d348 已归位（commit 1686c67）

验收落点：§5.5 B7 建卡→wiki 采集链的 frontmatter 中 `task_code` 字段即 v4 编号；`memctl drift` / `lint` 扩展覆盖编号三方一致性（详见 v4 PRD §5）。

---
