# QA-EXEC 报告 — DPL-173 oc_wake L4 强制输出根治（t_cadede3b）

评审对象: dev 卡 t_3692069a（commit 3c2734c，含 merge-fix 9749aca/69888a6），本 worktree wt/t_cadede3b
日期: 2026-09-29 | 执行人: game-qa（QA-EXEC，DPL-137 只跑本卡子集）
执行模式: CC-MAX（cc-glm 派发 A1/A2，session 738da489 / 61dcb80d）

## 1. A1 子集复跑（cc 实跑输出）

- pytest tests/test_dpl173_oc_wake_blocked_still.py -q → **8 passed in 4.55s**（T1-T8）✅
- bash -n scripts/oc_wake_check.sh → SYNTAX-OK ✅
- 回归 pytest -k "oc_wake or dpl172 or gate_audit" -q → **39 passed, 0 failed**（722 deselected；唯一 warning 为 cmd_chain.py:2059 SyntaxWarning，与本改动无关）✅
- git grep oc_wake_monitor -- scripts/ → 1 命中，仅 scripts/oc_wake_check.sh:1540 注释行（历史说明），活代码引用 = 0 ✅

## 2. A2 行为级沙箱探针（cc 独立实跑，非测试夹具复用）

| 探针 | 断言 | 实测 | 结果 |
|------|------|------|------|
| P1 | 2 张 blocked 卡连续 2 tick → 每 tick 输出 `[blocked-still] N=2`，ts nonce 两 tick 互不相同，无 NO_ANOMALY | tick1 `ts=1790624481` / tick2 `ts=1790624482`，tids=t_pa,t_pb | PASS |
| P2 | glm 停机窗口（glm_tail 非空）→ 不含 `[blocked-still]`，输出 `[glm-shutdown] active…` | 抑制生效，仅 glm-shutdown 行 | PASS |

## 3. §1.2 判定公式对照（qa-finding-classification.md）

- 无用户可感知缺陷项：BLOCKER=0 / MAJOR=0 / MINOR=0 / SUGGESTION=0
- 安全项: 无 → 独立判定不适用
- 与父卡 QA-D1（t_fc3075cc）独立结果一致（8/8 + 39 回归 + 探针语义吻合）

## 4. SLA 对照

无 BLOCKER/MAJOR 发现 → 无 SLA 时钟，不适用。

## 5. 发布门禁对照（§10）

BLOCKER=0 AND MAJOR=0 AND 安全漏洞=0 AND 无未裁定申诉 → **门禁 PASS**。
全量 pytest 留待合并后 main 节点（DPL-137），本卡未跑全量。

## 6. Verdict

PASS — 本卡子集 T1-T8 全绿 + 行为级探针 P1/P2 全 PASS，QA-EXEC 验证完成。
