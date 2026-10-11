# DPL-060 FIX va_backfill 静默 skip 盲区 — QA 执行测试报告（test_report.md）

> 版本：v1.0 | 日期：2026-08-16 | 作者：game-qa（独立执行，非研发自测）
>
> 任务卡：t_01738e10 [DEV-QA-EXEC] FIX va_backfill 静默 skip 盲区 — claim 无 changed_files 段时 VA 缺口无感（DPL-060）
> 上游：t_85f38e3b（QA-D1 测试方案，docs/qa/dpl060-va-backfill-skip-visibility-test-plan.md v1.0 @ wt/t_85f38e3b，commit a644a71）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0（判定公式 §1.2 / SLA §8 / 发布门禁 §10）

---

## 0. 执行摘要

| 项 | 结果 |
|---|---|
| 被测对象确认 | **devPPL main @ 6195f34**（`git merge-base --is-ancestor 6195f34 HEAD` ✅，DPL-060 S1 77dc2d1 + S2 08ab896 + S3 6195f34 全部已合入 main） |
| 前置语法 | **6/6 OK**（py_compile discover.py/constants.py/cmd_chain.py + bash -n autopilot/oc_wake_check/test_va_backfill/test_cmd_channel/test_number_backfill） |
| 基线三套（独立复跑） | test_va_backfill.sh **75 PASS / 0 FAIL** + test_number_backfill.sh **33 PASS / 0 FAIL** + test_cmd_channel.sh **398 PASS / 0 FAIL** |
| pytest 全量 | **281 passed / 8 failed / 1 error — 与存量基线完全一致，零新增失败**（§2.4，613.87s） |
| 静态核对 S1-S12 | **12/12 PASS**（§3） |
| 独立探针 P1-P6 | **19/19 PASS**（§4，独立编写 scripts/qa_dpl060_probes.sh，非研发自测） |
| 验收 R1-R4 | **R1 5/5 + R2 4/4 + R3 3/4 + R4 2/2**（§5；R3-d claim-schema skill 节归属 DPL-061，本链不实测） |
| **QA 发现** | **0 BLOCKER / 0 MAJOR / 0 MINOR / 0 SUGGESTION**；3 项观察与 D1 一致（OBS-1 R3-4 skill 节 → DPL-061；OBS-2 源 H 真实库冒烟见 §4.5；OBS-3 no-claim 分支设计使然） |

**结论：DPL-060 三层机制（R1 四条件宽化 / R2 skip 三分类留痕+注册+源 H 巡检 / R3 建卡提示+格式完整性文案）经 QA 独立执行全部成立，发布门禁满足（BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定申诉）。**

---

## 1. 前置确认（执行前）

| # | 检查项 | 命令/依据 | 结果 |
|---|---|---|---|
| 1 | main 被测 commit | `git log --oneline -3`（HEAD=6195f34 merge）+ `git merge-base --is-ancestor 6195f34 HEAD` | ✅ 6195f34 为 main HEAD 且为祖先（S1/S2/S3 全部在 main） |
| 2 | py_compile 3 py | `python3 -m py_compile pipeline/discover.py pipeline/constants.py pipeline/cmd_chain.py` | ✅ OK |
| 3 | bash -n 5 sh | autopilot.sh / oc_wake_check.sh / test_va_backfill.sh / test_cmd_channel.sh / test_number_backfill.sh | ✅ 5/5 OK |

---

## 2. 基线三套 + pytest（独立复跑，非转述）

| # | 测试集 | 命令 | 结果 |
|---|---|---|---|
| G1 | test_va_backfill.sh（T1-T10，75 断言） | `cd /workspace/devPPL && bash scripts/test_va_backfill.sh` | **PASS=75 FAIL=0**（EXIT=0） |
| G2 | test_number_backfill.sh（33 断言） | `bash scripts/test_number_backfill.sh` | **PASS=33 FAIL=0**（EXIT=0） |
| G3 | test_cmd_channel.sh（398 断言，含 T59e/i/j） | `bash scripts/test_cmd_channel.sh` | **PASS=398 FAIL=0 / ALL TESTS PASSED**（EXIT=0） |
| G4 | pytest tests/ 全量 | `python3 -m pytest tests/ -q --tb=no`（后台） | 见 §2.4 |

### 2.4 pytest 全量结果（对照存量基线 281/8/1）

- 命令：`cd /workspace/devPPL && python3 -m pytest tests/ -q --tb=no`（后台，613.87s）
- 结果：**281 passed / 8 failed / 1 error** — 与存量基线 **完全一致**（DPL-057 实测 281/8/1，621s）
- 失败集逐条对照存量清单（t_4436b52e/t_56ab5309/t_e7d69f20 WIP 记录）：
  - `test_memory_middleware_qa.py::test_tc19_blast_radius_engine` — 存量 ✅
  - `test_memory_middleware_qa.py::test_tc20_gai_links_adapter` — 存量 ✅
  - `test_memory_middleware_qa.py::test_tc23_drift_engine` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound0_Static::test_TC14_double_rollback_idempotent` — 存量（docstring 自述已知缺陷）✅
  - `test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_rollback_retry_count_preserved` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_upsert_retry_count_bug_demo` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_rollback_verdict_preserved` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound4_Boundary::test_BE01_empty_branches_default_advance` — 存量 ✅
  - `test_P2-02_full.py::test`（ERROR，模块顶层 `def test(...)` 被 pytest 误收集 fixture error）— 存量 ✅
- **结论：零新增失败（R4-a 后半成立）**

---

## 3. 静态核对 S1-S12（QA 独立读码，非转述）

| # | 核对项 | 证据（文件:行） | 结果 |
|---|---|---|---|
| S1 | `_latest_claim_has_changed_files` 四条件 OR 顺序 1/2→3→4→False；条件 3 不命中不短路条件 4 | `pipeline/discover.py` L1146-1191（L1184-1188） | ✅ |
| S2 | `_metadata_has_file_claims`：claims 数组 file_* 或 changed_files 非空；异常 fail-open False | discover.py L1086-1117（L1116-1117 except → False） | ✅ |
| S3 | `_claim_has_delivery_commit`：commit 引用 + 交付语义双条件 AND | discover.py L1120-1143（_COMMIT_REF_RE L1082 IGNORECASE + _DELIVERY_SEMANTIC_RE L1083） | ✅ |
| S4 | `_va_skip_reason` 三分类：legit-container（task_links EXISTS）/ no-claim / nonstd，异常→nonstd | discover.py L1205-1228 | ✅ |
| S5 | `_va_skip_leave_trace`：comment 幂等（写前查）+ snippet 捕获 + tmp+os.replace 原子写 + skip_count 递增 + first_skip_at 保留 | discover.py L1231-1297 | ✅ |
| S6 | va-claim 补扫 body 含 [格式完整性] 文案（D11 一处） | discover.py L1378-1380 | ✅ |
| S7 | autopilot.sh va-claim 步含 [格式完整性] 文案（D11 另一处） | scripts/autopilot.sh L472 | ✅ |
| S8 | oc_wake_check 源 H：窗口查询与候选 SQL 对齐 + reason 正则 [a-z][a-z-]* + skip_count 读注册文件 + 状态型键 va-skip:<tid>:<skip_count> | scripts/oc_wake_check.sh L372-419 | ✅ |
| S9 | 源 H 底部统一写回（va_skip_new_keys 排除列表含 va-skip） | oc_wake_check.sh L430-445 | ✅ |
| S10 | 容器豁免双保险：legit-container reason 不输出 | oc_wake_check.sh L405-406 | ✅ |
| S11 | constants CLAIM_HINT_LINE + cmd_chain _dev_card_body 插行（CHECKPOINT → CLAIM_HINT → WIP，WIP 末行） | constants.py L263-266 + cmd_chain.py L715-718 | ✅ |
| S12 | 存量实证：t_4436b52e 已有 VA 卡 t_679f3765 | `/workspace/devPPL/scripts/devppl_query.sh task t_679f3765` → `va-claim: t_4436b52e | done | verifier` | ✅ |

---

## 4. 独立探针 P1-P6（game-qa 独立编写 scripts/qa_dpl060_probes.sh）

> 探针 harness：与 test_va_backfill.sh 同款隔离（temp kanban.db 复制真实 schema + DROP 触发器 + FAKE_REPO 注册隔离 + HERMES_KANBAN_DB 指向 temp）；每探针独立 DB 防扫描累积；P5 真实库只读（oc_wake_check 内部 mode=ro URI）。

| # | 探针 | 方法 | 结果 |
|---|---|---|---|
| P1 | 条件 3 run 选取边界：run status='done' 命中 / 'gave_up' 不命中 | temp 库 seed run metadata，run_scan 断言 | ✅ done 补建 / gave_up 未建且 nonstd skip + 留痕 comment 恰 1 条（skipped=1） |
| P2 | 条件 4 双条件边界：大写 commit ref（IGNORECASE）命中 / 裸 commit 负例 | seed 交付+commit ABCDEF… / 参考 commit abc1234 | ✅ 大写命中补建 / 裸 commit 仍 skip |
| P3 | 注册文件损坏恢复：旧 json 非法 → skip_count 从 1 重计（fail-open） | 预写坏 json，run_scan 后读注册 | ✅ 不抛、字段齐全、skip_count=1、reason=nonstd |
| P4 | comment 幂等边界：同 (task_id,reason) 3 次扫描 → 恰 1 条 | 3×run_scan | ✅ comment 恰 1 条；注册 skip_count=3（D8 递增） |
| P5 | 源 H 真实库只读冒烟：live board 不崩、不写卡 | `SEEN_FILE=temp AUTOPILOT_JOBS_JSON=temp DEPLOY_DRIFT_CHECK=temp bash oc_wake_check.sh /workspace/devPPL` | ✅ exit 0 / 任务数前后不变 / 无 traceback（见 §4.5） |
| P6 | CLAIM_HINT_LINE 插行零回归：T59e/i/j 断言存在 + WIP 末行 | grep 断言 + _dev_card_body 顺序实测 | ✅ T59e/i/j 各 1；CHECKPOINT < CLAIM_HINT < WIP 且 WIP 为末行 |

**探针汇总：PASS=19 FAIL=0（脚本自报），对应上述 19 条断言。**

### 4.5 P5 源 H 真实库冒烟明细

- exit=0；真实库任务数 before=after（只读不写卡）；无 python traceback。
- 源 H 输出 2 行，含 1 行 `[va-skip]`（live board 现存真实 skip 卡，报告即预期行为——只报告不写卡）。
- SEEN_FILE 指向 temp，未触碰真实 /tmp/oc_wake_seen。

---

## 5. 验收标准核对（PRD §5 R1-R4）

| # | 验收要点 | 证据锚点 | 结果 |
|---|---|---|---|
| R1-a | done 卡 claim 只含「4. 交付 - commit e0e84a2（3 files）」→ 补建（条件 4） | T9a-d ✅（基线）+ P2 ✅ | ✅ |
| R1-b | comment 无产物但 metadata.claims 含 file_modified → 补建（条件 3） | T9e-g ✅（基线）+ P1 ✅ | ✅ |
| R1-c | metadata.claims=[] 且 comment 无 commit → 仍 skip（负例） | T9h ✅（基线） | ✅ |
| R1-d | comment 含「参考 commit abc1234」无交付语义 → 仍 skip | T9i ✅（基线）+ P2b ✅ | ✅ |
| R1-e | 既有 T1-T8 断言全部不变（只增不删） | T9j/k 计数锚点 ✅（基线 75/0） | ✅ |
| R2-a | skip 卡 → 卡面 [VA-SKIP] comment 恰好 1 条（幂等 D7） | T10a/a2 ✅（基线）+ P4 ✅ | ✅ |
| R2-b | .pipeline/va-skip/<tid>.json 字段齐全 | T10b-b5 ✅（基线）+ P3 ✅ | ✅ |
| R2-c | 源 H 输出含卡+reason+skip_count；重跑不重复报（状态型键） | T10c-c3+e ✅（基线）+ P5 ✅ | ✅ |
| R2-d | 容器卡不写 comment、不出现在源 H（D6 豁免） | T10d/d2 ✅（基线） | ✅ |
| R3-a | dev 卡 body 含 CLAIM_HINT_LINE | T59i ✅（基线 398/0）+ P6a ✅ | ✅ |
| R3-b | CLAIM_HINT_LINE 在 WIP 之前（WIP 保末行） | T59j ✅（基线）+ P6b-d ✅ | ✅ |
| R3-c | va-claim 卡 body 含格式完整性文案（D11 两处） | 静态 S6/S7 ✅ | ✅ |
| R3-d | claim-schema skill「格式演进同步规则」节 | ⏳ **DPL-061 t_6c381232 跟进**（OBS-1，本链不实测） | ⏳ |
| R4-a | 三套脚本回归全绿 + pytest 无新增失败 | va 75/0 + number 33/0 + cmd 398/0 ✅ + pytest（§2.4） | ✅ |
| R4-b | t_4436b52e 实证记录（VA 卡 t_679f3765） | 静态 S12 ✅（devppl_query 实测） | ✅ |

---

## 6. 分级标准对照（qa-finding-classification.md v1.0）

### 6.1 判定公式对照（标准 §1.2）

| 步骤 | 标准要求 | 本报告执行 |
|---|---|---|
| 1 用户可感知？ | 缺陷是否被用户/下游感知 | 探针 P1-P6 与基线断言均以「行为可观测」为准（补建/留痕/巡检输出） |
| 2 功能阻断？ | 是否阻断核心功能 | 本次未发现功能阻断缺陷 |
| 3 workaround？ | 是否有绕行方案 | 无缺陷 → 无需判定 |
| 4 定级 | 按公式输出 BLOCKER/MAJOR/MINOR/SUGGESTION | **0 BLOCKER / 0 MAJOR / 0 MINOR / 0 SUGGESTION** |
| 5 安全漏洞独立判定 | 不经过用户可见过滤，最低 MAJOR | 本次不涉及安全面（无凭据/注入/越权路径） |

### 6.2 SLA 对照（标准 §8）

- 本次无任何发现 → 不触发 SLA 流程（BLOCKER 4h 响应 / 8h 定位 / 24h 方案均无适用对象）。

### 6.3 分级示例对照（标准 §5 表 + 方案 §6）

| 假设缺陷 | 按公式应定级 | 实测 | 结论 |
|---|---|---|---|
| 四条件全命中仍 skip 且无留痕 | BLOCKER（用户可感知+功能阻断+无 workaround） | 未复现（P1-P4 全过） | 不适用 |
| [VA-SKIP] comment 文案与文档不一致 | MINOR（可感知+不阻断+workaround） | 文案含时间戳+处置指引（discover.py L1256-1258） | 不适用 |
| 源 H 对 legit-container 防御冗余 | SUGGESTION（不阻塞不劣化） | 双保险符合 arch D6（S10） | 不适用 |

### 6.4 发布门禁（标准 §10）

- BLOCKER=0 ✅ AND MAJOR≤3（0）✅ AND 安全漏洞=0 ✅ AND 无未裁定申诉 ✅ → **门禁满足，可发版**。

---

## 7. 观察项（与 D1 一致，无新增）

| # | 观察 | 说明 | 归属 |
|---|---|---|---|
| OBS-1 | R3-4 claim-schema skill 节 | repo 外 PINNED skill 跨 profile 同步回滚；本链不实测 | **DPL-061 t_6c381232**（game-engine 跟进，qa-post/qa-exec 在 DPL-061 合入后复验） |
| OBS-2 | 源 H 真实库冒烟输出含 1 行 [va-skip] | live board 现存真实 skip 卡（只报告不写卡，P5 实测） | 部署态由 qa-post/OC 补观测 |
| OBS-3 | 无 claim comment 卡不进入条件 3，直接走 R2 no-claim 分支 | 设计使然：R2 恰好补位（探针 P4/P1 实测确认） | 非缺陷 |

---

## 8. 风险登记回顾（对照方案 §8）

| # | 风险 | 处置 |
|---|---|---|
| R1 | DPL-061 合入/未合入导致 R3-4 验收漂移 | 报告注明 R3-4 归属 DPL-061（§5），避免重复判定 |
| R2 | main 前进导致被测对象变化 | 前置确认 6195f34 为 HEAD 且祖先 ✅ |
| R3 | pytest 602s 超长 | 后台跑，与静态/探针并行（§2.4） |
| R4 | P5 真实库冒烟潜在写 seen 风险 | SEEN_FILE 指向 temp，只读核对，未触碰真实 seen ✅ |
| R5 | cmd 398 断言执行时长 | 单遍全绿（81s 级）✅ |
| R6 | claim-schema skill 同步回滚影响引用 | 本卡不改 skill（OBS-1 归属 DPL-061） |

---

## 附：证据文件

- 测试方案：`/workspace/devPPL/.worktrees/t_85f38e3b/docs/qa/dpl060-va-backfill-skip-visibility-test-plan.md`（a644a71 @ wt/t_85f38e3b）
- 探针脚本：`scripts/qa_dpl060_probes.sh`（本卡 wt/t_01738e10，a3417fa）
- WIP 发现笔记：`.pipeline/wip/t_01738e10.md`
- 基线三套：`bash scripts/test_va_backfill.sh`（75/0）+ `test_number_backfill.sh`（33/0）+ `test_cmd_channel.sh`（398/0）
