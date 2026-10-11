# 评估报告 — MEM-003 建卡铁律 v4 memctl 侧：next-seq 分配 + drift 扩展 + lint I5

> 评估人：寇豆码（game-engine） | 日期：2026-08-12 | 评估卡：t_est_40ec4bde
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）
> 源卡：t_40ec4bde（[DEV] MEM-003 建卡铁律 v4 memctl 侧 — next-seq 分配 + drift 扩展 + lint I5）
> 来源：架构设计 t_84884feb（commit f5fdcb6）子卡 B；PRD t_4e8e0d71（commit ba431a6）。P1-2 排期。
> 架构文档：docs/arch/arch-card-numbering-chain-v4.md（§2 next-seq / §5 drift / §6 lint I5 / §11.2 测试 T8-T13）

## 1. 结论（TL;DR）

**拆 2 张串行子卡（预计 24-30 轮 > 20 轮阈值）。**

三个实现点（next-seq / drift 扩展 / lint I5）互不依赖，但**共享 schema.py 常量**
（CARD_CODE_RE + PROJECT_CODES_PATH，架构 §6.3），且各自带独立测试——拆成 2 张
子卡后每张 10-14 轮，均在 ≤20 轮阈值内。串行而非并行：schema.py 共享常量先落 S1，
S2 消费，避免同仓双 worktree 合并冲突。

## 2. 工作量评估（读码结论，非假设）

| 维度 | 评估 | 依据 |
|------|------|------|
| 改动面 | **6 个代码文件 + 1 个文档 + 3 个测试文件**：memcore/seq.py（新）、memcore/cli.py、memcore/schema.py、memcore/drift.py、memcore/lint.py、wiki/SCHEMA.md、tests/test_seq.py（新）、tests/test_drift.py、tests/test_lint.py | 源卡 + 架构 §2/§5/§6 |
| 现状基线 | 存量 89 个 test 函数（test_lint 19 / test_cli 22 / test_drift 9 …），当前全绿；memctl 为 repo 直连 console script（/usr/local/bin/memctl，sys.path 注入 repo，改代码无需重装） | grep 计数 + 实测 test_drift+test_lint 28 例 PASS + 读 bin/memctl |
| ① next-seq | 新建 memcore/seq.py（~80-120 行）：`load_project_codes`（读 PROJECT_CODES.md 表格，11 个注册码，2-3 字母）+ `next_seq`（校验 CODE ∈ 注册码 → GaiAdapter.fetch_events 读 GAI 任务 ID 列取 max → wiki/actions/ 目录兜底 → 001 → fcntl.flock 共享锁）。cli.py 新增 cmd_next_seq + argparse 接线 | 架构 §2；schema.py 现有 11 码表可复用 GaiAdapter（sources/gai.py 已有列位感知解析，MEM-QA-02 修复后不会误匹配优先级列 P1-07） |
| ② drift 扩展 | drift.py：`_kanban_active` 增 body + task_links 读取（现 L16-34 只取 id/title/status）；新增 `_extract_codes`（复用 CARD_CODE_RE）；新增 `_numbering_diffs`（存在性 kanban→GAI / kanban→wiki、唯一性三源查重、链一致性连通分量判定，~80 行）；接入 three_way_check 追加在既有缺页/断链之后 | 架构 §5.2；task_links 表结构（parent_id/child_id）已从 kanban.db 确认 |
| ③ lint I5 | lint.py `_frontmatter_errors` 追加 ⑤ task_code 非空 + 格式 `[CODE]-\d{3}`、⑥ id==task_code；骨架页豁免复用 `_mechanical_skeleton`（OBS-01 模式）；schema.py 新增 PROJECT_CODES_PATH 常量 + CARD_CODE_RE regex；wiki/SCHEMA.md §4/§7 同步 | 架构 §6.1-6.3 |
| 测试 | 新增 6 例（架构 T8-T13）：T8 next-seq DPL max+1 / T9 兜底 001 / T10 非法 CODE 拒绝 / T11 drift 三维度各出差异+一致空 / T12 lint task_code 缺失/格式/id 不同值+骨架豁免 / T13 CARD_CODE_RE 双仓同串 | 架构 §11.2 |
| 回归 | 存量 89 例全绿 + 真实仓库 `memctl lint`（I5 生效后零问题）+ `memctl drift` 输出空（编号维度） | 架构 §11.3 完成定义 |

**预计轮数：24-30 轮**（① next-seq 8-10 + ② drift 7-9 + ③ lint I5 5-7 + 回归修 fallout 3-4 + commit/claim/飞书 1-2）> 20 轮阈值。

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| parse.Page 无 page_type 字段 | **高** | 架构 §6.1 伪代码引用 `page.page_type`，实测 parse.py L224-313 只有 type 无 page_type（SCHEMA §7 I5 ①-④ 尚未实现，仅文档）。实现须二选一：① parse.py 增加 page_type 解析（+20 行 + parse 测试）② 按 SCHEMA §3.1 映射规则用 `page.type == "action"` 推断 task（架构 §6.2 注释已暗示 actions/ 页天然满足 id==task_code）。建议选 ②，省一个文件改动面 |
| lint I5 不变式归属 | 中 | 现有 frontmatter 错误全归 I4 bucket（lint.py L349-350 `Issue("I4", ...)`），SCHEMA §7 把 task_code 划归 I5。⑤⑥ 挂在 _frontmatter_errors 后自然落 I4 输出；若要 I5 独立渲染需改 render() + LintResult 不变式循环（L49-55 硬编码 I1-I4）。建议：⑤⑥ 落 I4 bucket（复用现有输出），SCHEMA.md 注明实现归口，避免动渲染层 |
| task_links 连通分量判定 | 中 | _numbering_diffs 链一致性需同编号活跃卡构无向图 + BFS/union-find 求连通分量（架构 A3：分量==1 成链）。~30 行算法代码，T11 需构造多卡 + 边 fixture |
| flock 并发测试 | 中 | next_seq 对 GAI 文件加 fcntl.flock 共享锁（L1）。单测验证锁行为成本高（多进程 fixture），建议 L1 用轻量断言（锁文件存在/可加锁），L2 CAS + L3 drift 查重逻辑用纯函数单测覆盖 |
| GAI 行解析边界 | 中 | 真实 GAI 现有 6 行待办，任务 ID 列已是 [CODE]-NNN 格式（MEM-001/DPL-009…），GaiAdapter 可复用；但 seq 的 max 统计必须只数 `f"{code}-\d{3}"` 前缀（防 INF-011 子串干扰） |
| 真实仓库 lint/drift 自检 | 中 | I5 ⑤⑥ 上线后真实 wiki（actions/ 现有 MEM-001/MEM-002/DPL-002/DPL-009/INF-011/CLC-001/WIKI-001）需全部通过——若老页缺 task_code 会误报，实现时须核对并补 task_code（或确认豁免走骨架） |
| schema.py 共享常量 | 低（串行规避） | CARD_CODE_RE / PROJECT_CODES_PATH 同时被 seq/drift/lint 消费；并行双 worktree 会在 schema.py 产生合并冲突 → 串行让 S1 先落常量 |

**关键决策点（实现时需拍板，已含倾向，均不改变轮数上限）**：
1. page_type 缺失 → 用 `page.type == "action"` 推断（架构 §6.2 语义一致），不扩 parse.py。
2. I5 ⑤⑥ 落 I4 bucket（复用 _frontmatter_errors 输出），不新增 I5 渲染行。
3. next-seq L1 flock 用轻量锁断言，L2/L3 用纯函数单测（不写多进程 fixture）。

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 预计轮数 | 24-30 轮 > 20 轮阈值 → **拆** |
| 模块依赖 | 三个实现点无代码级依赖，但共享 schema.py 常量（CARD_CODE_RE/PROJECT_CODES_PATH） |
| 并行收益 | 有但有限——3 模块独立可并行，但 schema.py 共享文件产生合并冲突；且同 profile 并行上限 3 张 |
| 串行收益 | S1 先落 schema.py 常量，S2 直接消费，零冲突；两张卡各 10-14 轮 ≤ 20 轮阈值 |
| 兜底 | 即使 S2 超预算，drift 与 lint I5 也是独立 commit 粒度，任一完成即可部分交付 |

**决策：拆 2 张串行子卡。** 单卡 24-30 轮逼近 60 轮预算一半，且 MEM-001 已有
60/60 超时实证（9a61d29 评估）；拆后每张 10-14 轮，留足余量。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 2 serial
1. [S1] next-seq 引擎 + schema 常量（mem-core）：memcore/seq.py（next_seq/load_project_codes
   + flock 并发 + GAI→wiki→001 双兜底）+ cli.py cmd_next_seq + schema.py 新增
   PROJECT_CODES_PATH/CARD_CODE_RE + 测试 T8-T10/T13。预计 10-12 轮。
2. [S2] drift 编号三维度 + lint I5 ⑤⑥（mem-core）：drift.py _kanban_active 扩 body/task_links
   + _numbering_diffs（存在性/唯一性/链一致性）+ lint.py _frontmatter_errors ⑤⑥ + 骨架豁免
   + wiki/SCHEMA.md 同步 + 测试 T11-T12。预计 12-14 轮。
   依赖：S2 消费 S1 落地的 schema.py CARD_CODE_RE → 串行，parents=[S1]
```

- SPLIT: yes（count=2）
- MODE: serial（S1 → S2，共享 schema.py 常量）
- ROUNDS_EST: 27
- FILES: memcore/seq.py(新), memcore/cli.py, memcore/schema.py, memcore/drift.py, memcore/lint.py, wiki/SCHEMA.md, tests/test_seq.py(新), tests/test_drift.py, tests/test_lint.py
- STATUS: not_started（源卡 t_40ec4bde 待 dev 实现）
- TESTS: 存量 89 例 PASS 基线；新增 T8-T13 共 6 例（架构 §11.2）
- RISK: parse.Page 无 page_type（用 type=action 推断）；I5 ⑤⑥ 归 I4 bucket；task_links 连通分量；flock 测试轻量化；真实 wiki 老页 task_code 补全核对
- ACTION: build_two_dev_cards（S1/S2 均 assignee=game-engine；S2 parents=[S1]）

## 6. 备注

- 源卡即架构子卡 B，实现依据全部在 arch-card-numbering-chain-v4.md §2/§5/§6/§11，无需再补文档。
- 三个实现点全部落 mem-core 仓（devPPL 仓的管线侧已在子卡 A t_xxxxx 范围，本卡不含）。
- 验收标准 5 条全部可映射到 T8-T13 + 真实仓库 memctl lint/drift 自检。
- 本评估卡不写代码；autopilot 读取 [SUB-SPLIT] comment 后建 2 张 [DEV-SUB] 卡执行。
