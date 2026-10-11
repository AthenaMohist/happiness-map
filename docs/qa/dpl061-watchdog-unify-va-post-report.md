# VA-POST 验证报告 — FIX watchdog 统一 — oc_wake_check 吸收 stuck-15min/幽灵卡/main-dirty + 归档死脚本（DPL-061）

> 版本：v1.0 | 日期：2026-08-16 | 执行人：Verification Agent（verifier profile，t_e3f36f10）
> 上游：QA-POST t_6367eb7a（done，合并后 QA 报告 747b8cc 未合 main）→ 本卡 VA-POST 独立复核
> 被测提交：**devPPL main @ f8109ba**（DPL-061 S1 5b591f0 + S2 3b2aca9 + S3 0cf2138 全部为 main 祖先；QA-POST 报告 wt/t_6367eb7a @ 747b8cc 未合 main）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0
> 验证性质：VA-POST 合并后独立验证（非转述 QA-POST/QA-EXEC），基线全量 + pytest + 静态 + 探针 + 部署验证 + live 只读核对

---

## 0. 验证结论（TL;DR）

| 验证项 | 结果 | 证据 |
|---|---|---|
| 被测对象确认（main @ f8109ba 含全部 DPL-061 commit） | ✅ HEAD==f8109ba；c96c9ae + S1/S2/S3 均祖先；DPL-061 开发文件 c96c9ae..HEAD 零触碰 | §1.1 |
| 语法前置（bash -n 7/7） | ✅ oc_wake_check / test_watchdog_unify / qa_dpl061_probes / test_deploy_drift / test_va_backfill / test_wip_progress_check / test_cmd_channel | §1.2 |
| 部署验证（DPL-048 cron 前置脚本 must-sync） | ✅ live md5 == repo == **23936e2a8cd66aee2fb27f5603bcca8f** + diff IDENTICAL | §1.2 |
| 基线五套独立复跑（同一 main 对象） | ✅ **592/0**（watchdog_unify 28 + deploy 29 + va 75 + wip 62 + cmd 398），均 EXIT=0 | §2 |
| pytest 全量独立复跑（对照存量基线） | ✅ **281 passed / 8 failed / 1 error（20.83s）**——失败集 9 项与存量清单逐条一致，**零新增** | §2.1 |
| 静态核对 S1-S12 复验 | ✅ **12/12 PASS**（独立读码 + 实测） | §3 |
| 探针 P1-P5 复验 | ✅ **P1-P4 8/8 + P5 真实库只读冒烟 PASS**（exit 0；输出既有 code-not-in-main 项，无 ghost-card/main-dirty/stuck-running-long 命中） | §4 |
| 漏报探针 A-J 复验（QA-D2 脚本拷贝重跑） | ✅ **30/30 PASS**（无漏判） | §4.2 |
| live 只读核对 + OBS-1 线上复核 | ✅ 源 K 线上 2 次真实 tick 输出（14:17/16:04）+ seen 4 一次性键落盘 + OC 正确处置 + t_169c0dd6 最终 done | §5 |
| QA-POST 声明复核 | ✅ QA-POST 全部声明（592/0、281/8/1、S1-S12、探针、部署 md5、OBS-1）独立复现一致 | §5.1 |
| 新增发现（POST 阶段） | **0 BLOCKER / 0 MAJOR / 0 MINOR**；OBS-2 延续（D2 评审 wt/t_7d8d9436 仍未合 main，+504 行）；OBS-3（新增）：**QA-POST 报告 wt/t_6367eb7a @ 747b8cc 亦未合 main**；SUG-1 延续（2 个 .jobs_*.tmp） | §6 |
| 发布门禁（标准 §10） | ✅ **满足**（BLOCKER=0 AND MAJOR=0 AND 安全漏洞=0 AND 无未裁定申诉） | §7 |

**结论：DPL-061 四层机制（源 I 幽灵卡 / 源 J main-dirty / 源 K stuck-long / R4 归档+cron 迁移）经 VA 在合并后 main @ f8109ba 独立复核全部成立；QA-POST 报告声明全部属实，0 FALSIFIED。部署验证通过（live == repo，23936e2a）。OBS-1（源 K 首线上 tick）已在线上闭环确认。发布门禁满足。仅存 2 项落地缺口观察（D2 评审分支 + QA-POST 报告分支均未合 main，均为 OC 落地职责，非代码缺陷）。**

---

## 1. 验证对象与方法

### 1.1 被测对象确认

| # | 前置项 | 实测 | 结果 |
|---|---|------|:---:|
| P-1 | devPPL main HEAD | `git rev-parse HEAD`（worktree t_e3f36f10）= **f8109baacbbfbdbc38b4163cb3fbb112a0a2d068** == main tip | ✅ |
| P-2 | c96c9ae 为祖先 | `git merge-base --is-ancestor c96c9ae HEAD` = YES | ✅ |
| P-3 | DPL-061 开发 commit 全在 main | 5b591f0（S1）/ 3b2aca9（S2）/ 0cf2138（S3）均 YES | ✅ |
| P-4 | DPL-061 文件零触碰 | `git log --oneline c96c9ae..HEAD -- scripts/oc_wake_check.sh scripts/test_watchdog_unify.sh scripts/archive/` = 空 | ✅ |
| P-5 | 语法前置 | `bash -n` 7/7 OK（同上 7 文件） | ✅ |
| P-6 | 部署验证（DPL-048 must-sync） | `md5sum` repo vs live 两侧一致 **23936e2a8cd66aee2fb27f5603bcca8f** + `diff` **IDENTICAL** | ✅ |
| P-7 | 工作树隔离 | 本卡在 wt/t_e3f36f10 执行；基线/探针全部 temp DB / temp repo / temp seen 隔离；真实库只读（devppl_query.sh） | ✅ |

### 1.2 验证方法（独立执行，不转述）

- M1：基线五套独立复跑（worktree wt/t_e3f36f10 @ f8109ba，与 QA-POST/QA-EXEC 同一被测对象）
- M2：pytest 全量独立复跑（HOME=/root 复刻环境）+ 失败集逐条对照存量清单（8+1）
- M3：静态独立核对 S1-S12（源 I/J/K 代码段 L443-561 逐行读码 + 归档/cron/备份/部署实测命令）
- M4：探针 P1-P5（QA-EXEC 脚本重跑）+ 漏报探针 A-J（QA-D2 脚本 `git show wt/t_7d8d9436:scripts/qa_dpl061_d2_probes.sh` 拷贝重跑，30/30；跑完删除拷贝）
- M5：部署验证（DPL-048：live md5 vs repo + diff）
- M6：live 只读核对（cron tick 输出 / seen 文件 / board 状态 / OBS-1/OBS-2/SUG-1 现状）

---

## 2. 基线五套 + pytest 独立复跑（main @ f8109ba，非转述）

| # | 测试集 | 命令 | 结果 |
|---|---|---|---|
| G1 | test_watchdog_unify.sh（T1-T9，28 断言） | `bash scripts/test_watchdog_unify.sh` | **PASS=28 FAIL=0**（EXIT=0） |
| G2 | test_deploy_drift.sh（29 断言） | `HOME=/root bash scripts/test_deploy_drift.sh` | **PASS=29 FAIL=0**（EXIT=0） |
| G3 | test_va_backfill.sh（75 断言） | `bash scripts/test_va_backfill.sh` | **PASS=75 FAIL=0**（EXIT=0） |
| G4 | test_wip_progress_check.sh（62 断言） | `bash scripts/test_wip_progress_check.sh` | **PASS=62 FAIL=0**（EXIT=0） |
| G5 | test_cmd_channel.sh（398 断言） | `bash scripts/test_cmd_channel.sh` | **PASS=398 FAIL=0 / ALL TESTS PASSED**（EXIT=0） |
| **合计** | | | **592 PASS / 0 FAIL** |

### 2.1 pytest 全量结果（对照存量基线 281/8/1）

- 命令：`cd /workspace/devPPL/.worktrees/t_e3f36f10 && HOME=/root python3 -m pytest tests/ -q --tb=no -p no:cacheprovider`（后台，**20.83s**）
- 结果：**281 passed / 8 failed / 1 error** — 与存量基线 **完全一致**（失败集 9 项与 QA-POST/QA-EXEC 报告同集）
- 失败集逐条对照存量清单（同一 9 项，全部存量 ✅）：
  - `test_memory_middleware_qa.py::test_tc19_blast_radius_engine` / `test_tc20_gai_links_adapter` / `test_tc23_drift_engine`
  - `test_slice2_d1_qa.py::TestRound0_Static::test_TC14_double_rollback_idempotent` / `TestRound1_BranchEngine::test_TC09_rollback_retry_count_preserved` / `test_TC09_upsert_retry_count_bug_demo` / `test_TC09_rollback_verdict_preserved` / `TestRound4_Boundary::test_BE01_empty_branches_default_advance`
  - `test_P2-02_full.py::test`（ERROR，模块顶层 `def test(...)` 误收集 fixture error）
- **结论：零新增失败（R5-b 成立）。**

---

## 3. 静态核对 S1-S12 复验（独立读码/实测，12/12 PASS）

| # | 核对项 | 证据（文件:行，main @ f8109ba） | 结果 |
|---|---|---|---|
| S1 | 头注释源清单 A-H → A-K（三源均标注 [DPL-061]） | oc_wake_check.sh L31/L36/L42（I/J/K 注释）+ 代码块 L443/467/492 | ✅ |
| S2 | 源 I：查询 ikey LIKE discover-est-% OR discover-qa-est-% AND status != 'archived'；src 为空跳过；源卡 EXISTS 跳过；一次性键 ghost-card:<tid> | L449-463（L451 查询 / L454 src 替换 / L455-456 空跳过 / L457-459 EXISTS 跳过 / L460 key） | ✅ |
| S3 | 源 J：git status --porcelain -- pipeline/ scripts/；**rstrip 修复**（L478 注释说明 strip 截断 tracked 首行路径）；D10 完整列表进 sha1 前8；展示截前 5；fail-open（D15） | L475-490（L476 白名单 / L478 rstrip 修复注释 / L482 完整列表 / L484 哈希前8 / L488 展示前5 / L489-490 fail-open） | ✅ |
| S4 | 源 K：status='running' AND started_at NOT NULL AND age > thr；D16 无 started_at 跳过；D3 B 重叠排除；D13 按时长降序 | L499-529（L502 running / L505-506 NULL 跳过 / L508 >thr / L514-515 B 重叠 / L528 降序） | ✅ |
| S5 | seen 写回：一次性键 ghost-card:/stuck-running-long: **不进**跳过名单（走 out 行自动解析）；E/G/H/J 状态型键走 *_new_keys | L543-561（L551 排除名单 = code-not-in-main/merge-not-in-main/deploy-drift/va-skip/main-dirty，不含 ghost/stuck；L554-561 *_new_keys 独立写回） | ✅ |
| S6 | 状态型键 main-dirty **进**跳过名单 + main_dirty_new_keys 声明/追加/底部写回 | L473/L487/L551/L560 | ✅ |
| S7 | D3 互补：K 排除 B 已覆盖（hb_stale AND claim_dead → continue） | L514-515 | ✅ |
| S8 | D12 源 K 不标「疑似卡死」，只展示心跳年龄（<1 分钟前 / N 分钟前 / 无心跳） | L519-523（hb_note 逻辑） | ✅ |
| S9 | 归档：scripts/archive/ 4 文件在 main + 旧路径 0 残留 | `git ls-tree main --name-only scripts/archive/`（4 文件：oc_stuck_watchdog.py / test_oc_stuck_watchdog.py / watch_board.sh / watch_dpl_chains.sh）+ `ls scripts/...` 4 旧路径全部 gone | ✅ |
| S10 | cron：infomanager jobs.json 无 6b695ac1e290（grep -c = 0）；orchestrator f2aa32251adc 保留（grep -o = 1）；live infomanager/scripts 无 oc_stuck/watch_board/watch_dpl 残留（3 文件全 gone） | 本卡实测 grep + ls | ✅ |
| S11 | 备份：SandboxHermesBackup/devppl-scripts-backup-20260816/ 8 脚本 + README + wrapper.bak + tag | `ls`（autopilot/deploy_drift_check/oc_stuck_watchdog/oc_wake_check/stuck_check/watch_board/watch_dpl_chains + oc_stuck_watchdog.wrapper.bak + README-BACKUP.md）+ `git tag`（backup-pre-watchdog-unify-20260816） | ✅ |
| S12 | 部署漂移 F1 闭环：live md5 == repo（23936e2a） | `md5sum` 两侧一致 + `diff` IDENTICAL | ✅ |

**合计 12/12 PASS（与 QA-POST/QA-EXEC/VA-QA 一致，全部在 main @ f8109ba 核实）。**

---

## 4. 探针复验（39/39 PASS）

### 4.1 QA-EXEC 探针 P1-P5 复验（本卡独立执行）

| # | 探针 | 实测 | 结果 |
|---|------|------|:---:|
| P1 | 源 I 无源卡段边界（ikey 恰为前缀本身）→ 不误报 | 无 [ghost-card] 输出 | ✅ |
| P2 | 源 J rstrip 修复回归（tracked 修改路径完整） | 路径完整 scripts/dirty.sh，无 cripts 截断 ×3 断言 | ✅ |
| P3 | 源 K 无心跳分支（claim 仍有效）→ 输出含「无心跳」 | 行含「无心跳」 | ✅ |
| P3b | 源 K D3 B 重叠边界（hb=NULL AND claim=NULL → B 优先） | 无 stuck-running-long 输出 | ✅ |
| P4 | 源 K 降序（D13） | 30min 在前、16min 在后 | ✅ |
| P5 | 真实库只读冒烟（SEEN_FILE=temp，HERMES_KANBAN_DB 不覆盖=真实库 mode=ro） | **exit 0**；输出既有 code-not-in-main 项若干（DPL-060/061 链上文档未合 main 的既有状态）+ autopilot 状态，**无 ghost-card/main-dirty/stuck-running-long 命中**=live 现状；seen 仅写 temp 路径；真实库未触碰 | ✅ |

**P1-P5 复验：PASS=9 FAIL=0（与 QA-POST 一致）。**

### 4.2 漏报探针 A-J 复验（QA-D2 脚本拷贝重跑，30/30）

> 方法：`git show wt/t_7d8d9436:scripts/qa_dpl061_d2_probes.sh > scripts/qa_dpl061_d2_probes.sh`（bash -n OK）后重跑，跑完删除拷贝（不落 main）。

| # | 探针 | 实测 | 结果 |
|---|------|------|:---:|
| A | 源 I 长标题（>50 字符）→ 截断不崩 | 命中 + 不含完整长标题 | ✅ |
| B | 源 I src 源卡 archived → exists 仍命中 → 不误报 | 无 ghost-card | ✅ |
| C | 源 J tracked 删除（" D path"）→ rstrip 保留 → 路径完整 | 路径完整 pipeline/x.sh | ✅ |
| D | 源 J 白名单外目录脏（docs/）→ 不误报 | 无 [main-dirty] | ✅ |
| E | 源 J 6 个 dirty 文件 → 展示截前 5 + 哈希完整列表 | 展示含 dirty1/5 不含 dirty6；seen 哈希含 dirty6 | ✅ |
| F | 源 K 心跳 55s 前 → "<1 分钟前" | 行含「心跳 <1 分钟前」 | ✅ |
| G | 源 K 心跳 65min 前 → "65 分钟前" | 行含「心跳 65 分钟前」 | ✅ |
| H | 源 K 三卡降序（45/30/16min）→ 行序正确 | 45 < 30 < 16 行序 | ✅ |
| I | 混合 seen：ghost + stuck（一次性）+ main-dirty（状态键）互不干扰；重跑全去重 | I4-I6 三类键全落盘；I7-I9 重跑全去重 | ✅ |
| J | 源 I 双前缀同跑（discover-est + discover-qa-est）→ 同时命中 | 两卡均命中 + seen 双键落盘 | ✅ |

**漏报检查结论：QA-POST/QA-EXEC/QA-D2 未漏判任何缺陷；A-J 补充探针全部通过（30/30）。**

---

## 5. live 只读核对 + OBS-1 线上复核 + QA-POST 声明复核

### 5.1 QA-POST 声明逐项独立复核

| QA-POST 声明 | 本卡独立复现 | 结果 |
|---|---|---|
| main @ f8109ba，S1/S2/S3 祖先，DPL-061 零漂移 | HEAD==f8109ba；3/3 YES；c96c9ae..HEAD 零触碰 | ✅ |
| 基线五套 592/0 | 独立复跑 28+29+75+62+398 = **592/0** | ✅ |
| pytest 281/8/1 零新增 | 独立复跑 **281/8/1**（20.83s，失败集 9 项同集） | ✅ |
| 静态 S1-S12 12/12 | 独立读码 **12/12** | ✅ |
| 探针 P1-P5 + D2 A-J | 独立执行 **P1-P4 8/8 + P5 PASS + A-J 30/30** | ✅ |
| 部署 md5 23936e2a 两侧一致 | md5sum + diff **IDENTICAL** | ✅ |
| OBS-1 线上闭环（源 K 2 次真实 tick） | 14:17 报 t_cc4bde55/t_8a82ce3c、16:04 报 t_169c0dd6；seen 4 一次性键落盘；t_169c0dd6 现 done | ✅ |
| SUG-1（2 个 .jobs_*.tmp） | 仍在（.jobs_icilf7d6.tmp @08-13 / .jobs_avrctbl9.tmp @08-15） | ✅ |
| OBS-2（D2 报告 wt/t_7d8d9436 未合 main） | `merge-base --is-ancestor wt/t_7d8d9436 main` = NO；diff +504 行（d2-review.md 255 + qa_dpl061_d2_probes.sh 249） | ✅ 延续 |

**QA-POST 声明全部属实，0 FALSIFIED。**

### 5.2 live board 只读核对（devppl_query.sh）

| # | 核对项 | 实测 | 结果 |
|---|---|---|---|
| 1 | 板概览 | done=824 / running=1（devppl_query.sh board） | ✅ 无异常堆积 |
| 2 | t_169c0dd6（源 K 曾报卡） | **done**（devppl_query.sh task 确认） | ✅ 「活着但跑太久」最终正常完成 |

---

## 6. VA-POST 发现（分级判定）

| # | 发现 | 判定路径（标准 §1.2） | 级别 |
|---|---|---|---|
| OBS-2（延续） | **QA-D2 评审报告仍未合 main**：wt/t_7d8d9436 非 main 祖先；d2-review.md（+255 行）+ qa_dpl061_d2_probes.sh（+249 行）未入 main | 用户可感知？否（D2 是评审产物，结论已由 VA-QA/QA-POST 复核一致）；功能阻断？否；workaround？✅（OC 补 merge 即闭环）→ 观察项（落地缺口） | 观察（非缺陷） |
| **OBS-3（新增）** | **QA-POST 报告亦未合 main**：wt/t_6367eb7a @ 747b8cc 非 main 祖先；qa-post-report.md（228 行）+ WIP 笔记 + qa_dpl061_d2_probes.sh 未入 main | 同上：用户可感知？否；功能阻断？否；workaround？✅（OC 补 merge）→ 观察项 | 观察（非缺陷） |
| SUG-1（延续） | infomanager cron 目录残留 2 个过期 .jobs_*.tmp | 用户可感知？否（cron 读 jobs.json，tmp 不参与调度）；不阻断、不劣化 → **SUGGESTION** | SUGGESTION（不阻塞） |
| OBS-1 | 源 K 首 tick 线上输出 | 已闭环（§5） | ✅ 关闭 |

### 6.1 判定公式对照

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|---|---|---|---|---|---|---|
| （无）产品功能缺陷 | — | — | — | — | — | **0 BLOCKER/MAJOR/MINOR** |
| OBS-2（D2 未合 main） | ❌ | ❌ | ✅（OC 补 merge） | 否 | 否 | **观察项** |
| OBS-3（QA-POST 未合 main） | ❌ | ❌ | ✅（OC 补 merge） | 否 | 否 | **观察项** |
| SUG-1（.jobs_*.tmp 残留） | ❌ | ❌ | ✅（人工 rm） | 否 | 否 | **SUGGESTION** |

### 6.2 SLA 对照（标准 §8）

- 本卡 0 BLOCKER / 0 MAJOR / 0 MINOR → **无 SLA 触发**。
- SUG-1 / OBS-2 / OBS-3 不设 SLA；由 OC 评估处置时机（SUG-1 待 Frank 决策，OBS-2/OBS-3 待 OC 补 merge）。

---

## 7. 发布门禁对照（标准 §10）

| 门禁条件 | 数值 | 满足 |
|---|---|---|
| BLOCKER = 0 | 0 | ✅ |
| MAJOR ≤ 3 | 0 | ✅ |
| 安全漏洞 = 0 | 0 | ✅ |
| 无未裁定的申诉 | 0 | ✅ |

**发布门禁满足。DPL-061 合并后状态经 VA 独立复核全部成立，可收尾。**

---

## 8. 处置建议（VA 只验证，不代 OC 落地）

1. **OBS-3（QA-POST 报告落地缺口）**：建议 OC 执行 `git merge wt/t_6367eb7a → main`（747b8cc），使 qa-post-report.md + WIP 笔记 + qa_dpl061_d2_probes.sh 进入 main。本卡 VA-POST 报告同理建议落地（OC 判断合并时机）。
2. **OBS-2（D2 评审落地缺口，延续）**：建议 OC 执行 `git merge wt/t_7d8d9436 → main`（392c063），使 d2-review.md + qa_dpl061_d2_probes.sh 进入 main。
3. **SUG-1（过期 .jobs_*.tmp）**：保持待 Frank 决策（OC 已记录）；非阻塞。
4. **部署验证**：live oc_wake_check.sh 与 repo **完全一致**（md5 23936e2a，diff IDENTICAL），无部署动作（部署永远留给 OC；本链无漂移）。
5. **OBS-1 关闭**：源 K 线上 2 次真实 tick 已确认 + seen 幂等落盘 + OC 处置正确 + 卡最终 done，无需后续观测。

---

## 附：执行记录

- 被测提交：devPPL main @ f8109ba（worktree wt/t_e3f36f10 HEAD 相同）；c96c9ae + S1 5b591f0 + S2 3b2aca9 + S3 0cf2138 均祖先；DPL-061 开发文件零触碰
- 基线五套（独立复跑）：watchdog_unify 28/0 + deploy 29/0 + va 75/0 + wip 62/0 + cmd 398/0 = **592/0**
- pytest：`HOME=/root python3 -m pytest tests/ -q --tb=no -p no:cacheprovider` → **281/8/1**（20.83s，失败集 9 项与存量逐条一致，零新增）
- 语法：bash -n 7/7 OK
- 静态：S1-S12 12/12（独立读码 + 实测）
- 探针：P1-P4 8/8（scripts/qa_dpl061_probes.sh）+ P5 真实库只读冒烟 PASS（exit 0）+ D2 A-J 30/30（`git show wt/t_7d8d9436:scripts/qa_dpl061_d2_probes.sh` 拷贝重跑后删除）
- 部署验证：md5sum live vs repo = **23936e2a8cd66aee2fb27f5603bcca8f** 两侧一致 + diff IDENTICAL
- live 核对：cron output f2aa32251adc 14:17 + 16:04 两 tick 源 K 输出确认；/tmp/oc_wake_seen 4 个 stuck-running-long 一次性键（t_cc4bde55/t_8a82ce3c/t_806c69a7/t_169c0dd6）；ghost-card=0 / main-dirty=0；t_169c0dd6 done；board done=824/running=1
- OBS-2 延续：wt/t_7d8d9436 非 main 祖先（diff +504 行）
- OBS-3 新增：wt/t_6367eb7a @ 747b8cc 非 main 祖先（qa-post-report.md 228 行 + WIP + 探针脚本未合入）
- SUG-1 延续：.jobs_icilf7d6.tmp/.jobs_avrctbl9.tmp 仍在（OC 待 Frank 决策）
- 工作树隔离：全部测试在 wt/t_e3f36f10 worktree；live 核对全部只读（devppl_query.sh / grep / ls / mode=ro）
- 本卡交付物：本报告 docs/qa/dpl061-watchdog-unify-va-post-report.md + JSON 报告 .va_reports/
