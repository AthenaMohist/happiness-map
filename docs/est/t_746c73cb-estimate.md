# EST 评估 — t_746c73cb / DPL-217 超时分类器覆盖不足根修

> 日期: 2026-10-07 | 评估人: game-engine | est_rounds=2
> PRD: wiki/projects/devppl/prd/dpl217-timeout-classifier-coverage-prd.md（v1.0，A1-A4 + AC1-AC6）
> 架构: wiki/projects/devppl/arch/arch-dpl217-timeout-classifier-coverage.md（v1.0，已裁定）

## 1. 现状核对（本 EST 卡盘点时的实测）

实现工作已在架构卡（t_394de96e）交付链内完成并落在
`fix/dpl217-timeout-classifier`（devPPL commit **ce39226**）：

- A1 repeat 分支 done 豁免（L563 三分支统一，与 DPL-201 对齐）
- A2 repeat 入口循环型检测放宽（落 `_history_signals`，L279-282）
- A3 墙钟超时显式归 F2（`is_wall_clock()` 纯函数 + 级联位置 F2 后、F5 兜底前）
- A4 rounds 不可知子集日报单独计数（report 层观测，分类器保持纯函数）
- 测试: `pytest tests/test_dpl158_patrol.py -k "dpl217 or wall or repeat or done"` → 14 passed（本卡复验通过，0.88s）
- AC6 dry-run 门禁: 未分类占比 0% < 30%（arch 卡 §3 实测）
- arch 卡 claim: "AC 复验 14 passed、dry-run 未分类占比 0%<30% 门禁"，与实测一致

## 2. 工作量评估

| 项 | 评估 |
|---|---|
| 复杂度 | 低。改动集中在 timeout_patrol.py 单文件四处，实现已锚点一致 |
| 风险点 | 仅合并链：实现分支待 OC 合并回 main；无新码风险 |
| 基准轮次 | 实现 0 轮（已完成）+ 复验/报告/收尾 ~6 轮 |
| K=2.32 校准后 | **6-8 轮**（含收尾链固定预算） |

## 3. 拆卡决策

**≤20 轮 → 不拆。** [SUB-SPLIT] 1 serial
1. DPL-217 收口复验+合并准备（实现已在 fix/dpl217-timeout-classifier ce39226，本卡无新码） 预计 6-8 轮

## 4. 结论

- [PRODUCES] docs/est/t_746c73cb-estimate.md（本文件，commit @ wt/t_746c73cb）
- 实现真源: devPPL fix/dpl217-timeout-classifier @ ce39226，待 OC 合并回 main
