# 评估报告 — [MERGE] 3 张 est 卡评估产物落地 main — t_est_15e790bc / t_e0635404 / t_96fab6aa 报告（消除 code-not-in-main 续报）

> 评估人：寇豆码（game-engine） | 日期：2026-08-30 | 评估卡：t_est_d683fdef | 源卡：t_d683fdef
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12）+ DPL-018 校准注入
> 源卡链：oc_wake_check [code-not-in-main] 命中 3 张 est 卡（t_est_15e790bc / t_e0635404 / t_96fab6aa）→ OC 核对落地链路（已核实 2026-08-30）→ MERGE 卡 t_d683fdef（本评估的源卡）→ 评估卡（本卡）→ [SUB-SPLIT] 子卡执行
> 有效轮折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）
> 校准注入: 累计偏差 +1.45 → K=2.45（clamp 0.5-3.0）；最近评估（t_31f8d1a9 / t_96fab6aa 同日）同用 K=2.45

## 1. 结论（TL;DR）

**拆 2 张串行子卡（校准后每张 22-34 / 22-34 轮，全部落在 42 有效轮预算内）。**

任务本质：把 3 张评估卡的产物——`docs/est/t_est_15e790bc-estimate.md`（11641B）、
`docs/est/t_e0635404-estimate.md`（14454B）、`.pipeline/wip/t_e0635404.md`（2059B）、
`docs/est/t_96fab6aa-estimate.md`（14771B）、`.pipeline/wip/t_96fab6aa.md`（2523B）——
从 3 个源 commit（b3bfc04 / bfc3369 / 80937b0）**逐文件 checkout** 落地 main，随后
三套全量回归 + 验收核对。纯文档搬运，无代码逻辑改动。与 DPL-085/086 同型（先例
t_5db95059：2 文件 + 同三套回归，拆 2 serial 22-34/22-37 已完成）；本任务 5 文件比
先例多 3 个，流程完全一致，仅逐文件 checkout 命令从 1 条变 3 条、验证项从 2 项变 5 项。

**评估期间实测确认（非假设）：**
- 3 个源 commit 均存在且 **NOT ancestor of main**（`git merge-base --is-ancestor`
  实测全 NO，main HEAD=66c1bb0）。
- 3 个源 commit 父提交均为 `de0dfc1`，**落后当前 main HEAD 4 个 commit**——与
  t_est_15e790bc 先例（父 == main HEAD）不同，但 5 个目标路径在 main **0 命中**已实测
  （`git cat-file -e main:<path>` 全 NO）→ 逐文件 checkout 到最新 main 上仍为纯新增，
  无假删除风险；merge --no-ff 的 branch diff 即 5 新增（无 D/M）。
- 5 文件尺寸实测与源卡表一致：11641B / 14454B / 2059B / 14771B / 2523B
  （`git cat-file -s`）；blob hash 与表一致（ls-tree 实测 ba5f53… / cba63d… /
  d10b79… / d793ea… / 49b056…）。
- main 三套回归套件均在：test_va_backfill.sh / test_watchdog_unify.sh /
  test_wip_progress_check.sh（断言数以执行时基线为准）。
- ⚠️ **本卡自身评估产物 `docs/est/t_d683fdef-estimate.md` 也将不在 main**——源卡注意
  条款已明示「若执行期间本卡链上新产生 docs/est/*.md 未在 main（如本卡自身评估卡
  产物），一并逐文件」→ SUB-1 落地时应一并纳入（合计 6 文件，第 6 个从
  wt/t_est_d683fdef 分支 checkout，见 §5 SUB-1 明细）。
- DPL-048 部署验证不适用：产物为 docs 文档，非 cron 前置脚本、非 must-sync 清单。

## 2. 工作量评估（实测结论，非假设）

改动面：**5 个新增文件**（纯新增，无修改/删除）+ 1 次 merge commit。无代码逻辑改动。

| 维度 | 评估 | 依据 |
|------|------|------|
| ① 文件落地 + 合并 main | 领卡 orient + 读源卡/评估卡 **1-2 轮**；worktree 准备（确认 workspace_kind、分支状态、5 个 blob 复核）**1 轮**；逐文件 checkout（3 条命令：b3bfc04 1 路径 / bfc3369 2 路径 / 80937b0 2 路径，另加本卡产物 1 路径）**1-2 轮**；staging 核对（仅 6 新增、保护文件 discover.py/oc_wake_check.sh/test_va_backfill.sh 零改动、gai/manifest/archive 零混入）**1-2 轮**；commit + merge --no-ff 进 main **1-2 轮**；验证（ls-tree 六命中 + blob hash == 源 commit×6 + merge diff 仅 6 新增）**2-3 轮**；claim(changed_files) + 飞书 + complete **2 轮** → **基准 9-14** | 5 文件路径已实测存在（blob 与源卡表一致）；3 源 commit 均存在且 NOT ancestor；保护文件核对为固定 3 项 grep；比先例 t_est_15e790bc（8-11）多 ~1-3 轮（5→6 文件、3+1 条 checkout 命令、验证项 5→6） |
| ② 回归 + 验收 | 领卡 orient + 确认 main 合并后状态 + **回归基线核对**（执行时 main 的三套计数，勿硬编码）**1-2 轮**；test_va_backfill.sh 全量（长耗，后台跑+心跳）**2-3 轮**；test_watchdog_unify.sh **1-2 轮**；test_wip_progress_check.sh（长耗）**2-3 轮**；失败排查缓冲 **0-2 轮**；验收核对（ls-tree 六命中 + blob×6 + merge diff 仅 6 新增 + 三套计数 vs 执行时基线）**2 轮**；claim + 飞书 + complete **2 轮** → **基准 9-14** | 与先例 t_est_15e790bc 完全同型（三套件断言计数来自验收标准，以执行时基准确认；纯 docs 落地预期零回归；DPL-030 S2 实证回归占大头） |

**基准轮数（未校准，合计）：18-28 轮（中位 ~23）。**
**DPL-018 校准：18-28 × K=2.45 → 校准后 44-69 轮**（单卡 105-164% 预算 → 必须拆卡）。

## 3. 复杂度与风险

| # | 风险 | 评级 | 说明与缓解 |
|---|------|:---:|------|
| R1 | main 并发推进 / 回归基线漂移 | 中 | 当前 worktree 有 4 个并行分支（wt/t_01a757e8 / t_60ca5f1b / t_93de9732 / t_fe41251e）在 running，main 可能继续前移；3 源 commit 父 de0dfc1 已落后 main 4 commit。缓解：SUB-1 merge 前刷新基线（最新 main 上重放单路径 checkout，blob 不变量校验取代 commit 祖先判断）；SUB-2 断言「≥ 执行时 main 计数全绿」。 |
| R2 | 整分支 merge 违规 | 低 | 3 源分支（wt/t_est_15e790bc / wt/t_e0635404 / wt/t_96fab6aa）均已删除，唯一路径就是逐文件 checkout——卡面要求与客观现实一致。缓解：只 `git checkout <src> -- <指定路径>`；禁止 `-- .` 全量。 |
| R3 | main 工作树并发污染 | 中 | main 工作树存在未跟踪噪音（.pipeline/gai/*.json 等）。缓解：SUB-1 在自己 worktree 执行；staging 显式单路径 add；`git diff --cached --stat` 逐项核对仅 6 新增。 |
| R4 | 回归套件长耗 | 中 | 三套全量断言量大，fixture 构建占大头（先例 t_61fcc7a8 实测 test_va_backfill 115 断言量级）。缓解：后台跑 + 长超时（300s+）+ 心跳保活；三套串行，每套独立核对计数。 |
| R5 | claim 格式（DPL-060） | 中低 | claim 必须带 changed_files 段。缓解：SUB-1 列 6 文件路径（5 源卡表 + 本卡产物）；SUB-2 为验证性质，列核对结果与三套计数。 |
| R6 | worktree 规范（DPL-026/027 教训） | 中 | 合并操作在子卡自己 worktree 分支进行，提交后 merge --no-ff 回 main；禁止直接改 main 工作树。 |
| R7 | 本卡产物落地遗漏 → code-not-in-main 三连报 | 中 | 若 SUB-1 只落地 5 文件、漏掉 `docs/est/t_d683fdef-estimate.md`，下次 oc_wake_check 又会命中本卡产物（正是 t_est_15e790bc 产物本次被纳入的同一模式）。缓解：SUB-1 卡面明确写第 6 文件及源 commit（wt/t_est_d683fdef 分支提交，blob 见 §5），claim 的 changed_files 必须 6 项齐全。 |
| R8 | 评估卡自身（本卡）超时 | 低 | 只读+估算，无功能代码，当前 ~12 轮内完成。 |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 18-28 轮（中位 ~23） |
| DPL-018 校准后 | 44-69 轮（×K=2.45）**> 20 轮阈值 → 必须拆卡** |
| 交付物数 | 2 个阶段（文件落地 / 回归验收）≥ 2 → 拆 2 卡合理 |
| 单卡方案复算 | base 18-28 → 校准 44-69 = 单卡 105-164% 预算 ❌ 且最近多卡 timed_out 前科 → 单卡不可行 |
| 本评估 2 卡方案 | SUB-1 基准 9-14 → 校准 22-34（34/42 = 81%）；SUB-2 基准 9-14 → 校准 22-34（34/42 = 81%）✅ |
| 依赖方向 | SUB-2 必须在 main 合并完成后跑回归 → 串行：SUB-1 合并进 main 后 SUB-2 才可测 |
| 并行收益 | 低——SUB-2 严格依赖 SUB-1 的 main 状态 |
| 兜底 | SUB-1 若超预算：6 文件落地失败极小概率，阻塞点只可能在 main 并发竞争 → 等待后重放；先落 5 源卡表文件、本卡产物可后补（blob 不变）。SUB-2 若超预算：三套按 test_va_backfill → test_watchdog_unify → test_wip_progress_check 顺序，前两套优先（覆盖核心）；失败排查缓冲已备 2 轮 |

**决策：拆 2 张串行子卡（[SUB-SPLIT] 2 serial）。**
量级参照：t_5db95059（DPL-085/086，2 文件 + 同三套回归，拆 2 serial 22-34/22-37
已完成）、t_1f937fcb（1 文件，拆 2 serial 20-27/22-34 已完成）、t_est_15e790bc（2 文件，
拆 2 serial 20-27/22-34，本次正是其产物的落地链）。本任务 5+1 文件与上述同型，2 卡
粒度与「落地/验证」天然分段对齐，无需拆 3 卡（回归阶段不随文件数线性增长）。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 2 serial
1. [DEV-SUB-1] t_d683fdef — 3 张 est 卡评估产物 6 文件落地 main
   （docs/est/t_est_15e790bc-estimate.md + docs/est/t_e0635404-estimate.md +
    .pipeline/wip/t_e0635404.md + docs/est/t_96fab6aa-estimate.md +
    .pipeline/wip/t_96fab6aa.md + 本卡评估产物 docs/est/t_d683fdef-estimate.md，
    逐文件 checkout，禁止整分支 merge）
   在自己 worktree（workspace_kind=worktree）执行：
   git checkout b3bfc04 -- docs/est/t_est_15e790bc-estimate.md
   git checkout bfc3369 -- docs/est/t_e0635404-estimate.md .pipeline/wip/t_e0635404.md
   git checkout 80937b0 -- docs/est/t_96fab6aa-estimate.md .pipeline/wip/t_96fab6aa.md
   git checkout <wt/t_est_d683fdef 最新 commit> -- docs/est/t_d683fdef-estimate.md
   （merge 前刷新基线：若 main 已前移，在最新 main 上重放上述单路径 checkout；
     第 6 文件源 commit 见评估卡 [PRODUCES] comment，blob 不变）
   staging 核对：git status + git diff --cached --stat 确认仅 6 新增文件，无 D/M，
   pipeline/discover.py / scripts/oc_wake_check.sh / scripts/test_va_backfill.sh 零改动，
   .pipeline/gai/ + manifest + archive 零混入；
   commit（message: [MERGE] 3 张 est 卡评估产物落地 main — t_est_15e790bc/t_e0635404/
   t_96fab6aa 报告（消除 code-not-in-main 续报））；
   merge --no-ff 进 main；验证：
   git ls-tree -r main -- <6 路径> → 六命中且 blob == 源（ba5f53…/cba63d…/d10b79…/
   d793ea…/49b056…/<本卡产物 blob>）；文件非空（11641B / 14454B / 2059B / 14771B /
   2523B / <本卡产物>B）；git show <merge> --stat 只含 6 新增（无 D/M）。
   claim 带 changed_files 段（6 文件全列，DPL-060）。预计 22-34 轮（校准后）
2. [DEV-SUB-2] t_d683fdef — 落地后回归 + 验收（main 上执行）
   ⚠️ 回归基线以执行时 main 为准（勿硬编码断言数）；
   三套全量回归：scripts/test_va_backfill.sh（≥执行时计数全绿）+ scripts/test_watchdog_unify.sh
   + scripts/test_wip_progress_check.sh（长耗后台跑 + 心跳保活）；
   验收核对：ls-tree 六命中 + blob×6 == 源 + 合并 diff 仅 6 新增且三保护文件零改动 +
   三套计数核对；
   失败排查（若回归失败，定位合并污染或环境问题，回退/修复后重跑）；
   claim 带 changed_files 段（验证性质，列出核对结果与三套计数）。预计 22-34 轮（校准后）
```

- SPLIT: yes（count=2，校准后 44-69 轮超 20 阈值；单卡 105-164% 预算不可行）
- MODE: serial（SUB-2 必须在 main 合并完成后跑回归，严格依赖）
- ROUNDS_EST（校准后）: 44-69（基准 18-28 × K=2.45；分卡后每张 22-34 / 22-34）
- FILES: 5+1 个新增（docs/est/t_est_15e790bc-estimate.md 11641B / blob ba5f53…；
  docs/est/t_e0635404-estimate.md 14454B / blob cba63d…；.pipeline/wip/t_e0635404.md
  2059B / blob d10b79…；docs/est/t_96fab6aa-estimate.md 14771B / blob d793ea…；
  .pipeline/wip/t_96fab6aa.md 2523B / blob 49b056…；docs/est/t_d683fdef-estimate.md
  本卡产物 / blob 见 [PRODUCES]）——纯新增，无修改
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 2 张子卡挂源卡 t_d683fdef）
- TESTS: SUB-1 ls-tree/blob/diff 验证 3 项（6 文件）；SUB-2 三套全量回归
  （test_va_backfill / test_watchdog_unify / test_wip_progress_check，计数以执行时基线）
- RISK: R1 main 并发推进+基线漂移（4 个并行 worktree running）；R2 整分支 merge
  违规（低，分支已删天然只能逐文件）；R3 main 工作树噪音混入；R4 回归长耗；
  R5 claim changed_files（DPL-060）；R6 worktree 规范；R7 本卡产物落地遗漏
  →code-not-in-main 三连报（SUB-1 必须 6 文件齐全）
- ACTION: build_two_dev_cards（assignee=game-engine，parents=[t_d683fdef]，serial，
  workspace_kind=worktree）

## 6. 备注

1. **部署验证（DPL-048）不适用**：产物为 docs 文档，非 jobs.json 直调脚本、非绝对路径引用、
   非 must-sync 清单成员。
2. **本评估卡自身产物** docs/est/t_d683fdef-estimate.md 在 wt/t_est_d683fdef 分支，
   源卡注意条款已明示「若执行期间本卡链上新产生 docs/est/*.md 未在 main（如本卡自身
   评估卡产物），一并逐文件」→ SUB-1 落地时一并纳入（第 6 文件），避免重演
   t_est_15e790bc 产物本次才被追回的同一模式。
3. **源 commit 结构**：3 源 commit（b3bfc04 / bfc3369 / 80937b0）父提交均为 de0dfc1，
   落后当前 main（66c1bb0）4 个 commit；但 5 个目标路径在 main 0 命中 → 逐文件
   checkout 到最新 main 上仍为纯新增，无假删除风险；逐文件 checkout 是卡面合规要求
   （分支已删，也无整分支 merge 可能）。
4. **与开发链无冲突**：当前 4 个并行 worktree（t_01a757e8 / t_60ca5f1b / t_93de9732 /
   t_fe41251e）在 running，但本卡只落地 docs 文档，不触碰 discover.py / oc_wake_check.sh /
   test_va_backfill.sh——预期零冲突；回归计数仍以执行时 main 为准。
5. 本评估卡不写功能代码；产出即本报告 + [SUB-SPLIT] comment，autopilot 读取后建 2 张
   [DEV-SUB] 卡执行。
