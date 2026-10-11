# 评估报告 — [MERGE] MEM-009 QA 产品落地 main — 消除 code-not-in-main

> 评估人：寇豆码（game-engine） | 日期：2026-08-20 | 评估卡：t_est_66e31a89 | 源卡：t_66e31a89
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12）+ DPL-018 校准注入
> 源卡链：oc_wake_check [code-not-in-main] 命中 → OC 核对落地链路 → **本评估** → MERGE 卡 t_66e31a89 执行
> 有效轮折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）
> 校准注入: 累计偏差 +1.45 → K=2.45（clamp 0.5-3.0）；最近 5 条子卡偏差全部 timed_out（估 18-33 轮全部撞 60 上限）

## 1. 结论（TL;DR）

**拆 2 张串行子卡（校准后每张 25-34 / 22-34 轮，全部落在 42 有效轮预算内）。**

任务本质：MEM-009 全部 QA/VA 卡均为 worktree 提交，5 份报告 + 2 个探针脚本 + 5 份 wip
笔记从未进 main（实测 `git ls-tree main | grep mem009 = 0` 命中）。本卡从 5 个 wt 分支
**逐文件 checkout** 12 个指定路径到 main 并提交，**禁止整分支 merge**，随后跑三套全量回归。

**评估期间实测确认（非假设）：**
- 12 个目标文件在源分支**全部存在**（5 docs + 2 scripts + 5 wip，大小 2.7-23 KB）。
- wt/t_48a3dd47 基于旧 main（merge-base 4e49c98，早于 DPL-077/078 合并）→ 分支 diff 含
  `pipeline/discover.py -74`、`scripts/oc_wake_check.sh -59`、`scripts/test_va_backfill.sh -132`
  **假删除** → 整分支 merge 会回退 DPL-077/078 已合改动。**必须逐文件 checkout，禁止 merge 分支本体。**
- wt/t_2fc5fd0a 附带 `.pipeline/gai/*.json`（3 个测试夹具）+ `.pipeline/manifest.jsonl +2` +
  `docs/est/t_f3108dfd-estimate.md -127` 等无关改动 → **只取指定 12 路径，不带 gai/manifest。**
- main 三套回归套件均在：test_va_backfill.sh（38.6KB）、test_watchdog_unify.sh（12.9KB）、
  test_wip_progress_check.sh（40.4KB）。验收断言计数 91/91 + 28/28 + 94/94。
- 目标文件不涉及 cron 前置脚本改动（qa_mem009_probes.sh 是 QA 探针，非 jobs.json 直调、
  非 must-sync 清单）→ **部署验证规则（DPL-048）不适用于本卡**，但回归套件本身会跑
  oc_wake_check.sh 相关断言（test_watchdog_unify T1-T9），等价覆盖。

## 2. 工作量评估（实测结论，非假设）

改动面：**12 个新增文件**（纯新增，无修改/删除）+ 1 次 merge commit。无代码逻辑改动。

| 维度 | 评估 | 依据 |
|------|------|------|
| ① SUB-1 文件提取 + 合并 main | 领卡 orient + 读源卡 + 确认 5 分支/12 文件/风险 diff **1-2 轮**；worktree 准备（确认 workspace_kind、分支状态）**1 轮**；逐文件 checkout（5 分支 12 路径，1-2 条 git checkout <branch> -- <path> 批量命令）**1-2 轮**；staging 核对（git status / diff --stat 确认仅 12 文件、无假删除、无 gai/manifest 混入）**2 轮**；commit + merge --no-ff 进 main（逐文件路径不冲突，风险低）**2-3 轮**；ls-tree 验证（mem009 7 命中 + wip 5 在 main）+ 合并 diff 核对三文件零改动 **2 轮**；claim(changed_files) + 飞书 + complete **2 轮** → **基准 10-14** | 12 文件已逐个 git cat-file -e 实测存在；两分支假删除/夹具 diff 已实测；main 三套件已实测在库 | 
| ② SUB-2 回归 + 验收 | 领卡 orient + 确认 main 合并后状态 **1-2 轮**；test_va_backfill.sh 91 断言（长耗，fixture 构建）**2-3 轮**；test_watchdog_unify.sh 28 断言 **1-2 轮**；test_wip_progress_check.sh 94 断言（长耗）**2-3 轮**；失败排查缓冲（若合并污染回归）**0-3 轮**；验收核对（7+5 命中 + 无回归 diff + 三套计数）**2 轮**；claim(changed_files) + 飞书 + complete **2 轮** → **基准 9-14** | 三套件断言计数来自验收标准（91/28/94）；合并 diff 先行验证无污染后回归应为纯验证性质；用例耗时按各套件 fixture 规模备（DPL-030 S2 实证回归占大头） |

**基准轮数（未校准，合计）：19-28 轮（中位 ~23）。**
**DPL-018 校准：19-28 × K=2.45 → 校准后 47-69 轮**（单卡 112-164% 预算 → 必须拆卡）。

## 3. 复杂度与风险

| # | 风险 | 评级 | 说明与缓解 |
|---|------|:---:|------|
| R1 | 假删除回退（验收核心） | 高 | wt/t_48a3dd47 基于旧 main，分支 diff 含 discover.py -74 / oc_wake_check.sh -59 / test_va_backfill.sh -132 假删除。缓解：**只逐文件 checkout 12 个指定路径，禁止整分支 merge**；SUB-1 验收显式 `git diff main^..main --stat` 确认合并只含 12 新增文件、三文件零改动。wt/t_2fc5fd0a 同理（另有 gai 夹具）。 |
| R2 | gai/manifest 夹具混入 | 中 | wt/t_2fc5fd0a 附带 .pipeline/gai/t_*.json（3 个）+ manifest.jsonl +2。缓解：checkout 时显式列 12 路径，不带 `-- .` 全量；staging 核对步骤逐项比对。 |
| R3 | 回归失败（若合并污染） | 中 | 三套全量回归是主耗时。缓解：SUB-1 先做合并 diff 无污染验证再提交 claim；SUB-2 跑回归前确认 main 状态；失败排查缓冲 0-3 轮。 |
| R4 | worktree 规范（DPL-026/027 教训） | 中 | 合并操作必须在自己 worktree（wt/t_66e31a89）进行，禁止直接改 main 工作树；提交后走 merge 卡/显式 merge 回 main。 |
| R5 | 回归套件耗时 | 中 | test_va_backfill 91 + test_wip_progress_check 94 断言含 fixture 构建。缓解：后台跑 + 长超时（300s+）；心跳保活；SUB-2 内三套串行跑，每套独立核对计数。 |
| R6 | claim 格式（DPL-060） | 中低 | 验收要求 claim 必须带 changed_files 段。缓解：两张子卡 claim 均列出 12 个文件路径；SUB-1 报 12 文件落地，SUB-2 报回归计数+验收结论。 |
| R7 | 评估卡自身（本卡）超时 | 低 | 只读码+估轮，不写功能代码，60 轮预算充裕（当前 ~10 轮内完成）。 |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 19-28 轮（中位 ~23） |
| DPL-018 校准后 | 47-69 轮（×K=2.45）**> 20 轮阈值 → 必须拆卡** |
| 交付物数 | 2 个阶段（文件落地 / 回归验收）≥ 2 → 拆 2 卡合理 |
| 单卡方案复算 | base 19-28 → 校准 47-69 = 单卡 112-164% 预算 ❌ 且最近 5 卡 timed_out 前科 → 单卡不可行 |
| 本评估 2 卡方案 | SUB-1 基准 10-14 → 校准 25-34（34/42 = 81%）；SUB-2 基准 9-14 → 校准 22-34（34/42 = 81%）✅ |
| 依赖方向 | SUB-2 必须在 main 合并完成后跑回归 → 串行：SUB-1 合并进 main 后 SUB-2 才可测 |
| 并行收益 | 低——SUB-2 严格依赖 SUB-1 的 main 状态；文件提取与回归无法并行（回归测的是合并后 main） |
| 兜底 | SUB-1 若超预算：12 文件提取可切块（contingency SUB-1b：先 7 个核心命中文件 docs/qa 5 + scripts 2，再补 5 个 wip）；SUB-2 若超预算：三套回归按 test_va_backfill → test_watchdog_unify → test_wip_progress_check 顺序，前两套优先（91+28 覆盖核心），test_wip_progress_check 94 可最后跑 |

**决策：拆 2 张串行子卡（[SUB-SPLIT] 2 serial）。**
量级参照：t_f3108dfd（DPL-077/078，同脚本族同型改造，拆 2 serial 15-25/17-25 已完成）、
t_dbbec269（DPL-071，oc_wake 源 E 跨仓测试补落地链路，单卡完成）。本任务比 DPL-077/078
小一个量级（无代码逻辑改动，纯文件搬运 + 回归验证），2 卡粒度与「落地/验证」天然分段对齐。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 2 serial
1. [DEV-SUB-1] MEM-009 QA 产品 12 文件提取 + 合并 main（逐文件 checkout，禁止整分支 merge）：
   源分支 5 个：wt/t_2fc5fd0a / wt/t_f91a64c5 / wt/t_ac88ed89 / wt/t_48a3dd47 / wt/t_de9e75df。
   在自己 worktree（wt/t_66e31a89）执行：
   git checkout wt/t_2fc5fd0a -- docs/qa/mem009-conversation-extraction-test-plan.md \
     scripts/qa_mem009_probes.sh .pipeline/wip/t_2fc5fd0a.md
   git checkout wt/t_f91a64c5 -- docs/qa/mem009-conversation-extraction-test-report.md \
     .pipeline/wip/t_f91a64c5.md
   git checkout wt/t_ac88ed89 -- docs/qa/mem009-conversation-extraction-d2-review.md \
     scripts/qa_mem009_d2_probes.sh .pipeline/wip/t_ac88ed89.md
   git checkout wt/t_48a3dd47 -- docs/qa/mem009-conversation-extraction-va-report.md \
     .pipeline/wip/t_48a3dd47.md
   git checkout wt/t_de9e75df -- docs/qa/mem009-conversation-extraction-qa-post-report.md \
     .pipeline/wip/t_de9e75df.md
   ⚠️ 禁止 `git checkout <branch> -- .` 全量；禁止 merge 分支本体（wt/t_48a3dd47 有假删除
   discover.py/oc_wake_check.sh/test_va_backfill.sh；wt/t_2fc5fd0a 有 .pipeline/gai/*.json +
   manifest.jsonl 夹具）。
   staging 核对：git status + git diff --stat 确认仅 12 新增文件，无修改/删除；
   commit（message: merge(mem009): QA/VA 产品落地 main — 12 文件逐文件 checkout）；
   merge --no-ff 进 main；验证：
   git ls-tree -r main --name-only | grep mem009 → 7 命中（docs/qa 5 + scripts 2）；
   .pipeline/wip/t_{2fc5fd0a,f91a64c5,ac88ed89,48a3dd47,de9e75df}.md 在 main；
   git diff main^..main --stat 只含 12 新增，pipeline/discover.py / scripts/oc_wake_check.sh /
   scripts/test_va_backfill.sh 零改动（无回退）。
   claim 带 changed_files 段（12 文件全列）。预计 25-34 轮（校准后）
2. [DEV-SUB-2] MEM-009 合并后全量回归 + 验收（main 上执行）：
   三套全量回归：scripts/test_va_backfill.sh（91/91）+ scripts/test_watchdog_unify.sh（28/28）
   + scripts/test_wip_progress_check.sh（94/94）全绿（长耗套件后台跑 + 心跳保活）；
   验收核对：mem009 7 命中 + wip 5 在 main + 合并 diff 无 discover.py/oc_wake_check.sh/
   test_va_backfill.sh 改动 + 三套计数核对；
   失败排查（若回归失败，定位合并污染或环境问题，回退/修复后重跑）；
   claim 带 changed_files 段（本次为验证性质，列出核对结果与三套计数）。预计 22-34 轮（校准后）
```

- SPLIT: yes（count=2，校准后 47-69 轮远超 20 阈值；单卡 112-164% 预算不可行）
- MODE: serial（SUB-2 必须在 main 合并完成后跑回归，严格依赖）
- ROUNDS_EST（校准后）: 47-69（基准 19-28 × K=2.45；分卡后每张 25-34 / 22-34）
- FILES: 12 个新增（docs/qa 5 + scripts 2 + .pipeline/wip 5）——纯新增，无修改
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 2 张子卡挂源卡 t_66e31a89）
- TESTS: SUB-1 ls-tree/diff 验证 3 项；SUB-2 三套全量回归 91+28+94 断言
- RISK: R1 假删除回退（wt/t_48a3dd47 旧 main 基线）；R2 gai/manifest 夹具混入；R3 回归失败；
  R4 worktree 规范；R5 回归套件耗时；R6 claim changed_files 段（DPL-060）
- ACTION: build_two_dev_cards（assignee=game-engine，parents=[t_66e31a89]，serial）

## 6. 备注

1. **禁止整分支 merge 是验收硬约束**：wt/t_48a3dd47 基于 4e49c98（早于 DPL-077/078 合并），
   分支 diff 含三个核心脚本的假删除；wt/t_2fc5fd0a 含 .pipeline/gai/*.json 测试夹具与
   manifest.jsonl 改动。两条分支都只允许逐文件 checkout 指定路径。
2. **部署验证规则（DPL-048）不适用**：目标 12 文件均为新增 QA 产品（报告/探针/wip 笔记），
   不是 cron 前置脚本，也不在 must-sync 清单（oc_wake_check.sh 未改动）。但 test_watchdog_unify.sh
   T1-T9 覆盖 oc_wake 相关断言，合并无污染即等价覆盖。
3. **回归套件耗时是主风险**：test_va_backfill.sh 91 断言 + test_wip_progress_check.sh 94 断言
   均含 fixture 构建，实测单套可能 1-3 分钟。SUB-2 内建议后台跑 + 长超时 + 心跳保活，避免
   前棒教训（DPL-026/027 抢 main 工作树 + 60 轮耗尽）。
4. **本评估卡不写功能代码**；产出即本报告 + [SUB-SPLIT] comment，autopilot 读取后建 2 张
   [DEV-SUB] 卡执行。源卡 t_66e31a89 作为容器由 autopilot 关闭。
