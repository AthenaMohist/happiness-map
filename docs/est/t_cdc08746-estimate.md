# 工作量评估 — t_cdc08746（DPL-184 DEV-EST）

## 结论：不拆卡（[SUB-SPLIT] 1 serial），预计 6-8 有效轮

## 实锚核验（2026-10-02，main 工作区 + worktree 实测）

| 项 | 证据 | 判定 |
|---|------|------|
| A1 无@ claim 识别 | main:scripts/oc_wake_check.sh:597-605 正则放宽 `(?:@\s+)?`，注释含 DPL-184 + t_c82b079f 案例锚点（C3 ✓），_is_git 守卫（A3 ✓） | 已落地 |
| A2 仓名前缀剥前缀归仓 | main:scripts/oc_wake_check.sh:502-512，非 git → None fail-open，workspace_path 兜底保留在其后（A4 ✓） | 已落地 |
| A5 回归测试 | tests/test_dpl184_oc_wake_noat_claim_repo.py 在 main；本 run 实跑 4/4 PASS（含反例） | 已落地 |
| A6 门禁子集 | 本 run 实测：dpl173/dpl180/dpl184 子集 20/20 PASS + bash -n OK | PASS |
| 父卡 claim | commit 0f3544b（devPPL main），test_dpl184 3-4 例 + oc_wake 子集 20 绿 | 一致 |

## 风险点
- 无实现风险：A1-A6 全部由父卡 t_d9ac83fa（arch）3 分钟前落地 main，本卡仅评估+收尾。
- 附属部署提示：oc_wake_check.sh 为 repo 路径执行脚本（autopilot 内部调用者），不适用 cron live 副本 must-sync 规则（DPL-048）。

## 预算口径（DPL-136 三项合计）
- 实现轮次：0（父卡已落地，本卡纯核验）
- 回归测试：~2 轮（子集 8.5s/遍，实跑两遍）
- 收尾链固定：+8 轮（estimate/claim 文件/finalize 四步/飞书推送）
- 历史偏差校准 K=2.53 不适用于零实现轮次场景；合计 6-8 有效轮，远低于 20 轮拆卡线。
