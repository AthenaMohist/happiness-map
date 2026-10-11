# DPL-060 FIX va_backfill 静默 skip 盲区 — QA-POST 合并后测试报告

> 版本：v1.0 | 日期：2026-08-16 | 作者：game-qa（QA-POST 合并后独立验证）
>
> 任务卡：t_26f9fc0f [DEV-QA-POST] FIX va_backfill 静默 skip 盲区 — claim 无 changed_files 段时 VA 缺口无感（DPL-060）
> 被测状态：**合并后** devPPL main @ `3b2aca9`（DPL-060 S1 77dc2d1 + S2 08ab896 + S3 6195f34 全部在 main 祖先；合并后 DPL-060 文件零漂移）
> 前置阶段：PRD t_a3ba04d3 → DEV t_bdcb5e16/t_af4313bd/t_de2602b3 → QA-D1 t_85f38e3b → QA-EXEC t_01738e10 → QA-D2 t_affe716b → VA-QA t_0b8a820f（done）→ MERGE t_6ff818be（done）
> 上游文档：QA-D1 方案（docs/qa/dpl060-va-backfill-skip-visibility-test-plan.md）、QA-EXEC 报告（docs/qa/dpl060-va-backfill-skip-visibility-test-report.md）、QA-D2 评审（docs/qa/dpl060-va-backfill-skip-visibility-d2-review.md）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0（判定公式 §1.2 / SLA §8 / 发布门禁 §10 / 输出格式 §6）

---

## 0. 执行摘要

| 项 | 结果 |
|---|---|
| **合并状态核对** | ✅ main @ `3b2aca9`；DPL-060 S1 77dc2d1 + S2 08ab896 + S3 6195f34 全部为 main 祖先；DPL-060 文件（discover.py/constants.py/cmd_chain.py/autopilot.sh）`git diff main HEAD` 为空 = **零漂移合并** |
| **合并后无 DPL-060 代码变更** | ✅ 自 QA-D2（088896a）后 main 前进 4 次：3 次 QA 报告合并（1eea397/141a6bd/ce9bde6）+ DPL-061 S1/S2（5b591f0/3b2aca9，watchdog 独立链）；DPL-060 代码零触碰 → 无新增回归面 |
| 基线复跑（合并后 main，独立执行） | ✅ test_va_backfill.sh **75/0** + test_number_backfill.sh **33/0** + test_cmd_channel.sh **398/0**，均 EXIT=0（§2.1） |
| pytest 全量 | ✅ **281 passed / 8 failed / 1 error — 与存量基线完全一致，零新增**（§2.2，与 QA-EXEC 613.87s / QA-D2 624.28s 同集） |
| 语法复验 | ✅ **6/6 OK**（py_compile discover/constants/cmd_chain 3/3 + bash -n autopilot/oc_wake_check/test_va_backfill/test_cmd_channel/test_number_backfill 5/5） |
| **live board 只读核对（本卡独立探针）** | ✅ 窗口内 done 5 条全部无 VA 子卡（源 H 候选集静默如实）；全库 [VA-SKIP] comment=**0**；va-skip 注册文件=**0**；seen 中 va-skip 键=**0**（§3） |
| **OBS-2 修正（本卡核心发现）** | 🔧 D2/EXEC 报告的 OBS-2「live board 现存真实 skip 卡」为 **QA 探针伪影**：`qa_dpl060_probes.sh` L233 `export HERMES_KANBAN_DB="$KDB"`（P4 temp DB）泄漏到 P5 段（未重置）→ P5 实际查询 P4 temp 库，`[va-skip] t_p4_idem` 行为 P4 fixture 卡而非 live 卡。本卡 live 探针（mode=ro）+ 源 H 冒烟证实 **live board 实际无 skip 卡**。定级 **MINOR**（探针脚本缺陷，产品行为正确，见 §4） |
| **部署验证（DPL-048）** | ✅ live oc_wake_check.sh 含 DPL-060 源 H 全部 11 处 va-skip 引用；live vs repo 唯一 diff = DPL-061 S2 rstrip 修复（6 行，T5b，3b2aca9 13:56 合入，live 待 OC 同步——DPL-061 部署职责，非本链回归） |
| **新增缺陷（POST 阶段新发现）** | **1 MINOR（探针脚本 env 泄漏，产品 0 缺陷）** — 详见 §4 |
| 发布门禁（标准 §10） | ✅ **满足**（BLOCKER=0 AND MAJOR=0 AND 安全漏洞=0 AND 无未裁定申诉） |

**结论**：合并过程正确——DPL-060 三层机制（R1 四条件宽化 / R2 skip 三分类留痕+注册+源 H 巡检 / R3 建卡提示+格式完整性文案）全部完整在 main、零漂移、无冲突残留、无合并引入回归；合并后基线三套在发布态 main 上独立复跑全绿，pytest 零新增失败。live board 实测无 skip 残留（源 H 静默如实），D2 阶段 OBS-2 因 QA 探针 env 泄漏误报——本卡以独立只读探针修正（MINOR，探针缺陷）。发布门禁满足，DPL-060 收尾闭环。

---

## 1. 合并状态核对（POST 前置检查）

### 1.1 主分支与合并记录

| 检查项 | 命令 | 结果 |
|---|---|---|
| devPPL main tip | `git log main -1` | ✅ `3b2aca9`（merge: t_9bb95b42 DPL-061 S2 测试+回归） |
| 本卡工作树 == main | `git rev-parse HEAD` | ✅ 相同（3b2aca9，worktree wt/t_26f9fc0f 与 main 同 tip） |
| DPL-060 S1 在 main | `git merge-base --is-ancestor 77dc2d1 main` | ✅ YES |
| DPL-060 S2 在 main | `git merge-base --is-ancestor 08ab896 main` | ✅ YES |
| DPL-060 S3 在 main | `git merge-base --is-ancestor 6195f34 main` | ✅ YES |
| 合并零漂移（DPL-060 全部代码文件） | `git diff main HEAD -- pipeline/discover.py pipeline/constants.py pipeline/cmd_chain.py scripts/autopilot.sh scripts/oc_wake_check.sh` | ✅ 空（merged 内容 == dev 分支内容） |
| 自 QA-D2 后的提交 | `git log --oneline 088896a..main` | ✅ 4 次：1eea397/141a6bd/ce9bde6（QA 报告合并）+ 5b591f0/3b2aca9（DPL-061 S1/S2，独立链） |

### 1.2 上游链完整性（全链 done）

| 卡 | 状态 | 卡 | 状态 |
|---|---|---|---|
| PRD t_a3ba04d3 | done | QA-D2 t_affe716b | done |
| DEV t_bdcb5e16 (S1) | done | VA-QA t_0b8a820f | done |
| DEV t_af4313bd (S2) | done | MERGE t_6ff818be | done |
| DEV t_de2602b3 (S3) | done | **本卡 t_26f9fc0f** | running |

---

## 2. 基线复跑结果（合并后 main，独立执行非转述）

### 2.1 基线三套（本卡独立复跑，均 EXIT=0）

| # | 测试集 | 命令 | 结果 |
|---|---|---|---|
| G1 | test_va_backfill.sh（T1-T10，75 断言） | `bash scripts/test_va_backfill.sh` | **PASS=75 FAIL=0**（EXIT=0） |
| G2 | test_number_backfill.sh（33 断言） | `bash scripts/test_number_backfill.sh` | **PASS=33 FAIL=0**（EXIT=0） |
| G3 | test_cmd_channel.sh（398 断言，含 T59e/i/j） | `bash scripts/test_cmd_channel.sh` | **PASS=398 FAIL=0 / ALL TESTS PASSED**（EXIT=0） |

- 与 QA-EXEC / QA-D2 三方一致，无回归。
- 语法复验 6/6 OK（§0）。

### 2.2 pytest 全量（对照存量基线 281/8/1）

- 命令：`cd /workspace/devPPL/.worktrees/t_26f9fc0f && python3 -m pytest tests/ -q --tb=no`（后台）
- 结果：**281 passed / 8 failed / 1 error** — 与存量基线完全一致（QA-EXEC 613.87s、QA-D2 624.28s 同集；DPL-057 实测亦 281/8/1）
- 失败集逐条对照存量清单（与 QA-D2 报告 §3.1 完全同集，8+1 项）：
  - `test_memory_middleware_qa.py::test_tc19_blast_radius_engine` — 存量 ✅
  - `test_memory_middleware_qa.py::test_tc20_gai_links_adapter` — 存量 ✅
  - `test_memory_middleware_qa.py::test_tc23_drift_engine` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound0_Static::test_TC14_double_rollback_idempotent` — 存量（docstring 自述已知缺陷）✅
  - `test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_rollback_retry_count_preserved` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_upsert_retry_count_bug_demo` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_rollback_verdict_preserved` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound4_Boundary::test_BE01_empty_branches_default_advance` — 存量 ✅
  - `test_P2-02_full.py::test`（ERROR，模块顶层 `def test(...)` 被 pytest 误收集 fixture error）— 存量 ✅
- **结论：零新增失败**。

---

## 3. live board 只读核对（本卡独立探针，非转述）

> 方法：独立只读探针 `scripts/qa_dpl060_post_live_probe.py`（sqlite3 mode=ro URI，只读不写卡/不写 comment/不写注册文件/不写 seen），直接查询 `/root/.hermes/kanban.db` 与 `.pipeline/va-skip/`。

| # | 核对项 | 实测 | 结果 |
|---|---|---|---|
| 1 | 窗口内（3600s）done [DEV-*]/[FIX] 无 VA 子卡（源 H 候选集） | 5 条：t_54b89425 / t_01738e10 / t_12539484 / t_0b8a820f / t_6ff818be —— 全部无 [VA-SKIP] comment | ✅ 源 H 静默如实（无缺口卡） |
| 2 | 全库 [VA-SKIP] comment 盘点 | **0 条** | ✅ 无 skip 留痕残留 |
| 3 | `.pipeline/va-skip/` 注册文件 | **0 个** | ✅ 无注册残留 |
| 4 | seen 中 va-skip 状态型键 | **0 条** | ✅ 无巡检状态残留 |

补充冒烟：`SEEN_FILE=temp AUTOPILOT_JOBS_JSON=temp DEPLOY_DRIFT_CHECK=temp bash oc_wake_check.sh /workspace/devPPL`（live 库只读）exit 0，输出中 **0 行 [va-skip]** —— 与探针一致：live board 当前无 skip 卡需要报告。

---

## 4. QA-POST 新发现：OBS-2 修正（MINOR）

### 4.1 现象

- QA-EXEC（§4.5）与 QA-D2（§5.1/§7.1）报告 OBS-2：「P5 源 H 真实库冒烟输出 2 行含 1 行 `[va-skip]`（live board 现存真实 skip 卡，只报告不写卡——预期行为）」，并建议「部署态由 qa-post/OC 补观测并处置（补建 VA / 要求补 claim / 确认容器归档）」。
- 本卡 live 探针（§3）实测：全库 [VA-SKIP] comment=0、注册文件=0、seen 键=0、源 H 冒烟 0 行 [va-skip] —— **live board 实际不存在 skip 卡**，OBS-2 描述与事实不符。

### 4.2 根因（读码确认）

- `scripts/qa_dpl060_probes.sh` **L233**（P4 段）：`export HERMES_KANBAN_DB="$KDB"` 将 HERMES_KANBAN_DB 指向 P4 的 temp DB（t_p4_idem fixture 卡所在库）。
- **L258-270（P5 段）未重置该 env**：P5 执行 `bash "$REPO_ROOT/scripts/oc_wake_check.sh" /workspace/devPPL` 时，oc_wake_check.sh L58 `KANBAN_DB="${HERMES_KANBAN_DB:-/root/.hermes/kanban.db}"` 读到的是 **P4 temp DB**（非 live 库）。
- 因此 P5 输出的 `[va-skip] t_p4_idem` 行来自 P4 fixture 卡（live board 不存在 t_p4_idem），被误读为「live board 现存真实 skip 卡」。
- P5 的其它断言（exit 0 / 任务数不变 / 无 traceback）基于错误的 DB，均属「对 temp 库只读」的弱断言，未暴露该泄漏。

### 4.3 分级判定（标准 §1.2 公式）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|---|---|---|---|---|---|---|
| P5 探针 env 泄漏 → OBS-2 误报 | ✅（下游 OC/qa-post 依据 OBS-2 可能去处置不存在的卡） | ❌（产品机制本身正常：源 H 静默如实、无缺口无感问题；泄漏仅影响 QA 报告准确性） | ✅（人工核对 live 库即可，本卡已用独立探针修正） | 否 | 否 | **MINOR**（探针缺陷，非产品缺陷） |

- 不是 BLOCKER：产品功能无阻断（live board 实测无 skip 卡，源 H 输出如实）。
- 不是 MAJOR：误报不直接影响核心功能链路，且可用只读核对绕行。
- 定 MINOR：QA 探针基础设施缺陷，导致上游报告 OBS-2 描述失实，需修复探针 + 修正观察项描述。
- 产品侧影响：**0 缺陷**——DPL-060 三层机制在合并后 main 上经基线三套 + pytest + live 核对全部成立。

### 4.4 修复建议（QA 只测不改，不代建 FIX 卡）

1. `qa_dpl060_probes.sh` P5 段开头显式重置 `export HERMES_KANBAN_DB=/root/.hermes/kanban.db`（或 `unset HERMES_KANBAN_DB`），使 P5 真正查询 live 库；P5c 断言建议加「源 H 输出行不含 t_p4_idem」以锁定该回归。
2. 修正 QA-EXEC/QA-D2 报告中 OBS-2 描述：live board 无真实 skip 卡；「部署态补观测处置」建议取消，无需 OC 处置。
3. 处置建议提交路径：本报告 comment 记录 → OC 评估（可建 FIX 卡给 game-engine 修探针，或由 DPL-061/后续 QA 卡顺带修复）。

---

## 5. 观察项状态更新（OBS-1 / OBS-2 / OBS-3）

| # | 观察 | QA-D2 记录 | QA-POST 实测（本卡） | 状态 |
|---|---|---|---|---|
| OBS-1 | R3-4 claim-schema skill 节跨 profile 回滚 | 归属 DPL-061 t_6c381232 | DPL-061 S1/S2 已合入 main（5b591f0/3b2aca9），S3（含 skill 节）仍待其独立链；本链不实测（OBS-1 维持归属） | ⏳ 维持（DPL-061 链跟进） |
| OBS-2 | 源 H 真实库冒烟含 1 行 [va-skip]（live board 现存真实 skip 卡） | P5 复验「确认」 | **伪影**：P5 env 泄漏查 P4 temp 库；live 探针实测全库 [VA-SKIP] comment=0 / 注册=0 / seen=0 / 源 H 冒烟 0 行 → live 无真实 skip 卡 | 🔧 **修正为伪影（MINOR）** |
| OBS-3 | no-claim 分支设计使然 | 非缺陷（R2 恰好补位） | 设计使然，基线 T10a/a2 + 探针 P4 实测确认 | ✅ 维持（非缺陷） |

> OBS-1 处置建议：DPL-061 t_6c381232 合入后，由该链 QA 复验 claim-schema skill「格式演进同步规则」节。
> OBS-2 处置建议（更新）：无需 OC 补观测处置（live 无卡）；仅需修复探针脚本（§4.4）并在报告层面修正描述。

---

## 6. 判定公式 / SLA / 分级示例对照（标准 §6 输出格式要求）

### 6.1 判定公式对照（标准 §1.2）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|---|---|---|---|---|---|---|
| （无）产品功能缺陷 | — | — | — | — | — | **0 BLOCKER/MAJOR/MINOR/SUGGESTION** |
| P5 探针 env 泄漏（OBS-2 伪影） | ✅ | ❌ | ✅（只读核对） | 否 | 否 | **MINOR**（探针缺陷） |
| OBS-1（skill 节跨 profile 回滚） | ✅（va-claim 验证不查格式演进规则） | ❌（机制本身已含 D11 文案） | ✅（DPL-061 独立链验证） | 否 | 否 | **观察项**（归属 DPL-061） |
| OBS-3（no-claim 分支设计使然） | ✅（无 claim 卡不进入条件 3） | ❌（R2 恰好补位留痕） | ✅（OC 按 no-claim 分类裁定） | 否 | 否 | **观察项**（设计使然） |

### 6.2 SLA 对照（标准 §8）

- 本卡 0 BLOCKER / 0 MAJOR → **无 SLA 触发**（BLOCKER 4h 响应 / 8h 定位 / 24h 方案均无适用对象）。
- 唯一 MINOR（探针 env 泄漏）不设 SLA；由 OC 评估处置时机。

### 6.3 分级示例对照（标准 §5 表）

- 未发现「四条件全命中仍 skip 且无留痕」类 BLOCKER（基线 T9a-d + 探针 P2/E 命中补建，合并后 main 上 G1 75/0 复证）。
- 未发现「[VA-SKIP] comment 文案与文档不一致」类 MINOR（discover.py L1256-1258 文案含时间戳+处置指引，S5 读码一致）。
- 未发现「源 H 对 legit-container 防御冗余」类 SUGGESTION（S10 双保险符合 arch D6）。

---

## 7. 发布门禁对照（标准 §10）

| 门禁条件 | 数值 | 满足 |
|---|---|---|
| BLOCKER = 0 | 0 | ✅ |
| MAJOR ≤ 3 | 0 | ✅ |
| 安全漏洞 = 0 | 0 | ✅ |
| 无未裁定的申诉 | 0 | ✅ |

**发布门禁满足。** DPL-060 全链（PRD → DEV → QA-D1/EXEC/D2 → VA → MERGE → QA-POST）闭环，可收尾。

---

## 8. 处置建议（QA 只测不改，不代建 FIX 卡）

1. **P5 探针修复（MINOR）**：`qa_dpl060_probes.sh` P5 段重置 HERMES_KANBAN_DB（§4.4）。建议 OC 评估：建 FIX 卡给 game-engine 修复，或由 DPL-061 后续 QA 卡顺带修复。
2. **OBS-2 描述修正**：QA-EXEC/QA-D2 报告中 OBS-2 应改为「live board 无真实 skip 卡（P5 探针 env 泄漏伪影）」，原「部署态补观测处置」建议取消。
3. **OBS-1 维持**：R3-4 claim-schema skill 节由 DPL-061 t_6c381232 链跟进，合入后复验。
4. **部署验证（DPL-048）**：live oc_wake_check.sh 与 repo 唯一 diff = DPL-061 S2 rstrip 修复（3b2aca9 13:56 合入），待 OC 同步部署；DPL-060 源 H 块已在 live（11 处 va-skip 引用），本链无需部署动作（部署永远留给 OC）。

---

## 9. 风险登记

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| R1 | live oc_wake_check.sh 与 repo 漂移（DPL-061 S2 rstrip 修复未部署） | live 源 J 路径截断 bug 仍存在（T5b） | 已在 §8.4 记录，属 DPL-061 部署职责；DPL-060 源 H 不受影响（已在 live） |
| R2 | P5 探针泄漏类 bug 可能存在于其它 QA 探针脚本 | 报告描述失实 | 本卡已修复建议 §4.4；后续 QA 卡写探针时统一检查 env 隔离 |
| R3 | main 工作树 .pipeline/* 脏文件来自并行管线/测试夹具（manifest.jsonl/gai/archive 时间戳 06:08Z） | 误判为回归 | 本卡全部测试在 worktree + temp DB 隔离；脏文件为测试夹具副作用，不提交（见执行记录） |
| R4 | pytest 602s+ 超长 | 拖慢报告 | 后台并行跑（与 live 核对/报告写作并行） |

---

## 附：执行记录

- 合并状态：main @ 3b2aca9 == HEAD；S1 77dc2d1 + S2 08ab896 + S3 6195f34 均祖先；`git diff main HEAD -- pipeline/discover.py pipeline/constants.py pipeline/cmd_chain.py scripts/autopilot.sh scripts/oc_wake_check.sh` 空（零漂移）；088896a..main 4 次提交含 3 次 QA 报告合并 + DPL-061 S1/S2
- 基线三套（本卡独立复跑）：`bash scripts/test_va_backfill.sh`（75/0）+ `bash scripts/test_number_backfill.sh`（33/0）+ `bash scripts/test_cmd_channel.sh`（398/0），均 EXIT=0
- pytest：`python3 -m pytest tests/ -q --tb=no`（后台）→ 281/8/1，失败集与存量逐条一致零新增
- 语法：py_compile 3/3 + bash -n 5/5 = 6/6 OK
- live 只读探针：`python3 scripts/qa_dpl060_post_live_probe.py`（sqlite3 mode=ro）→ 窗口 5 条 done 无 VA 子卡 / 全库 [VA-SKIP] comment=0 / 注册=0 / seen 键=0；源 H 冒烟（SEEN/JSON/DRIFT env 隔离）exit 0 且 0 行 [va-skip]
- P5 泄漏根因：`scripts/qa_dpl060_probes.sh` L233 export HERMES_KANBAN_DB → P5（L258-270）未重置 → oc_wake_check.sh L58 读到 P4 temp DB
- 部署核对：`md5sum` live vs repo oc_wake_check.sh（64b560c8 vs 23936e2a），`diff` 仅 6 行 = DPL-061 S2 rstrip 修复（T5b）；live 版含 11 处 va-skip 引用（DPL-060 源 H 已在 live）
- 本卡交付物：本报告 + `scripts/qa_dpl060_post_live_probe.py`（只读探针）+ 发现笔记 `.pipeline/wip/t_26f9fc0f.md`
- 工作树隔离：全部测试在 wt/t_26f9fc0f worktree；live 核对全部只读（mode=ro / temp SEEN）
- 轮次存档：run 1067 timed_out 前已写 [CHECKPOINT]（见卡 comment），本 run 依据 `.pipeline/wip/t_26f9fc0f.md` 接续，禁止从零重来（DPL-030）
