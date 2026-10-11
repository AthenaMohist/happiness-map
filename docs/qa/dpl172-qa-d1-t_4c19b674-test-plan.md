# DPL-172 QA-D1 测试方案（t_4c19b674）

- 角色: QA（game-qa）· 分支: `wt/t_4c19b674`
- 范围: DPL-172 R2「角色边界矩阵真源页 + SOUL 指针注入 + role_boundary_scan + 注入幂等」QA-D1 独立产出
- 用例文件: `tests/test_dpl172_soul_pointer_matrix.py`（与 `tests/test_role_boundary_scan.py` T6-T8 互补，不重复）
- 验收命令（targeted-only）: `python3 -m pytest tests/test_dpl172_soul_pointer_matrix.py tests/test_role_boundary_scan.py -q`

## 用例矩阵

### T-M1 真源页存在且 greppable（交付分支内容）
- 方法: `git -C /workspace/mem-core show wt/t_4ada71e1:wiki/concepts/patterns/role-boundary-matrix.md`（subprocess），保证验证的是交付分支内容而非 main/工作区副本。
- 通过标准:
  - 含「角色=」的行数 >= 6（六角色矩阵）；
  - 六个角色语义（产品/架构/研发/QA/VA/OC）各出现在至少一行矩阵行中。

### T-M2 SOUL 指针注入 5/5
- 方法: 直接读 5 个 profile 的 `/root/.hermes/profiles/<p>/SOUL.md`（p = game-architect, game-director, game-engine, game-qa, verifier）。
- 通过标准: 每个 SOUL.md 均含「真源指针（DPL-172）」且提及 `role-boundary-matrix`（5/5，任一缺失即 FAIL）。

### T-M3 真源页与 constants.py 允许集一致性抽查
- 方法: 读 `pipeline/constants.py` 的 `ROLE_FILE_ALLOW_RULES`，对照真源页矩阵行语义。
- 通过标准:
  - `game-qa` 的 deny ⊇ {`pipeline/**`, `scripts/**`}（QA 禁改源码）；
  - `verifier` 的 deny ⊇ {`pipeline/**`, `scripts/**`, `tests/**`}（VA 只读取证，禁任何实改）。

### T-M4 scan() 行为级
- 方法: 调用 `role_boundary_scan.scan(files, role)`。
- 通过标准:
  - `scan(["pipeline/foo.py"], "game-qa")` → 恰 1 hit 且 `pattern == "pipeline/**"`；
  - `scan(["tests/x.py"], "game-qa")` → 0 hit；
  - `scan(["anything"], "unknown-role")` → 0 hit（未知角色不误报，交人工裁量）。

### T-M5 注入幂等（不实际写入）
- 方法: `bash scripts/inject_test_gate_rule.sh --dry-run`（subprocess），并在执行前后快照 5 个 SOUL.md 内容。
- 通过标准:
  - 退出码 0；
  - stdout 含 `新增=0`、`已存在跳过=9`、`缺失=0`；
  - 所有已存在 SOUL.md 内容前后逐字节一致（dry-run 不写文件）。

## 结果

见任务产出（pytest 摘要）——5 用例全绿为 PASS。
