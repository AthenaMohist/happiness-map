# 评估报告 — [FIX] worker 手工建卡缺编号/缺 GAI — 补登记 + autopilot 检测注入编号机制

> 评估人：寇豆码（game-engine） | 日期：2026-08-15 | 评估卡：t_est_74963b5d
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）+ DPL-018 校准注入
> 源卡：t_74963b5d（[FIX] worker 手工建卡缺编号/缺 GAI — 补登记 + autopilot 检测注入编号机制）
> 有效轮数折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）

## 1. 结论（TL;DR）

**拆 3 张串行子卡（校准后预计 51-78 轮 > 20 轮阈值）。**

任务本质是**编号/GAI 登记的机制化补齐**，含两半性质迥异的工作：
- **A 半（补登记）**：为 2 条缺失编号的链（t_14fb6a11 链 + t_0f418cf6 链，共 6 张卡）补分配编号
  （DPL/MEM，走 memctl next-seq）+ 补写 .pipeline/gai/ json。纯数据修复，零新机制代码，
  但要求「先 SQL 实测 kanban max 防撞号」——与 DPL 编号盲区教训（08-14）直接相关。
- **B 半（机制防复发）**：worker 手工建卡（SUB-SPLIT / autopilot 暂停期兜底）必须走编号分配。
  选项 A（autopilot.sh 检测无编号 FIX/[DEV-*] 卡 → 自动注入编号 + 登记 GAI）与既有
  `process_va_backfill`（discover.py L1084，每 tick 扫描 + 建卡 + fail-open）**完全同构**，
  实现模式成熟；但存在**已实锤的存量洪泛风险**（board 有 **168 张无编号 [FIX]/[DEV-*]/[CMD] 卡**，
  实测 SQL COUNT），必须带窗口防历史卡一次性全注入。

自然边界：S1 = 补登记（纯数据 6 卡）、S2 = 机制函数 + autopilot 挂载、S3 = 3 fixture 测试 +
全量回归 + 自身 merge 落地。S1 独立可先行（数据修复不等机制）；S2 机制不依赖 S1 的数据结果
（扫描器天然跳过已编号卡）；S3 测试断言依赖 S2 函数在 main 上存在 → 串行。

**评估期间实锤现状**（2026-08-15 10:40）：
- 6 张待补登记卡**全部 done**：t_14fb6a11/t_6c4a9cae/t_a2466834（链 1）、
  t_0f418cf6/t_6d807f49/t_288e56a6（链 2）——全部无（DPL/MEM-NNN）编号、无 .pipeline/gai/ json。
- kanban 标题实测 max：DPL=30、MEM=8（SQL COUNT，防撞号基线）；memctl next-seq DPL → DPL-031。
- 编号格式实证：t_740b5ab3 标题 `（DPL-029）`（全角括号，编号在标题尾部）——同编号连续步骤
  task_links 成链（建卡铁律 v4），故链 1 分 DPL-031、链 2 分 DPL-032（各 1 个号，同链复用）。
- 补验卡 t_ad5656e4 已核验这两条链的 claim（verifier），本卡补的是编号/GAI 登记，不重复核验。
- 基线 test_cmd_channel.sh 现为 **387 PASS**（T15-T18 后），源卡验收 4 写 386 为 T15-T18 前快照。

## 2. 工作量评估（读码结论，非假设）

| 维度 | 评估 | 依据 |
|------|------|------|
| 改动面 | **~4-6 个文件**：pipeline/discover.py（+`process_number_backfill` ~80-120 行）、scripts/autopilot.sh（+1 挂载块 ~10 行，仿 L188-193 va_backfill 块）、6 张卡标题 UPDATE（kanban.db 直改）+ .pipeline/gai/ ×6 json、scripts/test_cmd_channel.sh 或新 test_number_backfill.sh（+3 fixture 场景 ~150-250 行断言） | 实测 `process_va_backfill`（discover.py L1084-1169）即模板：连接 kanban.db → 扫描候选 → 过滤 → `_hermes_create`/UPDATE → 日志 → fail-open 全内吞；autopilot.sh L188-193 挂载块结构现成 |
| ① 补登记（S1） | SQL 实测 kanban 标题 max（DPL=30/MEM=8 已实测，防撞号）→ `memctl next-seq DPL` 分配 DPL-031/032 → UPDATE tasks SET title 追加 `（DPL-031）`/`（DPL-032）`（链 1：t_14fb6a11/t_6c4a9cae/t_a2466834；链 2：t_0f418cf6/t_6d807f49/t_288e56a6）→ 补写 .pipeline/gai/ ×6 json（task_id/completed_at/steps 最小格式，对齐 manifest 既有形状）→ 验证（devppl_query 复查标题 + json 落盘） | 实测 6 卡标题现均无编号（read_file/kanban_show 实证）；t_740b5ab3 标题 `（DPL-029）` 为编号格式样本；.pipeline/gai/t_036c544e.json 为 json 形状样本；kanban max 防撞号 = 源卡参考「DPL 编号盲区教训」 |
| ② 机制函数（S2） | 仿 process_va_backfill 新增 `process_number_backfill`：扫描 title 无 `（DPL/MEM-\d{3}）` 的 [FIX]/[DEV-*] 卡（排除 [DEV-EST]/[DEV-MERGE]/va-claim/[DEV-QA-SUB-*]）→ 窗口内（env `NUMBER_BACKFILL_WINDOW_H` 默认 24h，防 168 张历史卡洪泛）→ `subprocess memctl next-seq`（或读 GAI max）分配编号 → UPDATE title 追加 `（CODE-NNN）` → 写 .pipeline/gai/ json。幂等：已带编号卡跳过（正则匹配）；编号与 kanban/GAI 一致（写入即同步） | 实测 board 168/254 张 [FIX]/[DEV-*]/[CMD] 卡无编号（SQL COUNT，洪泛风险实锤）；process_va_backfill L1084-1169 同构模板；UPDATE tasks SET title 有先例（test_cmd_channel.sh L708、probe_dpl018_qa.py L186） |
| ③ autopilot 挂载 | 仿 L188-193 va_backfill 挂载块：`python3 -c` 调 `process_number_backfill` + `|| true` fail-open；注释写明「本机制同时满足需求 2：worker 手工建卡（SUB-SPLIT / autopilot 暂停期兜底）编号分配统一走 memctl next-seq，禁手工编号」 | 实测 L171-176/L188-193 挂载模式（每 tick 一次，独立于 ACTIVE_TASKS 循环） |
| ④ 测试（S3） | 3 fixture 场景（验收 3）：(a) 无编号手工卡被检测 → 注入编号（断言：标题出现（DPL-NNN）+ gai json 落盘）；(b) 编号注入幂等 — 已编号卡不重复分配（重跑卡数/编号不变）；(c) 编号与 GAI/kanban 一致（标题编号 == json 编号 == next-seq 序列）。外加窗口边界 / 排除前缀 / 非法 env fail-open / DB 缺失 fail-open | 实测 test_va_backfill.sh（286 行，T1-T7 共 37 断言）harness 现成：隔离 temp kanban.db（复制真实 schema + DROP 触发器）+ 受控注入行 + q1 helper；test_cmd_channel.sh L22-116 同款 harness |
| ⑤ 全量回归 | test_cmd_channel.sh 387 + test_wip_progress_check.sh 62 + bash -n ×2（discover.py/autopilot.sh）；main 上复跑 | 实测当前基线 387 PASS（T15-T18 后）；S2 改动只增不删 → 既有断言不受影响，但必须全量复跑确认 |
| ⑥ 收尾 | S3 自身分支 merge 进 main + 结构化 claim + [PRODUCES] comment + 飞书推送 + kanban_complete | 落地铁律：禁卡 done 代码留 worktree；SOUL 5.1 飞书硬性要求 |

**基准轮数（未校准）：17-26 轮**（① 4-6 + ② 5-8 + ③ 1 + ④ 5-7 + ⑤ 1-2 + ⑥ 2-3）。
**DPL-018 校准：基准 × K=3.00 → 校准后 51-78 轮**（取中位 64）> 20 轮阈值。

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| R1 **存量洪泛（最大风险）** | **中-高** | 实测 board 有 **168 张无编号 [FIX]/[DEV-*]/[CMD] 卡**（254 张项目卡中）。若无窗口，机制一次 tick 会给全部 168 张历史卡注入编号 → 编号序列被历史卡吃光 + GAI json 批量落盘 + 与「补登记只补 6 张」的源卡语义冲突。**必须窗口**（env `NUMBER_BACKFILL_WINDOW_H` 默认 24h，可调宽）+ 每 tick 上限（仿 VA_BACKFILL_MAX_PER_TICK），超窗历史卡记日志留给 OC（fail-open，不阻断）。S2 内定窗口 + 上限 |
| R2 编号分配口径 | 中 | 「编号分配统一走 memctl next-seq（禁手工编号）」→ 机制函数必须 subprocess 调 `memctl next-seq DPL`（或复用其逻辑读 GAI max），**不能手写编号**。但 memctl next-seq 读 GAI max+1 可能滞后 kanban（DPL 盲区教训 08-14：GAI max=30 而 kanban 标题 max 也=30，当前一致，但未来可能分歧）→ **分配前必须先 SQL 实测 kanban 标题 max，取 max(kanban, GAI)+1 防撞号**（源卡参考 1 明示）。S1 补登记同样要过此检查 |
| R3 编号归属规则 | 中 | 哪类卡该被注入编号？（a）[FIX] 源卡 + [DEV-SUB-*] 子卡同链共号（建卡铁律 v4：同编号连续步骤成链）；（b）[DEV-EST] 评估卡/va-claim/[DEV-MERGE]/[DEV-QA-SUB-*] 应排除（title 前缀命中但非项目实现卡）；（c）[CMD] 命令卡是否要号需定（t_740b5ab3 参考体只覆盖 [FIX]/[DEV-*]）。**S2 内定排除清单**（仿 _VA_BACKFILL_EXCLUDED_PREFIXES 模式） |
| R4 GAI json 形状 | 低-中 | 6 张卡是 FIX 链（非完整 7 步管线卡），无 chain_spec_hash/steps 结构。补写的 json 取 manifest 既有最小形状（task_id/completed_at/steps），与 t_036c544e.json 等完整形状并存不冲突。机制写入同样用最小形状。**S1 内定 json 模板**，S2 复用 |
| R5 幂等 | 低 | 已编号卡标题正则命中 → 跳过（每 tick 重扫天然幂等）；UPDATE 前再查一次防并发重复分配；同链同号不重复消耗 next-seq。fixture (b) 覆盖 |
| R6 全量回归 | 低 | discover.py/autopilot.sh 改动只增不删 → 既有 387 断言不受影响；但标题 UPDATE 走 kanban.db 直改 → 确认不触发 subsplit 触发器（实测触发器 WHEN 只在 [DEV-EST] done 迁移瞬间触发，title 更新不触发，安全）；必须全量复跑确认 |
| R7 自身落地自引用 | 低 | S3 改的 test 文件与 discover.py 也要进 main → S3 收尾含自身 merge，与源卡约束 5 一致；fixture 测试保证能力不依赖 live 状态 |
| R8 与 t_4e179008 冲突 | 低 | 源卡约束 parents=[t_4e179008]（唤醒链路 FIX）——**已落地**（26bcebf merge 进 main，1h 前）。autopilot.sh 现无同文件挂载冲突；S2 若遇冲突在分支解决 |

**关键决策点（实现时拍板，不改轮数量级）**：D1 窗口（`NUMBER_BACKFILL_WINDOW_H`，默认 24h + 每 tick 上限）；
D2 编号分配（subprocess memctl next-seq + SQL 实测 kanban max 取大防撞号）；D3 排除前缀清单
（[DEV-EST]/[DEV-MERGE]/va-claim/[DEV-QA-SUB-*]，仿 _VA_BACKFILL_EXCLUDED_PREFIXES）；
D4 GAI json 最小形状（S1 定模板，S2 复用）。

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 17-26 轮（中位 21） |
| DPL-018 校准后 | 51-78 轮（×K=3.00，中位 64）**> 20 轮阈值 → 必须拆卡** |
| 模块依赖 | S1（补登记）独立可先行；S2（机制）扫描器天然跳过已编号卡 → 不依赖 S1 结果；S3（测试断言）依赖 S2 函数在 main 上存在 → S1/S2 可并行，S3 串行在后 |
| 并行收益 | 中——S1 纯数据（4-6 轮）与 S2 机制函数（5-8 轮）**无代码/数据依赖**，可 parallel；S3 必须等 S2 merge 进 main |
| 兜底 | 每张子卡独立验收闭环：S1 交付 6 卡编号 + GAI json（需求 1 可验）；S2 交付检测注入机制 + 挂载（需求 2 可验）；S3 交付 3 fixture 测试 + 全量回归（需求 3/4 可验）+ 自身 merge（需求 5）。任一卡超预算，已完成卡可先 merge 不阻塞 |

**决策：拆 3 张串行子卡（[SUB-SPLIT] 3 serial）。** 量级参照：t_e6b787f1（VA 补扫机制，拆 2 serial）
与本卡同构但少「补登记 6 卡」半；本卡多了纯数据半（S1 4-6 轮）+ 洪泛风险（R1 168 张历史卡）
→ 拆 3 卡后每卡 12-24 校准轮，均在单会话可控区间（42 有效轮）。S1 与 S2 虽无强依赖，但
串行建卡（S2 parents=[S1]）可让 S2 的 live 演示验证「补登记后的 6 卡不再被机制重复注入」
（正例），故取 serial 而非 parallel。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 3 serial
1. [DEV-SUB-1] 补登记 — 6 卡编号 + .pipeline/gai/ json
   （先 SQL 实测 kanban 标题 max 防撞号（DPL=30/MEM=8 已实测）→ memctl next-seq DPL
    分配 DPL-031（链 1: t_14fb6a11/t_6c4a9cae/t_a2466834）/ DPL-032（链 2:
    t_0f418cf6/t_6d807f49/t_288e56a6）→ UPDATE tasks SET title 追加（DPL-031）/
    （DPL-032）→ 补写 .pipeline/gai/ ×6 json（task_id/completed_at/steps 最小形状，
    S1 定 D4 模板）→ devppl_query 复查；禁裸 python3 -c，查状态用 devppl_query.sh）
    预计 4-6 轮
2. [DEV-SUB-2] 机制 — discover.py process_number_backfill + autopilot.sh 挂载
   （仿 process_va_backfill L1084：扫描 title 无（DPL/MEM-\d{3}）的 [FIX]/[DEV-*] 卡 →
    排除 [DEV-EST]/[DEV-MERGE]/va-claim/[DEV-QA-SUB-*]（D3）→ 窗口 NUMBER_BACKFILL_
    WINDOW_H 默认 24h + 每 tick 上限防 168 张历史卡洪泛（D1）→ subprocess memctl
    next-seq + SQL 实测 kanban max 取大分配（D2，禁手工编号）→ UPDATE title +
    写 .pipeline/gai/ json；头注释写明「本机制满足需求 2：worker 手工建卡（SUB-SPLIT /
    autopilot 暂停期兜底）编号分配统一走 memctl next-seq」；autopilot.sh L193 后追加
    挂载块 || true fail-open） 预计 5-8 轮
3. [DEV-SUB-3] 测试 + 回归 + 落地 — 3 fixture 测试 + 全量回归 + 自身 merge
   （test_cmd_channel.sh 追加或新 test_number_backfill.sh，复用隔离 temp DB harness：
    (a) 无编号手工卡被检测 → 注入编号（断言标题（DPL-NNN）+ json 落盘）；
    (b) 已编号卡不重复分配（重跑卡数/编号不变，幂等）；(c) 编号与 GAI/kanban 一致
    （标题编号 == json 编号）；+ 窗口边界 / 排除前缀 / 非法 env fail-open / DB 缺失
    fail-open；全量回归 test_cmd_channel.sh 387 + test_wip_progress_check.sh 62 +
    bash -n；S3 自身分支 merge 进 main + claim + 飞书 + complete） 预计 8-12 轮
```

- SPLIT: yes（count=3，校准后 51-78 轮远超 20）
- MODE: serial（S3 测试断言依赖 S2 函数在 main 上存在；S2 parents=[S1] 便于 live 正例验证）
- ROUNDS_EST（校准后）: 64（基准 21 × K=3.00）
- FILES: S1 改 kanban 6 卡标题 + .pipeline/gai/ ×6 json（+可能一个一次性 SQL/脚本）；
  S2 改 pipeline/discover.py（+process_number_backfill ~80-120 行）+ scripts/autopilot.sh（+挂载 ~10 行）；
  S3 改 scripts/test_cmd_channel.sh 或新 scripts/test_number_backfill.sh（+3 fixture ~150-250 行）
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 3 张子卡挂 t_74963b5d）
- TESTS: S1 devppl_query 复查标题 + json 落盘；S2 bash -n + 冒烟（隔离 DB 跑一次注入 1 卡）；
  S3 3 fixture 场景（~10-15 断言）+ 全量回归 387 + 62
- RISK: R1 存量洪泛 168 张（窗口 + 上限必做）；R2 编号分配口径（memctl next-seq + SQL max 防撞号）；
  R3 排除前缀清单；R4 GAI json 最小形状；D1-D4 实现时拍板
- ACTION: build_three_dev_cards（assignee=game-engine，parents=[t_74963b5d]，serial）

## 6. 备注

- **补登记与机制的关系**：S1 补的是存量 6 卡的编号/GAI 登记（需求 1）；S2 机制防的是未来
  worker 手工建卡再缺编号（需求 2）。两者互补：S2 的扫描器天然跳过 S1 已编号的 6 卡
  （幂等正例），S1 的数据修复也可先落（不等机制）。
- **R1 窗口是必做项**：168 张无编号历史卡若无窗口会一次性洪泛编号序列。窗口 + 每 tick 上限
  双保险；超出窗口的历史缺口记日志留给 OC（fail-open，不阻断主流程）。
- **编号格式对齐**：全角括号 `（DPL-029）` 追加在标题尾部（t_740b5ab3 样本）；同链同号
  （建卡铁律 v4 同编号连续步骤 task_links 成链）→ 链 1/链 2 各 1 个号，子卡不单独耗号。
- **防撞号先例**：memctl next-seq 读 GAI max+1 可能滞后 kanban（DPL 盲区教训 08-14）→
  S1/S2 分配前都先 SQL 实测 kanban 标题 max，取 max(kanban, GAI)+1。
- **本评估卡不写代码**；autopilot 读取 [SUB-SPLIT] comment 后建 3 张 [DEV-SUB-*] 卡
  （parents 链按 serial 挂接）。
- 评估期间实测基线：test_cmd_channel.sh PASS=387 FAIL=0（含 T15-T18；源卡验收 4 写 386
  为 T15-T18 前快照，S3 回归以 387 为准）。
- 每张子卡完成后推飞书（send_claim_feishu.py，SOUL 5.1 硬性要求）。
