# 工作量估算 — DPL-980 编号复用验证主题（DEV 卡）

> 估算卡: t_0d7c4091（DEV-EST）| 估算人: game-engine（寇豆码）| 日期: 2026-09-28
> 上游: PRD v1.0（t_ded0bdec done）+ ARCH v1.0（t_d13ee4ea done，commit 90decb0）
> 校准: K=2.53（DPL-018 注入，累计偏差率 +1.53）

## 1. 任务定性

本链是**验证链**，不是功能开发：

- PRD A3 + ARCH G3 双重钉死：零生产代码改动、零 kanban 写（claim 除外）、不跑全量 pytest。
- ARCH C3 结论：无需任何 [FIX] 卡——负例判新链、正例判 repair 都是设计行为。
- 下游 dev 卡实际工作 = 复跑 ARCH §1 探针 P1-P3（classify_chain 只读复算）+ 产出验证报告页（wiki/projects/devppl/verify/ 或 dev 卡 body 约定位置）。

## 2. 工作量构成（DPL-136 三项合计口径）

| 项 | 基准轮 | 说明 |
|---|---|---|
| 实现轮（探针复跑+报告页） | 8 | P1/P2 classify_chain 探针 2 轮、P3 wiki 页谓词核验 1 轮、报告页撰写+mem-core commit 3 轮、缓存损耗 2 轮 |
| 收尾链固定预算 | 8 | merge 后验证/WIP 笔记/claim/finalize 四步/飞书推送（t_b4014d10/t_b185e090 实证） |
| 回归测试 | 0 | 零代码改动，无 pytest 子集需跑；判定层探针即测试（ARCH G3） |

## 3. 校准后预估（K=2.53）

- 实现轮校准: 8 × 2.53 ≈ 20 预算轮
- 总预算: 20 + 8 = **28 预算轮**；有效轮 ≈ 28 × 0.7 ≈ **20 有效轮**

## 4. 决策

- **≤20 有效轮 → 不拆卡**。[SUB-SPLIT] N=1 serial。
- 复杂度: 低（全只读探针，无代码路径改动）。风险点: 仅 mem-core commit/push 环节（历史 HTTPS 故障，走 SSH 绝对 key 路径，已有成熟绕法）。

## 5. 子卡交付定义（给下游 dev 卡的输入）

1. 复跑 P1: `classify_chain(KANBAN_DB, 'DPL-980', …)` → 期望 `{chain_kind: new, basis: 默认}`。
2. 复跑 P2: `classify_chain(KANBAN_DB, 'DPL-172', …)` → 期望 `{repair, 编号复用, repair_code: DPL-172}`。
3. 复跑 P3: `wiki/actions/DPL-980.md` 不存在 / `DPL-172.md` 存在，与 L2 同源谓词一致。
4. 产出验证报告页（含探针输出原文 + 与 ARCH P1-P3 一致性结论），commit 到 mem-core，[PRODUCES] 报告页路径。
