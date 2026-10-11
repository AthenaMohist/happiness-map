# 工作量评估 — MEM-017 wiki 访问账户 + 四信号埋点（指针收口）

> est 卡: t_fa01a360 | 评估人: game-engine | 日期: 2026-10-06

## 1. 输入

- PRD: mem017-signal-account-pointer-prd.md v1.0（指针型收口文档，不新开实现范围）
- 架构: arch-mem017-signal-account-pointer.md v1.0（指针型架构，设计真源 = MEM-008 R2 架构）
- 前棒卡 t_3d4e3515（arch）已交付实锚复验 V1-V3 通过

## 2. 实现范围盘点（= 0 新实现）

| 项 | 结论 |
|----|------|
| schema/接口/埋点 | 无——R2 已全部交付（record_signal/resolve_actor/MEM_ACCESS_ACTOR/page_signal 实锚 main） |
| 测试 | 无新增——tests/test_mem008_r2_signal.py 14 用例在库 |
| 回归 | 无需全量——零代码改动 |
| 本卡实际工作 | 纯文档/状态收口：确认任务页 MEM-017 status=done 行到位（PRD §3 A2 称已更新）+ est 结论落卡 |

## 3. 工作量估算（DPL-136 口径：总轮次 = 实现轮 + 收尾链 8 + 回归轮）

- 实现轮（文档核对 + 收口确认）：3-5 轮
- 收尾链固定预算：+8 轮
- 回归测试轮：0（零代码改动，跑本卡 targeted 子集 ≤1 轮，计入收尾）
- **合计：11-13 轮**

按偏差校准 K=2.32 上限口径：约 25-30 轮（纯文档卡历史偏差主因是审批/竞态空转，非工作量本体）。

## 4. 决策

总轮次 ≤20 → **不拆卡，[SUB-SPLIT] 1 serial，建 1 张 dev 收口卡**。

风险点：
1. 任务页 status 若未实际更新 → 收口卡补一行（轻微，+2 轮内）
2. PRD/架构页均在 mem-core 仓库（wiki/），dev 卡需跨 repo 落文档——按前棒惯例 claim 落 kanban、wiki 不动（PRD/架构 v1.0 已是最新版，无需改）
