# 工作量估算 — [MERGE] DPL-980 estimate 报告择合 main（t_0d7c4091 缺口补卡）

> 估算卡: t_est_87009a9e（DEV-EST）| 估算人: game-engine（寇豆码）| 日期: 2026-09-27
> 源卡: t_87009a9e（[MERGE] 缺口补卡，OC-DIRECT 唤醒巡察检出 chain-missing-merge）
> 校准: K=2.53（DPL-018 注入）

## 1. 任务定性

**机械合并卡**（DPL-126 择合先例），非功能开发：

- 唯一产线: 把 wt/t_0d7c4091 上的 commit 74e479d cherry-pick 到 main——该 commit 只含一个新增文件 `docs/est/t_0d7c4091-estimate.md`（38 行，已实测 `git show 74e479d --stat` 确认单文件零冲突面）。
- 无代码路径改动、无 pytest 子集（纯 docs 产物，DPL-137 合并后验证口径即可）。

## 2. 工作量构成（DPL-136 三项合计口径）

| 项 | 基准轮 | 说明 |
|---|---|---|
| 实现轮 | 3 | cherry-pick 74e479d → main（含 worktree/分支切换）1 轮；grep/log 实锚验证 1 轮；push 备份远端 1 轮 |
| 收尾链固定预算 | 8 | claim 六字段/finalize/飞书推送/kanban 状态操作（t_b4014d10/t_b185e090 实证） |
| 回归测试 | 0 | 零代码改动，仅 `git grep` 实锚验收 |

## 3. 校准后预估（K=2.53）

- 实现轮校准: 3 × 2.53 ≈ 8 预算轮
- 总预算: 8 + 8 = **16 预算轮**；有效轮 ≈ 16 × 0.7 ≈ **11 有效轮**

## 4. 决策

- **≤20 有效轮 → 不拆卡**。[SUB-SPLIT] N=1 serial。
- 复杂度: 低（单文件、单 commit、无冲突面）。风险点: 仅 push 备份远端环节（历史 HTTPS 故障，走 SSH 绝对 key 路径，已有成熟绕法）。

## 5. 子卡交付定义（给下游 merge 卡的输入）

1. `git cherry-pick 74e479d` 到 main（该 commit 仅 docs/est/t_0d7c4091-estimate.md，天然无夹带）。
2. 验收实锚: `git log main -- docs/est/t_0d7c4091-estimate.md` 非空 + `git grep` 文件存在于 main。
3. push 备份远端成功（GIT_SSH_COMMAND 绝对 key 路径）。
4. claim 含 changed_files=[docs/est/t_0d7c4091-estimate.md] + merge commit SHA。
