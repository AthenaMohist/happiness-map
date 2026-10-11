# Memory Middleware 架构设计 — 记忆中间层（L3 知识编译层 + L4 检索导航层）

> 发言人：高见远（架构师） | 日期：2026-08-10 | 版本：v1.0
> 输入：PRD v1.0（docs/prd/memory-middleware-prd.md，commit 87731a4）+ R3 三卷（product/architect/engineer）+ R1 调研资料 + Frank 裁定（2026-08-10）
> 定位：6 步闭环 Step 2 —— 把 PRD §10 交接的 7 项全部落地为可执行设计，工程师可直接照写代码
> 核心隐喻：**wiki-llm 是知识的编译器，不是搜索引擎**（Karpathy）。正确性度量 = 编译质量（互链完整、矛盾标记、updated 时间戳），不是检索准确率。

---

## 0. 范围定义

### 0.1 本设计做什么（PRD §10 七项交接全覆盖）

| # | PRD 交接项 | 本设计章节 |
|---|-----------|-----------|
| 1 | SCHEMA.md 定稿 | §3 |
| 2 | memctl CLI 接口契约 | §4 |
| 3 | F2 落地（同仓 repo 布局与提交约定） | §2 |
| 4 | mem_meta.db schema | §5 |
| 5 | golden file 测试夹具 | §9 |
| 6 | boot_context v2 集成契约 | §7 |
| 7 | close.sh S3 替换方案 | §8 |

另覆盖任务书要求：整体架构图（§1）、blast radius 增量更新（§6）、200 文件墙对策（§10）、替代本体文件迁移机制（§11）、部署与备份方案（§12）。

### 0.2 架构裁决总表（对 PRD §8 推荐与 Frank 裁定的确认/细化）

| 决策点 | 裁决 | 说明 |
|--------|------|------|
| F2 repo 形态 | ✅ **同仓**：/workspace/mem-core 单 repo（引擎 + wiki 正文 + skill） | PRD §8 推荐，六条理由全接受；§2 细化目录布局与提交约定 |
| 定位 | L3 编译层 + L4 检索导航层，叠加渐进吸收 | 否决推倒重建；L0/L1 不动，L2 保留 fast-path |
| 编译管线是主体 | 确认"编译器不是搜索引擎" | 索引/检索是编译质量的副产品，不是目标 |
| 记忆宫殿 | Wing/Room/Shelf = frontmatter 标签 + index 双视角，**非目录** | 两套目录 = 双倍维护；§3.4 定义 taxonomy |
| 跨会话恢复 | 启动协议（SCHEMA→index→log→定向读页）+ boot_context v2 | §7 |
| 写入三层 | close.sh S3 主路径（强制）+ skill 协议（次路径）+ 周 cron 兜底 | §8；不靠行为约定（OBS-01 教训） |
| 增量更新 | blast radius 先列受影响页（零 LLM）→ 只更新受影响页 | §6 |
| 200 文件墙 | 四层对策：目录级索引 > 分区 > 页≤200行 > 归档 | §10 |
| 替代本体文件 | 编译产物先存在、本体保持现状、等价性证明后逐项提案 | §11（红线流程落地） |
| 北极星 | Frank 重复教的次数归零 | 所有验收断言向北极星靠，不向页数靠 |

### 0.3 明确不做（继承 PRD §3 N1-N10 + 架构层补充）

- ❌ 不替代注入型记忆（memory/mem0 每轮注入机制保持原样）
- ❌ 不做抽象层（不统一封装 L0-L2 API）
- ❌ 不引入向量检索作主路径（MEM-005 维持；V3 可选须换 bge-m3 级中文模型）
- ❌ 不做 MCP server（预留 `memctl mcp-serve` 占位）
- ❌ 不替代 session_search 全文检索（两个检索面不合并）
- ❌ 不复制 12 个 profile 副本（LLM-WIKI 单副本，frontmatter 标签区分来源）
- ❌ 不把 wiki 塞进每轮注入（只通过 boot_context 摘要 ≤800 字被动可见）
- ❌ 不改 mem0 平台侧债（MEM-003 原卡独立；中间层测试义务是**新的** golden file 测试）
- ❌ 不做守护进程/HTTP 服务（13 profile 同机，服务化 = 新增可用性依赖；local-first 文件 + 确定性检索）
- ❌ 架构层补充：不把 memctl 写死成 gai.py（source adapter 模式，GAI 只是第一个 source，严禁 CLI 硬编码表名）

---

## 1. 整体架构：分层全景 + 数据流

### 1.1 五层全景（叠加 + 渐进吸收）

| 层 | 载体 | 写者 | 读时 | 本质 | 处置 |
|----|------|------|------|------|------|
| L0 确定性状态 | kanban.db / pipeline_state.db / GAI 表 | 机器脚本 | 每轮注入 | 事实真源，零 LLM | **不动**（基础设施） |
| L1 情节检索 | session_search / state.db 转录 | 会话自动 | 按需 | 原始历史，FTS5 | **不动**（基础设施） |
| L2 语义记忆 | memory 工具 / mem0 | agent 策展 | 每轮注入 | 蒸馏事实与偏好 | **保留为 fast-path，长期被 L3 吸收** |
| **L3 编译知识（新增·核心）** | **wiki-llm 互链 markdown（mem-core/wiki/）** | **编译管线 memctl（单一写者）** | 会话启动 + 定向 | 编译后的持久记忆 | 中间层主体 |
| **L4 检索导航（新增）** | **SQLite FTS5 trigram + bigram 回退 + 空间标签 + 会话恢复协议** | 脚本 | 按需/启动 | 确定性检索、导航、跨会话恢复 | 中间层读路径 |

### 1.2 数据流（三条路径 + 一条反向禁令）

**写入路径（事件驱动，单向，唯一入口 = memctl）**：
```
事件源（kanban 生命周期 / 会话摘要 / 纠正 / 决策 / GAI 更新）
  → ① 增量检测：memctl update --plan（反向索引查候选页，零 LLM，只列不动手）→ blast radius 裁定
  → ② 语义编译：更新 raw/entities/concepts/actions 页（LLM，幂等，bump updated）
  → ③ 机械维护：index.md / log.md / 双链校验（脚本，零 LLM）
  → ④ 原子提交 git（memctl 单写者）+ 备份 manifest
```

**读取路径（两级：确定性优先，语义兜底）**：
```
agent 会话启动 → boot_context v2 第五源 memctl context（≤800 字）
                   ↓ 深读时
                 读 SCHEMA.md + index.md + log.md → 定向读相关页（10-20 文件，零 LLM）
按需查询 → memctl query（FTS5 trigram → bigram 回退 → LIKE，零 LLM 零 API）→ 命中页面 → 读页合成
```

**更新路径（增量，禁止全量重写）**：
```
新信息 → 矛盾检测 → 标记 contradictions: / 双版本并存 → 只更新受影响页 → bump updated → log
```

**反向不成立（状态流单向）**：
```
L0 → 编译 → wiki → 读取
wiki 不产生状态、不回写 kanban/pipeline_state/GAI、不替代 session_search 全文检索
```

### 1.3 宏观架构图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    记忆中间层 Memory Middleware（L3 + L4）                          │
│                                                                                 │
│  ┌─────────────────── 编译管线 Compile Pipeline（写入·单一入口 memctl）────────────┐ │
│  │ 事件源: kanban 生命周期 / 会话摘要 / 纠正 / 决策 / GAI 更新                      │ │
│  │    │ ① blast radius 识别（memctl update --plan，零 LLM，只列不动手）             │ │
│  │    ▼                                                                         │ │
│  │ ② 语义编译: 更新 raw/entities/concepts/actions 页（LLM，幂等，bump updated）    │ │
│  │    ▼                                                                         │ │
│  │ ③ 机械维护: index.md / log.md / 双链校验 / mem_meta.db 增量（脚本，零 LLM）      │ │
│  │    ▼                                                                         │ │
│  │ ④ 原子提交 git + 备份 manifest（BKP-003 链路）                                 │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─────────────────── 存储层 Wiki Store（L3·核心，mem-core/wiki/）───────────────┐ │
│  │ SCHEMA.md │ index.md（类型×空间双视角）│ log.md（append-only）                 │ │
│  │ raw/（不可变源）│ entities/（稳定实体）│ concepts/（概念·模式）                  │ │
│  │ concepts/decisions/（决策四段页）│ actions/（GAI 待办详情页 [[ID]]）            │ │
│  │ _archive/（归档）                                                             │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─────────────────── 检索/导航层 Read Path（L4）──────────────────────────────┐  │
│  │ 空间导航: Wing/Room/Shelf 标签 + index 分区（非目录，纯机械维护）              │  │
│  │ 本地检索: SQLite FTS5 trigram（CJK 原生）+ bigram 回退表（零 LLM·零 API）      │  │
│  │ 反向索引: term → pages（blast radius 候选集计算，零 LLM）                     │  │
│  │ 会话恢复: SCHEMA→index→log→定向读页→上下文注入（跨会话协议）                   │  │
│  │ 用户接口: memctl CLI（add/done/update/query/lint/drift/context/status）      │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
          │ 读（机械注入/定向）                           │ 写（事件驱动，唯一入口）
          ▼                                              ▲
┌──────────────────────────── 现有记忆体系（不动）──────────────────────────────────┐
│ L0 确定性状态: kanban.db / pipeline_state.db / GAI 表（机器写，真源）               │
│ L1 情节检索: session_search / state.db（FTS5 原始历史）                            │
│ L2 语义记忆: memory 工具 / mem0（每轮注入 fast-path，逐步被 L3 吸收）               │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. F2 落地：mem-core 同仓 repo 布局与提交约定

### 2.1 目录布局（定稿）

```
/workspace/mem-core/                     ← 独立 git repo（与 devPPL 同级，物理隔离）
├── memcore/                             # Python 库（确定性引擎）
│   ├── __init__.py
│   ├── schema.py                        # SCHEMA.md 的机器可读镜像（frontmatter 字段、type 枚举、location 枚举、ID 模式）
│   ├── parse.py                         # frontmatter + wikilink + 表格解析（容错）
│   ├── indexer.py                       # mem_meta.db 构建：pages/links/events + FTS5 trigram + bigram + term_pages 反向索引
│   ├── blast.py                         # 增量更新候选集计算（反向索引查表，零 LLM）
│   ├── drift.py                         # 漂移检测（时间戳/状态/断链/三方对账 kanban vs wiki vs GAI）
│   ├── context.py                       # 会话上下文摘要（boot_context v2 的引擎）
│   ├── lint.py                          # 四不变式校验
│   ├── cli.py                           # memctl 命令分发（argparse，禁止硬编码 GAI 表名）
│   └── sources/                         # source adapter 模式（GAI 是第一个，后续接 kanban/会话/纠正）
│       ├── __init__.py
│       ├── base.py                      # SourceAdapter 抽象（fetch_events / map_ids / mirror_status）
│       └── gai.py                       # GAI 适配器（gai-links + drift 三方对账 + 状态镜像，1.5h）
├── bin/memctl                           # CLI 可执行入口（#!/usr/bin/env python3 → memcore.cli:main）
├── bin/mem                              # 官方短别名（symlink → memctl；PRD/R3 历史文档引用 mem，软链保证两名字同一入口）
├── wiki/                                # 记忆正文（L3 编译产物）
│   ├── SCHEMA.md                        # 域规则（§3 全文）
│   ├── index.md                         # 目录（类型 × 空间双视角，脚本维护）
│   ├── log.md                           # append-only 操作日志
│   ├── raw/                             # 不可变源材料（sessions/ events/ research/）
│   ├── entities/                        # 稳定实体页
│   ├── concepts/                        # 概念/模式页
│   │   └── decisions/                   # 决策档案四段页（type=decision）
│   ├── actions/                         # GAI 待办详情页（每 ID 一页，如 P0-19.md）
│   └── _archive/                        # 归档（done/superseded 移出活跃索引）
├── tests/                               # golden file 测试体系（§9）
│   ├── conftest.py
│   ├── test_parse.py
│   ├── test_indexer.py
│   ├── test_lint.py
│   ├── test_query.py
│   ├── test_blast.py
│   ├── test_context.py
│   ├── test_done.py
│   └── golden/                          # 真实正文样本夹具（R3 三页编译产物等）
├── SKILL.md                             # mem-worker skill 正文（策展协议，随 repo 走，单副本）
├── pyproject.toml                       # pip install -e 安装单元
├── pytest.ini
└── README.md
```

### 2.2 提交约定

| 约定 | 规则 |
|------|------|
| 提交粒度 | 按事件（一次 `memctl done/add/update` = 一个 commit），commit message 由 memctl 生成：`mem(<ID>): <type> <摘要>` |
| 单一写者 | git 写权限仅 memctl（编译管线）；Frank 只读（C8）。repo 权限强制：`git config receive.denyNonFastForwards` + 日常操作走 memctl |
| 提交原子性 | ③ 机械维护（index/log/db 增量）与 ② 语义编译必须同一 commit；禁止单独提交 index 或正文（防中间态） |
| wiki/ 与引擎 | 同仓同版本；SCHEMA 改动必须与 schema.py/parse.py 同步提交，`memctl lint` 在 CI 校验（改 SCHEMA 不提交解析器 = lint 红） |
| 防漂移 | mem_meta.db **不提交 git**（派生数据，.gitignore）；唯一真源是 wiki 文件 |

### 2.3 与 devPPL 的边界

- **devPPL repo**：管代码/脚本/标准/PRD；提交按 slice
- **mem-core repo**：管记忆/决策/认知；提交按事件
- 物理隔离保持：提交节奏不同，混仓毁 git log；单一写入者靠 repo 权限强制
- 集成点反向：devPPL 的 close.sh / boot_context.py **只通过 memctl CLI 与 mem-core 交互**，不直接读 wiki 文件内部格式（除 boot_context 深读协议外，§7）

---

## 3. SCHEMA.md 完整定稿

> 本节全文即 wiki/SCHEMA.md 的权威内容。schema.py 是它的机器可读镜像（两者必须同步，lint 校验）。

### 3.1 节点类型（type 枚举）

| type | 目录 | 内容 | 写者 |
|------|------|------|------|
| `raw` | wiki/raw/ | 不可变源材料（会话摘要、事件快照、调研资料）；git 版本化，编译输入 | memctl add raw（机械） |
| `entity` | wiki/entities/ | 稳定实体：机制、项目、角色、工具（"watchdog v5 于 2026-07-23 上线"） | memctl 编译（LLM 策展） |
| `concept` | wiki/concepts/ | 概念/主题/模式：事件驱动、fail-open、单一写者、双链约定 | memctl 编译（LLM 策展） |
| `decision` | wiki/concepts/decisions/ | 决策档案四段式（背景/问题/验收/参考）——GAI 详情页的核心形态 | memctl 编译（LLM 策展） |
| `action` | wiki/actions/ | GAI 待办详情页（每 ID 一页，如 P0-19.md）；状态镜像 L0 | memctl done/add（机械+LLM） |

### 3.2 frontmatter 字段全集

```yaml
---
id: P0-19                  # 必填，唯一。ID 模式见 3.3
type: action               # 必填，枚举见 3.1
status: done               # 必填，枚举: draft|active|done|superseded|archived
priority: P0               # action/decision 必填，枚举: P0|P1|P2|P3|P4|P5；其余可选
mechanism: close.sh        # 可选。生效机制/写入机制（close.sh|cron|skill 协议|memctl add|manual）
est_hours: 9.5             # action 必填。预估工时（数字，小时）
created: 2026-08-10T08:00:00Z   # 必填。ISO8601 UTC
updated: 2026-08-10T09:30:00Z   # 必填。ISO8601 UTC（语义编译/状态变更时 bump）
source_task: t_2345b07e    # 可选。来源 kanban 任务 ID（t_ 前缀）
external_id: MEM-003       # 可选。外部系统 ID（GAI 编号等）
links:                     # 可选。显式出链（正文内 [[wikilink]] 之外的补充）
  - concepts/single-writer.md
location: devppl/memory/architecture   # 可选（P2 起必填）。Wing/Room/Shelf，见 3.4
profile: game-architect    # 可选。内容来源 profile（LLM-WIKI 单副本，标签区分来源）
domain: devppl             # 可选。领域标签（与 location.wing 对齐）
tags:                      # 可选。自由标签数组
  - architecture
  - memory
contradictions:            # 可选。矛盾标记（P1-4 矛盾检测写入）
  - concepts/rag-vs-compiler.md
superseded_by:             # 可选。被谁取代（status=superseded 时必填）
archived_at: 2026-09-01    # 可选。归档时间（status=archived 时必填）
---
```

**lint 校验规则**：
- 必填字段缺失 = lint 失败（id/type/status/created/updated）
- 枚举值非法 = lint 失败（type/status/priority/location 三段）
- id 与文件名不一致 = lint 失败（id 必须等于文件名去扩展名，actions/ 除外——actions/ 文件名为外部 ID）
- status=superseded 无 superseded_by = lint 失败
- 每页 ≤200 行（C4，超限 = lint 警告，拆子页 + 交叉链）

### 3.3 wikilink 解析规则

正文内双链语法（兼容 Obsidian）：`[[目标]]` 或 `[[目标|显示文本]]`。

**解析优先级**（parse.py 实现）：
1. **ID 模式**：`[A-Z]+-\d{2,3}`（如 `P0-19`、`MEM-003`、`DPL-011`）→ `wiki/actions/<ID>.md`（ID 大写规范化，两位三位兼容——兼容 GAI 现有两位编号 P0-19）
2. **相对路径**：`[[concepts/single-writer.md]]` → 按 wiki/ 根相对解析
3. **名称映射**：`[[单一写者]]` → 查 index.md 的 title → id 映射表（由 indexer 构建）；命中唯一则解析，多义则 lint 报歧义
4. **别名**：`[[目标|显示]]` → 链接目标按 1-3 解析，显示文本为 `显示`

**断链判定**：以上 1-3 全部失败 = 断链，`memctl lint` 报告（不变式 I1）。
**禁止裸 URL 式断链**：`[[目标]]` 若目标页不存在但近期将创建（待办未回填），允许带 `status: planned` 的占位页（actions/ 由 `memctl add task` 骨架预填），不视为断链。

### 3.4 空间标签 taxonomy（Wing/Room/Shelf，非目录）

`location` 字段格式：`<wing>/<room>/<shelf>`（三段，斜杠分隔，小写 slug）。

**Wing（顶层域，枚举）**：
| wing | 含义 |
|------|------|
| `devppl` | devPPL 项目域 |
| `infomanager` | InfoManager 项目域 |
| `hermes` | Hermes 引擎/平台域 |
| `claude` | Claude Code 集成域 |
| `general` | 通用/跨域 |

**Room（子域/主题，枚举，可扩展）**：
| room | 含义 |
|------|------|
| `memory` | 记忆系统 |
| `pipeline` | 管线/闭环 |
| `qa` | QA 标准/发现 |
| `roundtable` | 圆桌/裁定 |
| `backup` | 备份/DR |
| `tooling` | 工具链 |
| `integration` | 集成点 |
| `general` | 通用 |

**Shelf（具体架子，自由标签，lint 校验已注册值）**：如 `architecture`、`testing`、`patterns`、`lessons`、`decisions`、`corrections`。

**新增值流程**：新 wing/room/shelf 必须先写入 SCHEMA.md 枚举表（含一句话定义），再使用；lint 校验 location 三段均为已注册值。这是"标签不是目录"的配套约束——避免标签体系失控。

**双视角**：index.md 提供两个视图——按 type（文件类型轴）+ 按 location（空间轴）。一个文件同时属于"entity 页"和"devppl/memory/architecture 房间"，零文件移动，纯机械维护（indexer 生成）。

### 3.5 三条铁律（违反即 lint 失败）

1. **单一写入者**：所有写入走编译入口 memctl CLI，禁止多路 ad-hoc 写。GAI 双份拷贝分叉 33 天的教训 + OBS-01（LLM 忘记手动步骤）的教训。
2. **状态不回写环**：kanban.db / pipeline_state.db / GAI 表是 L0 真源，中间层只读不写。wiki 不产生状态。
3. **机械层零 LLM**：index 维护、双链校验、原子写、git 提交、mem_meta.db 构建全部脚本化确定性完成；LLM 只做 blast radius 识别（候选集内裁定）与页面语义编译。

**确定性 vs LLM 分工线**（判定原则：**输出可机械校验的进代码，输出需要理解的进 LLM**）：

| 归确定性引擎（代码，零 LLM） | 归 LLM 策展（agent） |
|------------------------------|---------------------|
| 解析 frontmatter/wikilink/表格 | 详情页四段正文撰写/更新 |
| 索引构建、反向索引、blast 候选集 | 候选集内裁定"哪几页真要改" |
| 漂移检测（时间戳/状态/断链） | 矛盾识别与裁决（打 contradictions: 标记） |
| CJK 检索（trigram+bigram） | 新决策的语义归纳（为什么/怎么算完） |
| 状态镜像（kanban→wiki status） | — |

### 3.6 三边界（wiki 不做什么）

1. **wiki 不存状态**：任务状态在 kanban.db；wiki 页 status 是镜像（供追溯），镜像由 memctl 从 L0 单向同步，不回写
2. **wiki 不替代检索**：不替代 session_search 的全文检索（L1 原始历史）；wiki 摘要给"现在该知道什么"
3. **wiki 不存事实偏好**：每轮注入的原子事实/偏好仍住 memory/mem0（L2 fast-path）；wiki 存编译后的知识结构（保真 + 互链）

### 3.7 四不变式（memctl lint 校验，零问题为一切提交前置）

| # | 不变式 | 校验内容 | 对应 A 断言 |
|---|--------|---------|------------|
| I1 | **断链零容忍** | 所有出链 wikilink 目标存在（解析规则 3.3）；actions/ 页 ID 与外部源一致 | A2, A8 |
| I2 | **孤儿页零容忍** | 每页 ≥2 出链且 ≥1 入链（SCHEMA/index/log 三首页除外） | A2 |
| I3 | **status 镜像** | action/decision 页 status 与 L0 真源（kanban/GAI）一致 | A2, A5 |
| I4 | **index 与文件一致** | index.md 页面清单 == wiki 实际文件清单；mem_meta.db 与文件一致（checksum） | A2, A4 |

---

## 4. memctl CLI 接口契约

> 命令名 **memctl**（正式），`mem` 为官方软链别名（PRD/R3 历史文档引用 mem，软链保证两名字同一入口）。
> 实现：bin/memctl → memcore.cli:main，argparse 分发。**禁止在 CLI 层硬编码 GAI 表名**（source adapter 模式，R3 反共识 1/风险 R3）。

### 4.1 命令总表

| 命令 | 用途 | 阶段 |
|------|------|------|
| `memctl add <spec>` | 新增节点（任务骨架/raw 材料/手写页入口） | MVP |
| `memctl done <ID> [--result "…"]` | 标记完成：补结果节 + status=done + bump updated + 机械维护 + git 提交 | MVP |
| `memctl query <terms…>` | 本地检索（FTS5 trigram → bigram 回退 → LIKE） | MVP |
| `memctl lint` | 四不变式校验；零问题退出码 0 | MVP |
| `memctl index [--rebuild]` | 构建/幂等重建 mem_meta.db | MVP |
| `memctl status` | 仓库状态（页数/断链/最近事件/db 一致） | MVP |
| `memctl context --scope project\|task [--id t_x]` | boot_context v2 第五源摘要输出 | MVP |
| `memctl update <source> --plan` / `--apply <pages…>` | 增量更新：候选集（零 LLM）→ LLM 只在候选集内改写 | V2 |
| `memctl drift` | 三方对账（kanban vs wiki vs GAI），只读 | V2 |
| `memctl gai-links` | GAI 待办行 [[ID]] 双链补/校验 | V2 |
| `memctl demote <ID> --reason "…"` | 状态变更（阻塞/降级），写 wiki + 镜像 L0 状态列 | V2 |
| `memctl mcp-serve` | MCP adapter 占位（V3） | V3 占位 |

### 4.2 退出码约定

| 码 | 含义 |
|----|------|
| 0 | 成功 / lint 零问题 / 无漂移 |
| 1 | 一般错误（参数校验失败、写入失败） |
| 2 | 用法错误（未知命令/缺参，argparse 默认） |
| 3 | 校验失败（lint 有问题 / drift 发现差异 / query 语法错误） |

### 4.3 命令详细契约（MVP 六条 + done 特殊）

```
memctl add task <task_id> [--title "…"] [--priority P0]
    建 actions/ 骨架页（frontmatter 机械预填：id/source_task/status=draft/mechanism=memctl add/created）
    从 kanban.db 只读 title 若未提供；参考材料自动收集（source_task 关联页）
    不写正文四段（留待 LLM 策展或 memctl update --apply）
    骨架为机械中间态：lint 豁免 I4 est_hours 必填 + I2 出链数（OBS-01，SCHEMA §5）；
    priority 必填与孤儿检查保留；active/手工页 est_hours 必填保持强制

memctl add raw <file|path> [--tag sessions|events|research]
    复制不可变源材料进 wiki/raw/<tag>/；不改内容；git 提交

memctl done <ID> [--result "…"] [--no-commit]
    ① 读 L0（kanban.db / GAI 表，只读）：任务状态、comments、result
    ② 无该页 → 先建骨架（同 add task）；有 → 定位现有页
    ③ 补/更新"结果"节（--result 优先；否则从 L0 提取；LLM 摘要可选）
    ④ 置 status=done + priority 保留 + bump updated
    ⑤ 机械维护：index.md / log.md / mem_meta.db 增量 / 双链校验（零 LLM）
    ⑥ 原子 git 提交（commit: mem(<ID>): done <title 前 60 字>）
    fail-open：L0 只读失败 → 仍完成 wiki 写（以 ID 为锚），close 不挂死；退出码记 warning

memctl query <terms…> [--limit N] [--type raw|entity|concept|decision|action] [--json]
    检索顺序：FTS5 trigram（≥3 字 term）→ bigram 回退表（2 字 term）→ LIKE 前缀
    输出：命中页列表（id / title / type / location / updated / 命中 snippet）
    --json 供脚本消费

memctl lint [--strict] [--json]
    四不变式（§3.7）全过 → 退出码 0；有断链/孤儿/镜像不一致/index 不一致 → 退出码 3
    输出：逐条问题清单（不变式编号 + 文件 + 详情）

memctl index [--rebuild]
    构建 mem_meta.db（幂等）：pages/links/events + FTS5 trigram + bigram + term_pages
    --rebuild：删库重建（用于校验 db 与文件一致）
    默认：增量更新（按 mtime/checksum 只处理变化文件）

memctl status
    输出：页数（按 type 分）、断链数、孤儿数、最近 5 条事件、db 一致标志、git 状态
```

### 4.4 V2 命令详细契约

```
memctl update <source> --plan
    读 source（md/文本）→ 提取 term（标题词、实体名、概念名、ID 模式）
    → 查 term_pages 反向索引 → 候选页集合（union）→ 按命中 term 数排序
    输出：候选页清单 + 命中理由（term → pages）+ 新增页建议；不读全 wiki（读取文件数 < 20，B1）
    --json 供 OC 裁定 blast radius

memctl update <source> --apply <pages…> [--reason "…"]
    LLM 只在候选集内读页、改写、bump updated；幂等：同一事件重复触发同一结果
    新信息 → 矛盾检测 → 打 contradictions: 标记 / 双版本并存 → log
    机械维护 + 原子 git 提交（同 done ⑤⑥）

memctl drift [--json]
    只读三方对账：
      kanban 活跃任务 vs wiki actions/ 页（缺页/status 不一致）
      GAI 待办行 vs wiki actions/ 页（缺页/断链）
      wiki index.md vs 文件清单
    输出为空 = 无漂移（B5）；有差异退出码 3

memctl gai-links
    对 GAI 待办行补/校验 [[ID]] 命名双链；缺页 → 报告（不自动建页，交 update --plan 流程）
    B2：5 项已回填待办零断链

memctl demote <ID> --reason "…"
    写 wiki：status 变更 + 变更说明节 + bump updated + log
    镜像 L0 状态列（sed 级展示更新，非语义写入）
```

### 4.5 source adapter 模式（防 R3 风险 R3：memctl 写死成 gai.py）

```
memcore/sources/base.py:
  class SourceAdapter:
      name: str
      def fetch_events(since) -> list[Event]      # 事件源枚举
      def map_id(external_id) -> wiki_id | None   # 外部 ID → wiki 页 ID
      def mirror_status(wiki_id, external_id)     # 状态镜像（单向，L0 → wiki）

memcore/sources/gai.py: SourceAdapter            # GAI 是第一个 source（V2）
# 后续：kanban_source / session_source / correction_source —— 接口不变，注册进 cli.py 的 SOURCES 表
# CLI 层严禁出现 "GLOBAL_ACTION_ITEMS.md" 或表名硬编码；一切外部系统读写走 adapter
```

---

## 5. mem_meta.db schema（派生数据，非第二真源）

> 存储位置：`/workspace/mem-core/mem_meta.db`（gitignore，可幂等重建）。
> 唯一真源 = wiki 文件；`memctl index --rebuild` 幂等；`memctl lint` I4 校验 db 与文件一致（C7）。

```sql
-- pages 表：页面元数据（由 indexer 从 frontmatter + 文件名确定性生成）
CREATE TABLE IF NOT EXISTS pages (
    id            TEXT PRIMARY KEY,          -- 节点 ID（frontmatter id，缺省 = 文件相对路径去 .md）
    file_path     TEXT NOT NULL UNIQUE,      -- wiki/ 相对路径（如 actions/P0-19.md）
    type          TEXT NOT NULL,             -- raw|entity|concept|decision|action
    status        TEXT NOT NULL DEFAULT 'draft',
    priority      TEXT,                      -- P0..P5 / NULL
    location      TEXT,                      -- wing/room/shelf / NULL
    profile       TEXT,
    domain        TEXT,
    title         TEXT,                      -- frontmatter title 或 H1 首行
    created       TEXT,                      -- ISO
    updated       TEXT,                      -- ISO
    source_task   TEXT,
    external_id   TEXT,
    checksum      TEXT NOT NULL,             -- 内容 SHA-256（drift/一致性校验用）
    line_count    INTEGER NOT NULL,
    word_count    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pages_type     ON pages(type);
CREATE INDEX IF NOT EXISTS idx_pages_location ON pages(location);
CREATE INDEX IF NOT EXISTS idx_pages_updated  ON pages(updated);

-- links 表：wikilink 图（出链/入链反查、孤儿检测、blast radius）
CREATE TABLE IF NOT EXISTS links (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    src_id  TEXT NOT NULL REFERENCES pages(id),   -- 出链页
    dst_id  TEXT NOT NULL REFERENCES pages(id),   -- 目标页
    kind    TEXT NOT NULL DEFAULT 'wikilink',     -- wikilink | external
    UNIQUE(src_id, dst_id)
);
CREATE INDEX IF NOT EXISTS idx_links_dst ON links(dst_id);   -- 入链反查

-- events 表：操作日志（mem_meta.db 内事件流，与 wiki/log.md 对应）
CREATE TABLE IF NOT EXISTS events (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT NOT NULL,                   -- ISO
    kind    TEXT NOT NULL,                   -- create|update|done|demote|archive|index_rebuild|link_added|link_removed
    page_id TEXT,                            -- 涉及页 / NULL
    actor   TEXT NOT NULL,                   -- memctl|close.sh|boot_context|cron
    detail  TEXT                             -- JSON 细节（--result 摘要等）
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);

-- term_pages 表：反向索引（term → pages，blast radius 候选集计算，零 LLM）
CREATE TABLE IF NOT EXISTS term_pages (
    term    TEXT NOT NULL,
    page_id TEXT NOT NULL REFERENCES pages(id),
    freq    INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY(term, page_id)
);
CREATE INDEX IF NOT EXISTS idx_term ON term_pages(term);

-- FTS5 trigram（CJK 原生，SQLite ≥ 3.34；本机 3.53.1 已实测）
-- 注意：SQLite 不支持 "CREATE VIRTUAL TABLE IF NOT EXISTS"。
-- indexer 实现：CREATE VIRTUAL TABLE pages_fts USING fts5(...) 包 try/except，
--   已存在则捕获 "already exists" 异常后跳过（与 rebuild 时先 DROP 再建配合）。
CREATE VIRTUAL TABLE pages_fts USING fts5(
    title, content,
    tokenize='trigram'
);

-- bigram 回退表（2 字 CJK 检索，trigram 对 2 字 MATCH 返回 0 的补）
CREATE TABLE IF NOT EXISTS bigram_index (
    bigram  TEXT NOT NULL,                   -- 2 字 term（如 中间）
    page_id TEXT NOT NULL REFERENCES pages(id),
    PRIMARY KEY(bigram, page_id)
);
CREATE INDEX IF NOT EXISTS idx_bigram ON bigram_index(bigram);
```

**构建流程（indexer.py）**：
1. 扫描 wiki/**/*.md → 逐页 parse（frontmatter + wikilink + 表格容错）
2. 写 pages（含 checksum/line_count/word_count）
3. 写 links（wikilink 解析结果，跳解析失败 = 断链记录，lint I1 用）
4. 写 term_pages：term 提取 = 标题词 + 实体名 + 概念名 + ID 模式 + 正文 2-gram/3-gram 切分（确定性，零 LLM）
5. 写 FTS5（title+content 全文）+ bigram 表
6. 写 events（index_rebuild）
7. `--rebuild` = DROP 后重建；幂等断言：重建前后 lint I4 均零问题（A4）

---

## 6. 增量更新引擎 blast radius

### 6.1 设计原则

- **候选集计算零 LLM**：term_pages 反向索引查表（O(term 数)），不读全 wiki（B1：读取文件数 < 20）
- **LLM 只在候选集内策展**：context 成本从"全 wiki"降到"候选页 ≤10 个"（R7 缓解）
- **先列不动手**：`--plan` 输出可人工/OC 裁定（Karpathy 原版的人工确认环节保留）
- **幂等**：同一事件重复触发同一结果；骨架页已存在则更新不重建，杜绝重复页

### 6.2 数据流

```
memctl update <source> --plan
  source（md/文本）→ extract_terms()（确定性：标题/实体/概念/ID/2-3gram）
    → SELECT page_id, COUNT(*) FROM term_pages WHERE term IN (...) GROUP BY page_id ORDER BY count DESC
    → 输出候选清单（term → pages 命中理由）+ 新增页建议（source 中未命中任何现有页的主题）
  → OC/人工裁定 blast radius（可改候选集）
memctl update <source> --apply <pages…>
  LLM 读候选页（≤10）→ 改写受影响页（四段结构保持）→ 矛盾检测（打 contradictions:）→ bump updated
  → ③ 机械维护 + ④ 原子 git 提交（同 §4.3 done ⑤⑥）
```

### 6.3 矛盾检测（P1-4，V2）

- 同 topic 页冲突识别：`memctl update --apply` 时，LLM 在候选集内发现与现有页冲突的新信息 → 打 `contradictions: [<页>]` 标记 + 双版本并存（不覆盖）
- review 队列：`memctl drift` 输出带 contradictions 的页清单（只读），交 OC/人工裁决
- B4 验证：注入两条冲突源 → 检查标记

---

## 7. 跨会话恢复协议 + boot_context v2 集成契约

### 7.1 会话启动协议（L4 读路径深读）

```
新会话前 3 轮内（agent 主动，确定性，零 LLM 检索）：
1. 读 SCHEMA.md（域规则，一次）
2. 读 index.md（目录，一次）
3. 读 log.md 最近 20-30 条（最近活动）
4. 若当前有活跃 kanban task → 定向读相关 entities/concepts/decisions/actions 页
   （source_task 匹配 + location 匹配）
5. 注入上下文摘要："上次做到 X，决策 Y 已定，当前任务 Z 进行中"
成本：约 10-20 个文件读取，全确定性路径
```

### 7.2 boot_context v2：第五源 memctl context（MVP P0-6）

**集成点**：`/workspace/devPPL/pipeline/boot_context.py` 增加数据源 5（现读四源：pipeline_state/kanban/sessions/memory，BOOT_CONTEXT_MAX_CHARS=2000）。

```
memctl context --scope project [--max-chars 800]
  输出固定 markdown 段（≤800 字，三子段）：
  ### wiki 段（第五源）
  - 最近更新页（24h 内，≤5 条：title / type / updated）
  - 活跃任务关联页（当前 kanban 活跃任务 source_task 匹配，≤3 条）
  - 未决决策/待办（status ∈ (active, draft) 的 decision/action；draft=待策展骨架，≤3 条）

memctl context --scope task --id t_x [--max-chars 400]
  输出该任务关联决策页 + 实体页摘要（worker 会话用，V2 P3-5 推广）
```

**boot_context.py 接线（硬约束）**：

| 约束 | 实现 |
|------|------|
| try-except 静默降级（C9） | `_wiki_digest()` 内 subprocess 调 memctl，异常/非零退出 → 返回空段，绝不阻塞 5min 注入 |
| 字符预算 | memctl context 自带 --max-chars 800；boot_context 层再防御性截断；总预算 2000 不变 |
| 优先级 | wiki 段插在 pipeline 活跃任务段**之后**（活跃任务段最高优先级保持第一），在 session/memory 段之前 |
| 不替代 session_search | wiki 段给"现在该知道什么"；session_search 给"过去发生过什么"，两个检索面不合并 |
| 配置 | boot_context 读取 mem-core 路径：环境变量 `MEM_WIKI_PATH`（默认 /workspace/mem-core），缺失则跳过第五源（与 try-except 同一降级路径） |

**A6 验证**：boot_context 输出含 wiki 段；移除 mem-core 路径跑一次 cron → 注入照常（无 wiki 段但无阻塞）。

---

## 8. close.sh S3 替换方案（MVP P0-7）

### 8.1 现状（实测核对）

close.sh 实际位置：`/root/.hermes/profiles/orchestrator/scripts/close.sh`（104 行）。
S3 当前逻辑（close.sh:70-73）：
```bash
check 3 "GLOBAL_ACTION_ITEMS.md 已标记完成" \
    "grep -q '$TASK_ID.*✅.*done\|$TASK_ID.*done' '$GAI_FILE' 2>/dev/null" \
    "sed -i 's/\($TASK_ID.*\)待办/\1✅ done/' '$GAI_FILE' 2>/dev/null"
```
- 对 2026-08-10 新格式 GAI（无"待办"字样）已 no-op；S3 是失效强制步骤
- 替换不是新增约定，是修复失效强制步骤（R2 分步 1 已定案：close.sh S3 主路径）

### 8.2 替换设计：S3 → S3a（wiki 编译）+ S3b（GAI 展示镜像）

```bash
# S3a: wiki 页编译完成（主路径，强制）
check 3a "wiki 页已编译完成（memctl done）" \
    "memctl done '$TASK_ID' --check 2>/dev/null || memctl lint 2>/dev/null | grep -q '零问题'" \
    "memctl done '$TASK_ID' 2>/dev/null"

# S3b: GAI 状态镜像（展示层，非语义写入）
check 3b "GLOBAL_ACTION_ITEMS.md 状态镜像已更新" \
    "grep -q '$TASK_ID.*✅.*done\|$TASK_ID.*done' '$GAI_FILE' 2>/dev/null" \
    "sed -i 's/\($TASK_ID.*\)待办/\1✅ done/' '$GAI_FILE' 2>/dev/null"
```

**关键裁决**：
- `memctl done` 是**语义写入主路径**（写 wiki 详情页 + 状态镜像）；GAI 的 sed 降级为**展示层镜像**（只是把 wiki 状态展示到 GAI 表，不做语义解析）
- fail-open（R2 分步 1 已承诺的工程约束）：memctl 异常时 close.sh **不得挂死**——S3a 失败仅记 FAIL 并提示手动补，close 流程继续；S3b 保持原 sed 兜底
- TASK_ID 兼容：close.sh 传 kanban ID（t_x）或 GAI ID（P0-19）都接受；memctl done 通过 source adapter 映射（§4.5）

### 8.3 memctl done 状态镜像格式（写进 wiki 页）

```markdown
---
id: P0-19
type: action
status: done
priority: P0
source_task: t_2345b07e
created: 2026-08-10T08:00:00Z
updated: 2026-08-10T09:30:00Z
location: devppl/memory/architecture
---

## 背景
（四段式第一段，LLM 策展）

## 要解决的问题
…

## 验收标准
…

## 参考
- [[concepts/single-writer.md]]
- [PRD §8](docs/prd/memory-middleware-prd.md)

## 结果（memctl done 追加）
- 状态: done
- 完成时间: 2026-08-10T09:30:00Z
- 结果摘要: …
```

**A5 验证**：关闭一个测试任务 → 检查 wiki 页含"结果"节 + status=done + updated 时间戳。

---

## 9. golden file 测试体系设计（吸收 MEM-003）

> MEM-003 裁决：中间层**新的**测试义务 = golden file 测试（吸收），mem0 平台侧债独立不掩盖。pytest 套件 ≥15 用例（A9），MVP 全绿。

### 9.1 测试夹具（tests/golden/）

| 夹具 | 内容 | 用途 |
|------|------|------|
| `golden/r3-architect.md` | R3 三卷之 Architect 卷编译产物（真实正文样本） | 解析/索引/检索端到端 |
| `golden/r3-engineer.md` | R3 三卷之 Engineer 卷编译产物 | 同上 |
| `golden/r3-product.md` | R3 三卷之 Product 卷编译产物 | 同上 |
| `golden/bad-frontmatter.md` | 缺必填字段/非法枚举/表格脏单元格 | 解析容错 |
| `golden/broken-links.md` | 断链/孤儿页样本 | lint 触发 |
| `golden/conflict-pair.md` | 同 topic 冲突双页 | 矛盾检测 |

### 9.2 测试用例清单（≥15）

| # | 测试 | 断言 |
|---|------|------|
| 1 | parse frontmatter 完整 | 字段正确解析 |
| 2 | parse frontmatter 容错（缺字段/脏表格） | 不抛异常，字段缺失有默认 |
| 3 | parse wikilink ID 模式 | `[[P0-19]]` → actions/P0-19.md |
| 4 | parse wikilink 名称映射 + 别名 | `[[单一写者|机制]]` 解析正确 |
| 5 | parse 断链判定 | 未命中目标 → 记录断链 |
| 6 | indexer 构建 | pages/links/events/term_pages 行数正确 |
| 7 | indexer 幂等重建 | `--rebuild` 两次 → 相同 db（lint I4 前后均零问题） |
| 8 | indexer checksum | 文件改动 → checksum 变化检测 |
| 9 | lint I1 断链 | 断链样本 → 报告 |
| 10 | lint I2 孤儿 | 孤儿样本 → 报告 |
| 11 | lint I3 status 镜像 | 模拟 L0 状态与 wiki 不一致 → 报告 |
| 12 | lint I4 index 一致 | index 缺页 → 报告 |
| 13 | query trigram CJK | `中间层`（≥3 字）命中对应页 |
| 14 | query bigram 回退 | `中间`（2 字）走 bigram/LIKE 命中 |
| 15 | context 输出 | ≤800 字、三子段格式固定 |
| 16 | done 集成（mock L0） | memctl done → 页含结果节 + status=done + updated bump |
| 17 | blast --plan | 候选集计算正确（term→pages），不读全 wiki |
| 18 | 矛盾检测 | 冲突源 → contradictions: 标记 |
| 19 | source adapter | GAI adapter 接口形状测试 |

### 9.3 测试义务边界

- 确定性引擎：pytest 全绿 = 引擎正确（机械层）
- LLM 策展：golden 正文样本人工抽查（四段非空 + ≥1 参考 + ≥2 出链，R6 措辞靠 lint 迭代）
- 不测 mem0 平台侧（MEM-003 原卡独立，不进本套件）

---

## 10. 200 文件墙四层对策（P3-1，wiki >50 页触发）

> 关键认识：**墙是编译期问题**（更新时要全局去重），不是检索期问题——检索期 agent 只读少量页面。解药集中在编译流程：blast radius + 目录级索引 + 归档。

| 层 | 机制 | 触发条件 | 实现 |
|----|------|---------|------|
| 1 | **目录级索引** | 每目录 >50 页拆子索引 | index.md + 每子目录独立索引（entities/、concepts/、concepts/decisions/、actions/）；agent 编译时只读 SCHEMA + index + 受影响页，**永不加载全 wiki** |
| 2 | **分区** | 多项目/多 Wing | 按 Wing 分目录边界（devppl/ vs infomanager/）；多项目 = 多 WIKI_PATH（项目级 wiki，非一张大 wiki） |
| 3 | **页面瘦身** | 每页 >200 行 | 拆子页 + 交叉链（llm-wiki 规则继承）；lint 校验 line_count |
| 4 | **归档** | status=done/superseded 稳定后 | `memctl archive <ID>` → 移入 `_archive/`，移出活跃索引（index.md 不再列出；FTS5 保留可检索或排除——默认排除，`--include-archive` 查询） |

**编译期保障**：blast radius（§6）保证增量更新永远只碰候选集；目录级索引保证编译上下文稳定；归档保证活跃索引大小受控。

---

## 11. 替代本体文件迁移机制（红线流程落地）

> 🔴 PRD §7.2 硬约束：替代 soul.md、memory.md、hermes.md（.hermes.md）、SKILL.md 必须逐项 Frank 确认。本设计把红线落成可执行机制——**编译产物先存在、本体保持现状、等价性证明后逐项提案**。

### 11.1 原则

1. 中间层先以编译产物存在（L3）；上述 Hermes 本体文件保持现状，**任何一项都不默认被替换**
2. 只有"注入型需求"被证明可以等价地由 wiki 读取协议（§7.1）满足时，才逐项提出替换提案
3. 每个替换提案必须包含：GAI 决策档案四段式（背景/问题/验收/参考）+ 迁移脚本 + 回退方案
4. 替换提案由 Frank 逐项签字后方可执行；未签字 = 不替换

### 11.2 提案生命周期状态机（wiki/concepts/decisions/ 页承载）

```
draft（决策页四段非空，出链到待替换本体文件的等价物）
  → proposed（含迁移脚本 + 回退方案，提交 Frank）
  → approved（Frank 签字：decision 页 status=approved + 签字记录）──┐
  → migrated（迁移脚本执行，本体文件替换为 wiki 读取协议引用）       │ 任何一步失败/被否
  → rolled_back（回退方案执行，本体恢复原状）◄──────────────────────┘
  → rejected（Frank 驳回，决策页记录驳回理由，关闭）
```

### 11.3 等价性证明模板（每个提案必填）

| 注入型需求 | wiki 读取协议等价满足方式 | 缺口 |
|-----------|--------------------------|------|
| 每轮注入的原子事实/偏好（现 memory 工具） | §7.1 启动协议定向读页 + boot_context 摘要 | 若存在"必须每轮注入且 ≤2200 字"的需求，wiki 摘要在字符预算内可覆盖 |
| 角色/人格定义（soul.md） | entities/ 角色页 + SCHEMA 域规则 | 人格声明的注入时点/优先级需 Frank 确认 |
| 项目规范（.hermes.md） | wiki/ 项目域页 + boot_context 第五源 | boot_context 动态段与静态规范段的分工需确认 |
| skill 操作手册（SKILL.md） | mem-worker skill（repo 内单副本）已示范；其余 skill 逐项评估 | 每 skill 独立提案 |

### 11.4 架构保障

- mem-core 作为**唯一同步/迁移单元**（F2 同仓）：每个替换提案 = 一个 wiki 决策页 + 一个迁移脚本 + 回退方案，全部在 mem-core 内闭环
- 迁移脚本落 mem-core/scripts/migrations/<提案ID>.py，回退脚本同目录 <提案ID>_rollback.py
- 未签字的提案不得触碰本体文件（lint 不涉及本体，靠流程纪律 + Frank 只读）

---

## 12. 部署与备份方案

### 12.1 部署（MVP P0-1/P0-9）

```
1. mkdir /workspace/mem-core && cd /workspace/mem-core && git init
2. 写入 SCHEMA.md（§3 全文）+ index.md/log.md 骨架 + memcore/ 库 + bin/memctl + bin/mem(symlink)
3. pip install -e .（pyproject.toml；依赖：Python ≥3.10，sqlite3 内置，无第三方运行时依赖）
4. ln -s /workspace/mem-core/bin/memctl /usr/local/bin/memctl
5. mem-worker skill：/workspace/mem-core/SKILL.md 单副本随 repo 走；
   各 profile 通过 Hermes skills 配置指向 repo 路径（零拷贝，C1 不复制 12 份）
6. 验证：memctl status / memctl lint / memctl query 中文词
```

### 12.2 备份（MVP P0-8，BKP-003 模式）

- 接入 `/workspace/manifest.yaml`（备份 manifest，backup_roots 模式）：
```yaml
backup_roots:
  - path: ~/.hermes/
    description: "Hermes config, memories, skills, sessions, env"
    recursive: true
  - path: /workspace/mem-core/
    description: "Memory middleware repo (engine + wiki + skill) — single backup unit"
    recursive: true
```
- mem_meta.db 不备份（派生数据，可从 wiki 幂等重建）；备份单元 = wiki 文件 + 引擎代码（git 历史天然含全部版本）
- 备份脚本沿用 `/workspace/hermes_backup_push.sh`（BKP-003 LFS 模式对超大附件按需启用）
- A7 验证：执行备份，检查 manifest.yaml 含 mem-core

### 12.3 环境变量与配置

| 变量 | 默认 | 用途 |
|------|------|------|
| `MEM_WIKI_PATH` | /workspace/mem-core | memctl 工作根（wiki/ 目录所在） |
| `MEM_DB_PATH` | $MEM_WIKI_PATH/mem_meta.db | 索引 db 位置 |
| `MEM_GAI_FILE` | /root/.hermes/profiles/orchestrator/GLOBAL_ACTION_ITEMS.md | GAI source adapter 的文件路径（adapter 内引用，CLI 不硬编码） |
| `MEM_KANBAN_DB` | ~/.hermes/kanban.db | L0 kanban 只读源 |

---

## 13. 组件间接口契约汇总

```
事件源（L0）                      memctl（单一写者）                wiki（L3）                 读取方（L4）
───────────                      ──────────────────                ──────────                ─────────────
kanban 任务创建  ──add task──▶   actions/ 骨架页  ──────────────▶   agent 启动协议（§7.1）
kanban 任务完成  ──done──▶       actions/ 详情页 status=done ◀──   boot_context v2 第五源（§7.2）
纠正/决策事件    ──update──▶     entities/ concepts/ 页             memctl query（§4.3）
GAI 更新        ──gai-links──▶  actions/ [[ID]] 双链              memctl context（§4.3/§7.2）
周对账          ──drift──▶      （只读三方 diff，不写）            深读：SCHEMA→index→log→定向读页
                                      │
                                      ▼
                          mem_meta.db（派生数据，indexer 构建）
                          FTS5 trigram + bigram 回退 + term_pages 反向索引
```

**反向不成立（硬边界）**：wiki 不产生状态、不回写 kanban/pipeline_state/GAI、不替代 session_search、不替代注入型 memory。

---

## 14. 工作量估算与里程碑映射（对齐 PRD §4）

| 里程碑 | PRD 需求 | 本设计章节 | 工时 |
|--------|---------|-----------|:---:|
| MVP | P0-0 消灭双份拷贝 | §0.3（git rm /workspace/devPPL/GLOBAL_ACTION_ITEMS.md） | 0.2h |
| MVP | P0-1 repo+SCHEMA | §2.1 + §3 | 1.5h |
| MVP | P0-2 index/log 骨架 | §2.1（折叠 P0-1） | 0 |
| MVP | P0-3 memcore 库 | §3.3/§5/§6 | 3h |
| MVP | P0-4 mem CLI 骨架 | §4.1-4.3 | 1h |
| MVP | P0-5 pytest | §9 | 折叠 |
| MVP | P0-6 boot_context v2 | §7.2 | 1h |
| MVP | P0-7 close.sh S3 替换 | §8 | 0.5h |
| MVP | P0-8 备份接入 | §12.2 | 0.3h |
| MVP | P0-9 mem-worker skill | §2.1 + §12.1 | 0.2h |
| MVP | P0-10 首批 3 页回填 | §9.1 golden 夹具 | 1.5h |
| **MVP 小计** | | | **9.5h** |
| V2 | P1-1 增量更新 | §6 | 3h |
| V2 | P1-2 GAI 适配器 | §4.4/§4.5 | 1.5h |
| V2 | P1-3 5 项待办回填 | §11.2 决策页形态 | 3.5h（并行） |
| V2 | P1-4 矛盾检测 | §6.3 | 2h（并行） |
| **V2 小计** | | | **~10h** |

**MVP 交付门禁** = PRD §5.1 A1-A9 全绿；V2 门禁 = B1-B5 全绿；北极星 C1-C4 长期观测（§0.2 北极星）。

---

## 15. 技术风险点

| # | 风险 | 缓解 | 验证点 |
|---|------|------|--------|
| R1 | 编译管线 LLM 质量参差 | 机械层全脚本化（index/校验/提交），LLM 只做 blast radius + 页面语义；lint 四不变式 + 周 drift 兜底 | A2/A4 |
| R2 | worker 忘触发编译 | close.sh S3 接线（强制）+ boot_context digest（被动可见）+ 周 cron 对账，三层保险不靠约定 | A5/A6 |
| R3 | memctl 写死成 gai.py | source adapter 模式（§4.5），GAI 只是第一个 source，严禁 CLI 硬编码表名 | B2 |
| R4 | sqlite < 3.34 无 trigram | M1 第一步验证 sqlite 版本（本机 3.53.1 已实测）；退路 = 关键词评分 + LIKE 前缀，不阻塞整体 | A3 |
| R5 | mem_meta.db 双写漂移 | 唯一真源是 wiki 文件；db 幂等重建 + lint I4 校验 db/文件一致 | A4 |
| R6 | 回填质量参差 | 只求四段非空 + ≥1 参考 + ≥2 出链；措辞靠 lint 迭代 | A8 |
| R7 | 200 文件墙 | 四层对策（§10）+ blast radius 控制更新集 | P3-1 触发后 |
| R8 | 替代本体文件引发回归 | 红线流程（§11）：逐项提案 + 回退方案 + Frank 签字 | §11.2 状态机 |
| R9 | boot_context 集成破坏 5min 注入 | try-except 静默降级 + MEM_WIKI_PATH 缺失跳过 + 防御性截断 | A6 |
| R10 | close.sh fail-open 破坏闭环验证 | S3a 失败仅记 FAIL 提示手动补，close 流程继续；S3b 保留原 sed 兜底 | A5 |

---

## 16. 一句话总结

记忆中间层 = **一个 repo**（/workspace/mem-core：引擎 + wiki 正文 + skill 单副本，F2 同仓）+ **一条命令**（memctl，`mem` 为软链别名）+ **两个挂点**（boot_context v2 第五源读、close.sh S3 替换写）——SCHEMA 定稿含三条铁律/三边界/四不变式与 Wing/Room/Shelf 空间标签，mem_meta.db 三表 + FTS5 trigram + bigram 回退 + 反向索引全部派生可重建，blast radius 先列不动手、LLM 只在候选集内策展，golden file 测试 ≥15 用例吸收 MEM-003，200 文件墙四层对策、替代本体文件走 Frank 逐项签字状态机——**MVP 9.5h 立起来，V2 10h 变厚，北极星是 Frank 重复教的次数归零**。
