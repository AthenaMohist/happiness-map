# QA-D2 结果严重度评审报告 — FIX va_backfill 静默 skip 盲区（DPL-060）

> 版本：v1.0 | 日期：2026-08-16 | 执行人：game-qa（QA-D2 结果严重度评审卡 t_affe716b）
> 上游执行报告：`docs/qa/dpl060-va-backfill-skip-visibility-test-report.md`（QA-EXEC t_01738e10 @ a3434ae，分支 wt/t_01738e10）
> 测试方案：`docs/qa/dpl060-va-backfill-skip-visibility-test-plan.md`（QA-D1 t_85f38e3b @ a644a71，分支 wt/t_85f38e3b）
> 被测提交：**devPPL main @ 6195f34**（DPL-060 S1 77dc2d1 + S2 08ab896 + S3 6195f34 全部已合入 main）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0
> 评审性质：QA-D2 独立复验（非转述 QA-EXEC），复核分级判定 + 漏报检查 + 处置建议

---

## 0. 评审结论（TL;DR）

| 评审项 | 结果 | 证据 |
|---|---|---|
| 分级判定复核（QA-EXEC 结论 0 BLOCKER/MAJOR/MINOR/SUGGESTION + 3 观察） | ✅ **复核一致** | §2 |
| 被测对象确认（main @ 6195f34 祖先） | ✅ 6195f34 为 main HEAD 且祖先（D2 阶段 main 未前进，与 QA-EXEC 同一对象） | §1.3 |
| 语法前置（py_compile 3 + bash -n 5） | ✅ **6/6 OK** | §1.3 |
| 基线三套独立复跑（同一 main 对象） | ✅ **va 75/0 + number 33/0 + cmd 398/0**，均 EXIT=0 | §3 |
| pytest 全量独立复跑（对照存量基线） | ✅ **281 passed / 8 failed / 1 error**（624.28s）——失败集 8+1 与存量清单逐条一致，**零新增** | §3.1 |
| 静态核对 S1-S12 复验 | ✅ **12/12 PASS**（独立读码） | §4 |
| 探针 P1-P6 复验（QA-EXEC 探针重跑） | ✅ **19/19 PASS** | §5.1 |
| 漏报探针 A-N（QA-D2 新增） | ✅ **28/28 PASS**（无漏判） | §5.2 |
| AC R1-R4 交叉核对 | ✅ **R1 5/5 + R2 4/4 + R3 3/4 + R4 2/2**（R3-d 归属 DPL-061，与 QA-EXEC 一致） | §6 |
| 漏报检查（QA-EXEC 是否漏判） | ✅ **无漏报**（A-N 补充探针全部通过） | §5.2/§7 |
| 发布门禁（标准 §10） | ✅ **满足**（BLOCKER=0 AND MAJOR=0 AND 安全漏洞=0 AND 无未裁定申诉） | §8 |

**评审结论：QA-EXEC 测试报告分级判定准确、证据链完整、无漏报、无错判。DPL-060 三层机制（R1 四条件宽化 / R2 skip 三分类留痕+注册+源 H 巡检 / R3 建卡提示+格式完整性文案）经 QA-D2 独立复验全部成立。结果评审通过（review_pass），可放行后续 va-qa → qa-post。**

---

## 1. 评审对象与方法

### 1.1 评审对象

- QA-EXEC 报告：`docs/qa/dpl060-va-backfill-skip-visibility-test-report.md`（v1.0，187 行，t_01738e10 @ a3434ae）
- 报告核心声明：基线三套 va 75/0 + number 33/0 + cmd 398/0、pytest 281/8/1 与存量一致零新增、静态 S1-S12 12/12、探针 P1-P6 19/19、R1-R4 验收 14/15（R3-d 归属 DPL-061）、0 缺陷 + 3 观察（OBS-1/OBS-2/OBS-3）

### 1.2 评审方法（独立复验，不转述）

| # | 方法 | 说明 |
|---|------|------|
| M1 | 基线三套独立复跑 | 本卡在 main @ 6195f34 重新执行 va/number/cmd 三套（与 QA-EXEC 同一被测对象，双重覆盖） |
| M2 | pytest 全量独立复跑 | 后台全量 + 失败集逐条对照存量清单（8+1），确认零新增 |
| M3 | 静态独立核对 | 独立读码复验 S1-S12（12 项） |
| M4 | 探针独立复验 + 漏报探针 | P1-P6 重新执行（QA-EXEC 探针脚本拷贝重跑）+ 漏报探针 A-N 新增（28 断言） |
| M5 | AC 交叉核对 | R1-R4 逐项对照验收要点（PRD §5 + test-plan §1.1 + EXEC 报告 §5） |
| M6 | 分级复核 | 对照标准 §1.2 判定公式，逐项复核 QA-EXEC 的 0 缺陷 + 3 观察判定 |

### 1.3 被测对象确认（P-1..P-4 复验）

| # | 前置项 | 实测 | 结果 |
|---|---|------|:---:|
| P-1 | devPPL main HEAD | `git log main -1` = 6195f34（merge t_de2602b3 DPL-060 S3） | ✅ |
| P-2 | 6195f34 为祖先 | `git merge-base --is-ancestor 6195f34 main` = YES（S1/S2/S3 全部在 main） | ✅ |
| P-3 | main 无前进 | `git log --oneline -5 main` 最后 5 条含 6195f34 + S2 merge 08ab896 + S1 77dc2d1（D2 阶段无新 merge） | ✅ |
| P-4 | 语法前置 | `python3 -m py_compile discover.py/constants.py/cmd_chain.py` ✅ + `bash -n autopilot.sh/oc_wake_check.sh/test_va_backfill.sh/test_cmd_channel.sh/test_number_backfill.sh` ✅ = **6/6** | ✅ |
| P-5 | 工作树隔离 | 本卡在 wt/t_affe716b 执行，探针全部 $TMPT 隔离；未触碰 main 工作树写操作 | ✅ |

---

## 2. 分级判定复核（标准 §1.2 公式逐项对照）

### 2.1 QA-EXEC 结论 vs 本卡复核

| QA-EXEC 判定 | 本卡复核 | 复核依据 |
|------|:---:|------|
| 0 BLOCKER | ✅ 一致 | 无用户可感知+功能阻断+无 workaround 组合（§2.2）；无安全漏洞；无数据一致性；无性能退化；无 OOM/崩溃 |
| 0 MAJOR | ✅ 一致 | 无用户可感知+功能阻断但有 workaround/体验严重退化；无 XSS/CSRF/SSRF；无数据一致性；无性能退化 |
| 0 MINOR | ✅ 一致 | 无用户可感知且影响核心任务完成的问题（基线三套 + pytest + 探针全绿） |
| 0 SUGGESTION | ✅ 一致 | 无用户不可感知但值得提的代码层面建议（四条件/留痕/源 H 均符合 arch 约定） |
| OBS-1（R3-4 skill 节 → DPL-061） | ✅ 一致 | repo 外 PINNED skill 跨 profile 同步回滚；本链不实测，归属 DPL-061 t_6c381232 |
| OBS-2（源 H 真实库冒烟含 [va-skip] 行） | ✅ 复确认 | 本卡 P5 复验同样观察到：源 H 输出 2 行含 1 行 [va-skip]（live board 现存真实 skip 卡，只报告不写卡——预期行为） |
| OBS-3（no-claim 分支设计使然） | ✅ 一致 | 无 claim comment 卡不进入条件 3，直接走 R2 no-claim 分支；探针 P4/Md 实测确认（comment 恰 1 条 + skip_count 递增） |

### 2.2 判定公式逐项（标准 §1.2）

| 条件 | 是否触发 | 证据 |
|------|:---:|------|
| 安全漏洞（认证绕过/数据泄露/远程注入） | 否 | 补扫/留痕/巡检全部本地 sqlite + bash 只读；无网络/认证面；P5 真实库 mode=ro URI |
| 数据一致性（S/A 级数据） | 否 | 读写 kanban task/comment/注册 json，属 C 级内部配置数据；comment 幂等 (task_id,reason) 防刷屏 |
| 性能退化（P95 ≥10x / ≥3x） | 否 | 每 tick 上限 _VA_BACKFILL_MAX_PER_TICK=10（红线未动，探针 L）；源 H 只读窗口查询 |
| OOM/崩溃 | 否 | Python 脚本 + bash 包装；全部异常内吞 fail-open（探针 M/N 实测不抛） |
| 概率性 bug（资金/核心功能） | 否 | 无状态机/并发面；注册文件 tmp+os.replace 原子写 |

**结论：QA-EXEC 的「0 缺陷 + 3 观察」分级判定与标准公式完全一致，无错判、无漏判。**

---

## 3. 基线三套 + pytest 独立复跑（同一 main @ 6195f34，非转述）

| # | 测试集 | 命令 | 结果 |
|---|---|---|---|
| G1 | test_va_backfill.sh（T1-T10，75 断言） | `cd /workspace/devPPL && bash scripts/test_va_backfill.sh` | **PASS=75 FAIL=0**（EXIT=0） |
| G2 | test_number_backfill.sh（33 断言） | `bash scripts/test_number_backfill.sh` | **PASS=33 FAIL=0**（EXIT=0） |
| G3 | test_cmd_channel.sh（398 断言，含 T59e/i/j） | `bash scripts/test_cmd_channel.sh` | **PASS=398 FAIL=0 / ALL TESTS PASSED**（EXIT=0） |
| G4 | pytest tests/ 全量 | `python3 -m pytest tests/ -q --tb=no`（后台，624.28s） | 见 §3.1 |

### 3.1 pytest 全量结果（对照存量基线 281/8/1）

- 命令：`cd /workspace/devPPL && python3 -m pytest tests/ -q --tb=no`（后台，624.28s）
- 结果：**281 passed / 8 failed / 1 error** — 与存量基线 **完全一致**（QA-EXEC 613.87s 同集 281/8/1；DPL-057 实测亦 281/8/1）
- 失败集逐条对照存量清单（与 QA-EXEC 报告 §2.4 完全同集）：
  - `test_memory_middleware_qa.py::test_tc19_blast_radius_engine` — 存量 ✅
  - `test_memory_middleware_qa.py::test_tc20_gai_links_adapter` — 存量 ✅
  - `test_memory_middleware_qa.py::test_tc23_drift_engine` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound0_Static::test_TC14_double_rollback_idempotent` — 存量（docstring 自述已知缺陷）✅
  - `test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_rollback_retry_count_preserved` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_upsert_retry_count_bug_demo` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_rollback_verdict_preserved` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound4_Boundary::test_BE01_empty_branches_default_advance` — 存量 ✅
  - `test_P2-02_full.py::test`（ERROR，模块顶层 `def test(...)` 误收集 fixture error）— 存量 ✅
- **结论：零新增失败（R4-a 后半成立，与 QA-EXEC 三方一致）**

---

## 4. 静态核对 S1-S12 复验（独立读码，12/12 PASS）

| # | 核对项 | 证据（文件:行，main @ 6195f34） | 结果 |
|---|---|---|---|
| S1 | `_latest_claim_has_changed_files` 四条件 OR 顺序 1/2→3→4→False；条件 3 不命中不短路条件 4 | `pipeline/discover.py` L1146-1191（L1183-1188） | ✅ |
| S2 | `_metadata_has_file_claims`：claims 数组 file_* 或 changed_files 非空；异常 fail-open False | discover.py L1086-1117（L1116-1117 except → False） | ✅ |
| S3 | `_claim_has_delivery_commit`：commit 引用 + 交付语义双条件 AND | discover.py L1120-1143（_COMMIT_REF_RE L1082 IGNORECASE + _DELIVERY_SEMANTIC_RE L1083） | ✅ |
| S4 | `_va_skip_reason` 三分类：legit-container（task_links EXISTS）/ no-claim / nonstd，异常→nonstd | discover.py L1205-1228 | ✅ |
| S5 | `_va_skip_leave_trace`：comment 幂等（写前查）+ snippet 捕获 + tmp+os.replace 原子写 + skip_count 递增 + first_skip_at 保留 | discover.py L1231-1297 | ✅ |
| S6 | va-claim 补扫 body 含 [格式完整性] 文案（D11 一处） | discover.py L1378-1380 | ✅ |
| S7 | autopilot.sh va-claim 步含 [格式完整性] 文案（D11 另一处） | scripts/autopilot.sh L472 | ✅ |
| S8 | oc_wake_check 源 H：窗口查询与候选 SQL 对齐 + reason 正则 [a-z][a-z-]* + skip_count 读注册文件 + 状态型键 va-skip:<tid>:<skip_count> | scripts/oc_wake_check.sh L372-419 | ✅ |
| S9 | 源 H 底部统一写回（va_skip_new_keys 排除列表含 va-skip） | oc_wake_check.sh L430-446 | ✅ |
| S10 | 容器豁免双保险：legit-container reason 不输出 | oc_wake_check.sh L405-406 | ✅ |
| S11 | constants CLAIM_HINT_LINE + cmd_chain _dev_card_body 插行（CHECKPOINT → CLAIM_HINT → WIP，WIP 末行） | constants.py L263-266 + cmd_chain.py L715-718 | ✅ |
| S12 | 存量实证：t_4436b52e 已有 VA 卡 t_679f3765 | `devppl_query.sh task t_679f3765` → `va-claim: t_4436b52e | done | verifier` | ✅ |

**合计 12/12 PASS（与 QA-EXEC 一致，全部在 main @ 6195f34 核实）。**

---

## 5. 探针复验 + 漏报探针（47/47 PASS）

### 5.1 QA-EXEC 探针 P1-P6 复验（本卡独立执行）

> 方法：拷贝 QA-EXEC 探针脚本 `scripts/qa_dpl060_probes.sh` 到本卡 worktree 后重跑（同一 main 代码，双重覆盖）。

| # | 探针 | 实测 | 结果 |
|---|------|------|:---:|
| P1 | 条件 3 run 选取边界：run status='done' 命中 / 'gave_up' 不命中 | 复验：done 补建 / gave_up 未建 + nonstd skip 留痕恰 1 条 + skipped=1 | ✅ |
| P2 | 条件 4 双条件边界：大写 commit ref 命中 / 裸 commit 负例 | 复验：大写命中补建 / 裸 commit 仍 skip | ✅ |
| P3 | 注册文件损坏恢复：旧 json 非法 → skip_count 从 1 重计（fail-open） | 复验：不抛、字段齐全、skip_count=1、reason=nonstd | ✅ |
| P4 | comment 幂等边界：同 (task_id,reason) 3 次扫描 → 恰 1 条 | 复验：comment 恰 1 条；注册 skip_count=3 | ✅ |
| P5 | 源 H 真实库只读冒烟：live board 不崩、不写卡 | 复验：exit 0 / 任务数不变 / 无 traceback；输出 2 行含 1 行 [va-skip] | ✅ |
| P6 | CLAIM_HINT_LINE 插行零回归：T59e/i/j 断言存在 + WIP 末行 | 复验：T59e/i/j 各 1；CHECKPOINT < CLAIM_HINT < WIP 且 WIP 末行 | ✅ |

**P1-P6 复验：PASS=19 FAIL=0（与 QA-EXEC 一致）。**

### 5.2 漏报探针（QA-D2 新增，检查 QA-EXEC 是否漏判）——28/28 PASS

> 独立编写 `scripts/qa_dpl060_d2_probes.sh`（A-N，28 断言），针对 test-plan §5 之外的边界。

| # | 探针 | 目标 | 实测 | 结果 |
|---|------|------|------|:---:|
| A | 条件 1 回归：comment 含 **changed_files** 段 → 补建 | R3 既有行为未被 R1 破坏 | va-backfill-t_d2a 建卡 | ✅ |
| B | 条件 2 回归：comment 含 JSON file_modified marker → 补建 | DPL-033 行为保留 | va-backfill-t_d2b 建卡 | ✅ |
| C | 条件 3 类型白名单：claims 只含 test_passed → 不命中 | 非文件类型不误建 | 不建 + nonstd 留痕 1 条 | ✅ |
| D | 条件 3 空数组权威：changed_files=[] → 不命中 | claims:[]/changed_files:[] 权威无产物信号 | 不建 | ✅ |
| E | 条件 4 IGNORECASE：大小写混合 Commit ref + 交付语义 → 命中 | 正则大小写边界（P2 只测全大写） | va-backfill-t_d2e 建卡 | ✅ |
| F | 容器豁免全路径：legit-container → 无 comment 无注册文件 | D6 豁免完整链路（P 系列未覆盖注册文件断言） | comment=0 / 注册=0 / skipped 计数如实=1 | ✅ |
| G | 源 H reason 正则边界：comment 含全角括号时间戳 → reason 仍提取 no-claim | 防 `\S+` 吞时间戳进 reason | 真实 oc_wake_check 输出 `t_d2g.*reason=no-claim` | ✅ |
| H | 源 H 状态型键幂等：同 skip_count 重跑 → 不重复报 | va-skip:<tid>:<skip_count> seen 写回 | 第 2 跑 t_d2g/t_d2i 均不再报 | ✅ |
| I | 源 H 计数增长重报：skip_count 1→2 → 自然重报 | 状态型键变化语义 | 第 3 跑 t_d2g 以 skip_count=2 重报 | ✅ |
| J | CLAIM_HINT 单一源：cmd_chain 插行引用 constants 常量（非硬编码副本） | R3 D10 防双源漂移 | cmd_chain.py 引用 2 处 / constants.py 定义恰 1 处 | ✅ |
| K | va-claim 文案两处一致：discover 补扫 + autopilot 均含 [格式完整性] | D11 双处一致性 | discover 1 处 + autopilot 1 处 | ✅ |
| L | 红线未动：_VA_BACKFILL_MAX_PER_TICK=10 + 窗口默认 24h | 非目标红线守卫 | 10 / 24 | ✅ |
| M | metadata 非 JSON fail-open：坏 metadata → 不抛，回退条件 4 | 解析失败 Fail-open 语义 | 不抛 / 无 Traceback / 不建 / no-claim 留痕 | ✅ |
| N | claims 数组非 dict 元素：类型安全不抛不命中 | isinstance dict 守卫 | 不抛 / 无 Traceback / 不建 | ✅ |

**漏报检查结论：QA-EXEC 未漏判任何缺陷；QA-D2 补充探针 A-N 全部通过（28/28）。**

---

## 6. R1-R4 交叉核对（与 QA-EXEC 报告交叉印证）

| # | 验收要点 | 本卡证据 | 结果 |
|----|---------|---------|:---:|
| R1-a | done 卡 claim 只含「4. 交付 - commit e0e84a2（3 files）」→ 补建 | 基线 T9a-d（G1 75/0）+ 探针 P2/E 复验 | ✅ |
| R1-b | comment 无产物但 metadata.claims 含 file_modified → 补建 | 基线 T9e-g + 探针 P1 复验 | ✅ |
| R1-c | metadata.claims=[] 且 comment 无 commit → 仍 skip | 基线 T9h + 探针 D 新增 | ✅ |
| R1-d | comment 含「参考 commit abc1234」无交付语义 → 仍 skip | 基线 T9i + 探针 P2b 复验 | ✅ |
| R1-e | 既有 T1-T8 断言全部不变（只增不删） | T1-T8 标签在位（grep 实证）+ G1 75/0 | ✅ |
| R2-a | skip 卡 → 卡面 [VA-SKIP] comment 恰 1 条（幂等 D7） | 基线 T10a/a2 + 探针 P4 复验 + 探针 F/Md | ✅ |
| R2-b | .pipeline/va-skip/<tid>.json 字段齐全 | 基线 T10b-b5 + 探针 P3 复验 | ✅ |
| R2-c | 源 H 输出含卡+reason+skip_count；重跑不重复报（状态型键） | 基线 T10c-c3+e + 探针 P5 复验 + 探针 G/H/I 新增 | ✅ |
| R2-d | 容器卡不写 comment、不出现在源 H（D6 豁免） | 基线 T10d/d2 + 探针 F 新增 | ✅ |
| R3-a | dev 卡 body 含 CLAIM_HINT_LINE | 基线 T59i（G3 398/0）+ 探针 P6a 复验 + 探针 J | ✅ |
| R3-b | CLAIM_HINT_LINE 在 WIP 之前（WIP 保末行） | 基线 T59j + 探针 P6b-d 复验 | ✅ |
| R3-c | va-claim 卡 body 含格式完整性文案（D11 两处） | 静态 S6/S7 复验 + 探针 K | ✅ |
| R3-d | claim-schema skill「格式演进同步规则」节 | ⏳ **DPL-061 t_6c381232 跟进**（OBS-1，本链不实测） | ⏳ |
| R4-a | 三套脚本回归全绿 + pytest 无新增失败 | va 75/0 + number 33/0 + cmd 398/0（§3）+ pytest 281/8/1 零新增（§3.1） | ✅ |
| R4-b | t_4436b52e 实证记录（VA 卡 t_679f3765） | 静态 S12 复验（devppl_query 实测） | ✅ |

**14/15 PASS（与 QA-EXEC 一致；R3-d 归属 DPL-061）。**

---

## 7. 发现汇总与分级（标准 §6 输出格式要求）

### 7.1 判定公式对照（标准 §1.2）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| （无）功能缺陷 | — | — | — | — | — | **0 BLOCKER/MAJOR/MINOR/SUGGESTION** |
| OBS-1（R3-4 skill 节跨 profile 回滚） | ✅（va-claim 验证不查格式演进规则） | ❌（机制本身已含 D11 文案） | ✅（DPL-061 独立链验证） | 否 | 否 | **观察项**（归属 DPL-061 t_6c381232，非缺陷） |
| OBS-2（源 H 真实库冒烟含 1 行 [va-skip]） | ✅（live board 现存真实 skip 卡） | ❌（只报告不写卡） | ✅（OC 处置后自然消失） | 否 | 否 | **观察项**（预期行为，P5 复验确认） |
| OBS-3（no-claim 分支设计使然） | ✅（无 claim 卡不进入条件 3） | ❌（R2 恰好补位留痕） | ✅（OC 按 no-claim 分类裁定） | 否 | 否 | **观察项**（设计使然，探针 P4/Md 实测） |

### 7.2 SLA 对照（标准 §8）

- 本卡 0 BLOCKER / 0 MAJOR → **无 SLA 触发**（QA-EXEC 与 QA-D2 均无发现）。
- OBS-1/OBS-2/OBS-3 均为观察项（非缺陷），不设 SLA；OBS-1 由 DPL-061 链跟进，OBS-2 由部署态 qa-post/OC 补观测。

### 7.3 分级示例对照（标准 §5 表）

- 未发现「四条件全命中仍 skip 且无留痕」类 BLOCKER（探针 A/B/E 命中补建 + P4/F 留痕幂等全过）。
- 未发现「[VA-SKIP] comment 文案与文档不一致」类 MINOR（S5 读码一致 + P4/F/Md 实测文案含时间戳+处置指引）。
- 未发现「源 H 对 legit-container 防御冗余」类 SUGGESTION（S10 双保险符合 arch D6，探针 F/G 实测）。

---

## 8. 发布门禁对照（标准 §10）

| 门禁条件 | 数值 | 满足 |
|---------|:---:|:---:|
| BLOCKER = 0 | 0 | ✅ |
| MAJOR ≤ 3 | 0 | ✅ |
| 安全漏洞 = 0 | 0 | ✅ |
| 无未裁定的申诉 | 0 | ✅ |

**发布门禁满足。DPL-060 结果评审通过，可进入 va-qa → qa-post。** 注：被测对象 main @ 6195f34 与 QA-EXEC 完全一致（D2 阶段 main 未前进），本卡在同一提交上独立复跑全部证据链，qa-post 阶段只需确认后续 merge 未引入回归。

---

## 9. 评审建议

1. **放行**：QA-EXEC 报告分级判定准确、证据链完整、无漏报无错判。DPL-060 可继续 va-qa → qa-post 流程。
2. **OBS-1 处置（同 QA-EXEC）**：R3-4 claim-schema skill 节归属 DPL-061 t_6c381232（game-engine 跟进）；qa-post/qa-exec 在 DPL-061 合入后复验。
3. **OBS-2 处置（同 QA-EXEC）**：源 H 对 live board 现存 [va-skip] 卡的只读报告为预期行为；部署态由 qa-post/OC 补观测并处置（补建 VA / 要求补 claim / 确认容器归档）。
4. **OBS-3 处置（同 QA-EXEC）**：no-claim 分支设计使然（R2 恰好补位），非缺陷，无需动作。
5. **无新增缺陷/观察**：QA-D2 漏报探针 A-N（28/28）全部通过，未发现 QA-EXEC 遗漏的功能缺陷或边界问题。

---

## 附：执行记录

- 独立复跑（main @ 6195f34）：`bash scripts/test_va_backfill.sh`（75/0）+ `bash scripts/test_number_backfill.sh`（33/0）+ `bash scripts/test_cmd_channel.sh`（398/0）+ `python3 -m pytest tests/ -q --tb=no`（281/8/1，624.28s，零新增）
- 探针复验：P1-P6（QA-EXEC 脚本拷贝重跑）19/19；漏报探针 A-N（本卡独立编写 `scripts/qa_dpl060_d2_probes.sh`）28/28
- 静态 S1-S12 独立读码（§4）
- 只读 DB 核对：`devppl_query.sh task t_679f3765` → `va-claim: t_4436b52e | done | verifier`（受控脚本，无内联裸读）
- 被测提交：devPPL main @ 6195f34（S1 77dc2d1 + S2 08ab896 + S3 6195f34 全部已合入）
- 本卡发现笔记：`.pipeline/wip/t_affe716b.md`（六节模板）
- commit：`5634b0f [WIP] checkpoint t_affe716b #1` + 最终 claim commit @ wt/t_affe716b
