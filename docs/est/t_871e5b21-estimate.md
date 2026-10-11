# 评估报告 — heartbeat 子卡进度不可见 — 拆卡步骤渲染"N/M🔄"（完成数/总数，DPL-024）

> 评估人：寇豆码（game-engine） | 日期：2026-08-13 | 评估卡：t_est_871e5b21
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）
> 源卡：t_871e5b21（[FIX] heartbeat 子卡进度不可见 — 拆卡步骤渲染"N/M🔄"（完成数/总数），DPL-024）
> 代码基线：main @ 98fd056

## 1. 结论（TL;DR）

**不拆（[SUB-SPLIT] 1）——单卡预计 9-13 轮（中位 11）≤ 20 轮阈值，单会话可完成。**

改动集中在 1 个渲染函数 + 1 个测试文件：`scripts/notify_check.py` 的 `_render_chain_line` 补子卡计数（约 +25 行），`scripts/test_notify_check.py` 更新 5 条旧断言 + 新增 6 组测试。无 schema 变更、无新模块、无跨库读写、无 prompt 面改动。

## 2. 工作量评估（读码结论，非假设）

### 2.1 现状基线（实测）

- 子卡归并逻辑在 `_render_chain_line`（notify_check.py L1450-1561）：`_merge_sub_status`（L1425-1447）只归并**状态**（blocked > running > 全一致 > 混合→running），**无计数结构** → 渲染 `研发🔄` 裸状态。
- 4 个子卡归并点：L1497（title `[DEV-SUB-N]` 无 step_name）、L1500（title `[QA-EXEC-SUB-N]`）、L1507（step `dev-sub-*`）、L1510（step `qa-exec-sub-*`）→ 全部并入 `sub_status["dev"/"qa-exec"]`。
- 渲染点 L1530-1550：`multi = len(nodes) + (1 if sub_st else 0) > 1` 决定紧凑/时间线；子卡节点走 `_step_node(label, sub_st, timeline=multi)`。
- `_merge_sub_status` 另有两处调用：`_current_step_card`（L2464/2467，摘要「当前阶段」推导）与 `_done_parts`（L2595/2598，摘要「已完成步骤」）——**只归并状态，不需要计数**；本卡不动它们（见 D1）。
- 存量测试：test_notify_check.py 3256 行，main() 注册 t1-t83，含 t_95ec1a49 新增的 T60-T63（子卡归并 blocked 优先，fixture 模式可直接复用）。

### 2.2 改动清单

| # | 项 | 内容 | 预估轮数 |
|---|----|------|:---:|
| ① | 计数结构 | `_render_chain_line` 新增 `sub_counts: dict[str, dict]`（done/total）；新 helper `_merge_sub_count`（~8 行）或并入 `_merge_sub_status` 传双 dict | 1 |
| ② | 4 个归并点计数 | L1497/1500/1507/1510 各补 total++，status==done 时 done++ | 1 |
| ③ | 渲染 | 子卡节点有计数时：紧凑 `研发 1/2🔄`、时间线 `研发 1/2(🔄)`（`_step_node` 增 count 参数或内联）；无子卡走原逻辑零改动 | 1-2 |
| ④ | 旧断言更新 | T60-2（`研发🚫`→`研发 2/3🚫`）、T61-2（`执行🚫`→`执行 1/2🚫`）、T62-1（`研发✅`→`研发 2/2✅`）、T63-1（`研发🔄`→`研发 0/2🔄`）、T63-3（`研发🔄`→`研发 1/2🔄`）——旧格式被新格式显式取代，属预期更新 | 1 |
| ⑤ | 新增测试 | T84 验收 e2e（SUB-1 done + SUB-2 running → `研发 1/2🔄`）；T85 全 done → `研发 2/2✅`（复用 T62 fixture + running prd 防 ✅✅ 精简）；T86 回归（单 dev 卡无子卡 → `研发🔄` 不变）；T87 qa-exec 计数（`执行 1/2🔄`）；T88 title 归并路径（无 step_name 的 `[DEV-SUB-N]` 也计数）；T89 时间线兼容（base 历史节点 + 子卡 → 计数在子节点、历史节点不变） | 2-3 |
| ⑥ | 全量回归 | test_notify_check.py 全量（~300+ 断言，单次 2-5 min），预计 1-2 次迭代修 fallout | 2-3 |
| ⑦ | 收尾 | commit + [PRODUCES] + 飞书推送 | 1 |

**预计总轮数：9-13 轮（中位 11）** ≤ 20 轮阈值 → **不拆**。

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| R1 断言子串误判 | **低** | 新格式 `研发 1/2🔄` 不含子串 `研发🔄`/`研发✅`，存量负向断言（T60-3/T62-2,3/T63-2,4/T47-3/T51-3/T55-4）均不受影响；受影响的正向断言仅 T60-2/T61-2/T62-1/T63-1/T63-3 共 5 条，均为 t_95ec1a49 的子卡测试，格式被本卡显式取代 |
| R2 时间线 × 计数交互 | **低** | 同 step 多卡（超时→重启→完成）是 base 卡历史节点，子卡计数只挂在子节点：`研发(超时⌛)→研发 1/2(🔄)`。需 T89 锁断言 |
| R3 `_chain_is_all_done` 交互 | 低 | 全链 done（含子卡）仍走 `✅✅ 链名` 精简行；子卡全 done 但其它 step running → `研发 2/2✅`（T85 用 running prd 卡构造，同 T62 手法） |
| R4 无子卡回归 | 低 | 计数只在 `sub_counts.get(step)` 有值时渲染；单卡链 T27/T43/T46 等断言零影响（已核对 60+ 处 `研发`/`执行` 断言） |
| R5 冲突面 | 低 | notify_check.py 近 3 个 FIX 均已合 main（0bab3b5/5a63105/f96d855）；在途 DPL-018/019 改 cmd_chain.py/discover.py，不碰 notify_check.py 渲染区；测试文件同理由本卡独占 |
| R6 超时符号语义 | 低（注意） | 子卡节点 currently 不携带 ever_timed_out（`_step_node` 子卡调用恒 False）；计数不改变该语义。若未来要「子卡超时也算 ⏰」属范围外，另卡 |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 预计轮数 | 9-13 轮 ≤ 20 轮阈值 → **不拆** |
| 模块依赖 | 单文件内改动（notify_check.py + 其测试），无跨模块依赖 |
| 拆卡收益 | 无——改动面小、fixture 现成、单会话余量充足（13 轮 vs 60 轮预算） |
| 兜底 | 若实现中发现断言波及面超预期（如摘要 `_done_parts` 也被要求加计数），可按「渲染主链路 / 测试对齐」拆 2 张串行子卡——但按现读码结论不需要 |

**决策：不拆（[SUB-SPLIT] 1），单卡可完成。** 与同系列 t_est_95ec1a49（8-14 轮 → 不拆）量级一致。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 1
1. [DEV-DEV] DPL-024 heartbeat 子卡进度计数渲染（game-engine，单卡 9-13 轮）
   a. scripts/notify_check.py：新增 _merge_sub_count（done/total 计数 helper，~8 行）
   b. _render_chain_line 4 个归并点（L1497/1500/1507/1510）补计数；子卡节点渲染
      `研发 N/M🔄`（紧凑）/ `研发 N/M(🔄)`（时间线）；无子卡零改动
   c. _step_node 增 count 参数（或渲染处内联），docstring 更新
   d. scripts/test_notify_check.py：更新 T60-2/T61-2/T62-1/T63-1/T63-3 旧断言为 N/M 格式
   e. 新增 T84（验收 e2e 1/2🔄）/T85（全 done 2/2✅）/T86（无子卡回归）/T87（qa-exec
      1/2🔄）/T88（title 归并路径计数）/T89（时间线兼容）——fixture 复用 T60-T63 手法
   f. 全量回归 test_notify_check.py（~300+ 断言）+ commit + [PRODUCES] + 飞书推送
   明确不做：摘要 _done_parts/_current_step_card 计数（D1，范围外）；子卡 ever_timed_out
   ⏰ 语义（R6，另卡）；任何 schema/prompt 改动
   预计 9-13 轮。依赖：无（main @ 98fd056 已含 t_95ec1a49 子卡归并）
```

- SPLIT: no（count=1）
- MODE: single（不拆）
- ROUNDS_EST: 11（9-13）
- FILES: scripts/notify_check.py, scripts/test_notify_check.py
- STATUS: not_started（评估卡 t_est_871e5b21 待 autopilot 建 [DEV-DEV] 卡）
- TESTS: 存量 t1-t83（~300+ 断言）PASS 基线；更新 5 条断言（T60-2/T61-2/T62-1/T63-1/T63-3）；新增 T84-T89 共 6 组 ≥18 断言
- RISK: R1 断言子串误判（已核对低）；R2 时间线×计数（T89 锁定）；R5 冲突面低
- ACTION: build_dev_card（assignee=game-engine，单卡）

## 6. 备注

- 关键决策点 D1：摘要区（`_done_parts`「已完成步骤」、`_current_step_card`「当前阶段」）是否也加 N/M 计数？源卡修复要求 1-4 与验收标准全部针对**卡链行渲染**（`研发 1/2🔄`），摘要区不在验收内。**建议严格按需求范围**：只改 `_render_chain_line`；若 Frank 希望摘要区也带计数，属范围扩展，需追加需求（预计 +3-5 轮，届时可拆第二张卡）。
- 本卡不写代码；autopilot 读取 [SUB-SPLIT] comment 后建 1 张 [DEV-DEV] 卡执行。
- 与在途分支冲突面：notify_check.py 近 3 个 FIX 已合 main；在途 DPL-018/019 不碰本文件渲染区，零冲突预期。
- 验收标准逐条可测：① SUB-1 done + SUB-2 running → `研发 1/2🔄`（T84）；② 全 done → `研发 2/2✅`（T85）；③ 单卡无子卡 → 渲染不变（T86 + 存量 T27/T43/T46）；④ qa-exec 同处理（T87）。
