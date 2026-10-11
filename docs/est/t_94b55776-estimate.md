# 评估报告 — [MERGE] t_2048b809 est 评估产物落地 main — docs/est/t_2048b809-estimate.md + .pipeline/wip/t_2048b809.md（消除 code-not-in-main）

> 评估人：寇豆码（game-engine） | 日期：2026-08-31 | 评估卡：t_est_94b55776 | 源卡：t_94b55776
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12）+ DPL-018 校准注入
> 源卡链：oc_wake_check [code-not-in-main] 命中 t_2048b809 est 产物 → OC 核对落地链路（comment 1950）→ MERGE 卡 t_94b55776（本评估的源卡，workspace_kind=dir @ /workspace/devPPL）→ 评估卡（本卡）→ [SUB-SPLIT] 裁决
> 有效轮折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）
> 校准注入: 累计偏差 +1.40 → K=2.40（clamp 0.5-3.0）；最近 5 条子卡偏差全部 timed_out（估 18-33 全撞 60 上限）

## 1. 结论（TL;DR）

**不拆（[SUB-SPLIT] 1）——源卡 t_94b55776 直接执行。校准后 19-26 轮（基准 8-11 × K=2.40），
落在 42 有效轮预算内（45-62%），且任务原子、无第二可分离阶段。**

任务本质：把 2 个评估产物——`docs/est/t_2048b809-estimate.md`（154 行 14752B）与
`.pipeline/wip/t_2048b809.md`（4213B 六节模板）——落地 devPPL main 分支并验证。
纯文档搬运，无代码逻辑改动，**无回归套件**（验收门禁仅 3 条 git 命令 + push）。

**评估期间实测确认（非假设）：**
- 源文件可从 dangling commit 恢复：`git cat-file -t af49250` = commit（存在，未被 gc）；
  `git show af49250:docs/est/t_2048b809-estimate.md | wc -l` = **154**、`wc -c` = **14752**，
  与 claim（comment 1949）一致；`47bf61a` 亦存在（commit）。
- `.pipeline/wip/t_2048b809.md` **已在 main 工作区磁盘**（/workspace/devPPL/.pipeline/wip/，
  untracked，4213B，六节模板实读）→ `git add` 即可，勿从别处复制覆盖。
- 目标路径在 main **0 命中**（docs/est/ 下 32 个 est 报告无 t_2048b809；.pipeline/wip/ 下无
  t_2048b809.md）→ 落地即纯 2 文件新增，无假删除风险。
- 源卡 workspace_kind=**dir** @ /workspace/devPPL（主工作树）→ 直接 main 提交，无需
  worktree + merge --no-ff；卡面要求「提交 main」与客观现实一致。
- 本卡链无回归阶段：验收门禁 = `git cat-file -e main:<2 路径>` + `wc -l == 154` + push，
  与先例 t_est_15e790bc（2 文件 + 三套回归）不同——**回归套件是先前例拆卡的主因，
  本卡没有**。
- DPL-048 部署验证**不适用**：产物为 docs 文档，非 cron 前置脚本、非 must-sync 清单成员。

## 2. 工作量评估（实测结论，非假设）

改动面：**2 个新增文件**（纯新增，无修改/删除）+ 1 次 main 直提 commit。无代码逻辑改动。

| 维度 | 评估 | 依据 |
|------|------|------|
| ① 文件落地 + 提交 main | 领卡 orient + 读源卡/评估卡 **1-2 轮**；确认 dangling commit 存在（`git cat-file -t af49250`）**0.5 轮**（本卡已实测存在，执行时复验即可）；提取 est 文件（`git show af49250:docs/est/t_2048b809-estimate.md > docs/est/t_2048b809-estimate.md`）+ wip 文件 `git add`（已在盘，untracked）**1 轮**；staging 核对（仅 2 新增、discover.py/oc_wake_check.sh/test_va_backfill.sh 保护文件零改动、.pipeline/gai/ + manifest + archive 零混入）**1 轮**；commit（message: [MERGE] t_2048b809 est 评估产物落地 main — 消除 code-not-in-main）**1 轮**；验证（`git cat-file -e main:<2 路径>` + `wc -l == 154`）**1 轮** → **基准 5.5-6.5** | 2 文件源已实测（af49250 存在 + wip 已在盘）；命令卡面全量给定，机械执行；无 worktree/merge/回归开销；比先例 t_est_15e790bc SUB-1（8-11，含 worktree 准备 + merge --no-ff）少 2-4 轮 |
| ② push + 收尾 | push（GIT_SSH_COMMAND 绝对 key，publickey 拒绝则如实报告 OC 不伪造）**1-2 轮**；claim(changed_files) + 飞书 + complete **2 轮** → **基准 3-4** | 卡面验收含 push；标准闭环 2 轮；push 失败路径是「报告」不是「重试循环」，预算不燃烧 |

**基准轮数（未校准，合计）：8.5-10.5 轮（中位 ~9.5）。**
**DPL-018 校准：8.5-10.5 × K=2.40 → 校准后 20-25 轮**（中位 ~22，42 有效轮预算的
48-60%）——**单卡可行，不拆**。

## 3. 复杂度与风险

| # | 风险 | 评级 | 说明与缓解 |
|---|------|:---:|------|
| R1 | dangling commit af49250 被 gc 剪掉 | 低 | 本卡已实测存在；执行与评估间隔短（分钟级），gc 概率极低。缓解：执行时先 `cat-file -t` 复验；若已剪 → 按卡面 fallback 从 kanban comment 1949 [PRODUCES] 的 claims 取证重建（文件尺寸/行数已知：154 行 14752B） |
| R2 | main 工作树并发污染（untracked 噪音） | 中 | /workspace/devPPL 存在 .pipeline/gai/*.json、.pipeline/wip/t_b533bf93.md、scripts/glm_quota_probe.sh 等 untracked 噪音（实测）。缓解：显式单路径 `git add docs/est/t_2048b809-estimate.md .pipeline/wip/t_2048b809.md`；`git diff --cached --stat` 逐项核对仅 2 新增；禁止 `git add -A`/`git add .` |
| R3 | push publickey 拒绝 | 低 | 卡面已明示「拒绝则如实报告 OC，不伪造成功」。缓解：GIT_SSH_COMMAND 用绝对 key 路径（memory：cron HOME=/root 下 ~ 展开错）；失败即报告，不反复重试烧轮 |
| R4 | SUB-2（t_2647fa3e）重复写入冲突 | 低 | 卡面已明示 SUB-2 claim 只需「验证 main 已存在（blob 一致）」，不重复写入。本卡先落地，SUB-2 后验，并行无冲突 |
| R5 | 本卡产物 docs/est/t_94b55776-estimate.md 自身 code-not-in-main | 中 | 本评估卡产物将提交在 wt/t_est_94b55776 分支，落 main 需后续 MERGE 卡（与 t_2048b809 产物本轮被 t_94b55776 追回同模式）。缓解：报告 §6 备注 + [PRODUCES] 给 OC 明确提示，由 OC 派 MERGE 卡追回（或随源卡完成后另立） |
| R6 | claim 格式（DPL-060） | 低 | 源卡 claim 必带 changed_files 段；本卡 [PRODUCES] 同样带 |
| R7 | 评估卡自身（本卡）超时 | 低 | 只读+估算，无功能代码，~15 轮内完成（本卡 run 已含 checkpoint 节奏） |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 8.5-10.5 轮（中位 ~9.5） |
| DPL-018 校准后 | 20-25 轮（×K=2.40），42 有效轮预算的 48-60% ✅ 单卡可行 |
| 20 轮阈值 | 校准中位 ~22 略超 20——但超阈值本义是「防单会话超预算」；22/42 = 52% 预算，余量充足，非拆分红线场景 |
| 任务原子性 | 2 文件 + commit + push 一气呵成，**无第二可分离阶段**（无回归/无测试/无接线）——拆卡无可拆内容 |
| 拆卡开销 | 2 卡 ×（orient + claim + 飞书 + complete）≈ 额外 4-6 轮 > 拆分收益（几乎为零） |
| 与先例差异 | t_est_15e790bc/t_d683fdef 拆 2 serial 是因为各有**三套全量回归**（回归段基准 9-14 轮，占大头）；本卡**无回归**，是 3 个 MERGE 先例中最轻的一张 |
| 历史偏差源 | 最近 timed_out 的 5 条全是**实现卡**（MEM-013/DPL-092 类，多模块代码+测试）；本卡是机械文档搬运，偏差驱动因素不存在 |

**决策：不拆（[SUB-SPLIT] 1）——源卡 t_94b55776 按卡面直接执行。**
量级参照：t_est_15e790bc SUB-1（落地段基准 8-11，含 worktree/merge 开销）本卡落地段
基准 5.5-6.5 更轻；t_d683fdef SUB-1（6 文件落地基准 9-14）本卡 2 文件。卡面命令全量给定、
前置已实测，无设计决策、无发现轮。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 1
```

- SPLIT: no（count=1；校准 20-25 轮在 42 有效轮预算内，任务原子无第二可分离阶段，
  拆卡开销 > 收益；历史偏差源为实现卡，本卡为机械文档搬运）
- MODE: N/A（单卡直接执行，源卡已存在 t_94b55776，workspace_kind=dir @ /workspace/devPPL）
- ROUNDS_EST（校准后）: 20-25（基准 8.5-10.5 × K=2.40）
- FILES: 2 个新增（docs/est/t_2048b809-estimate.md 154 行 14752B，源 dangling commit
  af49250；.pipeline/wip/t_2048b809.md 4213B，已在 main 工作区磁盘 untracked）——纯新增
- STATUS: not_started（本评估卡待 complete，源卡 t_94b55776 的 parents=[t_2048b809,
  t_est_94b55776] 全 done 后自动 promote ready → 直派）
- TESTS: 验收三门禁 = `git cat-file -e main:docs/est/t_2048b809-estimate.md` &&
  `git cat-file -e main:.pipeline/wip/t_2048b809.md` + `git show main:docs/est/t_2048b809-estimate.md
  | wc -l == 154` + push 成功（GIT_SSH_COMMAND 绝对 key）
- RISK: R1 dangling commit gc（低，已实测存在）；R2 main 工作树噪音混入（中，显式单路径
  add）；R3 push publickey 拒绝（低，报告不伪造）；R5 本卡产物自身 code-not-in-main（中，
  OC 另派 MERGE 追回）
- ACTION: none（不建子卡；源卡 t_94b55776 直接执行）

## 6. 备注

1. **部署验证（DPL-048）不适用**：产物为 docs 文档，非 jobs.json 直调脚本、非绝对路径引用、
   非 must-sync 清单成员（deploy-drift-audit-2026-08-15.md §1.1 判定式）。
2. **本评估卡自身产物** docs/est/t_94b55776-estimate.md 将提交在 wt/t_est_94b55776 分支，
   落 main 需后续 MERGE 卡——与 t_2048b809 产物本轮由 t_94b55776 追回同一模式
   （t_d683fdef 报告 R7 教训：est 产物落地遗漏 → code-not-in-main 续报）。建议 OC 在
   本卡（t_est_94b55776）done 后按同样机制派 MERGE 卡追回，或在源卡执行时一并纳入
   （卡面「只动这 2 个文件」未含本卡产物，需 OC 显式扩 scope 或另立卡）。
3. **源 commit 结构**：af49250 / 47bf61a 均为 dangling commit（worktree 已清理、分支已删），
   仅 commit 对象残留，随时可能被 gc——执行时先复验，已实测存在。逐文件 `git show` 提取
   是唯一路径（与卡面一致，分支已删无整分支 merge 可能）。
4. **与开发链无冲突**：本卡只落地 docs 文档 + wip 笔记，不触碰 discover.py / oc_wake_check.sh /
   test_va_backfill.sh；SUB-2（t_2647fa3e）只验证 blob 一致，无写入竞争。
5. 本评估卡不写功能代码；产出即本报告 + [SUB-SPLIT] 1 comment + [PRODUCES] claim，
   autopilot 按 count=1 不建子卡，源卡直接执行。
