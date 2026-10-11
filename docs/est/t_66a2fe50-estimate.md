# 工作量评估 — t_66a2fe50（合并 wt/t_f772a2ee 入 main 并核实 DPL-056 其余分支跳过）

评估卡: t_87495388 · run 3727 · 2026-10-07

## 实测状态（git 实证）

### 目标分支 wt/t_f772a2ee
- tip = 3852c62「[WIP] glm-shutdown checkpoint 20260928T055559Z」
- `git merge-base --is-ancestor wt/t_f772a2ee main` → rc=1（tip 未入 main）
- `main..wt/t_f772a2ee` = **仅 1 个 commit**
- 该 commit 改动仅 `.pipeline/registry_gap.tsv`（+5 行，registry gap 追加记录）

### 冲突预判
main 的 registry_gap.tsv 是分支版本的**严格超集**（分支全部行均已在 main，且 main 另有更晚的追加行，
如 MEM-007 1790442671+、INF/DPL-167 后续条目）。合并若冲突 → 取 main 侧（--ours），零改动丢失。

### 17 个跳过分支核查方法
逐个 `git rev-parse wt/<name>` + `git merge-base --is-ancestor`：分支缺失（被 dispatcher 清理，
tip 已 squash/merge 入 main）或 tip 已是 main 祖先 → 记录证据即可，无需合并。

## 工作量估算（DPL-136 三项合计口径）

| 项 | 轮次 |
|---|---|
| 实现（merge + 冲突取 ours + 17 分支核实 + 验证 tip 入 main） | 3-5 |
| 回归测试（本卡无代码逻辑改动，registry_gap.tsv 为运行时数据文件，targeted 冒烟即可） | 1-2 |
| 收尾链固定预算（merge 后验证/WIP 笔记/claim/finalize 四步/飞书推送） | 8 |
| **合计** | **12-15 轮** |

- 有效轮数 ≈ 4×0.7 ≈ 3 有效轮 + 回归 + 收尾 → 远低于 30 有效轮拆卡线
- 复杂度：低（单文件数据超集合并，解冲突策略唯一且机械）
- 风险点：① main 工作树有未提交的 .pipeline 运行时状态（归 OC/autopilot 管，merge 时需干净区，
  建议子卡在 main 工作树独占窗口内执行）；② 17 个跳过分支中部分已被 dispatcher 删除，核实依据 =
  ref 缺失 + 同名任务卡已 merge 记录，属正常状态非异常。

## 决策

**≤20 轮 → 不拆卡。[SUB-SPLIT] 1**（serial 单卡执行，指派 game-engine，CC-MAX）

预估 changed_files: main..wt = `.pipeline/registry_gap.tsv`（合并结果 = main 现状，实际 net diff 可能为零）
[FILE-COLLISION] none
