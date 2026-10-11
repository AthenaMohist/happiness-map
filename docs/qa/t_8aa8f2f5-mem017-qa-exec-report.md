# MEM-017 QA-EXEC 测试报告（t_8aa8f2f5）

> 日期: 2026-10-06 | 执行模式: CC-MAX（cc-glm，doctor 四检全绿）| QA 只测不改: 零代码变更
> 依据: PRD mem017-signal-account-pointer-prd.md §3 A1-A5 / 架构 arch-mem017-signal-account-pointer.md §1 V1-V3
> 方案: docs/qa/t_ffcd77dc-mem017-qa-plan.md（T1-T7，前棒 QA-D1 产出）
> 性质: QA-EXEC 只跑本卡测试方案用例（targeted + 行为级独立复跑），不跑全量（DPL-137）

## 结论: PASS — 0 BLOCKER / 0 MAJOR / 1 MINOR（维持前棒 MINOR-1）。MEM-017 收口验收通过。

## 用例结果（QA 独立复跑，非转述 dev/D1 结果）

| # | 用例 | 结果 | 实测证据（本次独立复跑输出） |
|---|------|------|----------|
| T1 | A1 功能符号落 main | PASS | git grep memcore/*.py: record_signal→cli.py+decay.py; resolve_actor→decay.py; MEM_ACCESS_ACTOR→decay.py+schema.py; page_signal→archive/cli/decay/indexer.py（4/4 符号实锚） |
| T2 | A2 合入记录 | PASS | wiki/actions/MEM-017.md `status: done`；第 26 行收口行在位（2026-09-29，含 575bd43/0ba037e） |
| T3 | A3 门禁独立复跑 | PASS | tests/test_mem008_r2_signal.py：14 passed in 0.34s（0 failed/error） |
| T4 | A4 四信号齐备 | PASS | schema.py:138 `SIGNALS = ("view","like","dislike","comment")`；:136 DEFAULT_SIGNAL_WEIGHTS 可 env 覆盖；test_no_update_delete_on_page_signal PASSED（append-only 行为级） |
| T5 | A5 归档护栏零回归 | PASS | -k archive 子集：20 passed, 469 deselected（无新增红） |
| T6 | actor 三态行为抽测 | PASS | test_actor_explicit_env / test_actor_profile_fallback / test_actor_anonymous_default / test_actor_three_states_land_in_page_signal 全在收集清单且套件 14/14 passed |
| T7 | 收口文档一致性 | PASS | 575bd436 / 0ba037ed / 26569124 三 commit 均可达（git log 实查）；引用口径与 T1/T2 证据一致 |

## MINOR-1（维持前棒判定）
PRD §3 A1 "page_signal 命中 schema.py" 措辞不精确（schema.py 实际命中的是 MEM_ACCESS_ACTOR）。本次复跑确认该描述瑕疵仍在。不阻塞收口，建议 PRD 下次改版修正。分级依据: §1.2 五步判定 → MINOR（用户不阻塞发版）。

## 判定公式对照
本卡为收口验收：A1-A5 均为证据可复现性判定；无安全类发现；0 BLOCKER / 0 MAJOR → 发布门禁（§10）满足。

## SLA 对照
无 BLOCKER/MAJOR 发现 → 无 SLA 时钟启动。

## 分级示例对照
MINOR-1 对应标准 §3 MINOR 档。

## 交付物
- 测试报告: 本文件（落盘 wt/t_8aa8f2f5）
- 执行脚本: /root/.hermes/profiles/game-qa/cache/scratch/qa_mem017_gate.sh（repo 外）
- changed_files: docs/qa/t_8aa8f2f5-mem017-qa-exec-report.md
