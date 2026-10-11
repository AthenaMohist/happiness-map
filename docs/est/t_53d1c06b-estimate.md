# 工作量评估 — t_53d1c06b（BKP-005 SandboxHermesBackup 增量包保留策略）

- 评估人: game-engine（est）| 日期: 2026-10-05
- 输入: PRD `mem-core/wiki/projects/devppl/prd/bkp005-sqlgz-retention-prd.md`（v1.0）+ 架构 `arch-bkp005-sqlgz-retention.md`（v1.0，前棒卡 t_c32b165e）
- 实测核验: hermes_backup_push.sh 1153 行在场；:505 `--exclude='incremental/'`、:187 锁、:748 BACKUP_TEST_STEP45 钩子均与架构 F1/F2/F3 一致；树上 sql.gz 现值 5876 个；顶层 incremental/（09-26 devppl bundle + 各 profile 旧目录）在场；config/incremental 8.2M（首跑 tar 归档成本可忽略，架构 §2.4 成立）。

## 范围盘点

| 项 | 内容 | 预估 |
|----|------|------|
| R2 exclude | rsync exclude 追加 `--exclude='cache/scratch/'` 一行 | 1 轮 |
| R1 prune_backup() | ~60 行纯 bash 三段（P1 scratch 存量 rm / P2 增量切片 14 天滚动+周归档 / P3 顶层 incremental/ 清除），插 Step 4.6（:748 早退钩子后），DRY_RUN + PRUNE summary 留痕 | 4-6 轮 |
| 首跑前置 | tar 归档 config/incremental + commit（架构 §2.4 硬性要求） | 1-2 轮 |
| R3 复核 | 既有 BKP-004 flock（:187-192）回归断言 A4，零新增代码（架构 §3 已裁定偏离 PRD 锁路径） | 1-2 轮 |
| A1/A5 验证 | bash -n + DRY_RUN=1 BACKUP_TEST_STEP45=1 干跑 + ls-tree 计数断言；A3 恢复演练 slice 对账 | 2-4 轮 |
| 收尾链固定预算 | merge 后验证 / WIP 笔记 / claim 六字段 / finalize / 飞书推送 | +8 轮 |

## 结论

- 基准实现轮 ~9-15，合计总轮次 **预估 20-28 轮**（含收尾 +8；已按校准口径计，K=2.32 下限保护）。
- ≤20 轮门槛边缘偏上 → **不拆卡**（SPLIT: no）：改动收敛在 hermes_backup_push.sh 单文件 + 一个新函数 + 一行 exclude，PRD §6 回滚口径与架构 §7 边界清单均按单棒设计；拆卡反而引入首跑前置（tar 归档）与 prune 的跨卡时序依赖。
- 复杂度: 低-中。风险点两个：① prune 时序必须在 rsync/Step4.5 之后、git add 之前（架构 §6 明令不得调换）；② P2 周归档按 ISO 周分组的 bash 实现（date +%G-W%V）需测试边界；③ 测试必须组合 BACKUP_TEST_STEP45=1 防干跑产生真 commit。

[SUB-SPLIT] 1 serial
1. 按架构 §2/§4 实现 prune_backup()（三段删除 + DRY_RUN + PRUNE summary）与 rsync exclude 一行，完成首跑 tar 归档前置与 R3 flock 回归断言，A1/A3/A4/A5 逐项留痕，bash -n + 干跑全绿后 claim+飞书推送 预计 20-28 轮
