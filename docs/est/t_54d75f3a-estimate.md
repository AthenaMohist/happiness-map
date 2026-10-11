# 工作量评估 — t_54d75f3a（DPL-215 oc_create_card [CMD]卡assignee机械校验）

- 评估人: game-engine（est）| 日期: 2026-10-05
- 输入: PRD `mem-core/wiki/projects/devppl/prd/dpl215-oc-create-card-cmd-assignee-gate-prd.md`（v1.0）+ actions/DPL-215.md + 前棒 t_e85f8909（R1 校验与 T7-T10 测试已有参考实现，commit ced0b94 @ main，gate 32/0、routing 29/0）

## 范围盘点

| 项 | 内容 | 预估 |
|----|------|------|
| R1 | oc_create_card.sh `_routing_gate_inner` [CMD] 分支加 assignee!=autopilot 拒绝（~10 行，大小写宽容 `^\[[Cc][Mm][Dd]\]`，位置在豁免命中后、[OC-DIRECT] 校验前） | 3-5 轮 |
| R2 | test_oc_create_card_gate.sh 新增 4 用例（拒绝/放行基线/小写/非 CMD 回归边界） | 2-4 轮 |
| 回归 | test_oc_routing_gate.sh + test_oc_create_card_gate.sh 零改动全绿 + bash -n | 1-2 轮 |
| A1-A5 留痕 | dry-run 逐项 + 存量扫描（预期 0 行） | 1-2 轮 |
| 收尾链固定预算 | merge 后验证 / WIP 笔记 / claim 六字段 / finalize / 飞书推送 | +8 轮 |

## 结论

- 基准实现轮 ~8-13，回归两套 gate 测试约 1-2 轮（分钟级），合计总轮次 **预估 18-24 轮**（含收尾 +8；已按校准口径计，K=2.32 下限保护）。
- ≤20 轮门槛边缘 → **不拆卡**（SPLIT: no，与 PRD §6 一致：单文件单函数 + 同文件测试，一棒完成）。
- 复杂度: 低。风险点仅一个——新校验与既有 SUB-2 段大小写正则口径对齐（前棒已验证方案可行）。

[SUB-SPLIT] 1 serial
1. 按 PRD R1+R2 实现 oc_create_card.sh [CMD] assignee 机械校验 + 4 个 gate 测试用例，A1-A5 逐项留痕 + 存量扫描，两套 gate 回归全绿后 claim+飞书推送 预计 18-24 轮
