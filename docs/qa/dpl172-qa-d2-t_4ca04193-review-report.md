# DPL-172 QA-D2 评审报告（t_4ca04193）

- 角色: QA（game-qa）· 分支: `wt/t_4ca04193` · 模式: CC-MAX（cc-glm doctor 四检通过: KEY=ok ENDPOINT=200 VERSION=2.0.0 SHUTDOWN=none）
- 对象: 前棒 QA-EXEC 报告 `docs/qa/dpl172-qa-exec-t_6841508f-test-report.md`（commit 9ed96b0 @ wt/t_6841508f）
- 依据: DPL-137 测试执行分层（QA-D2 = 改报告评审 + 随机抽测 2-3 断言，不实跑全量）

## 抽测结果（随机 3/5）

| # | 抽测项 | 复现方式 | 实测 | 判定 |
|---|--------|---------|------|------|
| A1 | T-M1 真源页 greppable | `git show ff0d4ac` + 实文件 grep | mem-core wt/t_4ada71e1 ff0d4ac 实存，`grep -c '角色='` = 7（报告称 ≥6，实测 7）| VERIFIED |
| A2 | T-M2 子集 pytest 12 passed | 重跑 `pytest tests/test_dpl172_soul_pointer_matrix.py tests/test_role_boundary_scan.py -q` | **12 passed in 0.26s**（wt/t_4c19b674 上复现；详见发现 F-1）| VERIFIED（结果属实）|
| A3 | T-M5 inject --dry-run 幂等 | 实跑 `scripts/inject_test_gate_rule.sh --dry-run` | exit=0，新增=0 已存在跳过=9 缺失=0，9 个 SOUL.md 前后 sha256 聚合一致（a58627f3…）| VERIFIED |

抽测 3/3 VERIFIED，0 FALSIFIED。

## 报告逻辑评审

- §1.2 判定公式对照：报告 BLOCKER=0/MAJOR=0/MINOR=0，与各用例 PASS 证据一致，判定正确。
- SLA 对照：无发现，不适用——标注正确。
- §10 门禁：BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定申诉 → PASS，成立。

## 发现

- **F-1（MINOR）**：QA-EXEC 报告 §命令与输出 写 `python3 -m pytest tests/… -q → 12 passed`，但 `test_dpl172_soul_pointer_matrix.py`（QA-D1 产物）不在 wt/t_6841508f 分支工作树内（该分支仅含 test_role_boundary_scan.py 7 用例）；12 passed 需在 wt/t_4c19b674（D1 分支）上复现。结果真实、无 falsify，但报告未注明执行目录，复现者会先撞 "file not found"。建议：报告注明命令的 cwd/分支。不阻塞发版（MINOR，用户不可感知、无功能阻断）。

## 分级判定（qa-finding-classification §1.2）

- BLOCKER=0 · MAJOR=0 · **MINOR=1**（F-1）· SUGGESTION=0
- SLA：MINOR 无 SLA 强制（§8 仅 BLOCKER），不适用。
- 门禁（§10）：BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定申诉 → **PASS**

## 结论

前棒 QA-EXEC 报告逻辑合规、抽测 3/3 VERIFIED，验收门禁 PASS。MINOR F-1 建议后续报告注明执行路径（不阻塞）。

---

## [CLAIM] t_4ca04193（QA-D2 评审轮，DPL-172）
- produces: docs/qa/dpl172-qa-d2-t_4ca04193-review-report.md（抽测 3/3 VERIFIED、0 FALSIFIED + MINOR F-1）
- changed_files: docs/qa/dpl172-qa-d2-t_4ca04193-review-report.md（commit f076000 @ wt/t_4ca04193）
- tests_run: 抽测 A1 grep '角色='=7（mem-core ff0d4ac）；A2 pytest 子集 12 passed（wt/t_4c19b674）；A3 inject_test_gate_rule.sh --dry-run exit=0 + 9 SOUL sha256 幂等一致
- verification: §1.2 判定 BLOCKER=0/MAJOR=0/MINOR=1；§10 门禁 PASS；前棒报告逻辑合规
- findings: F-1 MINOR — QA-EXEC 报告未注明 12 passed 的执行分支（结果真实，不阻塞）
- 执行模式: CC-MAX（doctor 4/4 ok），本轮零代码改动（评审轮）
