# 评估报告 — DPL-018 MERGE 冲突 — test_cmd_channel.sh 230 行冲突块 + 重试链卡（DPL-027）

> 评估人：寇豆码（game-engine） | 日期：2026-08-13 | 评估卡：t_est_99e71001
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）
> 源卡：t_99e71001（[FIX] DPL-018 MERGE 冲突 — test_cmd_channel.sh 230 行冲突块 + 重试链卡，DPL-027）
> 代码基线：main @ eaecaf4（评估时刻，autopilot 仍在合入，基线可能继续前移）

## 1. 结论（TL;DR）

**不拆（[SUB-SPLIT] 1）——单卡预计 12-18 轮（中位 15）≤ 20 轮阈值，单会话可完成。**

但**源卡低估了冲突数量**：实测不止 1 个冲突块，而是 **2 个**——S1（wt/t_a7b7c08c）merge main 冲突块 230 行（L1831-2060），S2（wt/t_d97cb2a0）merge main 冲突块 **452 行（L1833-2284）**。源卡要求 5 已提示"未含 623bfa7 则继续 merge S2"，但没写明 S2 也会冲突。修复 worker 必须两个分支都预解，否则 merge 卡在 S2 上二次失败（见 R2）。

## 2. 工作量评估（读码+实测结论，非假设）

### 2.1 现状基线（实测复现）

- 在干净 worktree 复现 S1 merge（`git merge main` @ wt/t_a7b7c08c = ba273ef）：**1 个冲突块** `scripts/test_cmd_channel.sh` L1831-2060（230 行），其余 7 个文件（cmd_chain.py/discover.py/constants.py/notify_check.py/test_notify_check.py 等）全部 auto-merge 干净。
- 复现 S2 merge（`git merge wt/t_d97cb2a0` @ main = eaecaf4）：**1 个冲突块** L1833-2284（452 行），同样只有 test_cmd_channel.sh 冲突。
- **测试编号冲突（关键）**：冲突块内 HEAD 侧（DPL-018 S1）测试编号为 T59-T63，main 侧（DPL-019 50轮存档）也是 T59-T62——**两侧共用 T59/T60/T61/T62**，断言编号重复（T59a、T60a…两侧各一份但断言内容不同）。验收要求"消除重复/矛盾断言" → **必须重编号一侧**（建议 S1 的 T59-T63 → T70-T74，避开 main 的 T59-T62 与 S2 的 T64-T69）。
- main 上 test_cmd_channel.sh 现有测试编号：T1-T58 + T59-T62（DPL-019）。T84-T95 在 test_notify_check.py（不同文件，无冲突）。T63、T70-T83 在 test_cmd_channel.sh 中空闲。
- merge 机制：`exec_chain_merge`（pipeline/cmd_chain.py L1256）在 main 上 `git merge --no-ff` 逐分支合入（branch_ids 按子卡序 S1→S2）；任一分支冲突 → 整卡 failed class='conflict' → blocked 终态。**所以 S1 修好后 unblock，autopilot 重试会先合 S1（干净）再合 S2——S2 若不预解会再次冲突、再次 blocked。**
- unblock 通道：`hermes kanban unblock` CLI 存在（评估环境无 kanban_unblock 工具，用 CLI 或走"直接完成 merge 卡"路径）。
- 全量回归 `bash scripts/test_cmd_channel.sh`：main 当前断言 308 条（assert_eq 204 + assert_contains 92 + assert_not 12），DPL-025 基线全量 341 PASS（含跨文件）。单次运行估计 5-15 min（集成级：真实建链 + git worktree + sqlite）。

### 2.2 改动清单

| # | 项 | 内容 | 预估轮数 |
|---|----|------|:---:|
| ① | 复现 + 定位 | 两个 worktree 各自 `git merge main` 复现冲突；确认冲突块范围与编号冲突；核对 main 是否已含 623bfa7（实测**未含**） | 1 |
| ② | S1 冲突解（核心） | 在 wt/t_a7b7c08c 预合 main，解 230 行冲突块：保留 main 侧 DPL-019 T59-T62 + DPL-018 S1 T59-T63 全套断言；**S1 侧重编号 T59-T63 → T70-T74**（含 banner、echo 头、~30 条 assert 标签）；消除重复编号/矛盾断言 | 2-3 |
| ③ | S2 冲突解（源卡未明示） | 在 wt/t_d97cb2a0 预合 main，解 452 行冲突块：保留 main 侧（含已解 S1 的 T59-T62+T70-T74）+ S2 侧 T64-T69 全套断言（编号本就唯一，无需重编号）；消除重复 | 2-3 |
| ④ | 分支提交 + push | 两个 worktree 各自 `git add + commit + push`（wt/t_a7b7c08c、wt/t_d97cb2a0） | 1 |
| ⑤ | 全量回归 ×2 | 每个分支解完冲突后跑一次 `bash scripts/test_cmd_channel.sh`，确认 ≥341 PASS + DPL-018 新断言（T70-T74/T64-T69）通过；有 fallout 则修 | 2-3 |
| ⑥ | 重试 merge 链 | unblock t_2364aa9a（CLI `hermes kanban unblock`）让 autopilot 重试，或直接完成 merge 卡；确认 S1、S2 均干净合入 main | 1-2 |
| ⑦ | main 上终验 | main 合入后全量回归一次（≥341 PASS + DPL-018 断言）；确认 623bfa7 已在 main；确认链后续（qa-post/va-post/close）正常推进 | 2-3 |
| ⑧ | 收尾 | commit + [PRODUCES] + 飞书推送 | 1 |

**预计总轮数：12-18 轮（中位 15）** ≤ 20 轮阈值 → **不拆**。

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| R1 测试编号冲突 | **中** | 两侧共用 T59-T62，必须重编号一侧。建议 S1 → T70-T74（避开 main T59-T62、S2 T64-T69）。若重编号不当（撞 T64-T69 或漏改 assert 标签），回归会误报/漏报。这是本卡唯一需要"设计判断"的点 |
| R2 **S2 二次冲突（源卡低估）** | **高** | 源卡只描述 1 个 230 行冲突块；实测 S2 merge 有第 2 个 452 行冲突块。若只解 S1 就 unblock，autopilot 合完 S1 会在 S2 上再次 conflict → merge 卡再次 blocked → 需要第二个修复轮。**修复 worker 必须一次把 S1、S2 两个分支都预解** |
| R3 main 持续前移 | **中** | 评估期间 main 从 023b80a 前移到 eaecaf4（autopilot 活跃）。预解冲突后到 unblock 之间若 main 再合入新提交，S2 分支可能再冲突。缓解：预解尽量贴近 unblock 时机；重试失败就再预解一次 |
| R4 全量回归耗时 | 低-中 | 每次 5-15 min，至少 3 次（S1/S2/main 终验），主要是墙钟时间；断言失败定位另计轮数 |
| R5 merge 卡归属 | 低 | t_2364aa9a assignee=autopilot；"直接完成"路径需确认 game-engine 可 complete 他 profile 的卡（工具层 task_id 参数支持），否则走 unblock 让 autopilot 重试 |
| R6 冲突区后续开发 | 低 | test_cmd_channel.sh 冲突区是测试文件末尾追加区，后续 DPL-026+ 若再在同区加测试，需沿用本卡编号约定（T63 起按序） |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 预计轮数 | 12-18 轮（中位 15）≤ 20 轮阈值 → **不拆** |
| 模块依赖 | 单文件冲突（test_cmd_channel.sh）+ 2 个 worktree 的 git 操作，无跨模块新代码 |
| 拆卡收益 | 无——两个冲突块都在同一文件同一区域，拆开反而要重复建 merge 上下文；S1/S2 预解是强串行（S2 依赖 main 已含 S1） |
| 兜底 | 若 S2 冲突块实际内容比预想复杂（如断言与 DPL-019 语义冲突需改代码），或 main 前移导致第三次冲突，可按「S1 预解 / S2 预解 / 链重试+终验」拆 2-3 张串行子卡——按现实测不需要 |

**决策：不拆（[SUB-SPLIT] 1），单卡可完成。** 量级与同系列 t_est_871e5b21（9-13 轮 → 不拆）相近，但因双冲突块 + 链重试，中位略高（15 vs 11）。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 1
1. [DEV-DEV] DPL-027 MERGE 冲突修复 — test_cmd_channel.sh 双冲突块预解 + 重试链卡
   （game-engine，单卡 12-18 轮）
   a. 复现：在 /workspace/devPPL/.worktrees/t_a7b7c08c（wt/t_a7b7c08c @ ba273ef）与
      t_d97cb2a0（wt/t_d97cb2a0 @ 623bfa7）各自 `git merge main` 复现冲突
      （S1: L1831-2060 共 230 行；S2: L1833-2284 共 452 行，均只有 test_cmd_channel.sh 冲突）
   b. S1 解冲突：保留 main 侧 DPL-019 T59-T62（50轮存档）+ DPL-018 S1 T59-T63（数据平面）
      全套断言；**S1 侧重编号 T59-T63 → T70-T74**（banner/echo/assert 标签全改），消除重复编号
   c. S2 解冲突：保留 main 侧（含已解 S1）+ S2 侧 T64-T69（注入平面，编号唯一无需重编号）
   d. 两个分支各自 commit + push（wt/t_a7b7c08c、wt/t_d97cb2a0）
   e. 分支回归：两个 worktree 各跑一次 `bash scripts/test_cmd_channel.sh`，≥341 PASS
      且 T70-T74/T64-T69 断言通过；有 fallout 就地修
   f. 重试链：`hermes kanban unblock t_2364aa9a` 让 autopilot 重试 merge；
      若 unblock 不可用则直接完成 merge 卡（需确认对 autopilot 卡可 complete）
   g. main 终验：合入后全量回归 ≥341 PASS + DPL-018 断言；确认 623bfa7 已在 main
      （git log main --oneline | grep 623bfa7）；确认链后续 qa-post/va-post/close 推进
   h. commit + [PRODUCES] + 飞书推送
   明确不做：S2 分支上重编号（T64-T69 唯一）；改任何业务代码（VA 已 review_pass，代码不动）；
   重排测试顺序；main 上直接解冲突（应在分支预解，保持 merge 干净）
   预计 12-18 轮。依赖：t_2364aa9a blocked（kind=capability）待 unblock；main 前移需重预解兜底
```

- SPLIT: no（count=1）
- MODE: single（不拆）
- ROUNDS_EST: 15（12-18）
- FILES: scripts/test_cmd_channel.sh（冲突解，含重编号）；git 操作在 wt/t_a7b7c08c、wt/t_d97cb2a0
- STATUS: not_started（评估卡 t_est_99e71001 完成 → t_99e71001 从 todo 放行）
- TESTS: 全量 test_cmd_channel.sh ≥341 PASS（DPL-025 基线）+ DPL-018 新断言（S1 重编号 T70-T74、S2 T64-T69）
- RISK: R2 最高（S2 二次冲突，源卡未明示，必须双分支预解）；R3 main 前移可能需二次预解
- ACTION: build_dev_card（assignee=game-engine，单卡）

## 6. 备注

- 关键决策点 D1：重编号方向。main 侧 DPL-019 T59-T62 已合入 main（编号固化），所以**动 S1 侧**（T59-T63 → T70-T74）而非 main 侧。备选：S1 → T96-T100（更靠后，与 T84-T95 的 notify 文件编号保持全局连续感）；推荐 T70-T74 使 DPL-018 两个子卡的测试相邻（T64-T69 S2 + T70-T74 S1）。
- 本卡不写业务代码：DPL-018 全部 6 文件改动已由 VA（t_9b6d345b）review_pass，冲突解只动测试文件编号与区块合并。
- S2 的 623bfa7 实测未在 main（`git branch --contains 623bfa7` 只有 wt/t_d97cb2a0 与 qa-* 探针分支）→ merge S2 必须做，且会冲突（R2）。
- 验收标准逐条可测：① 冲突解 commit 在 wt/t_a7b7c08c（④）；② 全量 ≥341 PASS 含 DPL-018 新断言（⑤⑦）；③ t_2364aa9a 最终 done（⑥）；④ 关闭后链推进 qa-post/va-post/close（⑦）。
- 评估过程中复现用的临时 worktree（/tmp/est-dpl027-*）已清理；不污染 /workspace/devPPL 主树。
