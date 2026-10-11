# MEM-017 QA-D2 复核报告（t_72e45560）

> 日期: 2026-10-06 | 执行模式: CC-MAX（cc-glm，doctor 四检全绿）| QA 只测不改: 零代码变更
> 性质: QA-D2 改报告评审 + 抽测——随机抽 EXEC 断言行为级独立复核 + 报告逻辑检查，不跑全量（DPL-137）
> 对象: docs/qa/t_8aa8f2f5-mem017-qa-exec-report.md（QA-EXEC，wt/t_8aa8f2f5 1213bd4）

## 结论: PASS — 抽测 4/4 独立复现一致，报告逻辑合规。0 BLOCKER / 0 MAJOR / 1 MINOR（维持）。

## 抽测断言复核（本卡独立重跑，实测于 /workspace/mem-core @ 312bc6d4）

| 抽样 | EXEC 断言 | 结果 | 本次实测证据 |
|------|-----------|------|------|
| T1 | A1 四符号实锚 | 复现一致 | git grep: record_signal→cli.py:98/103/2443/2497 + decay.py；resolve_actor→decay.py:85；MEM_ACCESS_ACTOR→schema.py:134 + decay.py:86；page_signal→archive/cli/decay/indexer 四文件命中 |
| T7 | 收口三 commit 可达 | 复现一致 | 575bd436（t_78c97d8c finalize）/ 0ba037ed（MEM-008 R2 merge）/ 26569124（INF-022 PRODUCES）均 git log 实达 |
| T3 | signal 套件 14/14 | 复现一致 | pytest tests/test_mem008_r2_signal.py → 14 passed in 0.34s（0 failed/error）；4 个 actor 用例单独点跑 4 passed |
| T5 | archive 护栏子集 | 复现一致 | pytest -k archive → 20 passed, 469 deselected（无新增红，与 EXEC 数字逐字一致） |

补充佐证: T4 部分抽验（schema.py:136-138 DEFAULT_SIGNAL_WEIGHTS 可 env 覆盖 + SIGNALS 四元组在位）；T2 部分抽验（wiki/actions/MEM-017.md `status: done`，2026-09-29 收口执行行在位）。

## 报告逻辑检查
- 判定公式对照（§1.2）: 报告含对照段，收口验收为证据可复现性判定，合规。
- SLA 对照: 无 BLOCKER/MAJOR → 无时钟启动，表述正确。
- 分级示例对照: MINOR-1 对应标准 §3 MINOR 档，正确。
- 审计口径: EXEC 报告称符号落 "memcore/*.py" 但未写明 repo 路径（实际在 /workspace/mem-core，非 devPPL repo）——属报告表述瑕疵，不影响判定，并入 MINOR-1 同档备忘，不新增发现。

## MINOR-1（维持）
PRD §3 A1 "page_signal 命中 schema.py" 措辞不精确（schema.py 实际命中 MEM_ACCESS_ACTOR）。本次抽测再次确认。不阻塞收口，建议 PRD 下次改版修正。分级依据 §1.2 → MINOR。

## 发布门禁对照（§10）
BLOCKER=0 ✓ MAJOR≤3 ✓ 安全漏洞=0 ✓ 无未裁定申诉 ✓ → 门禁满足。

## 交付物
- 本报告: docs/qa/t_72e45560-mem017-qa-d2-report.md（落盘 wt/t_72e45560）
- 抽测脚本: /root/.hermes/profiles/game-qa/cache/scratch/qa_mem017_d2_spot.sh（repo 外）
- changed_files: docs/qa/t_72e45560-mem017-qa-d2-report.md
