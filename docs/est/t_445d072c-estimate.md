# 评估报告 — [MERGE] t_a5c7400d est 评估产物落地 main — docs/est/t_a5c7400d-estimate.md + .pipeline/wip/t_a5c7400d.md（消除 code-not-in-main）

> 评估人：寇豆码（game-engine） | 日期：2026-09-01 | 评估卡：t_est_445d072c | 源卡：t_445d072c
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12）+ DPL-018 校准注入
> 源卡链：t_a5c7400d（[DEV-EST] DPL-101 评估卡，done）→ 产物在 wt/t_a5c7400d @ commit 6d54362 → 本 MERGE 卡落地 main 消除 code-not-in-main
> 有效轮折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）
> 校准注入: 累计偏差 +1.40 → K=2.40（clamp 0.5-3.0）；沿用最近同源 MERGE 卡校准（t_52c4a9c1 2026-08-30 同 K）

## 1. 结论（TL;DR）

**不拆（[SUB-SPLIT] 1）——源卡 t_445d072c 直接执行。校准后 12-22 轮（基准 5-9 × K=2.40，中位 ~17），
落在 42 有效轮预算内（29-52%），且任务原子（2 文件单 commit）、无第二可分离阶段。**

任务本质：**纯 git 机械落地**。把 t_a5c7400d 评估卡产出的 2 个文件从 commit 6d54362
显式单路径提取到 main。卡片已把全部步骤与验证命令给定（见源需求 步骤 1-4），
无设计决策、无发现轮、无代码编写、不依赖 GLM 额度。

**评估期间实测确认（非假设）：**
- commit 6d54362 存在（`git cat-file -t` = commit）✅
- 分支 wt/t_a5c7400d **仍存在**且指向 6d54362（`git rev-parse --verify` 命中）✅
  ——比先例 t_ab21ecc4（从 dangling commit 494ef48 恢复）更简单，无需恢复 dangling 对象
- 两个目标文件在 6d54362 中均命中，尺寸与卡面一致：
  - docs/est/t_a5c7400d-estimate.md = 16703B / 151 行（卡面称 151 行 ✅）
  - .pipeline/wip/t_a5c7400d.md = 2738B / 36 行（卡面称 36 行 ✅）
- main 当前 **LACKS** 两个文件（`git cat-file -e main:<path>` 均 exit 128）✅
  ——确认需落地，消除 code-not-in-main 告警
- main 的 docs/est/ 与 .pipeline/wip/ 目录已存在（各 20+ 评估产物），**无需新建目录**
- 先例已跑通：t_ab21ecc4 同类 MERGE（2 文件 160 行）commit 9d3fb73 在 main 历史中可见，
  模式完全一致（显式单路径 add + commit + cat-file 验证）

## 2. 工作量评估（实测结论，非假设）

改动面：**2 个文件新增**（docs/est/t_a5c7400d-estimate.md 16703B + .pipeline/wip/t_a5c7400d.md
2738B），0 个文件修改/删除。全部为显式单路径 `git show <sha>:<path>` 提取，禁止整分支 merge。

| # | 工作项 | 基准轮数（未校准） | 依据 |
|---|------|:---:|------|
| ① | 领卡 orient + 读源卡 body + 确认产物 commit/分支可用 | 1-2 | 本评估已实测 6d54362 + wt/t_a5c7400d 均在；执行时复核即可（git cat-file -t + rev-parse） |
| ② | 确认 main LACKS 两文件（cat-file -e 预期 exit 128） | 0.5-1 | 本评估已实测 LACKS；执行时复跑一次 |
| ③ | 显式单路径提取两文件（git show 6d54362:path > file × 2）+ git add | 1-2 | 机械命令，卡面已给命令形态；注意工作树在 merge 卡自己的 worktree 上操作 |
| ④ | commit（标题 [MERGE] t_a5c7400d est 评估产物落地 main） | 0.5-1 | 单 commit；message 卡面已给定 |
| ⑤ | push（HERMES_BACKUP_PUSH=1；GIT_SSH_COMMAND 绝对 key 路径） | 0.5-1 | 实测当前 HERMES_BACKUP_PUSH=unset，执行时需显式置 1；SSH 先例 9d3fb73 已 push 成功 |
| ⑥ | 验证：git cat-file -e main:<path> 两文件均命中 + git log 显示新 commit | 0.5-1 | 卡面步骤 4；先例全绿 |
| ⑦ | claim（changed_files 段，DPL-060）+ 飞书推送 + complete | 1-1.5 | 标准闭环；claims 以 cat-file 验证 + commit sha 为主 |

**基准轮数（未校准，合计）：5-9 轮（中位 ~7）。**
**DPL-018 校准：5-9 × K=2.40 → 校准后 12-22 轮**（中位 ~17，42 有效轮预算的 29-52%）
——**单卡可行，不拆**。

## 3. 复杂度与风险

| # | 风险 | 评级 | 说明与缓解 |
|---|------|:---:|------|
| R1 | 执行时 wt/t_a5c7400d 分支已被 dispatcher 清理，commit 6d54362 变 dangling | 低 | 本评估实测分支仍存在；即使被清，`git show 6d54362:path` 按 SHA 仍可提取（先例 t_ab21ecc4 即从 dangling 494ef48 恢复）。唯一例外是 git gc 已 prune 对象——devPPL 仓日常不跑 gc，风险极低 |
| R2 | push 失败（网络/认证） | 低 | GIT_SSH_COMMAND 绝对 key（memory 记录 cron HOME 陷阱）；先例 9d3fb73 push 成功；失败则重试或如实报告，不伪造 |
| R3 | HERMES_BACKUP_PUSH 未设置导致 push 被跳过 | 低 | 实测 unset；卡面已注明"push（若需 HERMES_BACKUP_PUSH=1）"，执行时显式置 1 |
| R4 | 误整分支 merge（把 wt/t_a5c7400d 全部历史带入） | 低 | 卡面明确"禁止整分支 merge"；只 add 2 个指定路径。先例 9d3fb73 仅 2 文件 160 行可对照 |
| R5 | 评估产物与 ARCH v1.1 描述不一致被下游误读 | 低 | 卡面已注明"仅落地历史评估记录，不改 DPL-101 链状态"；本卡不触碰 SUB 卡描述 |
| R6 | 本卡评估产物自身 code-not-in-main | 中 | 先例 R7 同款：docs/est/t_445d072c-estimate.md 会落在 wt/t_est_445d072c，需 OC 后续派 MERGE 卡追回（[PRODUCES] 中明示） |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 5-9 轮（中位 ~7） |
| DPL-018 校准后 | 12-22 轮（×K=2.40），42 有效轮预算的 29-52% ✅ 单卡可行 |
| 20 轮阈值 | 校准上限 22 略超——但超阈值本义是「防单会话超预算」；中位 ~17 ≤ 20，且本卡是**机械 git 落地**（命令卡面全给定），非多模块实现；22 是保守尾端，实际走 ⑤⑥ 验证全绿即收 |
| 任务原子性 | 提取 2 文件 + 单 commit + 验证一气呵成，**无第二可分离阶段**——拆卡无可拆内容 |
| 拆卡开销 | 2 卡 ×（orient + claim + 飞书 + complete）≈ 额外 4-6 轮 > 拆分收益（几乎为零） |
| 代码改动量 | 2 文件纯新增（从已知 commit 单路径提取）——拆卡没有实现分片可拆 |
| 与先例差异 | t_ab21ecc4（同类 MERGE 2 文件，不拆，commit 9d3fb73 全绿）；t_94b55776（2 文件机械落地不拆，校准 19-26）；本卡量级更小（源分支还在，无需恢复 dangling） |
| 历史偏差源 | 最近 timed_out 的 5 条全是**实现卡**（MEM-013/DPL-092 类）；本卡是机械 git 操作，偏差驱动因素弱 |

**决策：不拆（[SUB-SPLIT] 1）——源卡 t_445d072c 按卡面直接执行。**
量级参照：t_ab21ecc4（同类 MERGE，2 文件 160 行，校准 19-26 不拆）——本卡基准更小
（5-9 vs 8-11）且源分支仍存活，预计执行更顺；t_94b55776（2 文件机械落地不拆）。
本卡卡面已把提取命令、commit 标题、验证命令全部给定，无设计决策、无发现轮。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 1
```

- SPLIT: no（count=1；校准 12-22 轮在 42 有效轮预算内，任务原子无第二可分离阶段，
  2 文件纯新增机械落地，拆卡开销 > 收益；历史偏差源为实现卡，本卡为 git 机械卡）
- MODE: N/A（单卡直接执行，源卡已存在 t_445d072c；merge 落地在源卡自身 worktree 内
  操作 main 分支文件——按先例 t_ab21ecc4 模式：显式单路径 add 提交到 main 后 push）
- ROUNDS_EST（校准后）: 12-22（基准 5-9 × K=2.40，中位 ~17）
- FILES: +2（docs/est/t_a5c7400d-estimate.md 16703B + .pipeline/wip/t_a5c7400d.md 2738B，
  均从 commit 6d54362 显式单路径提取，禁止整分支 merge）
- STATUS: not_started（本评估卡待 complete，源卡 t_445d072c 的 parents=[t_est_445d072c]
  done 后自动 promote ready → 直派）
- TESTS: 验收门禁 = ① `git cat-file -e main:docs/est/t_a5c7400d-estimate.md` 命中；
  ② `git cat-file -e main:.pipeline/wip/t_a5c7400d.md` 命中；③ `git log --oneline -1`
  显示 [MERGE] t_a5c7400d est 评估产物落地 main commit；④ （可选）远端 ls-remote 含新 commit
- RISK: R1 源分支被清/dangling（低，SHA 提取兜底）；R2 push 失败（低，绝对 key + 重试）；
  R4 误整分支 merge（低，卡面已禁）；R6 本卡产物自身 code-not-in-main（中，OC 另派 MERGE 追回）
- ACTION: none（不建子卡；源卡 t_445d072c 直接执行）

## 6. 备注

1. **本卡不写功能代码**；产出即本报告 + [SUB-SPLIT] 1 comment + [PRODUCES] claim，
   autopilot 按 count=1 不建子卡，源卡直接执行。
2. **全部关键事实已在评估期间实测**：6d54362 存在、wt/t_a5c7400d 存活、main LACKS 两文件、
   文件尺寸与卡面一致（151 行 / 36 行）、docs/est 与 .pipeline/wip 目录已存在。
3. **先例闭环**：t_ab21ecc4 同类 MERGE（commit 9d3fb73）已入 main 历史，模式完全一致；
   执行时可直接对照 9d3fb73 的 commit stat（2 文件 160 行）作为"无整分支污染"的 sanity check。
4. **push 注意**：当前 HERMES_BACKUP_PUSH=unset，执行时显式 `HERMES_BACKUP_PUSH=1`；
   GIT_SSH_COMMAND 用绝对 key 路径 `/root/.hermes/profiles/orchestrator/home/.ssh/id_ed25519_github`
   （cron HOME=/root 下 ~ 展开错误陷阱，memory 已记录）。
5. **GLM 依赖**：本卡纯 git 操作，不执行任何 cc-glm/Claude Code 步骤；GLM 停机窗口内照常执行。
6. **建议执行顺序**：复核 6d54362 与 LACKS → 单路径提取 2 文件 → add + commit → push →
   cat-file 双验证 + git log → claim（含 changed_files）→ 飞书推送 → complete。
   若提取/提交即失败 → 按 R1/R4 处理，如实报告，不伪造验证结果。
