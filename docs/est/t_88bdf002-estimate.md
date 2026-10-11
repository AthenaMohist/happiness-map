# DPL-173 工作量评估报告（DEV-EST t_88bdf002）

- 评估人: game-engine（cc-glm run2352）| 日期: 2026-09-29
- 输入: PRD v1.0（df14b10）+ ARCH v1.0（5d8a6e9，t_b28beeb0 交付）
- 锚点实勘（本 worktree 3a0fbef 实测）:
  - oc_wake_check.sh 共 1513 行；源 C :257-283 双条件+一次性键 ✓
  - 跳过名单 :1441 现有 11 个 tag，**不含** blocked-still/monitor-nonce（需 +2）✓
  - 输出区 :1488-1512（glm_tail 守卫 / NO_ANOMALY 判定）与 ARCH 引用一致 ✓
  - oc_wake_monitor.sh 存在；全仓非 wiki 引用 = 0（死引用实证，D5 可安全删除）✓
  - tests/ 现有 test_dpl172_* 三个文件，无 dpl173 冲突 ✓

## 1. 工作量拆解

| 项 | 内容 | 预估轮次 |
|---|---|---|
| D1+D2 | blocked_still 查询 + 输出行 + NO_ANOMALY 条件扩展（+~15 行） | 2-3 |
| D3 | monitor-nonce 迁移进主脚本（paused 判定 + 输出，+3 行） | 1-2 |
| D4 | 跳过名单 +2 tag（1 行改动） | 1 |
| D5 | git rm oc_wake_monitor.sh + grep 复核 | 1 |
| T1-T8 | 新增 tests/test_dpl173_oc_wake_blocked_still.py（sqlite 沙箱 + SEEN_FILE 隔离 + bash 入口直跑，沿用 dpl172 模式） | 5-8 |
| 本卡子集门禁 | pytest 该文件 + bash -n，修复迭代余量 | 2-3 |
| 实现小计 | | **12-17 轮** |

## 2. 总轮次（DPL-136 口径）

- 实现轮次: 12-17
- 收尾链固定预算: +8（merge 后验证/WIP 笔记/claim/finalize 四步/飞书推送）
- 回归测试: +2（本卡子集 8 用例已含在实现小计，此项为合并前复跑余量）
- **总预估: 22-27 轮**（≤20 实现有效轮 → 不拆卡，N=1）

## 3. 复杂度与风险点

- 低: D1-D5 全部有 ARCH 精确代码块与锚点行号，照抄级实现。
- 中: T3（paused 状态注入）与 T6（glm 窗口构造）需 mock autopilot_tail 路径——dpl172 测试有现成基建可复制，风险可控。
- 低: D5 删除面经 grep 实证零外部引用；jobs.json 零改动。
- 校准说明: 历史偏差 K=2.53 主要来自 timed_out 级大卡；本卡变更面 ~30 行 + 1 测试文件，属小卡，按基准口径评估未额外放大。

## 4. 决策

**[SUB-SPLIT] 1 serial — 不拆卡**，单张 dev 卡串行完成（实现 12-17 轮 < 20 轮阈值）。

## 5. 交付物

- 本报告: docs/est/t_88bdf002-estimate.md
- [SUB-SPLIT] comment（N=1 serial）
