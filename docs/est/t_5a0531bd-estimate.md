# 评估报告 — [DEV-EST] MEM-009 对话提取 — 对话/纠正自动提取记忆与经验（蓝图方向A，第三源 conversation adapter）

> 评估人：寇豆码（game-engine） | 日期：2026-08-19 | 评估卡：t_5a0531bd
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）+ DPL-018 校准注入
> 源卡链：t_3f5c8462（PRD v1.0，276 行）→ t_71a9b5f9（arch v1.0，714 行，commit e727cea @ mem-core main）→ **本评估 → dev**
> 有效轮折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）
> 校准注入: 累计偏差 +1.55 → K=2.55（clamp 0.5-3.0）；最近 5 条子卡偏差全部 timed_out（60 轮），含 t_cc4bde55（18-29→60）、t_de2602b3（20-31→60）、t_0d7a4a1a（18-24→60）

## 1. 结论（TL;DR）

**拆 4 张串行子卡（校准后每张 18-33 轮，全部落在单会话 42 有效轮预算内）。**

任务本质是**蓝图第二环（对话流）**落地：mem-core 新增第三个 SourceAdapter
（`sources/conversation.py`，白名单发现/机械摘要/强弱词纠正检测/复合游标全在 adapter 内闭包），
memctl 扩三个命令面（add conversation / note --correction / query --corrections + status 三计数），
devPPL 侧引擎仅扩 `_COUNTER_KEYS` 两个计数键 + 新增 conv_sync.sh 两阶段包装与 conv_curate.py 策展脚本。

架构 §11 建议 ~13h 拆 2 张 dev 卡（D1=mem-core S1+S2，D2=devPPL S3+S4）。
**按 DPL-018 校准 K=2.55 复算：D1 基准 19-26 → 校准 48-66 ❌、D2 基准 9-13 → 校准 23-33 ✓。
D1 单卡超出 42 有效轮预算**——正是 MEM-007 评估（t_2ba7e58f，当时 K=3.00）把架构 2 卡方案
复算后拆成 5 卡的同款情形，且当前 K=2.55 下最近 5 张子卡仍全部 timed_out，粒度必须再压。
本评估按「测试独立成卡」+「命令面独立成卡」拆 4 张，每张基准 7-13 轮、校准后 18-33 轮。

**评估期间实测基线**（本卡 run 内）：
- mem-core pytest **226 用例全绿**（`--collect-only` 226，全量跑 137s——全量回归 ≈ 1 轮，非大头）；
- `sources/base.py` 60 行：initial_cursor / command_for / page_exists 三个可选方法 **MEM-007 已加好，本环零改动**（比 MEM-007 少一步基类扩展）；
- `SOURCES` 注册表现 2 源（gai+kanban），加一行即可；`schema.py L20-28` PAGE_TYPE_ENUM **已含 conversation→raw**（lint/indexer 零适配，实测确认）；
- `cli.py` 1760 行：cmd_add(L164)/cmd_note(L769)/cmd_query(L842)/cmd_status(L902) 四个挂载点明确；events 表实读 schema（kind/page_id/detail TEXT，detail 需 json_extract=JSON1）；
- `tests/conftest.py` 230 行只有 wiki/mem_meta fixture，**无 state.db fixture**（需新建，MEM-007 kanban.db fixture 同模式先例）；
- `mem_sync.py` 529 行 `_COUNTER_KEYS` @L65（实证 #9：新 kind 不扩表 counters[ev.kind] KeyError）；
- devPPL scripts/ 无任何 conv_* 文件（全新增）；devPPL pytest 基线 281 例（t_e3f36f10 VA-POST 实测引用）；
- **用例膨胀实证**：MEM-007 架构估 12 用例，实际 test_sources_kanban.py 落地 **17 用例（+42%）**——本评估按此膨胀系数备预算。

## 2. 工作量评估（读码结论，非假设）

改动面：**跨 2 仓 9 文件**（mem-core 5：conversation.py 新 / __init__.py 改 / cli.py 改 / test_sources_conversation.py 新 / test_cmd_conversation.py 新；devPPL 4：mem_sync.py 改 1 行 / conv_sync.sh 新 / conv_curate.py 新 / test_conv_sync.sh 新）。架构 §10.1 文件清单 + conftest.py 改（fixture）。

| 维度 | 评估 | 依据 |
|------|------|------|
| ① SUB-1 adapter 机制（mem-core） | conversation.py ~350 行（架构 §2/§3）：D2 白名单 SQL（archived/source/ended-静置/title 冒号四条件原文给出）+ user 计数批查（噪声前缀排除）+ 页存在性去重 + 机械摘要行生成（均匀取样 ≤80 行 ×120 字）+ 强弱词表检测（18 词两级+双弱词门控）+ fingerprint（sha256[:12]）+ mute 名单 + D3 复合游标（首跑锚点/棘轮/回看窗）+ Event 两 kind 组装 + map_id/page_exists/command_for（--summary-file 临时文件）。架构契约定到 SQL/词表/公式实现级 → 主体照搬但体量大 **8-10 轮**；SOURCES 注册一行 0.5 轮；手工冒烟 3-4 断言（临时 profile 树 fixture）1-1.5 轮；pytest 全量回归 1 轮 → **基准 10-13** | 架构 §2.2 SQL/§3.1 词表/§2.4 游标全部原文定稿；base.py 可选方法已在（实测）；kanban.py 217 行先例（conversation 多发现+摘要+检测三块，~1.6×） |
| ② SUB-2 pytest 用例（mem-core） | conftest.py 新建 state.db fixture（profile 树 + sessions/messages 建表 + feishu/cli/cron/噪声样本注入，golden 模式）**2-2.5 轮**；test_sources_conversation.py 按架构 §8.1 前 14 用例（白名单/静置/user_min/噪声注入/游标首跑/晚 end 反例/崩溃窗/事件序/强词/弱词门控/指纹稳定/mute/只读/map_id+command_for）**4-5 轮**；全量回归修绿 1 轮 → **基准 7-9** | §8.1 用例表断言逐条列明；MEM-007 12→17 膨胀 +42% 已计入（14 用例按 18-20 实做预算） |
| ③ SUB-3 memctl 命令面（mem-core） | cli.py 四触点：add conversation 子命令（§2.6 骨架模板 frontmatter 全字段 + page_id 前缀归一化 + 幂等 exit 1 + 维护链 _log_append/_maintenance/_git_commit）**2-3 轮**；note --correction（(page,fingerprint,message_id) 去重查询 + INSERT 只写 events 不走维护链 + JSON1 回退 LIKE）**1.5-2 轮**；query --corrections（对话级 GROUP BY + links UNION 记忆级 + --json + 无参 Top-20）**1.5-2 轮**；status 三计数 0.5 轮；test_cmd_conversation.py 6 用例 + 回归 **2-2.5 轮** → **基准 8-10** | 架构 §4 契约表（幂等键/退出码/写入边界）逐项定稿；cmd_add/note/query/status 挂载点实测定位；events schema 实读 |
| ④ SUB-4 devPPL 管线 | mem_sync.py `_COUNTER_KEYS` += conversation/correction/curated（**1 行**，实证 #9 防 KeyError）+ test_mem_sync.sh 回归 0.5 轮；conv_sync.sh 两阶段薄包装（fail-open 恒 0）0.5 轮；conv_curate.py ~250 行（队列 JSON 原子写/打分 ≥3 入队/Top-N=3/learn --llm 子进程/rc 协议重试 <3/≥3 abandoned+页内记行/日志行）**3-4 轮**；test_conv_sync.sh ≥12 断言（临时 2 profile state.db + 临时 wiki git init + 假 LLM 成功/失败两态，覆盖 A1-A8/A10/A11）**4-5 轮**；devPPL pytest 281 例回归 1 轮 → **基准 9-11** | 架构 §5/§6/§8.2 断言清单逐条；test_mem_sync.sh（521 行 89 断言）与 test_deploy_drift T5 桥模式先例；假 C 命令可测性架构 D9 已保证 |

**基准轮数（未校准，合计）：34-43 轮（中位 ~38）。**
**DPL-018 校准：34-43 × K=2.55 → 校准后 87-110 轮**（远超 42 有效轮单卡预算 → 必须拆卡）。

## 3. 复杂度与风险

| # | 风险 | 评级 | 说明与缓解 |
|---|------|:---:|------|
| R1 | 架构契约实现级定稿，主体照搬 | 低（利） | D1-D11 裁决齐 + SQL/词表/argv/退出码/骨架模板原文给出；研发风险在细节遗漏不在设计决策 |
| R2 | cli.py 1760 行四触点手术 | 中 | add/note/query/status 四处改动互不重叠但同文件；SUB-3 独占该文件（串行拆卡天然隔离），pytest 全量 226 例兜底 |
| R3 | 双 fixture 新建 | 中 | conftest state.db fixture（SUB-2）+ test_conv_sync.sh shell fixture（SUB-4）两处独立建设；MEM-007 kanban.db fixture 同模式先例（golden 复制基建可复用） |
| R4 | note --correction 是**新语义非继承** | 中低 | 只写 events、不走 _maintenance/git commit——与 note 既有「执行记录+状态镜像」路径不同，必须严格按 D5 契约防误触维护链；test_cmd_conversation 断言「无 git diff」兜底 |
| R5 | conv_curate 与 learn 子进程联调 | 中 | 假 C 命令成功/失败两态 + --supersedes 分支 + rc 协议；learn _run_llm 契约（stdin JSON/stdout md/fail 不写）已有 test_learn.py 先例可参照 |
| R6 | 用例数膨胀 | 已计入 | MEM-007 实证 12→17（+42%）；本评估 §8.1 前 14 用例已按 18-20 实做预算，不再追加 |
| R7 | 双仓并行冲突 | 低 | 拆卡天然按仓边界：SUB-1/2/3 全在 mem-core、SUB-4 全在 devPPL，串行执行零同仓写冲突（DPL-026/027 教训） |
| R8 | 新 kind 不扩计数键 → KeyError | 低（已实证） | 架构实证 #9 + D7 已列；SUB-4 第一个动作就是扩 _COUNTER_KEYS 再跑回归 |
| R9 | SUB-1 校准后 33 轮 = 预算 79%，最紧 | 中 | 兜底：若 SUB-1 执行中发现超预算，纠正检测块（§3 词表/指纹/mute，独立可测）可再切 SUB-1b 卡——不改变其余 3 卡结构，作为 contingency 由实现者按 50 轮存档铁律判断 |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 34-43 轮（中位 38） |
| DPL-018 校准后 | 87-110 轮（×K=2.55）**远 > 20 轮阈值 → 必须拆卡** |
| 交付物数 | 4 个（adapter 机制 / pytest 用例 / memctl 命令面 / devPPL 管线+集成测试）≥ 4 → 按规则拆 ~3-4 卡 |
| 架构 2 卡方案复算 | D1=mem-core(S1+S2) 基准 19-26 → 校准 48-66 ❌ 超 42；D2=devPPL(S3+S4) 基准 9-13 → 校准 23-33 ✓。**D1 不可行 → 至少 3 卡** |
| 3 卡方案复算 | ①S1 机制+测试合并 基准 17-22 → 43-56 ❌；②测试并入命令面（跨目标）15-19 → 38-48 边缘超 ❌。**3 卡无解 → 4 卡** |
| 本评估 4 卡方案 | 每张基准 7-13 → 校准 18-33，全部 < 42 有效轮 ✅（最紧 SUB-1 = 33/42 = 79%） |
| 依赖方向 | SUB-2 断言 SUB-1 的 adapter 行为；SUB-3 命令面是 SUB-1 command_for 的 argv 落点（契约已定稿，但需实物对齐）；SUB-4 引擎经 SOURCES 调 adapter + subprocess 调 memctl 三命令 → 全链依赖 SUB-1+SUB-3 |
| 并行收益 | 低——SUB-2/SUB-3 理论文件不重叠（tests/ vs cli.py）可并行，但同仓（mem-core）双 worker 有 worktree 冲突面（R7），默认串行最稳 |
| 兜底 | 每张子卡独立验收闭环：SUB-1 交 adapter+注册+冒烟；SUB-2 交 14+ 用例全绿；SUB-3 交三命令+6 用例；SUB-4 交管线+≥12 断言。任一卡超预算，已完成卡可先合并不阻塞 |

**决策：拆 4 张串行子卡（[SUB-SPLIT] 4 serial）。**
量级参照：MEM-007 同管线拆 5 卡（t_2ba7e58f，当时 K=3.00）；本任务引擎/基类/schema 复用度更高（base.py 零改、PAGE_TYPE_ENUM 已含、引擎 1 行）但 adapter 体量更大（350 vs 217 行）+ 命令面三命令，4 卡粒度与 MEM-007 5 卡同量级。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 4 serial
1. [DEV-SUB-1] mem-core S1 机制 — conversation adapter：memcore/sources/conversation.py（~350 行：
   D2 白名单发现 SQL + user 消息计数过滤（噪声前缀排除）+ 页存在性去重 + 机械摘要行生成（≤80 行×120 字）
   + 强弱词纠正检测（18 词两级+双弱词共现门控）+ fingerprint sha256[:12] + mute 名单 + D3 复合游标
   （首跑锚点/单调棘轮/8h 回看窗）+ conversation/correction 两 kind Event 组装（correction 排后不变量）
   + map_id/page_exists/command_for（--summary-file 临时文件））；sources/__init__.py SOURCES 一行注册；
   手工冒烟 3-4 断言（临时 profile 树：白名单/静置/只读）；mem-core pytest 226 全量回归。
   预计 26-33 轮
2. [DEV-SUB-2] mem-core S1 测试 — conftest.py 新建 state.db fixture（profile 树 + sessions/messages 建表
   + feishu/cli/cron/subagent/[ASYNC DELEGATION 噪声样本，golden 模式）
   + tests/test_sources_conversation.py 架构 §8.1 前 14 用例（白名单/静置兜底/user_min/噪声注入/
   游标首跑 events=0/晚 end 回看窗反例/崩溃窗自愈/事件排序/强词检出/弱词门控/指纹跨会话稳定/mute/
   mode=ro 只读/map_id+command_for argv）+ mem-core pytest 全量回归。
   预计 18-23 轮
3. [DEV-SUB-3] mem-core S2 命令面 — cli.py：add conversation 子命令（§2.6 骨架模板 frontmatter 全字段
   + page_id 前缀归一化 + 幂等页存在 exit 1 + 维护链 _log_append/_maintenance/_git_commit）
   + note --correction（(page_id,fingerprint,message_id) 三元去重键查询 + INSERT 只写 events 不走维护链
   + JSON1 不可用回退 LIKE）+ query --corrections（对话级 GROUP BY + links UNION 记忆级聚合 + --json
   + 无参全局 Top-20）+ status 三计数（conversation 页/correction 事件/策展队列积压）
   + tests/test_cmd_conversation.py 6 用例（页生成 frontmatter 断言/幂等 exit 1 无 diff/去重重放 3 次/
   同指纹异 message_id 计数 2/links 聚合/三计数行）+ 回归。
   预计 20-26 轮
4. [DEV-SUB-4] devPPL S3+S4 管线 — scripts/mem_sync.py _COUNTER_KEYS += conversation/correction/curated
   （实证 #9 防 KeyError，引擎唯一改动）+ scripts/conv_sync.sh 两阶段薄包装（fail-open 恒 exit 0）
   + scripts/conv_curate.py（conv_queue.json 原子写/打分 ≥3 入队/Top-N=3/learn --llm 子进程调用/
   rc≠0 重试 <3、≥3 abandoned+页内记行/每 tick 日志行）+ scripts/test_conv_sync.sh ≥12 断言
   （临时 2 profile state.db + 临时 wiki git init：A1 feishu 页生成/A2 cli 静置/A3 噪声排除 skipped/
   A4 纠正 3 事件聚合 2+1/A5 重放 3 次不变/A6 state.db md5 一致/A7 删库 fail-open/A8 work-gated/
   A10 假 LLM exit 1 骨架保留 rc=0/A11 假 LLM 成功态记忆页+双链+lint 零新增/A12 grep 引擎零对话语义）
   + test_mem_sync.sh 回归 + devPPL pytest 281 例回归。
   预计 23-28 轮
```

- SPLIT: yes（count=4，校准后 87-110 轮远超 20 阈值；3 卡方案复算无解）
- MODE: serial（SUB-2/3 依赖 SUB-1 实物对齐；SUB-4 依赖 SUB-1+SUB-3 全链；同仓避免 worktree 冲突）
- ROUNDS_EST（校准后）: 87-110（基准 34-43 × K=2.55；分卡后每张 18-33）
- FILES: mem-core 5 文件（conversation.py/__init__.py/cli.py/两个测试文件 + conftest）+ devPPL 4 文件（架构 §10.1 清单）
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 4 张子卡挂本卡）
- TESTS: SUB-1 冒烟 3-4 + 226 回归；SUB-2 14+ 用例全绿；SUB-3 6 用例全绿；SUB-4 ≥12 断言 + 281 回归
- RISK: R2 cli.py 四触点（串行卡隔离）；R3 双 fixture 新建；R4 note --correction 新语义防误触维护链；
  R5 learn 子进程联调；R9 SUB-1 最紧 79% 预算（contingency：检测块可切 SUB-1b）
- ACTION: build_four_dev_cards（assignee=game-engine，parents=[t_5a0531bd]，serial）

## 6. 备注

1. 架构 §11 的 2 卡建议基于人时估算（~13h，D1=7h/D2=5h），未过 DPL-018 轮数校准；D1 复算 48-66 轮
   超 42 预算，照搬会重蹈最近 5 张子卡 timed_out 覆辙。4 卡方案与 MEM-007（5 卡）同粒度水平。
2. S5（cron 注册 + 真实链路冒烟 §8.3）**不建 dev 卡**——基础设施铁律注册权归 OC（架构 §7、DPL-048、
   MEM-007 D12 同款）；真实链路冒烟归 OC 上线后观察（本卡自身会话即首个样本）。
3. QA 卡（A1-A12 全量验证）由 OC 按 QA 流程另建，不在本 [SUB-SPLIT] 内。
4. 双仓提交：SUB-1/2/3 全部落 mem-core main（各自 worktree 分支 merge --no-ff）；SUB-4 落 devPPL main。
   conv_queue.json 是运行时产物不入库（.pipeline/ 已忽略）。
5. 本评估卡不写功能代码；产出即本报告 + [SUB-SPLIT] comment，autopilot 读取后建 4 张 [DEV-SUB] 卡执行。
