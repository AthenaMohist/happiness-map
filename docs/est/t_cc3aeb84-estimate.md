# Estimate — t_cc3aeb84 / INF-022 watchdog 双副本漂移根治

评估人: game-engine | 日期: 2026-10-06 | 依据: PRD v1.0 (inf022-watchdog-dual-copy-prd.md, commit 26569124)

## 1. 范围盘点（R1-R4 → A1-A6）

| 需求 | 内容 | 交付面 | 复杂度 |
|------|------|--------|--------|
| R1【P0】 | 8 个 profile-only 脚本回填 repo + DEFAULT_SYNC_LIST 追加 + jobs.json 引用断言脚本（缺失即 FAIL） | scripts/ 8 文件搬入 + 断言脚本 + 清单改动 | 中（搬运机械，断言需红绿验证） |
| R2【P0】 | kanban_watchdog.py 三副本 + meta.json + sentinel_alert.sh.bak 清零，md5 留痕 | 删除操作 + 留痕记录 | 低（但硬约束：必须在 A1 断言网落地之后） |
| R3【P1】 | deploy_drift_check.sh 报告 pass 增"清单外扫描段"（[deploy-drift-x] 告警）+ scripts/deploy_drift_ledger.md 台账 36 项登记 | shell 改动 + 台账 md | 高（报告段三态判定 + 告警通道接入 + 不改 tick 退出码 + A3 红绿验证） |
| R4【P1】 | 死副本机制化扫描（[dead-copy] 告警，seen 去重）+ deploy-drift-mode.md 增补⑥⑦ + docs/wiki 双写互链 | shell 新段 + 2 处文档 | 中（A4 红绿验证） |

## 2. 风险点

1. R2 删除的前置硬约束（先 A1 断言网后动刀）→ 决定 R1/R2 必须串行，不能并行。
2. deploy_drift_check.sh 是 cron 直调 + profile 部署双副本文件（deploy-drift 规则适用），改动后需 md5 同步留痕，且验收时 tick 实跑不能破坏 fail-open exit 0 语义。
3. 台账 36 项逐项"三选一 + 理由"需要实勘每个脚本被谁引用（kanban_collector/watchdog 系调用关系），是 R3 里最耗轮次的环节。
4. kanban_watchdog.py 实勘调用方（R2）若发现隐藏调用方需改走真源回填分支，留缓冲。

## 3. 轮次估算（含校准 K=2.32 口径）

实现基准合计 ~22 轮（R1: 6 / R3: 10 / R4: 4 / 文档双写: 2），校准后有效轮远超 20 → **拆卡**。

## 4. 拆卡决策

串行 2 卡（R2 依赖 R1 断言网，R4 依赖 R3 告警通道，天然 serial）：

1. **DEV-FIX-A：R1 + R3** —— 8 脚本真源回填 + SYNC_LIST 追加 + jobs.json 引用断言（A1）+ deploy_drift_check.sh 清单外扫描段 + [deploy-drift-x] 告警 + ledger 台账 36 项登记（A3）。预计 18-24 轮（含回归与收尾链）。
2. **DEV-FIX-B：R2 + R4** —— kanban_watchdog 三副本清零 + .bak 清除（md5 留痕，A2）+ [dead-copy] 机制化扫描（A4）+ deploy-drift-mode.md ⑥⑦ + wiki/docs 双写互链（A6）。预计 12-16 轮。

A5（bash -n + 本卡子集测试）随各卡自带。

## changed_files（本卡）

- docs/est/t_cc3aeb84-estimate.md（新增，本评估报告）
