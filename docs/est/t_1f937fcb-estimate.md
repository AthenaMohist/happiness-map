# 评估报告 — [MERGE] t_est_569d4425 评估产物落地 main — 消除 code-not-in-main 续报

> 评估人：寇豆码（game-engine） | 日期：2026-08-20 | 评估卡：t_est_1f937fcb | 源卡：t_1f937fcb
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12）+ DPL-018 校准注入
> 源卡链：oc_wake_check [code-not-in-main] 命中 t_est_569d4425 → OC 核对落地链路 → 评估卡（本卡）→ MERGE 卡 t_1f937fcb 执行
> 有效轮折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）
> 校准注入: 累计偏差 +1.45 → K=2.45（clamp 0.5-3.0）；最近 5 条子卡偏差全部 timed_out（估 18-33 轮全部撞 60 上限）

## 1. 结论（TL;DR）

**拆 2 张串行子卡（校准后每张 20-27 / 22-34 轮，全部落在 42 有效轮预算内）。**

任务本质：把 DPL-087 评估报告 `docs/est/t_569d4425-estimate.md`（152 行 / 14632B，blob
`37b081d`）从分支 `wt/t_est_569d4425` **逐文件 checkout** 落地 main，随后三套全量回归 +
验收核对。纯文档搬运，无代码逻辑改动。

**评估期间实测确认（非假设）：**
- 源分支 `wt/t_est_569d4425` **恰好基于当前 main HEAD**（merge-base = b5e37da），
  仅 1 个提交（09a26fb），`git diff main..wt/t_est_569d4425` 仅 1 行新增
  （`A docs/est/t_569d4425-estimate.md`）→ **结构性无假删除风险**（对比：DPL-085 的
  wt/t_est_66e31a89 基于旧 main 含 -1951 假删除）。卡面仍要求逐文件 checkout——保持执行
  （成本 ~0，且防分支未来追加提交被意外带入）。
- 目标文件在 main 0 命中（git ls-tree -r main 实测），在源分支 blob `37b081d` 与评估卡
  claim 一致。
- main 三套回归套件均在：test_va_backfill.sh（91 断言）/ test_watchdog_unify.sh（28）/
  test_wip_progress_check.sh（94）。
- ⚠️ **回归基线是移动目标**：DPL-087 修复链卡 t_569d4425（priority 80）正在 running，
  其 SUB-2 将给 test_va_backfill.sh 增 T11 用例组（91 → 91+N）且 discover.py/cmd_chain.py
  改动将推进 main HEAD。源卡已裁定「修复链路优先」——落地子卡若与之并发，先让修复链路。
- DPL-048 部署验证不适用：产物为 docs 文档，非 cron 前置脚本、非 must-sync 清单。

## 2. 工作量评估（实测结论，非假设）

改动面：**1 个新增文件**（纯新增，无修改/删除）+ 1 次 merge commit。无代码逻辑改动。

| 维度 | 评估 | 依据 |
|------|------|------|
| ① SUB-1 文件落地 + 合并 main | 领卡 orient + 读源卡/评估卡 **1-2 轮**；worktree 准备（确认 workspace_kind、分支状态、blob `37b081d` 复核）**1 轮**；逐文件 checkout（1 条命令）**1 轮**；staging 核对（仅 1 新增、保护文件 discover.py/oc_wake_check.sh/test_va_backfill.sh 零改动、gai/manifest 零混入）**1 轮**；commit + merge --no-ff 进 main（若 main 已被 DPL-087 推进，对最新 main 重放 checkout，blob 不变量校验）**1-2 轮**；验证（ls-tree 命中 + blob hash == 37b081d + merge diff 仅 1 新增）**1-2 轮**；claim(changed_files) + 飞书 + complete **2 轮** → **基准 8-11** | 1 文件路径已实测存在（ls-tree blob 37b081d）；分支 diff 仅 1 新增已实测；保护文件核对为固定 3 项 grep |
| ② SUB-2 回归 + 验收 | 领卡 orient + 确认 main 合并后状态 + **回归基线核对**（执行时 main 的 va_backfill 计数；DPL-087 T11 落地后 >91，勿硬编码 91）**1-2 轮**；test_va_backfill.sh 全量（91 或 91+T11，长耗，后台跑+心跳）**2-3 轮**；test_watchdog_unify.sh 28 断言 **1-2 轮**；test_wip_progress_check.sh 94 断言（长耗）**2-3 轮**；失败排查缓冲 **0-2 轮**；验收核对（ls-tree + blob + merge diff 仅 1 新增 + 三套计数 vs 执行时基线）**2 轮**；claim + 飞书 + complete **2 轮** → **基准 9-14** | 三套件断言计数来自验收标准（91/28/94）；纯 docs 落地预期零回归；DPL-030 S2 实证回归占大头；基线漂移核对为本次新增 1 轮开销 |

**基准轮数（未校准，合计）：17-25 轮（中位 ~21）。**
**DPL-018 校准：17-25 × K=2.45 → 校准后 42-61 轮**（单卡 100-145% 预算 → 必须拆卡）。

## 3. 复杂度与风险

| # | 风险 | 评级 | 说明与缓解 |
|---|------|:---:|------|
| R1 | main 并发推进 / 回归基线漂移（本卡特有） | 高 | DPL-087 修复链 t_569d4425 正在 running（priority 80），将 merge discover.py + cmd_chain.py + test_va_backfill.sh(T11) → main HEAD 前移 + va_backfill 计数 91→91+N。缓解：源卡已裁定修复链路优先；SUB-1 merge 前刷新 main 基线（在最新 main 上重放 checkout，blob 不变量 37b081d 校验取代 commit 祖先判断）；SUB-2 断言「≥ 执行时 main 计数全绿」而非硬编码 91。 |
| R2 | 整分支 merge 违规 | 低 | 源分支当前恰好基于 main HEAD 且仅 1 提交——但卡面明令禁止整分支 merge。缓解：只 `git checkout wt/t_est_569d4425 -- docs/est/t_569d4425-estimate.md` 单路径；禁止 `-- .` 全量；分支未来追加提交不波及本卡。 |
| R3 | main 工作树并发污染 | 中 | main 工作树现存大量未跟踪噪音（.pipeline/gai/*.json 数十件 + va-skip/ + 多份未跟踪 docs）。缓解：SUB-1 在自己 worktree 执行；staging 显式单路径 add；`git diff --cached --stat` 逐项核对仅 1 新增。 |
| R4 | 回归套件长耗 | 中 | 213+ 断言，fixture 构建占大头。缓解：后台跑 + 长超时（300s+）+ 心跳保活；三套串行，每套独立核对计数。 |
| R5 | claim 格式（DPL-060） | 中低 | claim 必须带 changed_files 段。缓解：SUB-1 列 1 文件路径；SUB-2 为验证性质，列核对结果与三套计数。 |
| R6 | worktree 规范（DPL-026/027 教训） | 中 | 合并操作在子卡自己 worktree 分支进行，提交后 merge --no-ff 回 main；禁止直接改 main 工作树。 |
| R7 | 评估卡自身（本卡）超时 | 低 | 只读+估算，无功能代码，当前 ~10 轮内完成。 |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 17-25 轮（中位 ~21） |
| DPL-018 校准后 | 42-61 轮（×K=2.45）**> 20 轮阈值 → 必须拆卡** |
| 交付物数 | 2 个阶段（文件落地 / 回归验收）≥ 2 → 拆 2 卡合理 |
| 单卡方案复算 | base 17-25 → 校准 42-61 = 单卡 100-145% 预算 ❌ 且最近 5 卡 timed_out 前科 → 单卡不可行 |
| 本评估 2 卡方案 | SUB-1 基准 8-11 → 校准 20-27（27/42 = 64%）；SUB-2 基准 9-14 → 校准 22-34（34/42 = 81%）✅ |
| 依赖方向 | SUB-2 必须在 main 合并完成后跑回归 → 串行：SUB-1 合并进 main 后 SUB-2 才可测 |
| 并行收益 | 低——SUB-2 严格依赖 SUB-1 的 main 状态；与 DPL-087 修复链也必须串行（R1） |
| 兜底 | SUB-1 若超预算：单文件落地失败极小概率，阻塞点只可能在 main 并发竞争 → 等待修复链路 merge 完成后重放。SUB-2 若超预算：三套按 test_va_backfill → test_watchdog_unify → test_wip_progress_check 顺序，前两套优先（覆盖核心）；失败排查缓冲已备 2 轮 |

**决策：拆 2 张串行子卡（[SUB-SPLIT] 2 serial）。**
量级参照：t_5db95059（DPL-085/086，2 文件 + 同三套回归，拆 2 serial 22-34/22-37 已完成）、
t_66e31a89（DPL-083/084，12 文件，拆 2 serial 已完成）。本任务是其最小变体（1 文件），
但回归套件工作量不变（213 断言主导），2 卡粒度与「落地/验证」天然分段对齐。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 2 serial
1. [DEV-SUB-1] t_1f937fcb — DPL-087 评估报告 1 文件落地 main（docs/est/t_569d4425-estimate.md，
   逐文件 checkout，禁止整分支 merge）
   在自己 worktree（workspace_kind=worktree）执行：
   ⚠️ 若 DPL-087 修复链（t_569d4425，priority 80）仍在 running/未合 main → 先让修复链路
   （源卡裁定），等其 merge 完成后再执行本步。
   git checkout wt/t_est_569d4425 -- docs/est/t_569d4425-estimate.md
   （merge 前刷新基线：若 main 已前移，在最新 main 上重放上述单路径 checkout）
   staging 核对：git status + git diff --cached --stat 确认仅 1 新增文件，无 D/M，
   pipeline/discover.py / scripts/oc_wake_check.sh / scripts/test_va_backfill.sh 零改动，
   .pipeline/gai/ + manifest + archive 零混入；
   commit（message: docs(est): DPL-087 评估报告落地 main — t_569d4425-estimate.md（消除 code-not-in-main））；
   merge --no-ff 进 main；验证：
   git ls-tree -r main -- docs/est/t_569d4425-estimate.md → 命中且 blob == 37b081d（与源分支一致）；
   git show <merge> --stat 只含 1 新增（无 D/M）。
   claim 带 changed_files 段（1 文件全列）。预计 20-27 轮（校准后）
2. [DEV-SUB-2] t_1f937fcb — 落地后回归 + 验收（main 上执行）
   ⚠️ 回归基线以执行时 main 为准（DPL-087 T11 落地后 test_va_backfill 为 91+N，勿硬编码 91）；
   三套全量回归：scripts/test_va_backfill.sh（≥执行时计数全绿）+ scripts/test_watchdog_unify.sh（28/28）
   + scripts/test_wip_progress_check.sh（94/94）（长耗后台跑 + 心跳保活）；
   验收核对：ls-tree 命中 + blob == 37b081d + 合并 diff 仅 1 新增且三保护文件零改动 + 三套计数核对；
   失败排查（若回归失败，定位合并污染或环境问题，回退/修复后重跑）；
   claim 带 changed_files 段（验证性质，列出核对结果与三套计数）。预计 22-34 轮（校准后）
```

- SPLIT: yes（count=2，校准后 42-61 轮超 20 阈值；单卡 100-145% 预算不可行）
- MODE: serial（SUB-2 必须在 main 合并完成后跑回归，严格依赖；且与 DPL-087 修复链串行）
- ROUNDS_EST（校准后）: 42-61（基准 17-25 × K=2.45；分卡后每张 20-27 / 22-34）
- FILES: 1 个新增（docs/est/t_569d4425-estimate.md，152 行 / 14632B，源 blob 37b081d）——纯新增，无修改
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 2 张子卡挂源卡 t_1f937fcb）
- TESTS: SUB-1 ls-tree/blob/diff 验证 3 项；SUB-2 三套全量回归 91(+T11)+28+94 断言
- RISK: R1 main 并发推进+基线漂移（DPL-087 修复链 running）；R2 整分支 merge 违规（低）；
  R3 main 工作树噪音混入；R4 回归长耗；R5 claim changed_files（DPL-060）；R6 worktree 规范
- ACTION: build_two_dev_cards（assignee=game-engine，parents=[t_1f937fcb]，serial，workspace_kind=worktree）

## 6. 备注

1. **部署验证（DPL-048）不适用**：产物为 docs 文档，非 jobs.json 直调脚本、非绝对路径引用、
   非 must-sync 清单成员。
2. **本评估卡自身产物** docs/est/t_1f937fcb-estimate.md 在 wt/t_est_1f937fcb 分支，按
   code-not-in-main 机制预计下次命中——与 t_est_5db95059 先例同样处理：建议 OC/autopilot
   在 SUB-1 merge 时一并纳入（非本卡验收范围，仅提示，避免再开一张同型落地卡）。
3. **源分支结构优势**：wt/t_est_569d4425 merge-base == 当前 main HEAD（b5e37da），分支 diff
   仅 1 新增——DPL-085 的假删除风险（旧 main 基线 -1951）在本卡结构性不存在；逐文件 checkout
   纯属卡面合规要求，非风险规避必需。
4. **优先序提醒**：源卡明确「修复链路卡 t_569d4425（DPL-087）优先于本卡执行」——SUB-1 开工
   前检查该卡状态，若仍 running 则等待；这同时缓解 R1 的 main 竞争与基线漂移。
5. 本评估卡不写功能代码；产出即本报告 + [SUB-SPLIT] comment，autopilot 读取后建 2 张
   [DEV-SUB] 卡执行。
