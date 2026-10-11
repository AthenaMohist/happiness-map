# EST 评估报告 — t_3d6c1acf（DPL-203 链关系真源归一 DEV 实现卡）

> 评估人: game-engine（DEV-EST）| 日期: 2026-10-03
> 输入: PRD v1.0（dpl203-chain-truth-db-edge-prd.md）+ ARCH v1.0（arch-dpl203-chain-truth-db-edge.md，父卡 t_7e1aa547 交付 9a9baad）

## 1. 工作量盘点（ARCH §4 T1-T8）

| 项 | 内容 | 基准轮数 | 复杂度 | 风险点 |
|---|---|---|---|---|
| T1 | chain_edges.py 新模块（parents_of/children_of + 薄 CLI + fail-open 读） | 2 | 中 | fail-open 语义对齐 drift._kanban_links；薄 CLI 参数设计 |
| T2 | 门限 a 换元 cmd_channel.sh:495-511 | 1 | 低 | shell 内嵌 python 改 import；grep 门禁验证 R1 |
| T3 | FIX_GATE 换元 cmd_channel.sh:527-566 | 1 | 低 | [FIX] 意图 token 判定不动，仅挂靠验证换源 |
| T4 | classify_chain L1 收敛（cmd_chain.py:1451-1511） | 2 | 中 | 意图 token 与编号反查拆分；wiki/actions 页编号读取兜底 refused 路径 |
| T5 | 建卡写边 fail-closed（oc_create_card.sh 尾段 + validate 调用方） | 1-2 | 中 | 测试桩模拟写边失败；dry-run 路径豁免区分 |
| T6 | chain_edges_audit.py 对账脚本 + chain_check.sh 接入 [chain-drift] | 2 | 中 | 幂等标记对齐 [chain-gap] 模式；--db 注入 |
| T7 | 红绿测试（I4 用例固化 + 既有子集适配） | 2-3 | 中 | 既有 test_parents_parse/test_cmd_channel 用例断言换源后需适配；隔离 temp db（R4） |
| T8 | 生产库对账实跑（只读）+ 差异清单交 OC | 1 | 低 | 不触碰生产写路径 |

实现基准合计: **12-15 轮**

## 2. 总轮数（DPL-136 三项合计口径）

- 实现轮次: 12-15（含发现/调试损耗已按保守取值）
- 回归测试轮次: 子集 `pytest -k "chain_edges or parents or cmd_channel"` 每遍 ~1-1.5 轮 × 预计 2 遍 ≈ 2-3 轮
- 收尾链固定预算: +8 轮（merge 后验证 / WIP 笔记 / claim / finalize 四步 / 飞书推送）

**总轮数 ≈ 22-26 轮**；按有效轮口径（×0.7 迭代预算）≈ 预算 31-37 轮。
K=2.53 历史校准已隐含在保守基准中（实现项多为点状改造 + 新模块有 DPL-195 registry_gate 同构模板可抄）。

## 3. 拆卡决策: **不拆（单卡 T1-T8 原子上线）**

- ARCH §7 明确论证：拆卡会产生「gate 已换元、classify 未换」的中间态——口径分裂正是本卡要根除的对象。
- 总轮数 22-26 < 42 拆卡线（有效轮 ~24 < 30）。
- 风险兜底: 若 run 内 50 轮触发 wind-down，按 [CHECKPOINT] 五字段存档 + M1-M4 里程碑断点继承（M1=T1-T2 / M2=T3-T4 / M3=T5-T6 / M4=T7-T8，均为可验证单元）。

## 4. 风险点汇总

1. classify_chain L1（T4）逻辑最重，弃读 body「编号:」行后 wiki/actions 页缺失场景须维持 refused（ARCH §6 记录项），不得放宽。
2. T5 fail-closed 与 dry-run 路径的区分容易误伤（dry-run 建卡预演不应拒交付）。
3. 既有 test_parents_parse.py 语义在换元后「生产门禁禁 import」与「对账保留」并存，grep 门禁（R1）需精确锚定生产路径。

## 5. 结论

[SUB-SPLIT] 1 serial —— 单卡交付 game-engine，T1-T8 按 M1-M4 顺序推进。
