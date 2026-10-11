# 评估报告 — [FIX] WIP 检测脚本落地 + oc_wake 落地质检（done 卡产物核对 main）

> 评估人：寇豆码（game-engine） | 日期：2026-08-15 | 评估卡：t_est_0f418cf6
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）+ DPL-018 校准注入
> 源卡：t_0f418cf6（[FIX] WIP 检测脚本落地 + oc_wake 落地质检 — 两个"卡 done 代码没落地"防线）
> 来源：Frank 2026-08-14 追问后实查发现（实例 1 t_6c4a9cae 脚本悬空 / 实例 2 DPL-030 7 文档 POST-01）
> 有效轮数折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）

## 1. 结论（TL;DR）

**拆 2 张串行子卡（校准后预计 36-60 轮 > 20 轮阈值）。**

任务两半性质迥异：A 半是**纯落地**（代码已在 wt/t_a2466834 写完测完，只差 merge 进 main + 回归验证），
B 半是**新检测源开发**（oc_wake_check.sh 新增"落地质检"源 E：解析 done 卡 claim 的 changed_files →
`git cat-file -e main:<path>` 核对 + [DEV-MERGE] 卡 merge commit 祖先核对 + 反例/正例验证）。
自然边界即 A/B：A 立即止血（Frank 标注"第一交付"），B 是规则落地（核心）。B 的正例验收
（"修复后不再报"）依赖 A 先落地 → 天然串行。

**评估期间实锤第三个同类实例**（源卡只列了 2 个）：6e8ba0c（t_est_14fb6a11 的评估文档，
done 卡产物）NOT in main —— 已并入 S1 落地范围。这本身就是本 FIX 要防的病，佐证 B 半必要性。

## 2. 工作量评估（读码结论，非假设）

| 维度 | 评估 | 依据 |
|------|------|------|
| 改动面 | **S1 纯落地 0 新代码**（merge 已有分支 + 验证）；**S2 新增 ~60-80 行检测源 + ~150-200 行测试**：scripts/oc_wake_check.sh（+源 E）、scripts/test_wip_progress_check.sh（+T9-T14 落地质检段，复用其既有 DB+git fixture） | 实测 diff main..wt/t_a2466834 = 6 文件 558 insertions **0 deletions**（wip_progress_check.sh 209 行 / test 243 行 / oc_wake +18 行源 D / autopilot +10 行挂载 / 2 个发现笔记） |
| ① S1 落地 merge | `git -C main工作树 merge --no-ff wt/t_a2466834`（⊇ S1' be2c512，一次 merge 全含）+ cherry-pick 6e8ba0c（est 文档第三实例）+ merge 本评估分支。main 自分叉后仅 +c9933d2（docs-only）→ **零冲突面**（diff 只增不删，无同文件双改） | 实测 git log main..wt/t_a2466834 仅 5dfe0af/be2c512 两 commit；merge-base 干净 |
| ② S1 验证 | bash -n 两脚本 + 真实 DB dry-run（对 running 卡输出检测文案，exit 0）+ test_wip_progress_check 24 断言 + test_cmd_channel 386 断言（main 上复跑） | 源卡验收 1；S2 claim 实录两套测试数字 |
| ③ S2 源 E 开发 | oc_wake_check.sh 仿源 D 模式（python heredoc 内新增检测段）：SELECT title LIKE '[DEV%' AND status='done' AND completed_at > now-N（env `LANDING_CHECK_WINDOW_H` 默认 24h）→ 取该卡 comments 里 `**changed_files**` 段的 bullet 路径（反引号 token，容忍 plain 文本）→ 路径规范化（跳过 repo 外绝对路径如 /tmp 冒烟脚本、NA 哨兵）→ `git cat-file -e main:<path>` 不存在 → 输出 `code-not-in-main: <tid> <file>`。**只报告不阻断**（OC 决定处置），fail-open | 实测 claim 格式（comment 1385/1386）：`**changed_files**:` + `- \`scripts/x.sh\`（说明）` bullet；task_runs.metadata 为空 → comment 是唯一数据源 |
| ④ S2 merge 核对 | [DEV-MERGE] 卡：claim comment 提取 7-40 位 hex sha → `git merge-base --is-ancestor <sha> main` 不通过 → `merge-not-in-main: <tid> <sha>`。当前 board 无 [DEV-MERGE] 现存卡 → 纯 fixture 测试，通用实现 | 实测 board grep 无 merge 卡；autopilot merge commit 格式 `autopilot merge: <tid>` 在 main 历史可见（86c4ec6 等） |
| ⑤ S2 测试 | 扩展 test_wip_progress_check.sh（复用既有隔离 DB + temp git fixture，**不新建文件**）：T9 反例（fixture 卡 done + changed_files 指向 fixture repo 不存在路径 → 检出）/ T10 正例（路径存在于 main 引用 → 不报）/ T11 路径变体（反引号/plain/绝对路径 repo 外跳过/NA）/ T12 [DEV-MERGE] sha 祖先核对正反例 / T13 窗口边界（24h±）/ T14 幂等 seen 键 + 只报告不阻断（卡状态不变）+ 源 A-D 只增不删回归 | 源卡验收 2/3/4；t_6c4a9cae 反例按验收原文"写进测试"（fixture 化）；DPL-030 文档正例 = S1 落地后 live 跑不报 |
| ⑥ S2 收尾 | live 全量扫描演示（真实 DB + main：t_6c4a9cae/DPL-030 不再报；若仍有其他 stray 卡 → 报告不阻断）+ 全量回归（test_cmd_channel 386 等）+ S2 自身分支 merge 进 main（自引用闭环：本卡不能犯它要修的错）+ claim + 飞书 + complete | 源卡约束"merge 进 main 后才算完成"；验收 3/4/5/6 |
| ⑦ 前置失败基线 | test_notify_exec_qa.py（14/1）与 test_incremental_backup.py 在 pristine main 同样复现 → 前置失败非回归，记录不修（S2 已有先例记录在发现笔记） | S2 claim 实录 + 本评估在 main 复核 |

**基准轮数（未校准）：12-20 轮**（S1 ①② 4-7 + S2 ③④⑤⑥⑦ 8-13）。
**DPL-018 校准：基准 × K=3.00 → 校准后 36-60 轮**（取中位 48）> 20 轮阈值。

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| R1 **claim changed_files 格式方差（S2 最大风险）** | **中-高** | comment 是自由 markdown：bullet 可能反引号可能 plain、一卡多 comment 多段 `**changed_files**`、路径可能绝对/相对/带空格/NA 哨兵、/tmp 冒烟脚本不在 repo。解析器必须宽容 + repo 外路径跳过，否则误报刷屏（清单只报告不阻断，误报会消耗 OC 注意力）。T11 变体测试必须覆盖。已实锤两个真实样本（comment 1385/1386）作解析基准 |
| R2 反例验证时序 | 中 | 验收 3 要求"修复前 t_6c4a9cae 会被检出"——但 S1 先落地后 live 状态已修复。按验收原文"写进测试**或**演示"取 fixture 化（T9），并在 S1 merge 前 live 演示一次源 E 对真实 DB 的检出输出（S2 开发期 t_6c4a9cae 已在 main → 用第三实例 6e8ba0c 若未及落地可 live 演示，否则纯 fixture）。注意：**不要为演示推迟 S1 落地**（止血优先） |
| R3 main 工作树合并窗口 | 中 | S1/S2 均需在 main 工作树（/workspace/devPPL）执行 merge——与其他 worker 并行时违反独占原则的概率低但非零（DPL-026/027 教训）。缓解：merge 前确认 main 工作树 `git status` clean、merge+push 一气呵成缩短持锁窗口；冲突在自己分支解决，禁 --abort 循环（SOUL 红线） |
| R4 误报面控制 | 中 | docs 类产物（est 报告/wiki）也走 cat-file 核对——正确（它们也该落地）；但 24h 窗口内刚 done、merge 卡尚在排队的卡会瞬时误报。缓解：窗口可 env 调宽 + 输出标注"OC 处置"；不做自动豁免逻辑（防复杂度膨胀），清单语义就是"给 OC 看" |
| R5 幂等键设计（决策点 D1） | 低-中 | 源 A-D 用一次性 seen 键，但落地质检是**状态型**异常（文件进 main 前一直异常，修好即消失）。seen 键 `landing:<tid>:<missing数>`（missing 集合变化可再报）或简单 `landing:<tid>`（一次性）——S2 实现时定，推荐前者 |
| R6 既有断言回归 | 低 | oc_wake 加源 E 只增不删 → PRD-GATE-T6（test_cmd_channel L465-476 [blocked-new]/[PRD审核门]）与源 D 断言不受影响；但必须全量 386 复跑确认（S2 claim 已有此惯例） |
| R7 S2 自身落地的自引用 | 低 | S2 改的 oc_wake_check.sh 也要进 main——S2 收尾含自身 merge，与源卡约束一致；fixture 测试保证检出能力不依赖 live 状态 |

**关键决策点（S2 实现时拍板，不改轮数量级）**：D1 seen 键粒度（推荐 `landing:<tid>:<missing-hash>`）；
D2 窗口 env 名与默认（`LANDING_CHECK_WINDOW_H=24`，对齐源卡 N=24h）；D3 [DEV-MERGE] sha 提取正则
（`\b[0-9a-f]{7,40}\b` 取 claim 段首个命中，宁缺勿滥——误报比漏报伤 OC 信任）。

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 12-20 轮（中位 16） |
| DPL-018 校准后 | 36-60 轮（×K=3.00，中位 48）**> 20 轮阈值 → 必须拆卡** |
| 模块依赖 | S1（落地止血）→ S2（源 E + 验证 + 收尾）单向依赖：S2 的正例验收"修复后不再报"必须等 S1 落地；S2 测试 fixture 不依赖 S1 但 live 演示依赖 |
| 并行收益 | 低——S2 的验收闭环含"main 已落地"前置；并行会使 S2 的正例验证悬空 |
| 兜底 | S1 独立交付即止血（wip 检测链复活，验收 1 闭环）；S2 若超预算，源 E + fixture 测试是原子交付，merge 收尾可单独补 |

**决策：拆 2 张串行子卡（[SUB-SPLIT] 2 serial）。** 量级参照：t_14fb6a11（同链前置，5 文件 + 设计空白 → 拆 2 serial，实际 S1/S2 均单会话完成）；本卡 S1 更轻（零新代码纯 merge），S2 更重（新检测源 + 解析器 + 6 组新测试）。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 2 serial
1. [DEV-SUB-1] 落地止血 S1 — wip_progress_check.sh 全链 + est 文档 merge 进 main
   （merge --no-ff wt/t_a2466834（⊇ S1' be2c512：wip_progress_check.sh 209 行 + test 243 行 +
    oc_wake 源 D + autopilot 挂载）+ cherry-pick 6e8ba0c（t_est_14fb6a11 est 文档，第三实例）+
    本评估卡分支；main 工作树 clean 前置 + merge 后立即 push（SSH 绝对路径 key）；
    验证：bash -n ×2 + 真实 DB dry-run running 卡检测输出 + test_wip_progress_check 24/24 +
    test_cmd_channel 386/386 在 main 复跑 + push remote） 预计 8-13 轮
2. [DEV-SUB-2] 落地质检 S2 — oc_wake_check.sh 源 E（code-not-in-main / merge-not-in-main）
   + 测试 + 全量回归 + 收尾
   （源 E：24h 窗口内 done [DEV-*] 卡 → 解析 claim comment **changed_files** bullet 路径（宽容解析 +
    repo 外跳过）→ git cat-file -e main:<path> 核对，缺 → "code-not-in-main: <tid> <file>"；
    [DEV-MERGE] 卡 sha → git merge-base --is-ancestor 核对 → "merge-not-in-main"；
    只报告不阻断 fail-open；幂等 seen 键 landing:<tid>:<missing-hash>；env LANDING_CHECK_WINDOW_H=24；
    测试：扩展 test_wip_progress_check.sh T9-T14（fixture 反例 t_6c4a9cae 场景 / 正例 / 路径变体 /
    merge sha 正反 / 窗口边界 / 只报告不阻断 + 源 A-D 只增不删）；live 演示：真实 DB 跑源 E，
    t_6c4a9cae + DPL-030 文档不再报；全量回归 test_cmd_channel 386 等；S2 自身分支 merge 进 main
    （自引用闭环）+ claim + 飞书 + complete） 预计 14-20 轮
```

- SPLIT: yes（count=2，校准后 36-60 轮远超 20）
- MODE: serial（S2 正例验收依赖 S1 落地完成）
- ROUNDS_EST（校准后）: 48（基准 16 × K=3.00）
- FILES: S1 零新文件（merge wt/t_a2466834 6 文件 + 6e8ba0c 1 文档）；S2 改 scripts/oc_wake_check.sh（+源 E ~60-80 行）+ scripts/test_wip_progress_check.sh（+T9-T14 ~150-200 行）
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 2 张子卡挂 t_0f418cf6）
- TESTS: S1 复跑 24+386；S2 新增 T9-T14（~18-24 断言）+ 全量回归 386+；前置失败基线 test_notify_exec_qa.py 14/1、test_incremental_backup.py 环境问题（pristine main 复现，非回归）
- RISK: R1 claim 格式方差（宽容解析 + T11 变体）；R2 反例时序（fixture 化，不为演示推迟止血）；R3 main 合并窗口（clean 前置 + 短持锁）；R4 瞬时误报（OC 处置语义）；D1-D3 实现时拍板
- ACTION: build_two_dev_cards（assignee=game-engine，parents=[t_0f418cf6]，serial）

## 6. 备注

- **第三实例（本评估新发现）**：6e8ba0c（t_est_14fb6a11 评估文档，done 卡产物）NOT in main——
  并入 S1 cherry-pick 落地。这证明"卡 done ≠ 进 main"是系统性问题而非孤例，B 半（源 E）值得做。
- S1 是零新代码纯落地卡：merge + 验证 + push，最短路径止血；若 merge 意外冲突（评估判断零冲突面），
  在自己分支解决后重试，禁 --abort 循环。
- S2 复用 test_wip_progress_check.sh 的隔离 DB + temp git fixture（不新建测试文件）——该 harness
  已含"合成 claim comment 注入"能力（count_wip_comments 同款手法），T9-T14 增量成本低。
- 源卡验收 6"结构化 claim + [PRODUCES] comment"按 claim-schema 执行；每张子卡完成后推飞书
  （send_claim_feishu.py，SOUL 5.1 硬性要求）。
- 本评估卡自身产物（本文件）随 S1 merge 进 main——评估卡不写代码，但产物不能悬空（不能犯它评估的错）。
- 校准口径说明：K=3.00 沿用 DPL-018（t_e33936c6 病例）。本卡 S1 半是纯机械 merge（风险极低），
  若 autopilot 支持不等权拆分，S1 可视 6-10 轮轻卡；S2 含解析器开发 + 6 组新测试，是工作量主体。
