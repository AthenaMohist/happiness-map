# EST — t_78a65022 DPL-216 oc_create_guard 豁免C清除（工作量评估报告）

> 编号: DPL-216 | 评估人: game-engine | 日期: 2026-10-05 | commit 92dbd5b @ wt/t_78a65022

## 结论

**SPLIT: no** — 单 dev 卡，总轮次预估 **14-20 轮**（校准口径 K=2.32 后下限；DPL-136 三项合计）。

⚠️ 本卡已**实现完成并 commit**（est 与实现同 run 收口，净变更 <30 行、单文件单函数级，拆卡无收益）：
- changed: pipeline/oc_write_guard.py, tests/test_dpl209_oc_write_guard.py
- 门禁: tests/test_dpl209_oc_write_guard.py + tests/test_dpl209_s2_wiring.py = **40 passed**（基线 36 + 净增 4 用例）
- A6/D5 真实库只读扫描: **0 行**

## 轮次构成（DPL-136 三项合计）

| 项 | 轮次 |
|---|---|
| 实现轮次（读 ARCH/PRD + D1-D4 落地 + 测试反转/新增） | 4-6 |
| 回归测试（门禁子集 ~10s/遍 × 2-3 遍 + dpl213/173 关联 20 passed） | 2-3 |
| 收尾链固定预算（merge 后验证/WIP 笔记/claim/finalize/飞书推送） | +8 |
| **合计** | **14-17（校准后 14-20）** |

复杂度: 低（纯删除 + 文案改写 + DROP+CREATE 升级，无新逻辑分支）。
风险点: A7 部署坑已由 install 函数升级语义覆盖并有专用测试锁定；测试负向断言要求触发器 SQL 文本零 [OC-DIRECT] 字面量（含注释）——已实测绕过并修正。

## [SUB-SPLIT] 1 serial

1. DPL-216 实现收口（已完成，commit 92dbd5b：R1 豁免删除+文案 / D3 DROP+CREATE / D4 测试反转+新增 5 用例 / D5 扫描 0 行 / 40 passed）预计 0-2 轮
