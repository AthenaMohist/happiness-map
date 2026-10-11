# MEM-017 QA-D1 测试报告（t_ffcd77dc）

> 日期: 2026-10-06 | 执行模式: CC-MAX（cc-glm run d278ad01，4 turns）| QA 只测不改: 零代码变更
> 依据: PRD mem017-signal-account-pointer-prd.md §3 A1-A5 / 架构 arch-mem017-signal-account-pointer.md §1 V1-V3
> 方案: docs/qa/t_ffcd77dc-mem017-qa-plan.md（T1-T7）

## 结论: PASS — 0 BLOCKER / 0 MAJOR / 1 MINOR。MEM-017 指针收口闭环成立。

## 用例结果

| # | 用例 | 结果 | 实测证据 |
|---|------|------|----------|
| T1 | A1 功能符号落 main | PASS | record_signal→cli.py+decay.py; resolve_actor→decay.py; MEM_ACCESS_ACTOR→decay.py+schema.py; page_signal→archive/cli/decay/indexer.py（4/4 符号实锚） |
| T2 | A2 合入记录 | PASS | wiki/actions/MEM-017.md status=done；收口行在位（2026-09-29，含 575bd43/0ba037e） |
| T3 | A3 门禁独立复跑 | PASS | tests/test_mem008_r2_signal.py 14/14 passed（QA 独立复跑，非转述） |
| T4 | A4 四信号齐备 | PASS | schema.py:138 SIGNALS=("view","like","dislike","comment")；:136 权重 view:1,like:3,dislike:2,comment:5 可 env 覆盖；append-only 由 T3 内 test_no_update_delete_on_page_signal 覆盖且 passed |
| T5 | A5 归档护栏零回归 | PASS | -k archive 子集 20/20 passed，无新增红 |
| T6 | actor 三态行为抽测 | PASS | T3 内 test_actor_explicit_env / profile_fallback / anonymous_default / three_states_land_in_page_signal 全 passed |
| T7 | 收口文档一致性 | PASS | 575bd436 / 0ba037ed / 26569124 三 commit 均可达；PRD/架构引用路径实存；口径无矛盾 |

## MINOR-1（SUGGESTION 级表述瑕疵）
PRD §3 A1 写 "page_signal 命中 … schema.py"，实际 grep page_signal 未列 schema.py（schema.py 命中的是 MEM_ACCESS_ACTOR）。dev claim 的合并表述（5 文件）无实质错误，仅 PRD 单符号→文件映射不精确。不阻塞收口，建议 PRD 下次改版时修正措辞。
分级依据: §1.2 五步判定——非用户可感知功能缺陷，不影响验收口径成立 → MINOR（不阻塞发版）。

## 判定公式对照
本卡为指针收口验证：A1-A5 均为证据可复现性判定，无安全类发现；无 BLOCKER/MAJOR，发布门禁（§10）天然满足。

## SLA 对照
无 BLOCKER/MAJOR 发现 → 无 SLA 时钟启动。

## 分级示例对照
MINOR-1 对应标准 §3 MINOR 档（用户能忍/不阻塞）。

## 交付物
- 测试方案: docs/qa/t_ffcd77dc-mem017-qa-plan.md（commit a237c33 @ wt/t_ffcd77dc）
- 测试报告: 本文件
- 执行脚本: /root/.hermes/profiles/game-qa/cache/scratch/qa_mem017_gate.sh（repo 外）
