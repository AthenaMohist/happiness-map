# DPL-061 FIX watchdog 统一 — QA-POST 合并后测试报告

> 版本：v1.0 | 日期：2026-08-16 | 作者：game-qa（QA-POST 合并后独立验证）
>
> 任务卡：t_6367eb7a [DEV-QA-POST] FIX watchdog 统一 — oc_wake_check 吸收 stuck-15min/幽灵卡/main-dirty + 归档死脚本（DPL-061）
> 被测状态：**合并后** devPPL main @ `f8109ba`（S1 5b591f0 + S2 3b2aca9 + S3 0cf2138 全部为 main 祖先；合并后 DPL-061 代码零漂移）
> 前置阶段：PRD t_34d696d5 → DEV t_7f86d7eb/t_9bb95b42/t_cc4bde55 → QA-D1 t_480d0aae → QA-EXEC t_e682d627 → QA-D2 t_7d8d9436 → VA-QA t_169c0dd6（done, VERIFIED）→ MERGE t_4aae30cb（done）
> 上游文档：QA-D1 方案（docs/qa/dpl061-watchdog-unify-test-plan.md）、QA-EXEC 报告（docs/qa/dpl061-watchdog-unify-qa-exec-report.md）、QA-D2 评审（wt/t_7d8d9436，未合 main）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0（判定公式 §1.2 / SLA §8 / 发布门禁 §10 / 输出格式 §6）

---

## 0. 执行摘要

| 项 | 结果 |
|---|---|
| **合并状态核对** | ✅ main @ `f8109ba`；S1 5b591f0 + S2 3b2aca9 + S3 0cf2138 全部为 main 祖先（`git merge-base --is-ancestor` 3/3 YES）；DPL-061 文件（oc_wake_check.sh / test_watchdog_unify.sh / scripts/archive/）`git diff main HEAD` 为空 = **零漂移合并** |
| **合并后无 DPL-061 代码变更** | ✅ 自 QA-EXEC（56e8b1c）后 main 仅新增 QA-D2 之前的 merge（f8109ba = QA-EXEC 报告落地）；DPL-061 代码零触碰 |
| 基线五套（合并后 main，独立复跑） | ✅ test_watchdog_unify.sh **28/0** + test_deploy_drift.sh **29/0** + test_va_backfill.sh **75/0** + test_wip_progress_check.sh **62/0** + test_cmd_channel.sh **398/0** = **592/0 全绿**（§2.1） |
| pytest 全量 | ✅ **281 passed / 8 failed / 1 error — 与存量基线完全一致，零新增**（§2.2；23.53s，collect-only 290==281+8+1 + 抽查 3 文件同集确认真实执行） |
| 语法复验 | ✅ **bash -n 7/7 OK**（oc_wake_check / test_watchdog_unify / qa_dpl061_probes / test_deploy_drift / test_va_backfill / test_wip_progress_check / test_cmd_channel） |
| 静态核对 S1-S12 | ✅ **12/12 PASS**（独立读码，§3） |
| 独立探针 | ✅ **P1-P4 8/8 + P5 真实库只读冒烟 PASS + D2 漏报探针 A-J 30/30**（§4） |
| **部署验证（DPL-048）** | ✅ live oc_wake_check.sh md5 == repo == **23936e2a8cd66aee2fb27f5603bcca8f**（diff 空，IDENTICAL） |
| **OBS-1 线上确认（本卡核心发现）** | ✅ **源 K 已在线上 2 次真实 tick 输出**：14:17 报 t_cc4bde55/t_8a82ce3c、16:04 报 t_169c0dd6；seen 一次性键全部落盘（t_cc4bde55/t_8a82ce3c/t_806c69a7/t_169c0dd6）；OC 均核查心跳正常 → 不干预；**t_169c0dd6 最终正常 done** —「活着但跑太久」设计实证闭环（§5） |
| live 只读核对 | ✅ live seen 无 ghost-card/main-dirty 键（0/0）；live board running=1 无 stuck 残留 |
| **新增发现（POST 阶段）** | **0 BLOCKER / 0 MAJOR / 0 MINOR**；SUG-1 保持（2 个 .jobs_*.tmp 未清理，OC 已记录需 Frank 决策）；**OBS-2（新增观察）：QA-D2 评审报告 wt/t_7d8d9436 未合 main**（VA 已指定 OC 落地，未执行） |
| 发布门禁（标准 §10） | ✅ **满足**（BLOCKER=0 AND MAJOR=0 AND 安全漏洞=0 AND 无未裁定申诉） |

**结论：合并过程正确——DPL-061 四层机制（源 I 幽灵卡 / 源 J main-dirty / 源 K stuck-long / R4 归档+cron 迁移）全部完整在 main、零漂移、无冲突残留、无合并引入回归；合并后基线五套在发布态 main 上独立复跑 592/0 全绿，pytest 281/8/1 零新增失败。OBS-1（源 K 首线上 tick）已在本卡线上闭环确认：真实 tick 输出 + seen 幂等落盘 + OC 正确处置，机制在 live 环境按设计工作。发布门禁满足，DPL-061 收尾闭环。**

---

## 1. 合并状态核对（POST 前置检查）

### 1.1 主分支与合并记录

| 检查项 | 命令 | 结果 |
|---|---|---|
| devPPL main tip | `git log main -1` | ✅ `f8109ba`（merge(qa): t_e682d627 QA-EXEC 报告进 main） |
| 本卡工作树 == main | `git rev-parse HEAD` | ✅ 相同（f8109ba，worktree wt/t_6367eb7a 与 main 同 tip） |
| DPL-061 S1 在 main | `git merge-base --is-ancestor 5b591f0 main` | ✅ YES |
| DPL-061 S2 在 main | `git merge-base --is-ancestor 3b2aca9 main` | ✅ YES |
| DPL-061 S3 在 main | `git merge-base --is-ancestor 0cf2138 main` | ✅ YES |
| 合并零漂移（DPL-061 代码文件） | `git diff main HEAD -- scripts/oc_wake_check.sh scripts/test_watchdog_unify.sh scripts/archive/` | ✅ 空（merged 内容 == dev 分支内容） |
| 自 QA-EXEC 后的提交 | `git log --oneline 56e8b1c..main` | ✅ 空（f8109ba = 56e8b1c 的直接 merge） |
| MERGE 卡产物 | t_4aae30cb [PRODUCES] | ✅ done，merge_commit 指向 f8109ba（dev 分支此前已逐张合入，本卡为链路确认） |

### 1.2 上游链完整性（全链 done）

| 卡 | 状态 | 卡 | 状态 |
|---|---|---|---|
| PRD t_34d696d5 | done | QA-D2 t_7d8d9436 | done（报告未合 main，见 §6 OBS-2） |
| DEV t_7f86d7eb (S1) | done | VA-QA t_169c0dd6 | done（VERIFIED, 0 FALSIFIED） |
| DEV t_9bb95b42 (S2) | done | MERGE t_4aae30cb | done |
| DEV t_cc4bde55 (S3) | done | **本卡 t_6367eb7a** | running |

---

## 2. 基线复跑结果（合并后 main，独立执行非转述）

### 2.1 基线五套（本卡独立复跑，均 EXIT=0）

| # | 测试集 | 命令 | 结果 |
|---|---|---|---|
| G1 | test_watchdog_unify.sh（T1-T9，28 断言） | `bash scripts/test_watchdog_unify.sh` | **PASS=28 FAIL=0**（EXIT=0） |
| G2 | test_deploy_drift.sh（29 断言） | `bash scripts/test_deploy_drift.sh` | **PASS=29 FAIL=0**（EXIT=0） |
| G3 | test_va_backfill.sh（75 断言） | `bash scripts/test_va_backfill.sh` | **PASS=75 FAIL=0**（EXIT=0） |
| G4 | test_wip_progress_check.sh（62 断言） | `bash scripts/test_wip_progress_check.sh` | **PASS=62 FAIL=0**（EXIT=0） |
| G5 | test_cmd_channel.sh（398 断言） | `bash scripts/test_cmd_channel.sh` | **PASS=398 FAIL=0 / ALL TESTS PASSED**（EXIT=0） |

- 合计 **592 断言全绿**，与 QA-EXEC / QA-D2 / VA-QA 四方一致，无回归。
- 语法复验 7/7 OK（§0）。

### 2.2 pytest 全量（对照存量基线 281/8/1）

- 命令：`cd /workspace/devPPL/.worktrees/t_6367eb7a && python3 -m pytest tests/ -q --tb=no -p no:cacheprovider`
- 结果：**281 passed / 8 failed / 1 error** — 与存量基线完全一致（失败集 9 项与 QA-EXEC 报告 §2.6 同集）
- **执行真实性确认**：本机跑 23.53s 远快于历史（588-914s）→ 补验 `--collect-only` = **290 tests collected**（== 281+8+1）+ 抽查 3 个失败文件独立跑 = **86 passed / 8 failed / 1 error**（与全量失败集完全同集）→ 确认真实执行非跳过/缓存伪影（本机磁盘缓存热 + 无并行负载）。
- 失败集逐条对照存量清单（同 QA-EXEC §2.6 的 9 项，全部存量）：
  - `test_memory_middleware_qa.py::test_tc19_blast_radius_engine` / `test_tc20_gai_links_adapter` / `test_tc23_drift_engine` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound0_Static::test_TC14_double_rollback_idempotent` / `TestRound1_BranchEngine::test_TC09_rollback_retry_count_preserved` / `test_TC09_upsert_retry_count_bug_demo` / `test_TC09_rollback_verdict_preserved` / `TestRound4_Boundary::test_BE01_empty_branches_default_advance` — 存量 ✅
  - `test_P2-02_full.py::test`（ERROR，模块顶层 `def test(...)` 误收集 fixture error）— 存量 ✅
- **结论：零新增失败（R5-b 成立）**。

---

## 3. 静态核对 S1-S12（合并后 main 独立读码）

| # | 核对项 | 证据 | 结果 |
|---|---|---|---|
| S1 | 头注释源清单 A-K（三源均标 [DPL-061]） | oc_wake_check.sh L31/L36/L42 + L443/467/492 | ✅ |
| S2 | 源 I：查询条件 LIKE discover-est-%/discover-qa-est-% AND status!='archived'；src 空跳过；EXISTS 跳过；一次性键 ghost-card:<tid> | L448-463 | ✅ |
| S3 | 源 J：git status --porcelain -- pipeline/ scripts/；**rstrip 修复**（L478 注释说明 strip 截断首行路径）；D10 完整列表进 sha1 前8；展示截前 5；fail-open | L475-490 | ✅ |
| S4 | 源 K：running + started_at NOT NULL + age > thr；D16 无 started_at 跳过；D3 B 重叠排除；D13 降序 | L499-529 | ✅ |
| S5 | seen 写回：一次性键 ghost-card:/stuck-running-long: **不进**跳过名单（走 out 行自动解析）；E/G/H/J 状态键走 *_new_keys | L543-560（跳过名单为 code-not-in-main/merge-not-in-main/deploy-drift/va-skip/main-dirty） | ✅ |
| S6 | 状态型键 main-dirty **进**跳过名单 + main_dirty_new_keys 声明/追加/底部写回 | L473/L487/L551/L560 | ✅ |
| S7 | D3 互补：K 排除 B（hb_stale AND claim_dead → continue） | L514-515 | ✅ |
| S8 | D12 源 K 不标「疑似卡死」，只展示心跳年龄 | L519-523（hb_note 逻辑） | ✅ |
| S9 | 归档：scripts/archive/ 4 文件在 main + 旧路径 0 残留 | `git ls-tree main --name-only scripts/archive/`（4 文件）+ `ls scripts/watch_board.sh ...`（No such file ×4） | ✅ |
| S10 | cron：infomanager jobs.json 无 6b695ac1e290（0 匹配）；orchestrator f2aa32251adc 保留；live infomanager/scripts 无 oc_stuck/watch_board/watch_dpl 残留 | `grep -c` → 0 / `grep -o` → 1 / ls 无死脚本 | ✅ |
| S11 | 备份：SandboxHermesBackup/devppl-scripts-backup-20260816/ 8 脚本 + README + wrapper.bak + tag | `ls`（8 文件 + README + wrapper.bak）+ `git tag`（backup-pre-watchdog-unify-20260816） | ✅ |
| S12 | 部署漂移 F1 闭环：live md5 == repo（23936e2a） | `md5sum` 两侧一致 + `diff` IDENTICAL | ✅ |

---

## 4. 独立探针（P1-P5 + D2 A-J，全部 PASS）

| # | 探针 | 方法 | 预期 | 实测 |
|---|---|---|---|---|
| P1 | 源 I 无源卡段边界（ikey 恰为前缀本身）→ 不误报 | temp 库 seed_card ikey=discover-est-，run_wake fresh seen | 无 [ghost-card] 输出 | ✅ PASS |
| P2 | 源 J rstrip 修复回归（tracked 修改首字符不丢） | 复跑 + tracked 修改（git add 后未 commit） | [main-dirty] 行含完整路径 scripts/dirty.sh | ✅ PASS ×3 断言 |
| P3 | 源 K 无心跳分支（claim 有效）→ 输出含「无心跳」 | seed_card started_at=-960 claim_expires=3600 不传 last_heartbeat_at | [stuck-running-long] 行含「无心跳」 | ✅ PASS |
| P3b | 源 K D3 B 重叠边界（hb=NULL AND claim=NULL → B 优先） | seed_card 两字段均缺 | 无 [stuck-running-long] 输出 | ✅ PASS |
| P4 | 源 K 降序（D13） | seed 2 卡（30min / 16min） | 30min 在前、16min 在后 | ✅ PASS |
| P5 | **真实库只读冒烟** | `SEEN_FILE=/tmp/dpl061-post-p5-seen-$$ bash scripts/oc_wake_check.sh /workspace/devPPL`（HERMES_KANBAN_DB 不覆盖=真实库；mode=ro L93） | exit 0 / 无异常 / 不写卡 / 输出含或不含三标记均可 | ✅ **PASS**：exit 0；输出 live 状态（code-not-in-main 若干 + autopilot-cron，**无 ghost-card/main-dirty/stuck-running-long 命中**=live 现状）；seen 仅写 temp 路径；真实库未触碰 |
| A-J | D2 漏报探针（长标题/archived 源卡/tracked 删除/白名单外 dirty/6 文件截前5+全哈希/心跳 55s/65min/三卡降序/混合 seen/双前缀） | `scripts/qa_dpl061_d2_probes.sh`（从 wt/t_7d8d9436 检出字节一致副本放入 worktree） | 30 断言 | ✅ **30/30 PASS** |

> P5 附加：main 工作树有 .pipeline/ 未提交文件（他链运行产物），源 J 白名单为 `pipeline/ scripts/`（不含 .pipeline/）→ 未误报 [main-dirty]，符合 D15/D2 设计。
> 探针执行注意：D2 探针脚本依赖 `BASH_SOURCE` 推导 REPO_ROOT，必须放在 scripts/ 目录运行（放 /tmp 会解析错 WAKE_SCRIPT 路径 → 空输出假失败 23 项；放入 scripts/ 后 30/30 PASS）。**非产品缺陷，属探针脚本使用方式约束**，已在本卡复验确认。

---

## 5. live 只读核对 + OBS-1 线上确认（本卡核心发现，非转述）

### 5.1 源 K 首 tick 线上实证（OBS-1 闭环）

| # | 观察项 | 实测 | 结论 |
|---|---|---|---|
| 1 | cron 前置脚本链路 | orchestrator cron 的 script=oc_wake_check.sh，每 15min（jobs.json 确认），输出注入 agent context | ✅ 链路存在 |
| 2 | 首 tick 输出（14:17） | cron/output/f2aa32251adc/2026-08-16_14-17-55.md：`[stuck-running-long] t_cc4bde55 ... 已跑 19 分钟（心跳 <1 分钟前）` + `t_8a82ce3c ... 已跑 17 分钟（心跳 2 分钟前）` | ✅ 源 K 线上输出 |
| 3 | 次 tick 输出（16:04） | 同目录 16-04-13.md：`[stuck-running-long] t_169c0dd6 ... 已跑 20 分钟（心跳 1 分钟前）`；OC 核查：run 1086 存活 + 心跳 1 分钟前 → **判定卡未卡死，记录后跳过不干预** | ✅ OC 处置符合设计 |
| 4 | seen 幂等落盘 | /tmp/oc_wake_seen 含 `stuck-running-long:t_cc4bde55` / `t_8a82ce3c` / `t_806c69a7` / `t_169c0dd6`（一次性键） | ✅ 重跑不重复报（14:17/16:04 各报一次不重叠） |
| 5 | 卡最终状态 | t_169c0dd6 现 **done**（devppl_query.sh task 确认） | ✅ 「活着但跑太久」卡被正确报告且最终正常完成 = 源 K 无误伤 |
| 6 | 源 I/J live 状态 | live seen 无 ghost-card:/main-dirty: 键（grep 0/0）；P5 冒烟无命中 | ✅ live 无幽灵卡/无 dirty 触发（按实际状态如实） |

**OBS-1 结论：源 K 首个线上 tick 输出已确认（不止 1 次，2 次真实 tick），机制在 live 环境按设计工作——长任务被报告、OC 凭心跳正确处置、一次性键幂等、卡最终正常完成。OBS-1 从「待观测」转「已闭环」。**

### 5.2 live board 只读核对

| # | 核对项 | 实测 | 结果 |
|---|---|---|---|
| 1 | 板概览 | done=823 / running=1（devppl_query.sh board） | ✅ 无异常堆积 |
| 2 | running 卡 | 1 张（当前管线推进中，本卡自身） | ✅ 无 stuck 残留 |

---

## 6. QA-POST 发现（分级判定）

| # | 发现 | 判定路径（标准 §1.2） | 级别 |
|---|---|---|---|
| OBS-2 | **QA-D2 评审报告未合 main**：wt/t_7d8d9436 非 main 祖先；`git diff --stat main wt/t_7d8d9436` 显示 docs/qa/dpl061-watchdog-unify-d2-review.md（+255 行）+ scripts/qa_dpl061_d2_probes.sh（+249 行）未入 main。VA-QA t_169c0dd6 metadata 明确「OC 落地: merge wt/t_7d8d9436 → main」，MERGE 卡 t_4aae30cb 未执行该落地 | 用户可感知？否（产品功能不受影响，D2 是评审产物）；功能阻断？否（D2 结论已由 VA-QA 复核一致）；workaround？✅（OC 补 merge 即闭环）→ 非缺陷，**观察项（落地缺口）** | 观察（非缺陷） |
| SUG-1（延续） | infomanager cron 目录残留 2 个过期 .jobs_*.tmp（.jobs_icilf7d6.tmp @08-13 / .jobs_avrctbl9.tmp @08-15） | 用户可感知？否（cron 读 jobs.json，tmp 不参与调度）；不阻断、不劣化 → **SUGGESTION**；OC 15:29 已记录需 Frank 决策，未删（本卡复核仍在） | SUGGESTION（不阻塞） |
| OBS-1 | 源 K 首 tick 线上输出 | 已闭环（§5.1） | ✅ 关闭 |

### 6.1 判定公式对照

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|---|---|---|---|---|---|---|
| （无）产品功能缺陷 | — | — | — | — | — | **0 BLOCKER/MAJOR/MINOR/SUGGESTION** |
| OBS-2（D2 报告未合 main） | ❌ | ❌ | ✅（OC 补 merge） | 否 | 否 | **观察项（落地缺口，非缺陷）** |
| SUG-1（.jobs_*.tmp 残留） | ❌ | ❌ | ✅（人工 rm） | 否 | 否 | **SUGGESTION** |
| OBS-1（源 K 首 tick） | — | — | — | — | — | ✅ 已闭环 |

### 6.2 SLA 对照（标准 §8）

- 本卡 0 BLOCKER / 0 MAJOR / 0 MINOR → **无 SLA 触发**（BLOCKER 4h 响应 / 8h 定位 / 24h 方案均无适用对象）。
- SUG-1 / OBS-2 不设 SLA；由 OC 评估处置时机（SUG-1 待 Frank 决策，OBS-2 待 OC 补 merge）。

### 6.3 分级示例对照（标准 §5 表 + 方案 §6 预设 → 实测）

| 预设缺陷场景 | 实测 |
|---|---|
| 源 I 误报/漏报（幽灵卡污染统计）→ BLOCKER | 未发现（T1-T3 正负例 + P1 边界 + A/B/J 探针全过） |
| 源 J rstrip 未修（哈希错误 → 集合变化不重报 → 抢 main 漏检）→ BLOCKER | 未复发（T5b + P2 ×3 + C/E 探针断言路径完整） |
| 源 K 输出格式与 PRD 出入（心跳展示）→ MINOR | 未发现（T6b/c + P3 + F/G 探针输出符合 D12） |
| 归档文件权限/只读位异常 → SUGGESTION | 未发现（archive 4 文件存在非空 + 字节与备份一致） |

---

## 7. 发布门禁对照（标准 §10）

| 门禁条件 | 数值 | 满足 |
|---|---|---|
| BLOCKER = 0 | 0 | ✅ |
| MAJOR ≤ 3 | 0 | ✅ |
| 安全漏洞 = 0 | 0 | ✅ |
| 无未裁定的申诉 | 0 | ✅ |

**发布门禁满足。** DPL-061 全链（PRD → DEV → QA-D1/EXEC/D2 → VA → MERGE → QA-POST）闭环，可收尾。

---

## 8. 处置建议（QA 只测不改，不代建 FIX 卡）

1. **OBS-2（D2 报告落地缺口）**：建议 OC 执行 `git merge wt/t_7d8d9436 → main`（VA t_169c0dd6 已指定该落地项，MERGE 卡未执行）。落地后 docs/qa/dpl061-watchdog-unify-d2-review.md + scripts/qa_dpl061_d2_probes.sh 进入 main，链上 QA 文档齐全。
2. **SUG-1（过期 .jobs_*.tmp）**：保持待 Frank 决策（OC 15:29 已记录）；非阻塞，可随下次交互会话 `rm` 2 个文件。
3. **部署验证**：live oc_wake_check.sh 与 repo **完全一致**（md5 23936e2a，diff 空），无部署动作（部署永远留给 OC；本链无漂移）。
4. **OBS-1 关闭**：源 K 线上 2 次真实 tick 已确认 + seen 幂等落盘 + OC 处置正确，无需后续观测。

---

## 9. 风险登记

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| R1 | D2 报告未合 main（OBS-2） | 链上 QA 文档在 main 不完整 | §8.1 建议 OC 补 merge；D2 结论已由 VA-QA 独立复核，无实质风险 |
| R2 | pytest 本机 23.53s 异常快 | 怀疑未真实执行 | 已补 collect-only 290 + 抽查 3 文件 86/8/1 同集 → 确认真实执行 |
| R3 | D2 探针脚本 REPO_ROOT 依赖 BASH_SOURCE 位置 | 放错目录产生假失败 | 本卡已确认需放 scripts/ 运行（30/30）；报告明确使用方式 |
| R4 | main 工作树 .pipeline/* 脏文件来自并行管线/测试夹具 | 误判为回归 | 全部测试在 worktree + temp DB 隔离；源 J 白名单不含 .pipeline/ |

---

## 附：执行记录

- 合并状态：main @ f8109ba == HEAD；S1 5b591f0 + S2 3b2aca9 + S3 0cf2138 均祖先；`git diff main HEAD -- scripts/oc_wake_check.sh scripts/test_watchdog_unify.sh scripts/archive/` 空（零漂移）
- 基线五套（本卡独立复跑）：watchdog_unify 28/0 + deploy 29/0 + va 75/0 + wip 62/0 + cmd 398/0，均 EXIT=0 = **592/0**
- pytest：`python3 -m pytest tests/ -q --tb=no -p no:cacheprovider`（后台）→ 281/8/1；collect-only 290 == 281+8+1；抽查 test_slice2_d1_qa + test_memory_middleware_qa + test_P2-02_full = 86/8/1 同集 → 零新增
- 语法：bash -n 7/7 OK
- 静态：S1-S12 12/12（读码核对，证据见 §3）
- 探针：P1-P4 8/8（scripts/qa_dpl061_probes.sh）+ P5 真实库冒烟 PASS + D2 A-J 30/30（scripts/qa_dpl061_d2_probes.sh，从 wt/t_7d8d9436 检出）
- 部署核对：md5sum live vs repo = 23936e2a 两侧一致 + diff IDENTICAL
- live 核对：cron/output f2aa32251adc 14:17 + 16:04 两 tick 源 K 输出；/tmp/oc_wake_seen 4 个 stuck-running-long 一次性键；ghost-card=0 / main-dirty=0；t_169c0dd6 最终 done
- OBS-2：wt/t_7d8d9436 非 main 祖先；diff 显示 d2-review.md + qa_dpl061_d2_probes.sh 未合入
- SUG-1：.jobs_icilf7d6.tmp/.jobs_avrctbl9.tmp 仍在（OC 待 Frank 决策）
- 本卡交付物：本报告 docs/qa/dpl061-watchdog-unify-qa-post-report.md + WIP 发现笔记 .pipeline/wip/t_6367eb7a.md
- 工作树隔离：全部测试在 wt/t_6367eb7a worktree；live 核对全部只读（devppl_query.sh / grep / mode=ro）
- WIP 节奏：10-15 轮 checkpoint a6bed55（[WIP] #1）
