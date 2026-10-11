# DPL-061 FIX watchdog 统一 — QA 执行测试报告（test_report.md）

> 版本：v1.0 | 日期：2026-08-16 | 作者：game-qa（独立执行，非研发自测）
>
> 任务卡：t_e682d627 [DEV-QA-EXEC] FIX watchdog 统一 — oc_wake_check 吸收 stuck-15min/幽灵卡/main-dirty + 归档死脚本（DPL-061）
> 上游：t_480d0aae（QA-D1 测试方案，docs/qa/dpl061-watchdog-unify-test-plan.md v1.0 @ wt/t_480d0aae，commit 8ba9286）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0（判定公式 §1.2 / SLA §8 / 发布门禁 §10）+ `docs/standards/devppl-test-spec.md` v1.0

---

## 0. 执行摘要

| 项 | 结果 |
|---|---|
| 被测对象确认 | **devPPL main @ 44bbcfd**（`git merge-base --is-ancestor c96c9ae HEAD` ✅ — 方案锁定的被测 commit c96c9ae 为祖先；DPL-061 文件 c96c9ae..HEAD 零触碰 `git log --oneline c96c9ae..HEAD -- scripts/oc_wake_check.sh scripts/test_watchdog_unify.sh scripts/archive/` 为空 ✅；S1 5b591f0 + S2 3b2aca9 + S3 0cf2138 全在 main） |
| 前置语法 | **bash -n 7/7 OK**（oc_wake_check / test_watchdog_unify / qa_dpl061_probes / test_deploy_drift / test_va_backfill / test_wip_progress_check / test_cmd_channel） |
| 部署漂移复核 | **live md5 == repo md5 == 23936e2a8cd66aee2fb27f5603bcca8f** ✅（F1 已闭环，DPL-048 规则） |
| 基线五套（独立复跑） | test_watchdog_unify.sh **28 PASS / 0 FAIL** + test_deploy_drift.sh **29/0** + test_va_backfill.sh **75/0** + test_wip_progress_check.sh **62/0** + test_cmd_channel.sh **398/0**（合计 **592 断言全绿**） |
| pytest 全量 | **281 passed / 8 failed / 1 error（588.73s）— 失败集 9 项与存量基线逐条一致，零新增失败**（§2.6） |
| 静态核对 S1-S12 | **12/12 PASS**（§3） |
| 独立探针 P1-P5 | **P1-P4 复跑 8/8 PASS + P5 真实库只读冒烟 PASS**（§4，共 9/9） |
| 验收 R1-R5 | **R1 4/4 + R2 3/3 + R3 3/3 + R4 3/3 + R5 2/2 全部成立**（§5，含部署项） |
| **QA 发现** | **0 BLOCKER / 0 MAJOR / 0 MINOR / 1 SUGGESTION**（SUG-1：infomanager cron 目录残留 2 个过期 .jobs_*.tmp 文件，非阻塞清理建议）+ OBS-1 延续（源 K 首个线上 tick 输出 → qa-post/OC 补观测） |

**结论：DPL-061 四层机制（源 I 幽灵卡 / 源 J main-dirty / 源 K stuck-long / R4 归档+cron 迁移）经 QA 独立执行全部成立，发布门禁满足（BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定申诉）。**

---

## 1. 前置确认（执行前）

| # | 检查项 | 命令/依据 | 结果 |
|---|---|---|---|
| 1 | main 被测 commit | `git log --oneline -3`（HEAD=44bbcfd）+ `git merge-base --is-ancestor c96c9ae HEAD` | ✅ c96c9ae 为 44bbcfd 祖先；方案锁定的被测对象未失位 |
| 2 | DPL-061 文件零触碰 | `git log --oneline c96c9ae..HEAD -- scripts/oc_wake_check.sh scripts/test_watchdog_unify.sh scripts/archive/ scripts/qa_dpl061_probes.sh` | ✅ 空输出（DPL-060 VA-POST 落地未波及 DPL-061 文件） |
| 3 | bash -n 语法 | oc_wake_check.sh / test_watchdog_unify.sh / qa_dpl061_probes.sh / test_deploy_drift.sh / test_va_backfill.sh / test_wip_progress_check.sh / test_cmd_channel.sh | ✅ 7/7 OK |
| 4 | 部署漂移复核（DPL-048） | `md5sum scripts/oc_wake_check.sh /root/.hermes/profiles/orchestrator/scripts/oc_wake_check.sh` | ✅ 两侧一致 **23936e2a8cd66aee2fb27f5603bcca8f**（与方案预期一致） |
| 5 | D1 交付物可用性 | 方案+探针脚本仅在 wt/t_480d0aae（未合 main）→ 本卡 checkout 字节一致副本（`git diff --no-index` 双侧 identical） | ✅ 探针可复跑 |

---

## 2. 基线五套 + pytest（独立复跑，非转述）

| # | 测试集 | 命令 | 结果 |
|---|---|---|---|
| G1 | test_watchdog_unify.sh（T1-T9，28 断言） | `bash scripts/test_watchdog_unify.sh` | **PASS=28 FAIL=0**（EXIT=0） |
| G2 | test_deploy_drift.sh（29 断言） | `bash scripts/test_deploy_drift.sh` | **PASS=29 FAIL=0**（EXIT=0） |
| G3 | test_va_backfill.sh（75 断言） | `bash scripts/test_va_backfill.sh` | **PASS=75 FAIL=0**（EXIT=0） |
| G4 | test_wip_progress_check.sh（62 断言） | `bash scripts/test_wip_progress_check.sh` | **PASS=62 FAIL=0**（EXIT=0） |
| G5 | test_cmd_channel.sh（398 断言） | `bash scripts/test_cmd_channel.sh` | **PASS=398 FAIL=0 / ALL TESTS PASSED**（EXIT=0） |
| G6 | pytest tests/ 全量 | `python3 -m pytest tests/ -q --tb=no`（后台，588.73s） | 见 §2.6 |

### 2.6 pytest 全量结果（对照存量基线 281/8/1）

- 命令：`cd /workspace/devPPL/.worktrees/t_e682d627 && python3 -m pytest tests/ -q --tb=no -p no:cacheprovider`（后台，**588.73s**）
- 结果：**281 passed / 8 failed / 1 error** — 与存量基线 **完全一致**（DPL-060 QA-EXEC 实测 281/8/1，613.87s；D1 实测 281/8/1，711.46s）
- 失败集逐条对照存量清单（DPL-060 test_report §2.4 同一 9 项）：
  - `test_memory_middleware_qa.py::test_tc19_blast_radius_engine` — 存量 ✅
  - `test_memory_middleware_qa.py::test_tc20_gai_links_adapter` — 存量 ✅
  - `test_memory_middleware_qa.py::test_tc23_drift_engine` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound0_Static::test_TC14_double_rollback_idempotent` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_rollback_retry_count_preserved` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_upsert_retry_count_bug_demo` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_rollback_verdict_preserved` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound4_Boundary::test_BE01_empty_branches_default_advance` — 存量 ✅
  - `test_P2-02_full.py::test`（ERROR，模块顶层 `def test(...)` 误收集 fixture error）— 存量 ✅
- **结论：零新增失败（R5-b 成立）**

---

## 3. 静态核对 S1-S12（QA 独立读码/实测，非转述）

| # | 核对项 | 证据（文件:行 / 实测命令） | 结果 |
|---|---|---|---|
| S1 | 头注释源清单 A-H → A-K（三源均标注 [DPL-061]） | oc_wake_check.sh L31/L36/L42 + 代码块 L443/467/492 | ✅ |
| S2 | 源 I：查询 ikey LIKE discover-est-% OR discover-qa-est-% AND status != 'archived'；src 为空跳过；源卡 EXISTS 跳过；一次性键 ghost-card:<tid> | oc_wake_check.sh L448-463 | ✅ |
| S3 | 源 J：git status --porcelain -- pipeline/ scripts/；**rstrip 修复**（L478 注释说明 strip 截断 tracked 首行路径）；D10 完整列表进 sha1 前8；展示截前 5；fail-open（D15） | oc_wake_check.sh L475-490 | ✅ |
| S4 | 源 K：status='running' AND started_at NOT NULL AND age > thr；D16 无 started_at 跳过；D3 B 重叠排除；D13 按时长降序 | oc_wake_check.sh L499-529 | ✅ |
| S5 | seen 写回：一次性键 ghost-card:/stuck-running-long: **不进**跳过名单（走 out 行自动解析）；E/G/H/J 状态型键走 *_new_keys | oc_wake_check.sh L543-560（排除列表不含 ghost-card/stuck-running-long） | ✅ |
| S6 | 状态型键 main-dirty **进**跳过名单 + main_dirty_new_keys 声明/追加/底部写回 | oc_wake_check.sh L473/L487/L551/L560 | ✅ |
| S7 | D3 互补：K 排除 B 已覆盖（hb_stale AND claim_dead → continue） | oc_wake_check.sh L514-515 | ✅ |
| S8 | D12 源 K 不标「疑似卡死」，只展示心跳年龄（<1 分钟前 / N 分钟前 / 无心跳） | oc_wake_check.sh L519-523 | ✅ |
| S9 | 归档：scripts/archive/ 4 文件在 main + 旧路径 0 残留 | `git ls-tree main --name-only scripts/archive/`（4 文件）+ `ls scripts/watch_board.sh ...`（No such file ×4）；字节 7397/12883/5925/2568 与备份一致 | ✅ |
| S10 | cron：infomanager jobs.json 无 6b695ac1e290（0 匹配）；orchestrator f2aa32251adc 保留 | `grep -c 6b695ac1e290 infomanager/cron/jobs.json` → 0；`grep -o f2aa32251adc orchestrator/cron/jobs.json` → 1；live infomanager/scripts 无 oc_stuck/watch_board/watch_dpl 残留 | ✅ |
| S11 | 备份：SandboxHermesBackup/devppl-scripts-backup-20260816/ 8 脚本 + README + wrapper.bak + tag | `ls`（autopilot/deploy_drift_check/oc_stuck_watchdog/oc_wake_check/stuck_check/watch_board/watch_dpl_chains + wrapper.bak + README-BACKUP.md）+ `git tag`（backup-pre-watchdog-unify-20260816） | ✅ |
| S12 | 部署漂移 F1 闭环：live md5 == repo（23936e2a） | `md5sum` 两侧一致 | ✅ |

---

## 4. 独立探针（P1-P5，9/9 PASS）

| # | 探针 | 方法 | 预期 | 实测 |
|---|---|---|---|---|
| P1 | 源 I 无源卡段边界（ikey 恰为前缀本身）→ 不误报 | temp 库 seed_card ikey=discover-est-，run_wake fresh seen | 无 [ghost-card] 输出 | ✅ PASS |
| P2 | 源 J rstrip 修复回归（tracked 修改首字符不丢） | 复跑 + tracked 修改（git add 后未 commit） | [main-dirty] 行含完整路径 scripts/dirty.sh，无 "cripts" 截断 | ✅ PASS ×3 断言 |
| P3 | 源 K 无心跳分支（claim 仍有效）→ 输出含「无心跳」 | seed_card started_at=-960 claim_expires=3600 不传 last_heartbeat_at | [stuck-running-long] 行含「无心跳」 | ✅ PASS |
| P3b | 源 K D3 B 重叠边界（hb=NULL AND claim=NULL → B 优先） | seed_card 两字段均缺 | 无 [stuck-running-long] 输出 | ✅ PASS |
| P4 | 源 K 降序（D13） | seed 2 卡（30min / 16min） | 30min 在前、16min 在后 | ✅ PASS |
| P5 | **真实库只读冒烟（qa-exec 新增执行）** | `SEEN_FILE=/tmp/dpl061-p5-seen-$$ bash scripts/oc_wake_check.sh /workspace/devPPL`（HERMES_KANBAN_DB 不覆盖=真实库；DB 连接 `mode=ro` L93 代码级保障） | exit 0 / 无异常 / 不写卡 / 输出含或不含三标记均可 | ✅ **PASS**：exit 0；输出 live 状态（wip-check / code-not-in-main / autopilot-cron，无 ghost-card/main-dirty/stuck-running-long 命中=live 现状）；seen 仅写 temp 路径；真实库未触碰 |

> P5 附加观察：main 工作树有 .pipeline/ 未提交文件（他链运行产物），但源 J 路径白名单为 `pipeline/ scripts/`（不含 .pipeline/）→ 未误报 [main-dirty]，符合 D15/D2 设计。

---

## 5. 验收 R1-R5 映射（PRD §5 对照）

| # | 验收要点 | 证据锚点 | 结果 |
|---|---|---|---|
| R1-a | ikey=discover-est-* 且源卡不存在 → 输出 `[ghost-card] <tid> 源卡 <src> 不存在` | T1a/T1b（28/0 套件）+ 静态 S2 | ✅ |
| R1-b | 源卡存在 → 不输出；status=archived → 不输出（负例） | T2a/T2c | ✅ |
| R1-c | qa 前缀 discover-qa-est-* → 命中 | T2b | ✅ |
| R1-d | 重跑不重复报告（一次性键 ghost-card:<tid> 落盘） | T3a/T3b + 静态 S5 | ✅ |
| R2-a | 脏 repo（pipeline/ scripts/ 未提交）→ 输出 `[main-dirty]` + 前 5 文件 | T4a/T4b + 静态 S3 | ✅ |
| R2-b | seen 含 main-dirty:<完整列表 sha1 前8>（状态型键 D10） | T4c + 静态 S6 | ✅ |
| R2-c | 干净 repo → 不输出；集合变化 → 重报；非 git → fail-open exit 0 | T5a/T5b/T5c（T5b 锁 rstrip 修复） | ✅ |
| R3-a | running + started_at 16min 前 + 心跳新鲜 → `[stuck-running-long] 已跑 16 分钟（心跳 N 分钟前）` | T6a/T6b/T6c + 静态 S4 | ✅ |
| R3-b | 14min 未超阈值 → 不输出；B 重叠（hb_stale AND claim_dead）→ K 不输出 | T7a/T7b + 静态 S7 | ✅ |
| R3-c | 重跑不重复报告（一次性键 stuck-running-long:<tid> 落盘） | T8a/T8b | ✅ |
| R4-a | scripts/archive/ 4 文件存在且非空；旧路径消失 | T9 + 静态 S9 | ✅ |
| R4-b | infomanager cron 6b695ac1e290 已删；orchestrator f2aa32251adc 保留；wrapper 清理 | 静态 S10（jobs.json 0 匹配 + orchestrator 保留 + live infomanager/scripts 无 oc_stuck 残留） | ✅ |
| R4-c | 迁移前备份存在（SandboxHermesBackup + tag） | 静态 S11 | ✅ |
| R5-a | 三套既有 oc_wake 测试全绿（源 A-D/E + G + H 零改动） | wip 62/0 + deploy 29/0 + va 75/0 | ✅ |
| R5-b | cmd 398 + pytest 无新增失败 | cmd 398/0 + pytest 281/8/1 零新增 | ✅ |
| 部署 | live oc_wake_check.sh md5 == repo（DPL-048） | md5 23936e2a 两侧一致 | ✅ |

**R1-R5 全部成立，0 项不通过。**

---

## 6. 发现分级对照（qa-finding-classification.md v1.0）

### 6.1 判定公式对照

| 发现 | 判定路径 | 级别 |
|---|---|---|
| SUG-1：infomanager cron 目录残留 2 个过期 `.jobs_*.tmp`（.jobs_icilf7d6.tmp @ 08-13、.jobs_avrctbl9.tmp @ 08-15，内含已删 cron id 6b695ac1e290） | 用户可感知？否（cron 读取的是 jobs.json，tmp 不参与调度；仅 grep 审计时出现假阳性）→ 不阻断、不劣化 → **SUGGESTION**（对照标准 §5 SUGGESTION 行） | SUGGESTION（不阻塞发版） |
| OBS-1（D1 延续）：源 K 首个线上 tick 输出观察 | 依赖 cron 节奏（15m），qa-exec 已记录现状（cron 删 + wrapper 清 + 备份在 + P5 实测无 stuck 命中）；最终线上确认归 qa-post/OC | 观察（非缺陷） |

### 6.2 SLA 对照

- 本次执行 0 BLOCKER / 0 MAJOR / 0 MINOR → **无 SLA 触发项**（§8 响应时限不适用）。
- 唯一 SUGGESTION（SUG-1）不进入 SLA 通道，建议随 OC 例行清理。

### 6.3 分级示例对照（方案 §6 预设 → 实测）

| 预设缺陷场景 | 实测 |
|---|---|
| 源 I 误报/漏报（幽灵卡污染统计）→ BLOCKER | 未发现（T1-T3 正负例 + P1 边界全过） |
| 源 J rstrip 未修（哈希错误 → 集合变化不重报 → 抢 main 漏检）→ BLOCKER | 未复发（T5b + P2 断言路径完整） |
| 源 K 输出格式与 PRD 出入（心跳展示）→ MINOR | 未发现（T6b/c + P3 输出符合 D12） |
| 归档文件权限/只读位异常 → SUGGESTION | 未发现（archive 4 文件存在非空 + 字节与备份一致） |

---

## 7. 结论与发布门禁

- **发布门禁（标准 §10）**：BLOCKER=0 ✅ AND MAJOR≤3 ✅ AND 安全漏洞=0 ✅ AND 无未裁定的申诉 ✅ → **门禁满足，DPL-061 可进入合流/发布流程**。
- **交付物**：
  1. 本报告 docs/qa/dpl061-watchdog-unify-qa-exec-report.md（v1.0）
  2. WIP 发现笔记 .pipeline/wip/t_e682d627.md
  3. 复跑探针记录 scripts/qa_dpl061_probes.sh（D1 交付物，本卡复跑 8/8 PASS + P5 独立执行）
- **下游建议**：
  1. SUG-1（过期 .jobs_*.tmp）→ OC 例行清理（非阻塞，不建 FIX 卡）。
  2. OBS-1（源 K 首 tick 线上输出）→ qa-post/OC 在下一自然 tick 后补观测记录。
  3. 部署态与 repo 一致（23936e2a），无需部署动作；后续如改动 oc_wake_check.sh 需按 DPL-048 复核 md5。
