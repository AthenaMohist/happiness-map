# DEV-EST 工作量评估 — t_089db8c6

任务: [DEV] DPL-125 R4 编号挂靠规则 — number_backfill topic 匹配继承 + [FIX] 永不进候选
评估人: game-engine（dev-est）@ 2026-09-04
基线: main @ ae85491

## 1. 源需求要点（R4 裁定，源卡 comment 2304）

1. `_number_backfill_candidates` 过滤：title 含 `[FIX]` 的卡不再进候选
2. 新增 `_match_chain_by_topic(title)`：剥前缀/尾部编号 → topic 规范化（去空白、全半角括号归一）比对；命中 = topic 相等或一方为另一方前缀且 ≥10 字符
3. backfill 三级判定：topic 命中 → 继承链编号 + comment 标注；未命中 → next-seq 新号；[FIX] 永远跳过
4. `[CMD] create` 编号判定顺序：topic 匹配 → body「编号:」行 → 最后 next-seq

## 2. 现状核对（main @ ae85491 实测）

- `pipeline/discover.py:1556` `_number_backfill_candidates`：SQL LIKE 白名单 `[DEV-%` / `[FIX]%` / `[CMD] create%`——`[FIX]` 目前**在**候选内，需改为排除（R4-1）
- 编号判定现状两级：`_body_has_number` 幂等跳过 → `_extract_topic_code` 取 CODE → memctl next-seq + kanban-max 防撞（无 topic 匹配继承）
- `_extract_topic_code` / `_topic_from_title` 已从 cmd_chain import（topic 基础设施在位）
- 测试基线：test_number_backfill.sh 39/39、test_chain_check.sh 38/38、test_cmd_channel.sh 396/398（PRD-GATE-T6 ×2 预存 flaky，干净树同败）

## 3. 工作量估算

| 项 | 内容 | 轮次 |
|---|---|---|
| R4-1 | 候选 SQL 去 `[FIX]%`（含注释/测试同步） | 1-2 |
| R4-2 | `_match_chain_by_topic`：剥前缀（`[...]`）/尾部（CODE-NNN）编号 → 全角括号→半角、去空白 → 相等或前缀≥10 字符判定 | 3-5 |
| R4-3 | process_number_backfill 三级判定插入：topic 命中查 kanban 既有链编号继承（复用 `_kanban_title_max_code`/全角编号 regex 逻辑取该 topic 既有号）+ comment 标注；comment 用 kanban_comment 路径确认（fail-open） | 3-5 |
| R4-4 | `[CMD] create` 分支：topic → body 编号行 → next-seq 顺序 | 1-2 |
| 测试 | test_number_backfill.sh 增量 4 例（FIX 不进候选 / topic 继承不增号 / 未命中新号 / 全半角括号空白边界） | 3-4 |
| 回归 | test_chain_check + test_cmd_channel 全量 | 1-2 |
| 收尾 | [PRODUCES]/[CLAIM] + finalize.sh | 1-2 |

**合计：约 13-22 轮，K 校准后有效轮 ≈ 12-16。复杂度：低-中。**

## 4. 风险点

- R4-3 「继承链编号」的取号来源：topic 命中链上最近编号卡的（CODE-NNN），需处理链上多号（取 max）与并发窗口——复用现有幂等双保险（UPDATE 前再查 title）
- topic 前缀≥10 字符阈值可能误挂靠相似标题 → 测试边界例覆盖；误挂可由 comment 标注追溯
- 全量回归中 PRD-GATE-T6 ×2 为预存 flaky（与 diff 无关），按预存豁免记

## 5. 决策

预计 ≤20 轮 → **不拆卡**（[SUB-SPLIT] 1），单 worktree 串行完成。
