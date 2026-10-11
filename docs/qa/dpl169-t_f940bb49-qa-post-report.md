# DPL-169 QA-POST 合并后验证报告（t_f940bb49）

日期: 2026-10-03  执行者: game-qa  分层: QA-POST（TL3, 合并后 main 节点）
被验对象: merge 8ad97d4（wt/t_fd4aa045 → main, t_62a881b4 merge）

## 1. 合并完整性确认

- main HEAD 含 merge commit 8ad97d4（Merge: 2dea81c a48cdd1）
- 实现修复 pipeline/parents_parse.py（commit 1e5b584, 双格式 parents: 行 ∪ 前棒卡: 行）已在 main
- 合并 diff: scripts/test_cmd_channel.sh（+G6FIX6 用例）、tests/test_parents_parse.py（+3 用例）、.pipeline/registry_gap.tsv

## 2. 本卡相关测试子集（合并后 main 实跑）

| 项 | 结果 |
|---|---|
| pytest tests/test_parents_parse.py | 7 passed / 0 failed（含新增 test_qianzhi_single_id / multi_id / parents 行优先） |
| pytest test_parents_parse + test_dpl169_classify_chain + test_dpl056_chain_gate | 36 passed / 0 failed |
| 行为级探针（parse_parents 直接调用 5 场景） | 5/5 PASS（单 id / parents 行优先 / 多 id 逗号 / 无行→[] / CMD 卡 body 上下文） |

## 3. e2e test_cmd_channel.sh（沙箱后台跑完, EXIT=183）

- 汇总: PASS=300 FAIL=183
- G6FIX: 仅 G6FIX3/3b（拒绝路径，不依赖建卡）通过；G6FIX1/2/4/5/6（放行路径）失败，缺「终态门限豁免」
- 环境归因证据: 日志大量 `stub hermes: connection refused` 与 `delegate_task child contexts cannot mutate Kanban tasks via the CLI` —— 沙箱 stub hermes 无法建卡，放行类断言依赖 prd 卡 body 故必然失败
- 对照: QA-D1 有权环境 G6FIX e2e 6/6 全过（t_0be04595）；QA-EXEC 沙箱同样环境归因（t_1ba27d3b）——本沙箱红与前两次 run 一致，非本合并引入
- G7b/G7c 红（T16 3 条）同为环境归因（stub 建卡失败）

## 4. QA 发现分级（按 qa-finding-classification §1.2）

- BLOCKER: 0
- MAJOR: 0
- MINOR: 0
- SUGGESTION: 0

判定说明: 行为级真源（parse_parents 双格式解析）已在合并后 main 由 pytest + 直接探针双重验证通过；e2e 红条目均为沙箱 stub 环境预存/环境归因，不属于用户可感知的功能缺陷。

## 5. 结论

**QA-POST 验收 PASS**。合并后 main 满足 DPL-169 验收标准：parse_parents 双格式生效、repair 链「前棒卡:」不再被终态门限误杀（单测+行为探针证实），无新增回归。
