# VA-POST 验证报告 — FIX va_backfill 静默 skip 盲区（DPL-060）

> 版本：v1.0 | 日期：2026-08-16 | 执行人：Verification Agent（verifier profile，t_806c69a7）
> 上游：QA-POST 合并后测试报告（t_26f9fc0f @ 418657a，claim 已推送）→ 本卡 VA-POST 独立复核
> 被测提交：**devPPL main @ 3b2aca9**（DPL-060 S1 77dc2d1 + S2 08ab896 + S3 6195f34 全部为 main 祖先；DPL-061 S1/S2 亦已合入 main）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0
> 验证性质：VA 独立执行（非转述 QA-POST/QA-D2/研发）——合并状态 + 基线全量 + pytest + live 只读核对 + 探针伪影根因读码 + 部署核对

---

## 0. 验证结论（TL;DR）

| 验证项 | 结果 | 证据 |
|---|---|---|
| 被测对象确认（main @ 3b2aca9 含全部 DPL-060 commit） | ✅ S1 77dc2d1 + S2 08ab896 + S3 6195f34 均为 main 祖先 | §1.1 |
| 合并零漂移（DPL-060 代码文件 diff 为空） | ✅ `git diff main HEAD -- discover.py/constants.py/cmd_chain.py/autopilot.sh/oc_wake_check.sh` = 0 行 | §1.2 |
| 语法前置（py_compile 3 + bash -n 5） | ✅ **6/6 OK** | §1.3 |
| 基线三套独立复跑（合并后 main） | ✅ **va 75/0 + number 33/0 + cmd 398/0**，均 EXIT=0 | §2 |
| pytest 全量独立复跑（对照存量基线 281/8/1） | ✅ **281 passed / 8 failed / 1 error（659.05s）**——失败集 8+1 与存量清单逐条一致，**零新增** | §2.1 |
| **live board 只读核对（本卡独立探针，mode=ro）** | ✅ 窗口内 done 无 VA 子卡 4 条全部无 [VA-SKIP] comment；全库 [VA-SKIP] comment=**0**；注册文件=**0**；seen va-skip 键=**0** | §3 |
| **OBS-2 伪影根因读码确认（QA-POST 核心发现）** | ✅ `qa_dpl060_probes.sh` L233 `export HERMES_KANBAN_DB="$KDB"` 泄漏到 P5 段（L258-270 未重置）→ oc_wake_check.sh L58 读 P4 temp DB；live board 实际无 skip 卡 | §4 |
| **部署核对（DPL-048）** | ✅ live oc_wake_check.sh（md5=64b560c8）vs repo（23936e2a）唯一 diff = DPL-061 S2 rstrip 修复（6 行，属 DPL-061 部署职责）；DPL-060 源 H 全部 va-skip 引用在 live（12 处，行号与 repo 完全一致） | §5 |
| 新增缺陷（POST 阶段） | ✅ 产品 **0 BLOCKER/MAJOR/MINOR/SUGGESTION**；1 MINOR 为 QA 探针 env 泄漏（OBS-2 伪影，非产品缺陷） | §6 |
| 发布门禁（标准 §10） | ✅ **满足**（BLOCKER=0 AND MAJOR=0 AND 安全漏洞=0 AND 无未裁定申诉） | §7 |

**结论：DPL-060 三层机制（R1 四条件宽化 / R2 skip 三分类留痕+注册+源 H 巡检 / R3 建卡提示+格式完整性文案）在合并后 main @ 3b2aca9 上经 VA 独立复核全部成立。QA-POST 报告（t_26f9fc0f）核心声明逐项实测一致：基线三套全绿、pytest 零新增、live board 无 skip 残留、OBS-2 伪影根因读码确认。0 FALSIFIED。发布门禁满足，DPL-060 全链收尾闭环。** 唯一文字级不精确：QA-POST 报告写「11 处 va-skip 引用」，实测为 12 处（repo 与 live 完全一致）——不影响结论（见 §5.3）。

---

## 1. 验证对象与方法

### 1.1 被测对象确认

| # | 前置项 | 实测 | 结果 |
|---|---|------|:---:|
| P-1 | devPPL main HEAD | `git log main -1` = 3b2aca9（merge t_9bb95b42 DPL-061 S2 测试+回归） | ✅ |
| P-2 | DPL-060 S1 在 main | `git merge-base --is-ancestor 77dc2d1 main` = YES | ✅ |
| P-3 | DPL-060 S2 在 main | `git merge-base --is-ancestor 08ab896 main` = YES | ✅ |
| P-4 | DPL-060 S3 在 main | `git merge-base --is-ancestor 6195f34 main` = YES | ✅ |
| P-5 | 合并零漂移 | `git diff main HEAD -- pipeline/discover.py pipeline/constants.py pipeline/cmd_chain.py scripts/autopilot.sh scripts/oc_wake_check.sh` = **0 行** | ✅ |
| P-6 | 语法前置 | py_compile 3/3（discover/constants/cmd_chain）+ bash -n 5/5（autopilot/oc_wake_check/test_va_backfill/test_cmd_channel/test_number_backfill）= **6/6** | ✅ |
| P-7 | 测试隔离 | 全部测试在本 worktree（wt/t_806c69a7）执行；live 核对全部只读（mode=ro / temp SEEN）；主 repo 零写 | ✅ |

### 1.2 验证方法（独立执行，不转述）

- M1：基线三套独立复跑（va/number/cmd，后台并行，本 worktree）
- M2：pytest 全量独立复跑（HOME=/root 复刻 worker 环境）+ 失败集逐条对照存量清单
- M3：live board 只读探针（qa_dpl060_post_live_probe.py 拷贝自 wt/t_26f9fc0f + 本卡独立核对）
- M4：OBS-2 伪影根因读码（qa_dpl060_probes.sh P4/P5 段 + oc_wake_check.sh L58）
- M5：部署核对（md5 + diff live vs repo oc_wake_check.sh + va-skip 引用行号比对）
- M6：DPL-060 机制代码复核（discover.py 四条件 OR / 三分类留痕 / 注册 / 源 H 巡检 + constants/cmd_chain/autopilot R3 文案）

---

## 2. 基线三套 + pytest 独立复跑（合并后 main @ 3b2aca9）

### 2.1 基线三套（本卡独立复跑，均 EXIT=0）

| # | 测试集 | 命令 | 结果 |
|---|---|---|---|
| G1 | test_va_backfill.sh（T1-T10，75 断言） | `bash scripts/test_va_backfill.sh` | **PASS=75 FAIL=0**（EXIT=0） |
| G2 | test_number_backfill.sh（33 断言） | `bash scripts/test_number_backfill.sh` | **PASS=33 FAIL=0**（EXIT=0） |
| G3 | test_cmd_channel.sh（398 断言，含 T59e/i/j） | `bash scripts/test_cmd_channel.sh` | **PASS=398 FAIL=0 / ALL TESTS PASSED**（EXIT=0） |

- 与 QA-POST（t_26f9fc0f）声明完全一致：75/0 + 33/0 + 398/0。
- T59e/i/j 专项核对：T59e（末行=WIP 节奏行）✅ / T59i（含 CLAIM_HINT_LINE）✅ / T59j（HINT 在 WIP 之前）✅ —— R3 D10 插行零回归。

### 2.2 pytest 全量（对照存量基线 281/8/1）

- 命令：`cd /workspace/devPPL/.worktrees/t_806c69a7 && HOME=/root python3 -m pytest tests/ -q --tb=no`（后台，唯一日志路径 /tmp/va_pytest_home_root.log）
- 结果：**281 passed / 8 failed / 1 error in 659.05s（0:10:59）**
- 失败集逐条对照存量清单（与 QA-POST §2.2 完全同集，8+1 项）：
  - `test_memory_middleware_qa.py::test_tc19_blast_radius_engine` — 存量 ✅
  - `test_memory_middleware_qa.py::test_tc20_gai_links_adapter` — 存量 ✅
  - `test_memory_middleware_qa.py::test_tc23_drift_engine` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound0_Static::test_TC14_double_rollback_idempotent` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_rollback_retry_count_preserved` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_upsert_retry_count_bug_demo` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_rollback_verdict_preserved` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound4_Boundary::test_BE01_empty_branches_default_advance` — 存量 ✅
  - `test_P2-02_full.py::test`（ERROR，模块顶层 def test 被误收集）— 存量 ✅
- **结论：零新增失败。**
- ⚠️ 方法学备注：首轮 pytest（默认 HOME）出现 275/14/1，6 项 `test_p0_18_qa.py::test_l1-l6` FileNotFoundError —— 根因为本会话 `HOME=/root/.hermes/profiles/verifier/home`，`~/.hermes/profiles/orchestrator/...` 解析到 verifier profile home 不存在该路径。`HOME=/root` 复跑 6/6 PASS（281/8/1），**非 DPL-060 回归**。与 t_0b8a820f 前轮方法论一致。

---

## 3. live board 只读核对（本卡独立探针）

> 方法：`scripts/qa_dpl060_post_live_probe.py`（拷贝自 wt/t_26f9fc0f @ 418657a，sqlite3 mode=ro URI）直查 `/root/.hermes/kanban.db` + `.pipeline/va-skip/`，只读不写。

| # | 核对项 | 实测 | 结果 |
|---|---|---|---|
| 1 | 窗口内（3600s）done [DEV-*]/[FIX] 无 VA 子卡（源 H 候选集） | 4 条：t_54b89425 / t_12539484 / t_0b8a820f / t_6ff818be —— 全部无 [VA-SKIP] comment | ✅ 源 H 静默如实（无缺口卡） |
| 2 | 全库 [VA-SKIP] comment 盘点 | **0 条** | ✅ 无 skip 留痕残留 |
| 3 | `.pipeline/va-skip/` 注册文件 | **0 个** | ✅ 无注册残留 |
| 4 | seen 中 va-skip 状态型键 | **0 条**（seen 文件不存在/无键） | ✅ 无巡检状态残留 |

- 窗口差异说明：QA-POST 探针（约 14:16 执行）窗口内 5 条（含 t_01738e10，completed 13:23）；本卡探针（约 14:45 执行）窗口 3600s 前移至 13:45，t_01738e10 滑出窗口 —— 4 vs 5 为时间推移导致，非状态差异。
- 独立交叉核对：`devppl_query.sh board` 显示 done 805 / running 3；`devppl_query.sh task t_p4_idem` 返回 BAD_ID —— **P4 fixture 卡确认不在 live board**（OBS-2 伪影旁证）。

---

## 4. OBS-2 伪影根因读码确认（QA-POST 核心发现复核）

| # | 检查点 | 实测 | 结果 |
|---|---|---|---|
| S-1 | `qa_dpl060_probes.sh` P4 段 L233 | `export HERMES_KANBAN_DB="$KDB"`（KDB=P4 temp DB，含 t_p4_idem fixture 卡） | ✅ 与 QA-POST 描述一致 |
| S-2 | P5 段 L258-270 | 未重置/未 unset HERMES_KANBAN_DB，直接 `bash oc_wake_check.sh /workspace/devPPL` | ✅ 泄漏确认 |
| S-3 | `oc_wake_check.sh` L58 | `KANBAN_DB="${HERMES_KANBAN_DB:-/root/.hermes/kanban.db}"` —— P5 场景读到 P4 temp DB | ✅ 泄漏路径成立 |
| S-4 | live board 实况 | 全库 [VA-SKIP] comment=0 / 注册=0 / seen=0；t_p4_idem 不在 live | ✅ live 无真实 skip 卡 |
| S-5 | 分级复核（标准 §1.2） | 探针缺陷（非产品）；用户可感知=是（下游可能处置不存在的卡）、功能阻断=否、workaround=有（只读核对）、安全=否、一致性=否 → **MINOR** | ✅ 与 QA-POST 判定一致 |

**结论：OBS-2 为 QA 探针 env 泄漏伪影，产品行为正确（源 H 静默如实）。QA-POST 修正成立，处置建议合理（P5 段重置 HERMES_KANBAN_DB）。**

---

## 5. 部署核对（DPL-048 前置脚本规则）

> 适用性确认：oc_wake_check.sh 为 cron jobs.json `"script"` 直调脚本（DPL-048 must-sync 清单项）→ 必须 diff/md5 比对 repo vs live。

| # | 检查项 | 实测 | 结果 |
|---|---|---|---|
| D-1 | live 文件存在 | `/root/.hermes/profiles/orchestrator/scripts/oc_wake_check.sh`（30311 B） | ✅ |
| D-2 | md5 比对 | live=`64b560c837a6e1202842c585fb01288f` vs repo=`23936e2a8cd66aee2fb27f5603bcca8f` —— **不一致** | ⚠️ 需 diff 定性 |
| D-3 | diff 定性 | 唯一差异 = **DPL-061 S2 rstrip 修复**（478c478,480：`.stdout.strip()` → `.stdout.rstrip()` + 注释 2 行，T5b 捕获）——属 DPL-061 部署职责（3b2aca9 13:56 合入，live 待 OC 同步），**非 DPL-060 回归** | ✅ |
| D-4 | DPL-060 源 H 在 live | live 含源 H 块（L392-439 + L558 写回），va-skip/VA-SKIP 引用 **12 处**，行号与 repo 完全一致（27/29/393/397/401/417/424/430/434/439/538/551） | ✅ |
| D-5 | DPL-060 源 H 冒烟 | 本卡 live 探针（§3）实测源 H 候选集 4 条无 [VA-SKIP] comment → 源 H 输出 0 行 [va-skip]（与探针一致） | ✅ |

### 5.3 文字级不精确记录（非缺陷）

- QA-POST 报告 §0/附 写「live 版含 **11** 处 va-skip 引用」，实测 grep -n 为 **12** 处（repo 与 live 均 12，行号逐位一致）。判定：计数口径差异（可能未计入头注释块 L27/29），**不影响结论**——源 H 全部引用在 live 属实。不升级为缺陷。

---

## 6. 机制代码复核（DPL-060 三层机制在 main 落点）

| # | 机制 | main 落点（行号） | 结果 |
|---|---|---|---|
| M-1 | R1 四条件 OR（_latest_claim_has_changed_files） | discover.py L1146-1191：① `**changed_files**` 子串（L1179）② JSON file_* marker（L1181）③ metadata.claims/changed_files（L1184→L1086-1117）④ commit+交付语义双条件（L1187→L1120-1143）；条件 3 不命中不短路条件 4（L1186） | ✅ |
| M-2 | R1 metadata 读取（_metadata_has_file_claims） | discover.py L1086-1117：task_runs 最近 done/completed run 的 metadata；claims 数组 type∈(file_created,file_modified) 或 changed_files 非空；claims:[] 权威无产物→False；异常 fail-open | ✅ |
| M-3 | R1 交付/commit 兜底（_claim_has_delivery_commit） | discover.py L1120-1143：commit [0-9a-f]{7,40} AND 交付/产物/files/文件；匹配 t_4436b52e 病例 | ✅ |
| M-4 | R2 skip 三分类（_va_skip_reason） | discover.py L1205-1228：legit-container（有子卡豁免）/ no-claim（无 claim comment）/ nonstd（有 claim 四条件不命中）；异常→nonstd fail-open | ✅ |
| M-5 | R2 留痕（_va_skip_leave_trace） | discover.py L1231-1297：① [VA-SKIP] comment 幂等（(task_id,reason) LIKE 查询 L1250-1259）② .pipeline/va-skip/<tid>.json 原子注册（tmp+os.replace，skip_count 递增 L1274-1297） | ✅ |
| M-6 | R2 源 H 巡检 | oc_wake_check.sh L392-441：候选 SQL 与 _va_backfill_candidates 对齐 + [VA-SKIP] comment 读取 + reason 正则（ASCII 小写+连字符，防全角括号）+ 注册文件 skip_count + 状态型键 va-skip:<tid>:<skip_count>（D9）+ legit-container 双保险跳过 | ✅ |
| M-7 | R3 CLAIM_HINT_LINE | constants.py L263-267：`claim 必须含 **changed_files** 段 或 JSON claims 或 交付/commit 产物段（DPL-060）`；cmd_chain.py L714-716 插于 WIP 之前（WIP 保末行） | ✅ |
| M-8 | R3 autopilot 格式完整性文案 | autopilot.sh L472：va-claim 卡 body 含 `[格式完整性] 若源卡 claim 缺 **changed_files**/JSON claims/交付-commit 产物声明（四源全无）→ 按 claim-schema 标记 [PARTIAL - no structured claims]` | ✅ |
| M-9 | 候选 SQL 排除前缀 | discover.py L1011-1023（_VA_BACKFILL_EXCLUDED_PREFIXES）+ L1040-1042 精确 LIKE 排除（[DEV-QA-SUB-% 等） | ✅ |
| M-10 | 窗口/上限 | discover.py L998/1000：VA_BACKFILL_WINDOW_DEFAULT_H=24 + MAX_PER_TICK=10 + env 覆盖 | ✅ |

---

## 7. 发布门禁对照（标准 §10）

| 门禁条件 | 数值 | 满足 |
|---|---|---|
| BLOCKER = 0 | 0 | ✅ |
| MAJOR ≤ 3 | 0 | ✅ |
| 安全漏洞 = 0 | 0 | ✅ |
| 无未裁定的申诉 | 0 | ✅ |

**发布门禁满足。DPL-060 全链（PRD → DEV → QA-D1/EXEC/D2 → VA-QA → MERGE → QA-POST → VA-POST）闭环。**

---

## 8. 处置建议

1. **OBS-2 探针修复（MINOR，归属 OC 评估）**：`qa_dpl060_probes.sh` P5 段开头重置 `export HERMES_KANBAN_DB=/root/.hermes/kanban.db` 或 `unset HERMES_KANBAN_DB`；P5c 断言加「输出行不含 t_p4_idem」锁定回归。
2. **OBS-2 描述修正**：QA-EXEC/QA-D2 报告中 OBS-2 应改为「live board 无真实 skip 卡（P5 探针 env 泄漏伪影）」，原「部署态补观测处置」建议取消（QA-POST 已修正，本卡复核确认）。
3. **部署**：live oc_wake_check.sh 的 DPL-061 S2 rstrip 修复（唯一 diff）待 OC 同步部署（DPL-061 职责，非本链）；DPL-060 源 H 已在 live，本链无需部署动作。
4. **文字级修正（可选）**：QA-POST 报告「11 处 va-skip 引用」→ 12 处（不影响结论）。
5. **OBS-1 维持**：R3-4 claim-schema skill 节由 DPL-061 t_6c381232 链跟进（该链已合入 S1/S2，S3 待其独立链）。

---

## 9. 风险登记

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| R1 | live oc_wake_check.sh 与 repo 漂移（DPL-061 S2 rstrip 未部署） | live 源 J 路径截断 bug 仍存在（T5b） | §8.3 已记录，属 DPL-061 部署职责；DPL-060 源 H 不受影响（已在 live） |
| R2 | 并发 pytest 干扰 / 共享 /tmp 日志路径 | 读数失真（首轮 275/14/1 伪象） | 唯一日志路径 + HOME=/root 复跑 + 失败集逐条对照（§2.2） |
| R3 | P5 探针泄漏类 bug 可能存在于其它 QA 探针脚本 | 报告描述失实 | 本卡已复核建议 §8.1；后续 QA 卡写探针统一检查 env 隔离 |

---

## 附：执行记录

- 合并状态：main @ 3b2aca9；`git merge-base --is-ancestor` S1/S2/S3 全 YES；`git diff main HEAD -- <5 DPL-060 文件>` = 0 行（零漂移）
- 基线三套（本卡独立复跑）：va 75/0 + number 33/0 + cmd 398/0，均 EXIT=0
- pytest：`HOME=/root python3 -m pytest tests/ -q --tb=no` → **281 passed / 8 failed / 1 error in 659.05s**，失败集与存量清单逐条一致零新增；首轮 275/14/1 为 HOME 环境伪象（test_p0_18_qa 6 项，HOME=/root 复跑 6/6 PASS）
- 语法：py_compile 3/3 + bash -n 5/5 = 6/6 OK
- live 只读探针：qa_dpl060_post_live_probe.py（拷贝自 wt/t_26f9fc0f）→ 窗口 4 条 done 无 VA 子卡全部无 [VA-SKIP] / 全库 [VA-SKIP] comment=0 / 注册=0 / seen 键=0；`devppl_query.sh task t_p4_idem` = BAD_ID（不在 live）
- OBS-2 根因读码：qa_dpl060_probes.sh L233 export HERMES_KANBAN_DB → P5（L258-270）未重置 → oc_wake_check.sh L58 读 P4 temp DB；分级 MINOR（探针缺陷，产品 0 缺陷）
- 部署核对：live md5=64b560c8 vs repo 23936e2a；diff 唯一 = DPL-061 S2 rstrip 修复（478c478,480）；va-skip 引用 12 处 repo/live 行号完全一致（QA-POST 写 11 处，文字级差异不升级）
- 本卡交付物：本报告 + .pipeline/wip/t_806c69a7.md + /root/.hermes/profiles/verifier/.va_reports/<timestamp>_va_t_806c69a7.json
- 工作树隔离：全部测试在 wt/t_806c69a7 worktree；live 核对全部只读（mode=ro / 探针脚本）；主 repo 零写
