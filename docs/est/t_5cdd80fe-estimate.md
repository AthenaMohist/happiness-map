# 评估报告 — [MERGE] DPL-087 claim 前缀容差修复链 → main — 消除 code-not-in-main 续报

> 评估人：寇豆码（game-engine） | 日期：2026-08-20 | 评估卡：t_est_5cdd80fe | 源卡：t_5cdd80fe
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12）+ DPL-018 校准注入
> 源卡链：oc_wake_check [code-not-in-main] 命中 t_a0ed83a9 → OC 核对落地链路 → **本评估** → MERGE 卡 t_5cdd80fe 执行
> 有效轮折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）
> 校准注入: 累计偏差 +1.45 → K=2.45（clamp 0.5-3.0）；同型先例 t_1f937fcb（单文件落地 + 三套回归）基准 17-25 → 校准 42-61

## 1. 结论（TL;DR）

**拆 2 张串行子卡（校准后每张 20-29 / 22-34 轮，全部落在 42 有效轮预算内）。**

任务本质：把 DPL-087 修复链的成果从 worktree 分支合并进 main——SUB-1 机制
（wt/t_a0ed83a9@3504b79，4 文件 +168/-16）+ SUB-2 测试回归（wt/t_1c7cfb3d，
堆叠在 SUB-1 之上，追加 T12 用例组 +194）。合并后跑 4 套全量回归
（635 断言：115+398+28+94），消除 .pipeline/wip/t_a0ed83a9.md 持续触发的
code-not-in-main 续报。

**评估期间实测确认（非假设）：**
- wt/t_a0ed83a9 与 wt/t_1c7cfb3d 的 merge-base 均为 **b5e37da = main 当前 HEAD**
  → 两分支都是 main 的干净后代，**无假删除风险，无需逐文件 checkout，直接 merge --no-ff 即可**。
- wt/t_1c7cfb3d 是堆叠链（3504b79 ∈ wt/t_1c7cfb3d，`merge-base --is-ancestor` 实测 YES）
  → 先合并 SUB-1 再合并 SUB-2，第二次 merge 实际只剩 2 个 commit（T12 用例 + wip 笔记）。
- 两分支 diff main 的完整文件清单：SUB-1 = 4 文件（constants.py/discover.py/cmd_chain.py/
  .pipeline/wip/t_a0ed83a9.md）；SUB-2 = 6 文件（追加 test_va_backfill.sh +194 +
  .pipeline/wip/t_1c7cfb3d.md）。**gai/manifest/archive 零混入（实测 grep 空）。**
- main 四套回归套件均在：test_va_backfill.sh（91+T12=115 断言）、test_cmd_channel.sh（398）、
  test_watchdog_unify.sh（28）、test_wip_progress_check.sh（94）→ 合计 635 断言。
- 部署验证（DPL-048）：目标为 pipeline/ 代码 + 测试脚本，**repo import 路径，合并 main 即生效，
  无 cron 直调脚本改动 → 无需 must-sync**（与 SUB-1 claim 判定一致）。

## 2. 工作量评估（实测结论，非假设）

改动面：6 个文件（4 修改 + 2 新增 wip 笔记），2 次 merge commit（--no-ff），无逻辑改动。

| 维度 | 评估 | 依据 |
|------|------|------|
| ① 合并 + 完整性验证 | 领卡 orient + 读源卡 + 确认 parents done（t_a0ed83a9 ✅ done + t_1c7cfb3d ✅ done）**1-2 轮**；备份分支（backup/main-before-dpl087-<sha>，先例 backup/main-before-* 存在）**1 轮**；merge --no-ff wt/t_a0ed83a9 **1-2 轮**；merge --no-ff wt/t_1c7cfb3d（堆叠链，无冲突预期）**1-2 轮**；ls-tree 验证 4 文件命中 + 保护文件零改动 + gai/manifest/archive 零混入 **2 轮**；claim(changed_files) + 飞书 + complete **2 轮** → **基准 8-12** | merge-base 已实测 = main tip，无假删除/夹具风险；两分支 diff 清单已实测仅 6 文件；main 四套件已实测在库 |
| ② 四套全量回归 + 验收 | 领卡 orient + 确认 main 合并后状态 **1-2 轮**；test_va_backfill.sh 115 断言（含 T12，长耗 fixture）**2-3 轮**；test_cmd_channel.sh 398 断言（最大套件，长耗）**3-4 轮**；test_watchdog_unify.sh 28 断言 **1-2 轮**；test_wip_progress_check.sh 94 断言（长耗）**2-3 轮**；失败排查缓冲（若合并污染回归）**0-3 轮**；验收核对（4 命中 + 零污染 + 四套计数）**2 轮**；claim(changed_files) + 飞书 + complete **2 轮** → **基准 9-14** | 断言计数来自验收标准（115/398/28/94=635）；SUB-1/SUB-2 分支内已各自全绿（claim 记录），合并后回归应为纯验证性质；test_cmd_channel 398 为主耗时（DPL-030 S2 实证回归占大头） |

**基准轮数（未校准，合计）：17-26 轮（中位 ~21）。**
**DPL-018 校准：17-26 × K=2.45 → 校准后 42-64 轮**（单卡 100-152% 预算 → 必须拆卡）。

## 3. 复杂度与风险

| # | 风险 | 评级 | 说明与缓解 |
|---|------|:---:|------|
| R1 | 合并污染 / 冲突 | 低 | 两分支 merge-base = main tip（b5e37da），干净后代无冲突预期。缓解：合并前备份分支；合并后 `git diff main^..main --stat` 核对仅 6 文件。 |
| R2 | 保护文件零改动（验收核心） | 中 | 验收要求保护文件零改动 + gai/manifest/archive 零混入。缓解：SUB-1 显式验证 `git ls-tree -r main` 命中 4 文件（constants.py/discover.py/cmd_chain.py/.pipeline/wip/t_a0ed83a9.md）+ diff 清单核对；两分支污染已实测为零。 |
| R3 | 回归失败（若合并污染） | 中 | 四套全量回归是主耗时（635 断言）。缓解：SUB-1 先做合并 diff 无污染验证再提交 claim；SUB-2 跑回归前确认 main 状态；失败排查缓冲 0-3 轮。 |
| R4 | worktree 规范（DPL-026/027 教训） | 中 | 合并操作必须在自己 worktree（wt/t_est_5cdd80fe 或 SUB 卡 worktree）进行，禁止直接改 main 工作树；提交后走 merge 卡/显式 merge 回 main。 |
| R5 | 回归套件耗时（test_cmd_channel 398 最大） | 中 | 398 断言套件含 fixture 构建，实测单套可能 2-4 分钟。缓解：后台跑 + 长超时（300s+）；心跳保活；SUB-2 内四套串行跑，每套独立核对计数。 |
| R6 | claim 格式（DPL-060） | 中低 | 验收要求 claim 必须带 changed_files 段。缓解：两张子卡 claim 均列出 6 个文件路径；SUB-1 报合并落地，SUB-2 报回归计数+验收结论。 |
| R7 | 堆叠链二次 merge 顺序 | 低 | SUB-2 已含 SUB-1 commit（3504b79 ∈ wt/t_1c7cfb3d 实测）。缓解：先 merge SUB-1 再 merge SUB-2，避免一次 merge 携带重复内容；或直接 merge SUB-2 一次到位（先例 t_143376eb 堆叠链合并）。 |
| R8 | 评估卡自身（本卡）超时 | 低 | 只读码+估轮，不写功能代码，60 轮预算充裕（当前 ~10 轮内完成）。 |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 17-26 轮（中位 ~21） |
| DPL-018 校准后 | 42-64 轮（×K=2.45）**> 20 轮阈值 → 必须拆卡** |
| 交付物数 | 2 个阶段（合并落地 / 回归验收）≥ 2 → 拆 2 卡合理 |
| 单卡方案复算 | base 17-26 → 校准 42-64 = 单卡 100-152% 预算 ❌ 且同型先例 t_1f937fcb 已拆 2 卡 → 单卡不可行 |
| 本评估 2 卡方案 | SUB-1 基准 8-12 → 校准 20-29（29/42 = 69%）；SUB-2 基准 9-14 → 校准 22-34（34/42 = 81%）✅ |
| 依赖方向 | SUB-2 必须在 main 合并完成后跑回归 → 串行：SUB-1 合并进 main 后 SUB-2 才可测 |
| 并行收益 | 低——SUB-2 严格依赖 SUB-1 的 main 状态；合并与回归无法并行（回归测的是合并后 main） |
| 兜底 | SUB-1 若超预算：合并动作可切块（contingency SUB-1b：先合并 SUB-1 分支 4 文件，再合并 SUB-2 分支 2 文件）；SUB-2 若超预算：四套回归按 test_va_backfill → test_watchdog_unify → test_wip_progress_check → test_cmd_channel 顺序，前三套（237 断言）优先，test_cmd_channel 398 最后跑 |

**决策：拆 2 张串行子卡（[SUB-SPLIT] 2 serial）。**
量级参照：t_1f937fcb（DPL-087 评估产物落地 main，单文件落地 + 三套回归，拆 2 serial
20-27/22-34 已完成）、t_66e31a89（MEM-009 12 文件落地 + 三套回归，拆 2 serial 25-34/22-34）。
本任务与 t_1f937fcb 同型但多一套 398 断言回归（test_cmd_channel），合并面无假删除
（优于 t_66e31a89 需逐文件 checkout），2 卡粒度与「落地/验证」天然分段对齐。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 2 serial
1. [DEV-SUB-1] DPL-087 SUB-1 + SUB-2 分支合并 main + 完整性验证（消除 code-not-in-main）：
   在自己 worktree 执行（禁止直接改 main 工作树）：
   git branch backup/main-before-dpl087-<当前main sha>   # 合并前备份（先例 backup/main-before-*）
   git merge --no-ff wt/t_a0ed83a9   # SUB-1 机制分支（3504b79，4 文件）
   git merge --no-ff wt/t_1c7cfb3d   # SUB-2 堆叠分支（追加 test_va_backfill.sh + wip 笔记）
   或一次 merge --no-ff wt/t_1c7cfb3d（含 SUB-1 commit，先例 t_143376eb 堆叠链合并）
   ⚠️ 合并后验收硬约束：
   git ls-tree -r main --name-only 命中 4 文件：pipeline/constants.py / pipeline/discover.py /
      pipeline/cmd_chain.py / .pipeline/wip/t_a0ed83a9.md（+ SUB-2 的 t_1c7cfb3d.md）
   git diff main^..main --stat 核对仅 6 文件，保护文件零改动；
   grep gai/manifest/archive = 零混入。
   commit（message: merge(dpl087): claim 前缀容差修复链落地 main — SUB-1 + SUB-2 堆叠链）；
   claim 带 changed_files 段（6 文件全列）。预计 20-29 轮（校准后）
2. [DEV-SUB-2] DPL-087 合并后四套全量回归 + 验收（main 上执行）：
   四套全量回归：scripts/test_va_backfill.sh（91+T12=115）+ scripts/test_cmd_channel.sh（398）
   + scripts/test_watchdog_unify.sh（28）+ scripts/test_wip_progress_check.sh（94）= 635 断言全绿
   （长耗套件后台跑 + 心跳保活；test_cmd_channel 398 最大，预留 300s+ 超时）；
   验收核对：4 文件命中 + 保护文件零改动 + gai/manifest/archive 零混入 + 四套计数核对；
   失败排查（若回归失败，定位合并污染或环境问题，回退/修复后重跑）；
   claim 带 changed_files 段（本次为验证性质，列出核对结果与四套计数）。预计 22-34 轮（校准后）
```

- SPLIT: yes（count=2，校准后 42-64 轮远超 20 阈值；单卡 100-152% 预算不可行）
- MODE: serial（SUB-2 必须在 main 合并完成后跑回归，严格依赖）
- ROUNDS_EST（校准后）: 42-64（基准 17-26 × K=2.45；分卡后每张 20-29 / 22-34）
- FILES: 6 个（pipeline 3 修改 + test_va_backfill.sh 修改 + wip 2 新增）——无 gai/manifest/archive
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 2 张子卡挂源卡 t_5cdd80fe）
- TESTS: SUB-1 ls-tree/diff 验证 4 项；SUB-2 四套全量回归 115+398+28+94 = 635 断言
- RISK: R1 合并污染（低，merge-base=main tip）；R2 保护文件零改动；R3 回归失败（635 断言主耗时）；
  R4 worktree 规范；R5 test_cmd_channel 398 耗时；R6 claim changed_files 段（DPL-060）；
  R7 堆叠链 merge 顺序；R8 评估卡自身超时（低）
- ACTION: build_two_dev_cards（assignee=game-engine，parents=[t_5cdd80fe]，serial）
- DEPLOY: repo import 路径，合并 main 即生效，无需 DPL-048 must-sync

## 6. 备注

1. **两分支均为 main 干净后代是核心利好**：merge-base b5e37da = main HEAD，与 t_66e31a89
   （MEM-009 旧基线假删除）不同，**无需逐文件 checkout，直接 merge --no-ff**。但仍须
   合并后 diff 核对保护文件零改动 + gai/manifest/archive 零混入（验收硬约束）。
2. **堆叠链合并方式**（先例 t_143376eb）：wt/t_1c7cfb3d 已含 SUB-1 commit（3504b79 实测
   ancestor）。可先 merge SUB-1 再 merge SUB-2（两次 --no-ff，第二次只带 2 commit），
   或一次 merge SUB-2 到位。推荐两次 merge 以便 claim 分开描述。
3. **部署验证规则（DPL-048）不适用**：目标为 pipeline/ 代码（repo import 路径）+ 测试脚本，
   非 cron 前置脚本（jobs.json 直调或绝对路径引用），合并 main 即生效，无 must-sync。
4. **回归套件耗时是主风险**：test_va_backfill.sh 115 断言 + test_cmd_channel.sh 398 断言 +
   test_wip_progress_check.sh 94 断言均含 fixture 构建，实测单套可能 1-4 分钟。SUB-2 内
   建议后台跑 + 长超时 + 心跳保活，避免前棒教训（DPL-026/027 抢 main 工作树 + 60 轮耗尽）。
5. **本评估卡不写功能代码**；产出即本报告 + [SUB-SPLIT] comment，autopilot 读取后建 2 张
   [DEV-SUB] 卡执行。源卡 t_5cdd80fe 作为容器由 autopilot 关闭。
6. **勿动 t_569d4425（源卡容器，autopilot 关闭）与 t_1f937fcb（评估产物 MERGE 容器，
   DPL-088/089 独立链）**——本卡只评估 DPL-087 修复链合并，不涉及其他链。
