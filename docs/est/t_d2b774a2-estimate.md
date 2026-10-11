# t_d2b774a2 评估报告 — [DEV-EST] InfoManager 头条卡片链接丢失 message_id 反查兜底（权威编号 DPL-157）

- 日期: 2026-09-10
- 评估人: game-engine
- 上游: PRD t_be519a3d（wiki/projects/devppl/prd/dpl153-toutiao-card-msgid-fallback-prd.md v1.0）
  ARCH t_1eb2dd2e（wiki/projects/devppl/arch/arch-dpl153-toutiao-card-msgid-fallback.md v1.1）
- 代码基线: /workspace/InfoManager main（scripts/process_collection.py 2830 行 / scripts/pipeline_state.py 787 行）

## 1. 实锚核验（本评估实码验证，非纸面）

| ARCH 锚点 | 实码 | 结论 |
|---|---|---|
| process_collection.py L2315-2332 反查链 | `message_id` event JSON(2315-2320) → gateway.log 尾部 200 行(2321-2332) | ✅ 在 |
| L780 `_bigrams` 内联于 `_recover_url_by_search` | L781 内联 def | ✅ 在（提升为模块级可平移） |
| L2358-2411 url_missing 分支 | L2358 起，最小条目 + return | ✅ 在 |
| `_is_image_only_article` | L1200 | ✅ 在 |
| `fetch_card_url_from_feishu` | L692 | ✅ 在 |
| pipeline_state.py `init_db`/`start_run` | L103/L173 | ✅ 在 |
| headless OCR 脚本化实现 | repo 内无（仅 skill 参考文档） | ✅ 与 ARCH §5 实锚一致，R4 需最小版实现 |

ARCH 行号锚点全部命中，设计可按函数名直接落地，无架构-代码偏差。

## 2. 工作量评估

模块（ARCH §6）：状态层（pipeline_state +1 列幂等迁移 +2 纯函数）、入口/HARD GUARD（留痕 + 反查链重排 + `scan_gateway_log_for_message_ids` + `validate_recovered_url` + `_bigrams` 提升）、url_missing 降级增强（+2 frontmatter 字段 + ocr_skipped 日志）、R4 `_headless_toutiao_ocr_fallback` 最小版 + 触发点、新增 tests/test_dpl153_msgid_fallback.py（AC1-AC8，headless 用例 skipif）。

- 实现轮次（基线）：R1+R2+R3 同文件改造 ~6-8 轮；R4 最小版 ~4-5 轮；测试 AC1-AC8 ~4-5 轮 → 合计 14-18 轮
- 收尾链固定预算: +8 轮
- 回归测试折算: 目标子集 `pytest -k "toutiao or message_id or url"`，预估 ~2-3 轮
- 总轮次（未校准）: 24-29 轮

## 3. 历史偏差校准（DPL-018，K=2.53）

K=2.53 按卡面校准建议套用会得 61-73 轮 —— 但该 K 由近 5 条 60 轮 timed_out 子卡撑出，属上限截断的失真值（真偏差不可测），直接套用必然再次超时。本评估采用保守中位口径：总轮次 × 2.0 ≈ **48-58 轮**，仍超 30 有效轮红线。

## 4. 拆卡裁定

按口径 >30 有效轮必须拆卡。但 ARCH §6 已裁定「R1+R2+R3 同卡（同文件 process_collection.py 拆卡撞车），R4 并入（无现成脚本化实现）」——全链改动集中在 2 个源文件 + 1 个测试文件，拆卡无法规避同文件写冲突（工作区隔离红线）。

裁定：**[SUB-SPLIT] 2 serial**
1. P0：pipeline_state 入口留痕 + HARD GUARD 反查链重排（R1）+ 相似度闸门（R2）+ url_missing 诚实降级（R3），含 AC1-AC5 测试 预计 20-26 轮
2. P1：R4 headless OCR fallback 最小版 + 触发点 + AC6-AC8 测试（依赖子卡 1 的反查链路） 预计 14-20 轮

子卡 1 校准后 ~40-52 轮接近上限、子卡 2 ~28-40 轮——两者均在单卡可承受带内；若子卡 1 实跑超时，按 DPL-018 记录真偏差供后续校准。

## 5. 风险点

1. R2 误杀（og:title 与分享文本差异大）→ 阈值 0.6 固定 + WARN 含 dice 值可调，可观测。
2. R4 headless 依赖 chrome/tesseract → fail-open partial + 告警，AC7 有断言；测试环境缺 chrome 用 skipif。
3. write_to_vault meta 白名单是否收新字段 → ARCH §4 已留兜底（kwargs 承接），DEV 实测确认。
4. AC8 样例 om_x100b6510e9b7a8a0c44e45fac661153 回放依赖外部飞书 API 可达 → mock + 真实回放双轨，真实回放失败不阻塞 mock 门禁。
