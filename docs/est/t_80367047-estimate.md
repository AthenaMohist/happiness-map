# 工作量评估 — t_80367047（DPL-162 R5 FIX：三证据裁决管线缺陷修复）

> 评估卡: t_est_80367047 | 评估人: game-engine | 2026-09-20
> 源码锚点基于 wt/t_est_80367047（main 6f596d9 恢复版），实测行号。

## 1. 源码实锚（实测，非引用卡面）

| 修复点 | 锚点 | 实测现状 |
|---|---|---|
| F1 aggregate_pits | `scripts/chain_review.py:832` | 组结构 `{representative, count, task_ids, signal_hashes}`，representative 取首个 pit，**无 evidence_refs 并集** — 卡面根因成立 |
| F1 _evidence_from_refs | `scripts/chain_review.py:864` | 只读 `pit.evidence_refs` 单 pit 计数 — 需改读组级 |
| F2 verify_with_evidence | `scripts/chain_review.py:398` | 现规则 L415-420：refuted（oc_diag_non_bug + 2 源）→ confirmed（total>=3 且 >=2 源非零）→ inconclusive。**追加规则插 L418 confirmed 之后、L420 inconclusive 之前** |
| F2 process_pits 传参 | `scripts/chain_review.py:882-920` | L914 调 `verify_with_evidence(rep, _evidence_from_refs(rep))` — high_volume 需在此注入（g["count"]>=5） |
| F3 memctl 固化 | `scripts/chain_review.py:708`（MEMCTL_BIN 优先，已支持 env）+ `scripts/dpl162_daily.sh`（cron 包装器，30 6 * * *） | cron 段未 export MEMCTL_BIN — 在 dpl162_daily.sh 加 export 即可（fail-open warn 已存在于 L716/L744） |

测试基线: `tests/test_chain_review.py` 943 行，59 passed 基线（S3 收口口径）。

## 2. 工作量评估

**实现基准**: 约 12-16 轮（单会话可完成）。

- F1 聚合并集: aggregate_pits 组结构加 `evidence_refs` 并集（去重保序）+ `_evidence_from_refs` 加组级兜底入参 + process_pits L914 传组级。约 3-4 轮实现 + 2-3 轮单测（跨源合并、前缀保留、代表兜底）。
- F2 同源高置信: verify_with_evidence 追加一条规则（不动既有 refuted/confirmed 语义）+ process_pits 注入 high_volume。约 2 轮实现 + 2 轮边界单测（count=4 不触发 / count=5 触发 / high_volume 缺省不触发）。
- F3 memctl 固化: dpl162_daily.sh 头部加 `export MEMCTL_BIN=...`（带存在性探测+静默降级），warn 文案核对。约 1-2 轮。
- AC1 真库 dry-run 复跑（--day 2026-09-16，1720 信号）+ 验证待定性收敛 <100：约 3-4 轮（脚本 10-15min 级，后台跑）。
- 收口（子集回归 59+新增全绿、worktree 提交、MERGE 落 main、备份推送）：约 3 轮。

**复杂度**: 低-中。三点全是链上微改，纯函数为主，测试基建齐全（59 例基线 + 既有 fixture 可复用）。

**风险点**:
1. **F1 并集改变 verdict 分布**：并集后部分组从 inconclusive 跳 confirmed，lessons 页回写量上升 — 由 signal_hash 去重兜底（update_lessons_page L488 已按 hash 去重），风险可控。
2. **F2 与量级守卫交互**：组数 >200 时 count<2 组走轻路径降级（L901），F2 规则只影响 count>=5 组，两规则无交集，安全。
3. **AC1 收敛数不确定**：OC 实锤 439 组 / 300 待定性；F1 并集 + F2 高置信双管齐下，预期 <100 达标概率高，但确切收敛数要跑了才知道 — 若不达标，归因上浮 OC，不在本卡内二次迭代。
4. **main 工作树刚重建**（6f596d9 restore），行号以本评估实测为准；实现时若发现偏移，按符号锚定不按行号。

## 3. 决策

预计 12-16 轮 **≤ 20 轮 → 不拆卡**（[SUB-SPLIT] 1）。

- 拆分边际收益为负：三点改动同文件强耦合（F1/F2 都动 process_pits），拆卡徒增 merge 成本。
- AC1 dry-run 是最后一步验证，串行收口自然。
