# DPL-172 QA-EXEC 测试报告（t_6841508f）

- 角色: QA（game-qa）· 分支: `wt/t_6841508f` · 模式: CC-MAX（cc-glm doctor 四检通过: KEY=ok ENDPOINT=200 VERSION=2.0.0 SHUTDOWN=none）
- 范围: DPL-172 R2 真源页 role-boundary-matrix + SOUL 指针注入 QA-EXEC 验收（targeted-only，DPL-136/DPL-137）
- 依据: QA-D1 测试方案 `docs/qa/dpl172-qa-d1-t_4c19b674-test-plan.md`（T-M1~T-M5）

## 执行结果

| 用例 | 验证对象 | 结果 |
|------|---------|------|
| T-M1 真源页 greppable | `git show wt/t_4ada71e1:wiki/concepts/patterns/role-boundary-matrix.md` 含「角色=」行 | PASS（≥6，实测 7 行）|
| T-M2 SOUL 指针 5/5 | tests/test_dpl172_soul_pointer_matrix.py | PASS |
| T-M3 constants 允许集一致性 | 同上（对照 ROLE_FILE_ALLOW_RULES deny 语义）| PASS |
| T-M4 scan() 行为级 | tests/test_role_boundary_scan.py + 独立探针 | PASS |
| T-M5 注入幂等 dry-run | 独立探针（前后逐字节 hash 对比）| PASS |

### 命令与输出

- `python3 -m pytest tests/test_dpl172_soul_pointer_matrix.py tests/test_role_boundary_scan.py -q` → **12 passed**（0 failed，0 error）
- 独立探针（scratch/exec_probe_t6841508f.py，实测输出）:
  - `scan(["pipeline/foo.py"],"game-qa")` → 1 hit, pattern="pipeline/**" ✓
  - `scan(["tests/x.py"],"game-qa")` → 0 hit ✓
  - `scan(["anything"],"unknown-role")` → 0 hit ✓
  - `inject_test_gate_rule.sh --dry-run` → exit 0，`新增=0 已存在跳过=9 缺失=0`，9 个 SOUL.md 前后 sha256 逐字节一致 ✓

## 分级判定（qa-finding-classification §1.2）

- BLOCKER=0 · MAJOR=0 · MINOR=0 · SUGGESTION=0
- SLA 对照：无发现，不适用。
- 门禁（§10）：BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定申诉 → **PASS**

## 结论

验收门禁 PASS，本卡 QA-EXEC 完成。
