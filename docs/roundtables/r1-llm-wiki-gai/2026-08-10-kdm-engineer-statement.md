# Roundtable R1: LLM-Wiki 记忆系统 + GAI 自动更新 — 工程师发言

> 发言人: 寇豆码（工程师） | 日期: 2026-08-10 | 版本: v1.0
> 关联: Product 发言 (t_5d04e206, comment #378) | Architect 发言 (t_9d1668cb, comment #379)

---

## 0. 实施前盘点（发言前实测）

动手算账之前，先把 GAI、close.sh、boot_context、wiki 现状全部实测了一遍：

| 组件 | 实测结论 | 对方案的影响 |
|------|---------|-------------|
| GAI 待办区 | **32 行**（P1×7 + P2×9 + P3×7 + P5×8 + OBS×1），不是 55 | 全量回填是 32 页，不是 7 页；MVP 只回填 P1 |
| GAI 表格结构 | **4 种表头、9 张表**：待办 5 列（优先级/任务ID/行动/机制/工时）、P5 4 列（…/发现/理由）、OBS 5 列（…/条件/到期）、归档 3 列（ID/行动/日期）×4 张 | gai.py 不能做行级 sed，必须表感知解析 |
| GAI 脏数据 | **L47 `P3-06 | MEM-003 | … | 记忆 | P3`** 工时列填了 "P3" | 解析器必须容错坏单元格，否则一崩全崩 |
| close.sh S3 修复 | sed `s/\($TASK_ID.*\)待办/\1✅ done/` —— 新表行里没有"待办"字样，**该修复对现行格式已是 no-op** | "手工 patch + grep 验证"连自修复都做不到了，这就是必须 CLI 化的直接证据 |
| workspace GAI 副本 | 全仓库 grep：**无任何脚本引用**，只有历史 roundtable/PRD 文档提及 | git rm 删除是零回归操作，比 symlink 干净（symlink 进 repo 在 worktree/克隆场景会断） |
| WIKI_PATH | orchestrator .env 无任何 wiki 条目 | "不设全局"的迁移成本为零，现在就是干净状态 |
| boot_context.py | 读 pipeline_state.db + kanban.db + sessions.db + memory，**不读 GAI** | 纠正架构师一处：GAI 不是 5 分钟机器注入的，是 OC/Frank 面向的文档；"1h 同步"语义 = 事件发生后 1h 内更新，不是"漂移能被机器及时发现" |
| kanban-worker skill | 各 profile 已存在（game-engine 确认） | worker 约定落点明确，不用新建 task-handoff skill，patch 现有 skill 即可 |
| 备份 | hermes_backup_push.sh 走 /workspace/manifest.yaml | wiki 加一行路径即可接入既有备份，无需新基建 |

---

## 1. LLM-Wiki 搭建工程方案（问题 1）

**目录结构**：采纳架构师的 `actions/ + entities/`（+ SCHEMA/index/log），砍 raw/comparisons/queries。但这意味着**不能原样套用 llm-wiki 通用 skill**——它的 lint 会扫 raw/ 校验 sha256、查 orphan 页、查 index 完整性，对决策档案大部分不适用。定制 SCHEMA 后，lint 范围收窄为 actions/ 子集。

**对接 llm-wiki skill 的正确姿势是"借模式，不复用"**：
- 新建 `gai-writer` skill（约 100-150 行）：借用 frontmatter/双链/索引三惯例，lint 只查 actions/；
- 通用 llm-wiki skill 留在研究型 wiki 用，不动它。

**一个架构师漏掉的坑——WIKI_PATH 不能全局设置**。llm-wiki skill 的激活条件就是"configured path 存在 wiki"。一旦在 profile .env 里设 `WIKI_PATH=/workspace/devPPL-wiki`，任何研究型会话加载 llm-wiki 都会把决策档案当通用 wiki 建 raw/ 页面，直接违反"单一写入者"不变式。方案：**WIKI_PATH 不写 .env，由 gai.py / gai-writer 在脚本内显式传参**。代价是零（当前未配置），收益是隔离性。

**初始化步骤与工时**（MEM-004a）：
1. `git init /workspace/devPPL-wiki` + SCHEMA.md 定制版（约 60-80 行：双链解析规则、frontmatter 字段、四段模板、不变量清单）— 0.5h
2. index.md / log.md 骨架 + 首批 entities 页（devPPL、cron、kanban、mem0 等 4-6 页）— 0.5h
3. 备份接入：manifest.yaml 加 `/workspace/devPPL-wiki` 路径 — 0.2h
4. gai-writer skill 骨架 — 0.5h
   小计 ≈ **1.7h，给 2h 上限**（含迭代），与架构师 004a=2h 一致。

---

## 2. GAI 作为 wiki 节点（问题 2）

三选项裁决：**原地生成 [[双链]]**，即 GAI 表「行动」列追加 `[[DPL-009]]`。理由：
- 复制到 wiki = 再造第三个漂移面，正是本议题要消灭的病；
- 详情页反向链接 GAI 解决不了"从 GAI 点进去"的入口问题；
- 表内追加 wikilink 是纯文本，不破坏任何现有消费者（close.sh grep、人工阅读都兼容）。

落地细节：
- **双份拷贝**：git rm `/workspace/devPPL/GLOBAL_ACTION_ITEMS.md` + 提交一次（0.2h）。实测零脚本引用，删除安全。
- **唯一真源不变式**：gai.py 是唯一写入口。close.sh S3 的 sed 同步换掉（见 §3/§5）。
- 双链解析规则写进 SCHEMA：`[[ID]]` 且 ID 匹配 `[A-Z]+-\d{3}` → `actions/`；其它 → `entities/`。

---

## 3. GAI 自动更新脚本（问题 3）— 反共识：4h 不够，拆账 7h

架构师估 004b = gai.py + gai_index.py + gai_drift.py + worker 约定 + 周 cron = 4h。实测拆账：

| 模块 | 内容 | 工时 |
|------|------|:---:|
| gai.py | **表感知解析器是核心难点**：4 种表头 9 张表 + 脏单元格容错（L47 实锤），不能正则行级处理；add/done/demote/list 四子命令 + 原子写（tmp+rename）+ 幂等 | **3h**（含 ~20 个 pytest，fixture 用 GAI 副本，绝不动真文件） |
| gai_index.py | index.md 机械维护 + --check 四不变式（断链/孤儿/status 镜像/索引一致） | 1.5h |
| gai_drift.py | **第一版砍掉 kanban 侧语义 diff**：32 个待办行没有 source_task 映射，语义对账等详情页回填后才有数据。第一版只做 GAI↔wiki 文件级检查（断链 + 缺页 + updated 过期）+ 周报模板 | 1h（语义对账 v2 再做） |
| gai-writer skill + kanban-worker 约定 + close.sh 接线 | 见 §4/§5 | 1.5h |
| **小计** | | **7h** |

差距 3h 落在：解析器（+1h）、gai_drift 语义 diff 砍掉才是 1h（架构师把它算进了 4h）、skill+约定+接线（+1h）。

**触发机制裁决：三层，不搞纯"worker 约定"**：
1. **主路径（done/归档）→ 接线进 close.sh S3**。这不是新约定，是替换现有强制步骤——close.sh 已经是闭环验证的强制入口，把 S3 的 sed 换成 `gai.py done <ID> --date`。事件驱动、零轮询、天然带 task_id 上下文。
2. **新指令（add）→ kanban-worker skill 协议**：patch 现有 skill，加"创建任务/新指令时同步 gai.py add"。这是行为约定，接受失忆风险，由第 3 层兜底。
3. **兜底 → gai_drift.py 周 cron**（唯一 cron）。

**为什么不能只靠 worker 约定**：GAI 里 OBS-01 就是"LLM 忘记调 relay_update.py"的活案例——同一个失败模式（LLM 记不住手动步骤），已经在观察期了。约定必须有强制路径 + 周期对账双保险，否则 wiki 就是下一个 OBS。

---

## 4. 详情页生成（问题 4）— 半自动，脚本保结构、LLM 填语义

**数据源优先级**：
1. GAI 行本身 → frontmatter 机械预填（id/status/priority/mechanism/est_hours，零 LLM）；
2. kanban.db → 参考材料（task_runs 的 summary/metadata + task_comments + task_events），直接复用 boot_context.py 的 `_safe_sqlite_query`（已存在，不用新写 sqlite 封装）；
3. docs/roundtables/ → 引用 roundtable 裁定；
4. session_search → 最后手段。

**半自动分界**：`gai.py add` 生成骨架页（frontmatter 完整 + 四段空节 + 自动收集参考材料链接），gai-writer skill 填四段正文，`--check` 验证四段非空。脚本保证结构完整可校验，语义撰写交给 LLM——不追求全文自动生成，那是把 LLM 的活硬塞给脚本。

**回填工时**：架构师估 P1 七行 = 1h，太乐观。每页要求四段非空 + ≥1 参考来源 + ≥2 出链，按 10-15 分钟/页 → **P1 七行 1.5-2h**（LLM 侧）。全量 32 行 = 5-6h，放 V2，不进 MVP。

---

## 5. 与 devPPL 管线集成（问题 5）

| 集成点 | 动作 | 工时 |
|--------|------|:---:|
| close.sh S3 | sed → `gai.py done`（主路径，见 §3） | 0.3h（含测试） |
| S6 验证 | close 后追加 `gai_index.py --check` 为门禁（MVP 后可选项） | 0.3h |
| 备份 | /workspace/devPPL-wiki 加入 manifest.yaml（BKP-003 模式，已有先例） | 0.2h |
| boot_context | 不注入 GAI（保持现状），可把 --check 摘要（"wiki 断链 N 处"）拼进输出——每个 OC 会话可见，低成本高价值 | 0.2h（可选加分项） |
| DPL-010 | post-commit hook 落地后 gai.py 调用自动迁移，无需改代码 | — |

---

## 6. 分阶段实施（问题 6）

**MVP（本周，~6.5h）**：
- M0 (0.5h)：git rm workspace GAI 副本 + 提交；grep 确认零引用
- M1 (2h)：devPPL-wiki 初始化（SCHEMA 定制 + index/log + entities 首 4-6 页 + 备份 manifest + gai-writer skill 骨架）
- M2 (3h)：gai.py 最小集（list/done/add）+ 表感知解析器 + ~20 pytest + close.sh S3 接线
- M3 (1.5h)：P1 七行回填（骨架自动 + gai-writer 填四段）

**V2（下周，~5h）**：gai_drift.py 周报（文件级，唯一 cron）+ gai.py demote/update + --check 四不变式全开 + P2/P3 回填

**V3（DPL-013 之后）**：引擎事件钩子，worker 约定整体迁移

**总账**：MVP 6.5h + V2 5h ≈ **11.5h 全量**。架构师 7h 的缺口：gai.py 解析器 +1h、gai_index/gai_drift 拆开 +1h、skill+约定+接线 +1h、回填 +0.5~1h。

---

## 7. 风险与反共识汇总

- **反共识 1**：004b 的 4h 做不到，7h 才是实数。要么扩预算，要么砍 gai_drift 语义 diff（我建议砍，语义对账本来就该等数据）。
- **反共识 2**："worker 约定"是 OBS-01 同款失败模式，必须接线进 close.sh 才有强制力。
- **反共识 3**：不给 profile 设全局 WIKI_PATH，脚本内显式传——否则 llm-wiki 通用 skill 会污染决策档案。
- 风险：GAI 表格解析是最大技术风险（脏数据 + 多 schema）→ 缓解：容错解析器 + fixture 测试 + --check 幂等，坏单元格只告警不崩。
- 风险：回填质量参差 → 缓解：只求四段非空 + 参考可溯源，措辞后续 lint 迭代（与架构师一致）。

---

## 8. 一句话结论

wiki 骨架不难（2h），难在 GAI 表格解析（4 种 schema + 脏数据实锤）和强制同步（close.sh 接线，不能只靠约定）。MVP 砍到 6.5h 可交付，架构师 7h 总估需上修到 ~11.5h。
