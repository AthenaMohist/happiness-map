# 工时评估 — t_458ccc3c（[FIX] DPL-217 [OC-VA] 抽查本轮 OC 合并收口）

- 评估卡: t_est_458ccc3c（run 3639）
- 源卡: t_458ccc3c（assignee=verifier，执行模式 CC-MAX，scratch 工作区）
- 评估日期: 2026-10-07

## 1. 源任务需求摘要

DPL-137 抽查模板，对 OC 本轮合并收口（[OC-DIAG] comment 14751）做 6 项独立核验：

1. devPPL main 含 ce39226 + timeout_patrol.py 含 repeat_retry/is_wall_clock（git grep 实锚）
2. devPPL 备份 push 成功（backup_ledger.json / backup-push.log 查 dd702bf14）
3. mem-core main 含 7fe8c3d5 + arch-dpl217 wiki 页在 main
4. mem-core 远端 origin/main = 7fe8c3d5（ls-remote 实锚）
5. pytest tests/test_dpl158_patrol.py 复跑 41 passed
6. 反例核验：t_394de96e 是否真的该 done（ARCH 产出合规性）

## 2. 工作量评估

- 轮次：每项核验 = 1-2 个只读命令（git log/grep、ls-remote、read_file、pytest 子集），6 项合计 8-12 个命令 + 汇总落卡 2-3 轮。
- 预计 **8-12 轮**（留 pytest 后台余量则上限 ~15 轮）。
- 复杂度：低。全部为只读核验，零代码改动，无合并冲突面。
- 风险点：
  - 第 5 项 pytest 复跑需在 devPPL 工作区执行（>2min 任务按 DPL-172 后台 + notify）；
  - ls-remote 依赖网络/SSH key（已知走绝对路径 GIT_SSH_COMMAND）；
  - comment 14751 属 OC 卡 comment，如 kanban_show 无法直达需 devppl_query.sh 查 events。

## 3. 决策

预计 ≤20 轮 → **不拆卡**。[SUB-SPLIT] 1 serial，N=1：整卡由 verifier 单卡完成即可，无需子任务。

## 4. 产出

- 本文档: docs/est/t_458ccc3c-estimate.md（commit @ wt/t_est_458ccc3c）
