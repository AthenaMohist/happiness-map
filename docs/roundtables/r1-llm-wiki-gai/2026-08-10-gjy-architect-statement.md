# Roundtable R1: LLM-Wiki 记忆系统 + GAI 自动更新 — 架构师发言

> 发言人: 高见远（架构师） | 日期: 2026-08-10 | 版本: v1.0
> 关联: Product 发言 (t_5d04e206, comment #378) | Engineer 发言 (t_a961dacc, todo)

---

## 0. 现状核查（发言前实测）

三个本机验证过的事实，直接决定方案走向：

1. **GAI 漂移已经是现实，不是预测**。`/workspace/devPPL/GLOBAL_ACTION_ITEMS.md`（197 行，2026-07-08 旧 P0 格式，仍在 devPPL git 里，最后一次提交 0da3e39）与 `/root/.hermes/profiles/orchestrator/GLOBAL_ACTION_ITEMS.md`（144 行，2026-08-10 新格式，含 DPL-009/MEM-004）已经分叉 33 天。方案若不先消灭"同一文件两份拷贝"这个根因，wiki 建好也只是第三个漂移面。
2. **llm-wiki skill 是通用 Karpathy 模式**（SCHEMA + index + log + raw/ + entities/ + concepts/ + comparisons/ + queries/），10 个 profile 各有一份，WIKI_PATH 未配置。适合研究型 wiki；决策档案只需要骨架，必须定制 SCHEMA，不能原样套用。
3. **kanban.db 是完整事件源**（tasks + task_runs summary/metadata + task_comments + task_events），且 `pipeline/boot_context.py` 已有安全的 sqlite 只读封装可复用。详情页"参考材料"不缺数据源，不需要额外采集。

---

## 1. 定位：第四层「决策档案」，不是另一个记忆库

现有记忆体系四层补齐（新增 L3，与既有三层零重叠）：

| 层 | 载体 | 写者 | 读时 | 本质 |
|----|------|------|------|------|
| L0 确定性状态 | kanban.db / pipeline_state.db / GAI 表 | 机器脚本 | 每轮注入（boot_context） | 事实真源，零 LLM |
| L1 情节检索 | session_search / state.db 转录 | 会话自动 | 按需 LLM 调用 | 原始历史，FTS5 |
| L2 语义记忆 | memory 工具 / mem0 / /learn /journey | agent 策展 | 每轮注入 / 按需 | 蒸馏事实与偏好 |
| **L3 决策档案（新增）** | **LLM-Wiki 详情页** | **agent 策展（单一写入者）** | **从 GAI 点进去** | **为什么/怎么算完，跨会话可追溯** |

边界规则（写进 SCHEMA.md，违反即 lint 失败）：
- **wiki 不存状态**：状态唯一真源是 kanban.db / GAI 表。详情页 status 仅作展示，校验时回读 GAI。
- **wiki 不替代检索**：全文搜索留在 session_search；FTS5 无 CJK 分词是已知边界，SCHEMA 里标注，别让后人误以为 wiki 有全文搜索。
- **wiki 不存事实偏好**：那是 L2 的活。详情页只回答"这个待办为什么存在、解决什么、怎么算完"。
- **写入者约束**：wiki 只允许 gai-writer skill / gai.py 机制写，Frank 只读；与 InfoManager vault 零交叉。

数据流单向：kanban 事件 → gai_index.py 重排 GAI 表 → gai-writer 更新详情页。反向不成立——详情页不产生状态，杜绝状态回写环。

---

## 2. 双链结构：命名双链 + 脚本校验

节点类型只建三种（砍掉 comparisons/queries/raw 与决策档案无关的层）：

```
devPPL-wiki/
├── SCHEMA.md          # 定制 schema（本域规则 + 双链解析约定）
├── index.md           # 内容目录（由 gai_index.py 维护，不是手写）
├── log.md             # 变更日志（append-only）
├── actions/           # ★ 决策档案页：每个 GAI ID 一页，如 DPL-009.md
└── entities/          # 机制/项目实体页：devPPL, InfoManager, cron, watchdog, mem0…
```

**Action 页 frontmatter**（正文四段由 Product 定；这里定义机器可校验字段，保证 lint 可自动化）：

```yaml
---
id: DPL-009
title: Webhook 替代 cron 轮询
status: todo            # todo | done | p5 | obs — 镜像 GAI 表，校验时回读
priority: P1
mechanism: devPPL
est_hours: 1
created: 2026-08-10
updated: 2026-08-10     # 每次语义层写入必 bump，漂移判定的时间戳
source_task: t_xxx      # 若来自 kanban 任务，留 task id 供脚本回读
links: [cron, webhook, devPPL-pipeline]   # 出链实体页
---
```

**链接拓扑**：
- GAI 表每行「行动」列追加 `[[DPL-009]]` → 解析到 `wiki/actions/DPL-009.md`。解析规则写进 SCHEMA：`[[ID]]` 且 ID 匹配 `[A-Z]+-\d{3}` → actions/；其它 wikilink → entities/ 或 index。
- Action 页 → entities/ 机制页（[[devPPL]], [[cron]], [[webhook]]）。
- entities/ 之间互链（[[cron]] ↔ [[devPPL-pipeline]]）。
- 每页至少 2 出链（llm-wiki 规则保留）。

**取舍：命名双链 + 脚本校验，而非 Obsidian 原生链接。** GAI 在 orchestrator profile（`/root/.hermes/...`），wiki 在 `/workspace`，跨 vault 无法用 Obsidian 原生 [[path]] 跳转；脚本校验（gai_index.py --check）保证每个 [[ID]] 有对应文件，断链即 lint 失败。代价是牺牲 Obsidian 点击跳转，换来跨目录一致性和零引擎依赖——对"从 GAI 已知 ID 点进去"的用法，足够。

---

## 3. 自动更新：双层架构，事件驱动，不轮询

Product 已定"机械层=脚本、语义层=skill"，这里给落地架构。

### 3.1 模块划分

```
devPPL/scripts/gai/            # 与 pipeline 同仓库、同备份、同 CI
├── gai.py            # CLI 入口：add / update / done / demote / list
│                     # 唯一允许改 GAI 表文件的入口（对账不变式）
├── gai_index.py      # 机械层：重排 GAI 表格、维护 index.md、--check 一致性
├── gai_drift.py      # 周漂移报告：GAI vs kanban vs wiki 三方 diff（cron 每周，只读）
└── gai-writer.skill.md  # 语义层 skill：详情页四段撰写/更新模板 + 触发协议
```

**架构不变式（最重要一条）**：GAI 文件任何增删改必须走 gai.py，禁止手工编辑。今天 GAI 是手工编辑 + git commit（最后一次 0da3e39），这既是漂移根源也是滞后根源。CLI 化之后：
- 机械动作（表格重排、Archived 移动、wikilink 追加）由 gai_index.py 确定性完成；
- 语义动作（详情页四段撰写/更新）由 gai.py 在需要时调用 gai-writer skill 完成。

### 3.2 触发架构：事件钩子 vs cron

四个触发场景（按 Product 的用户可见事件排序），各自的实现：

| 场景 | 触发机制 | 谁执行 | 延迟 |
|------|---------|--------|------|
| 新指令 → 新行 + 上下文 | kanban_create 之后 / OC 会话内 | gai.py add → gai-writer 建详情页 | 会话内（最新鲜） |
| 完成/归档 | kanban_complete / 管线 close 时 | gai.py done → gai-writer 补结果节 | 事件时 |
| 状态变更（阻塞/降级/P5）记理由 | kanban_block / comment 时 | gai.py demote 附理由 | 事件时 |
| 周漂移对账 | cron 每周（**唯一**的 cron 场景） | gai_drift.py（只读） | 每周 |

**关键设计决策——事件怎么到达脚本**：Hermes 引擎目前没有 post-kanban hook（DPL-013 是未来改造方向，不能等）。主路径采用 **worker 行为约定**：task-handoff skill 里约定「kanban 生命周期动作必须同步调用 gai.py」——完成/阻塞/创建后一行命令，同步、零轮询、天然带 task_id 上下文。这与 DPL-013「发起时才启动」方向一致，零引擎改动。

三个备选方案取舍：
- **A. 引擎层 post-event hook**：最干净，但引擎没这能力，工期不可控 → 列为 DPL-013 的后续吸收项，不阻塞本轮。
- **B. 事件表轮询 cron**：回到轮询，滞后必然复发 → 否。
- **C. worker 约定 + 同步调用**：可用、零依赖 → **选这个**。DPL-013 落地后整体迁移到 A。

### 3.3 与 kanban 状态的关系

- 状态流单向：kanban.db（task status/runs）→ GAI 表（项目级视图）→ 详情页 status（展示）。
- 同步信号：详情页 `updated` 字段 = 最后一次语义层写入时间；gai_drift.py 用它与事件时间戳比对，判定"1 小时同步"是否达成。
- 一致性校验（gai_index.py --check，进 CI 或周漂移）：
  1. GAI 每个待办行都有 [[ID]] 且 actions/<ID>.md 存在（无断链）；
  2. actions/ 无孤儿页（无 GAI 引用的详情页 → 标记或归档）；
  3. 详情页 status 与 GAI 表一致；
  4. index.md 与 actions/ 文件列表一致。

### 3.4 工期影响（修正 MEM-004 原估）

MEM-004 原估 2h 只覆盖 wiki 骨架，不含自动更新。拆成两张卡：
- **MEM-004a wiki 核心**（SCHEMA 定制 + WIKI_PATH + 目录初始化 + 双链约定）：~2h
- **MEM-004b 自动更新**（gai.py + gai_index.py + gai_drift.py + worker 约定 + 周 cron）：~4h
- P1 七行回填：~1h（LLM 侧，语义层）
- 合计 ~7h。004a 可先行试点，004b 并行，互不阻塞。

---

## 4. InfoManager-vault-writer：不复用，独立 wiki

核查结论：**不复用**。三个硬理由：

1. **数据域不同**：InfoManager 是个人内容收藏（01-Items/ 按日期命名、概念/实体/评价三类型标签、≤100 字摘要、飞书采集管道）；决策档案是系统级"为什么"。schema 无一可复用。
2. **写入者冲突**：InfoManager vault 有 tag-system / gateway-eng / vault-writer / infomanager 四个写者 + 自动 git push；Product 红线要求 wiki 单一写入者。混用必然重蹈并发冲突学费（git worktree 教训已交过一次）。
3. **路径/仓库边界**：vault 是独立 git repo（AthenaMohist/InfoManager）；wiki 需要自己的 repo + 备份链路，物理隔离最干净。

可借鉴的只有三条低价值惯例：frontmatter schema 写法、git 版本管理、Obsidian 兼容（双链渲染）。不构成复用理由。若工程师提议"复用 vault-writer 省基建"——驳回。

---

## 5. WIKI_PATH 与 GAI 的关系：兄弟文件，不合并

- **WIKI_PATH = `/workspace/devPPL-wiki`**（独立 git repo，与 devPPL 仓库同级）。不放 devPPL 仓库内，理由：提交节奏不同（devPPL 按 slice 提交、wiki 按事件高频提交），混仓让 git log 无法分辨代码与记忆变更；单一写入者在独立 repo 上用 git 权限最容易强制。
- **GAI 保持 `/root/.hermes/profiles/orchestrator/GLOBAL_ACTION_ITEMS.md` 不动**，承担 index 角色。不并入 wiki：GAI 是 orchestrator 全局待办，被 boot_context / OC 直接读取；wiki 是决策档案。合并 = 让简单表格背上 wiki 复杂度。
- **连接方式**：GAI 每行 [[ID]] 命名双链，由 gai_index.py 校验解析到 wiki/actions/。SCHEMA.md 写明解析规则。
- **GAI 双份拷贝问题（实测发现，本次改造第一步）**：删除或 symlink `/workspace/devPPL/GLOBAL_ACTION_ITEMS.md`，以 orchestrator 路径为唯一真源。两版已分叉 33 天，不处理则 wiki 建好也只是第三个漂移面。
- **备份**：devPPL-wiki 加入现有备份链路（hermes_backup_push.sh 的 LFS 推送清单，BKP-003 模式）。记忆系统不可再生，备份不是可选项。

---

## 6. 验收标准 → 可验证断言

Product 五条验收，落成脚本可判定的形式（进 gai_drift.py / CI）：

| 验收 | 判定 |
|------|------|
| 30 秒追溯 | --check：每个 action 页四段非空 + ≥1 参考材料来源 + ≥2 出链 |
| 1 小时同步 | drift：事件时间戳 vs 详情页 updated，差 >1h 计入漂移 |
| 周漂移报告为空 | gai_drift.py 输出 diff 为空 |
| 自动归档带日期 | check：Archived 区每行有日期；对应详情页 status=done 且 updated 为归档当天 |
| Frank 只读 | wiki repo 写权限仅 agent（git hook/分支保护）；GAI 只经 gai.py 写入 |

---

## 7. 试点清单（本周）

1. 处理 GAI 双份拷贝：删 /workspace/devPPL 旧版或改 symlink（0.1h）
2. 初始化 /workspace/devPPL-wiki + SCHEMA.md（定制版）+ index.md + log.md（0.5h）
3. gai.py + gai_index.py 落地（2h）
4. gai-writer skill 落地（1.5h）
5. 回填 P1 七行详情页（1h）
6. worker 约定写入 task-handoff skill + 接通「新指令」「归档」两触发点（0.5h）
7. gai_drift.py 周 cron + 下周对账验证（0.5h）

---

## 8. 风险与取舍汇总

- 取舍：事件驱动 worker 约定 vs 引擎 hook —— 选约定，引擎 hook 留给 DPL-013，不为这事改 Hermes 内核。
- 取舍：命名双链 + 脚本校验 vs Obsidian 跨 vault 原生链接 —— 选前者，跨目录一致性优先。
- 风险：worker 忘调用 gai.py —— 缓解：gai_drift.py 周报告兜底（滞后 ≤1 周可探测）+ task-handoff 约定按铁律级写入。
- 风险：P1 七行回填质量 —— 缓解：回填只要求四段非空 + 参考材料可溯源，不追求完美措辞，后续 lint 迭代。

---

## 9. 一句话结论

把"记忆"从玄学变成工程：**L3 决策档案层 + 单一真源 + 命名双链 + 事件驱动双层同步**。GAI 是索引、kanban.db 是状态、wiki 详情页是为什么——三者单向流动，漂移可探测，验收可断言。
