# DPL-153/157 QA-D2 报告评审 + 抽测 — t_14e441bc（INF-018）

- 作者: game-qa（QA-D2）｜日期: 2026-09-10
- 被评审: t_8b793888（QA-EXEC）报告 docs/QA/DPL-157-qa-exec-report.md（commit b01c03a）
- 依据: test-execution-layering-spec.md（TL2 抽测 2-3 个 EXEC 断言 + 报告逻辑检查）、qa-finding-classification.md §1.2

## 1. 抽测结果（3 项，独立复跑，非采信报告文本）

| # | EXEC 断言 | D2 独立验证 | 结论 |
|---|---|---|---|
| S1 | F-1: API 返回嵌套 JSON、无 `<img>` 标签、regex 提图恒空 | 真网重放 `m.toutiao.com/api/pc/detail/?group_id=1875751979183364`：`data.content` 为 JSON 字符串，`json.loads` 后 `rich_content.images` 为 list len=3（web_uri×3），全文无 `<img`；`process_collection.py:1380` 的 `re.findall(r'<img…')` 复算结果 `[]` | **属实** |
| S2 | E1: qa_d1_scripts.py 7/7 PASS | 从 commit 0813a52 独立取出脚本，/tmp 复跑：`SUMMARY: 7/7 PASS, 0 FAIL/ERROR` | **属实** |
| S3 | E2: 验收子集 31 passed, 133 deselected | 在被测 repo /workspace/InfoManager 重跑 `pytest tests -k "toutiao or message_id or url" -q`：**31 passed, 133 deselected (42s)** | **属实** |

## 2. 报告逻辑检查（对照 §1.2）

- F-1 定级 MAJOR 论证成立：用户可感知（image-only OCR 兜底失效）+ 核心场景 AC8 无 workaround + 非安全漏洞 + 有 fail-open 数据不丢（不满足 BLOCKER）。✔
- F-2 定级 SUGGESTION（环境约束非缺陷）合理。✔
- 发布门禁建议（MAJOR=1 ≤3 但建议 FIX 后复测再关链）与 §10 语义一致。✔

## 3. D2 发现（不影响 EXEC 结论）

- **F-D2-1（SUGGESTION）报告表述瑕疵**：报告写图片位于 `rich_content.spans[].images[]`，实测 images 位于 `rich_content` 的同级顶层字段 `images`（spans[].images 均为 null）。不影响 F-1 结论（嵌套 JSON + web_uri×3 + 无 `<img>` 均属实），但建议研发修复时按实际字段路径取数。
- 环境备注：devPPL tests 目录含模块级 `sys.exit` 脚本（test_notify_dpl150/gai_b1/b2 等）会导致 pytest collection INTERNALERROR，与本卡无关（EXEC 的 31/31 在 InfoManager repo，正确）。

## 4. D2 结论

- 报告可信：抽测 3/3 断言独立复跑属实，分级与门禁逻辑合规。
- 维持 EXEC verdict：R1-R3 质量确认，AC8 真网未达成（F-1 MAJOR）。
- 建议 OC：开 FIX 卡修复 F-1（按 rich_content.images[].web_uri 实际路径解析 + 旧格式 `<img>` 兼容），修后 QA 复测 AC8 再关 INF-018 链。
- 0 BLOCKER / 1 MAJOR（F-1，沿用）/ 0 新增 MINOR。
